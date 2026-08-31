from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.document_parsing import BoundedDocumentParser, DocumentParsingError, PasswordProtectedDocumentError
from revenueos.main import create_app
from revenueos.models import BetaSystemEvent

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL
from .test_business_api import create_company, create_contact, create_opportunity
from .test_meeting_api import cast_auth_dependency, secondary_user


def _document_request(
    opportunity_id: str,
    company_id: str,
    content: bytes,
    *,
    key: str = "document-evidence-1",
    document_type: str = "rfp",
    ownership: str = "customer_provided",
) -> dict[str, object]:
    return {
        "companyId": company_id,
        "opportunityId": opportunity_id,
        "documentType": document_type,
        "sourceOwnership": ownership,
        "filename": "customer-requirements.txt",
        "mimeType": "text/plain",
        "contentBase64": base64.b64encode(content).decode("ascii"),
        "checksumSha256": hashlib.sha256(content).hexdigest(),
        "documentAt": "2026-08-15T09:30:00+10:00",
        "authorityConfirmed": True,
        "externalProcessingAcknowledged": True,
        "idempotencyKey": key,
    }


def _review_all(client: TestClient, kind: str, source: dict[str, object]) -> dict[str, object]:
    decisions = [
        {"candidateId": candidate["id"], "decision": "accept"}
        for candidate in source["candidates"]  # type: ignore[union-attr]
    ]
    response = client.post(
        f"/api/v1/evidence/{kind}/{source['id']}/review",
        json={"decisions": decisions, "idempotencyKey": f"review-{source['id']}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _settings(storage_directory: Path, **changes: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "log_level": "WARNING",
        "cors_origins": "http://localhost:3000",
        "visual_storage_directory": str(storage_directory),
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_customer_document_is_private_review_gated_and_flows_downstream(client: TestClient) -> None:
    company = create_company(client, name="Document evidence account")
    opportunity = create_opportunity(client, str(company["id"]), name="Customer RFP")
    content = (
        b"REQUIREMENTS:\n\nThe platform must support SSO integration.\n\n"
        b"Our approved budget is AUD 150,000 and go-live deadline is December."
    )
    request = _document_request(str(opportunity["id"]), str(company["id"]), content)

    created = client.post("/api/v1/evidence/documents", json=request)
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["processingStatus"] == "received"
    assert document["interactionId"] is None
    assert document["downloadUrl"].startswith("/api/v1/evidence/documents/")
    assert "contentBase64" not in document

    downloaded = client.get(document["downloadUrl"])
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert downloaded.headers["content-security-policy"] == "sandbox"

    repeated = client.post("/api/v1/evidence/documents", json=request)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == document["id"]
    changed_content = b"The platform must support a different identity provider."
    conflicting_retry = client.post(
        "/api/v1/evidence/documents",
        json={
            **request,
            "contentBase64": base64.b64encode(changed_content).decode("ascii"),
            "checksumSha256": hashlib.sha256(changed_content).hexdigest(),
        },
    )
    assert conflicting_retry.status_code == 409
    assert conflicting_retry.json()["code"] == "idempotency_conflict"
    duplicate = client.post(
        "/api/v1/evidence/documents",
        json={**request, "idempotencyKey": "same-document-new-key"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "duplicate_document"

    processed_response = client.post(
        f"/api/v1/evidence/documents/{document['id']}/process",
        json={"idempotencyKey": "process-customer-rfp"},
    )
    assert processed_response.status_code == 200, processed_response.text
    processed = processed_response.json()
    assert processed["processingStatus"] == "review"
    assert processed["revenueBrainSnapshotId"] is None
    assert processed["candidates"]
    assert all(candidate["validationState"] == "unreviewed" for candidate in processed["candidates"])
    assert all(candidate["originClass"] == "customer_direct" for candidate in processed["candidates"])
    assert all(candidate["interpretationOrigin"] == "ai_inferred" for candidate in processed["candidates"])
    assert client.get(f"/api/v1/evidence/opportunities/{opportunity['id']}").json() == []

    decisions = [
        {
            "candidateId": candidate["id"],
            "decision": "reject" if index == len(processed["candidates"]) - 1 else "accept",
            **({"statement": "The customer requires standards-based SSO integration."} if index == 0 else {}),
        }
        for index, candidate in enumerate(processed["candidates"])
    ]
    reviewed_response = client.post(
        f"/api/v1/evidence/documents/{document['id']}/review",
        json={"decisions": decisions, "idempotencyKey": "review-customer-rfp"},
    )
    assert reviewed_response.status_code == 200, reviewed_response.text
    reviewed = reviewed_response.json()
    assert reviewed["acceptedCount"] == len(processed["candidates"]) - 1
    assert reviewed["rejectedCount"] == 1
    assert reviewed["candidates"][0]["edited"] is True
    assert reviewed["candidates"][0]["statement"] == "The customer requires standards-based SSO integration."
    assert reviewed["opportunityUpdated"] is True
    assert reviewed["revenueBrainUpdated"] is True

    workspace_items = client.get(f"/api/v1/evidence/opportunities/{opportunity['id']}").json()
    assert workspace_items
    assert {item["sourceType"] for item in workspace_items} == {"rfp"}
    assert {item["originClass"] for item in workspace_items} == {"customer_direct"}
    brain = client.get(f"/api/v1/evidence/accounts/{company['id']}/brain").json()
    assert len(brain) == 1
    assert brain[0]["sourceId"] == document["id"]

    deleted = client.delete(f"/api/v1/evidence/documents/{document['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {
        "sourceKind": "document",
        "sourceId": document["id"],
        "deleted": True,
        "retryRequired": False,
    }
    assert client.get(document["downloadUrl"]).status_code in {403, 404, 410}
    assert client.get(f"/api/v1/evidence/opportunities/{opportunity['id']}").json() == []
    deleted_retry = client.post("/api/v1/evidence/documents", json=request)
    assert deleted_retry.status_code == 409
    assert deleted_retry.json()["code"] == "document_already_deleted"
    reimport = client.post(
        "/api/v1/evidence/documents",
        json={**request, "idempotencyKey": "deleted-document-new-key"},
    )
    assert reimport.status_code == 409
    assert reimport.json()["code"] == "duplicate_document"


def test_seller_document_never_becomes_customer_confirmed(client: TestClient) -> None:
    company = create_company(client, name="Seller proposal account")
    opportunity = create_opportunity(client, str(company["id"]), name="Seller proposal")
    content = b"We believe the customer is interested and will proceed by December. Pricing is AUD 90,000."
    created_response = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(
            str(opportunity["id"]),
            str(company["id"]),
            content,
            key="seller-proposal",
            document_type="proposal",
            ownership="salesperson_provided",
        ),
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    processed_response = client.post(
        f"/api/v1/evidence/documents/{created['id']}/process",
        json={"idempotencyKey": "process-seller-proposal"},
    )
    assert processed_response.status_code == 200, processed_response.text
    processed = processed_response.json()
    assert "buying_signal" not in {item["category"] for item in processed["candidates"]}
    assert {item["originClass"] for item in processed["candidates"]} == {"seller_prepared"}
    assert {item["supportClass"] for item in processed["candidates"]} == {"context"}
    _review_all(client, "documents", processed)
    downstream = client.get(f"/api/v1/evidence/opportunities/{opportunity['id']}").json()
    assert downstream
    assert {item["originClass"] for item in downstream} == {"seller_prepared"}


def test_new_reviewed_evidence_can_explicitly_supersede_an_accepted_item(client: TestClient) -> None:
    company = create_company(client, name="Evidence supersession account")
    opportunity = create_opportunity(client, str(company["id"]), name="Budget change")

    first = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(
            str(opportunity["id"]),
            str(company["id"]),
            b"The customer budget is approved.",
            key="budget-approved",
            document_type="requirements",
        ),
    ).json()
    first_processed = client.post(
        f"/api/v1/evidence/documents/{first['id']}/process",
        json={"idempotencyKey": "process-budget-approved"},
    ).json()
    first_reviewed = _review_all(client, "documents", first_processed)
    prior_budget = next(item for item in first_reviewed["candidates"] if item["category"] == "budget")

    second = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(
            str(opportunity["id"]),
            str(company["id"]),
            b"The customer budget is not approved and remains blocked.",
            key="budget-not-approved",
            document_type="requirements",
        ),
    ).json()
    second_processed = client.post(
        f"/api/v1/evidence/documents/{second['id']}/process",
        json={"idempotencyKey": "process-budget-not-approved"},
    ).json()
    decisions = [
        {
            "candidateId": candidate["id"],
            "decision": "accept",
            **({"supersedesCandidateId": prior_budget["id"]} if candidate["category"] == "budget" else {}),
        }
        for candidate in second_processed["candidates"]
    ]
    response = client.post(
        f"/api/v1/evidence/documents/{second['id']}/review",
        json={"decisions": decisions, "idempotencyKey": "review-budget-not-approved"},
    )
    assert response.status_code == 200, response.text
    superseding = next(item for item in response.json()["candidates"] if item["category"] == "budget")
    assert superseding["conflictState"] == "supersedes"
    assert superseding["supersedesCandidateId"] == prior_budget["id"]
    workspace = client.get(f"/api/v1/evidence/opportunities/{opportunity['id']}").json()
    assert {item["conflictState"] for item in workspace} >= {"not_assessed", "supersedes"}
    assert client.delete(f"/api/v1/evidence/documents/{first['id']}").status_code == 200
    remaining = client.get(f"/api/v1/evidence/opportunities/{opportunity['id']}").json()
    assert remaining
    assert {item["sourceId"] for item in remaining} == {second["id"]}
    assert any(item["conflictState"] == "supersedes" for item in remaining)


def test_inbound_email_requires_review_and_outbound_claims_remain_seller_reported(client: TestClient) -> None:
    company = create_company(client, name="Email evidence account")
    opportunity = create_opportunity(client, str(company["id"]), name="Email evidence deal")
    contact = create_contact(client, str(company["id"]), first_name="Casey")
    inbound_payload = {
        "companyId": company["id"],
        "opportunityId": opportunity["id"],
        "sourceType": "customer_sent",
        "direction": "inbound",
        "senderContactId": contact["id"],
        "subject": "Next steps",
        "body": "We are interested and have approved the budget. Please proceed by December.\n\n--\nCasey",
        "messageAt": "2026-08-15T11:00:00+10:00",
        "authorityConfirmed": True,
        "externalProcessingAcknowledged": True,
        "idempotencyKey": "inbound-customer-email",
    }
    created_response = client.post("/api/v1/evidence/emails", json=inbound_payload)
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    assert created["senderIdentityState"] == "verified_contact"
    assert created["quoteHandling"] == "stripped"
    repeated = client.post("/api/v1/evidence/emails", json=inbound_payload)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == created["id"]
    conflicting_retry = client.post(
        "/api/v1/evidence/emails",
        json={**inbound_payload, "body": "This is a different message."},
    )
    assert conflicting_retry.status_code == 409
    assert conflicting_retry.json()["code"] == "idempotency_conflict"
    processed_response = client.post(
        f"/api/v1/evidence/emails/{created['id']}/process",
        json={"idempotencyKey": "process-inbound-email"},
    )
    assert processed_response.status_code == 200, processed_response.text
    processed = processed_response.json()
    assert "buying_signal" in {item["category"] for item in processed["candidates"]}
    assert {item["originClass"] for item in processed["candidates"]} == {"customer_direct"}
    _review_all(client, "emails", processed)

    outbound_payload = {
        **inbound_payload,
        "sourceType": "salesperson_sent",
        "direction": "outbound",
        "senderContactId": None,
        "body": "You are interested and will proceed. We can provide pricing by December.",
        "messageAt": "2026-08-15T12:00:00+10:00",
        "idempotencyKey": "outbound-seller-email",
    }
    outbound = client.post("/api/v1/evidence/emails", json=outbound_payload).json()
    processed_outbound_response = client.post(
        f"/api/v1/evidence/emails/{outbound['id']}/process",
        json={"idempotencyKey": "process-outbound-email"},
    )
    assert processed_outbound_response.status_code == 200, processed_outbound_response.text
    processed_outbound = processed_outbound_response.json()
    assert "buying_signal" not in {item["category"] for item in processed_outbound["candidates"]}
    assert {item["originClass"] for item in processed_outbound["candidates"]} == {"salesperson_reported"}
    assert {item["supportClass"] for item in processed_outbound["candidates"]} == {"context"}
    _review_all(client, "emails", processed_outbound)

    internal_payload = {
        **inbound_payload,
        "sourceType": "internal_forward",
        "direction": "internal",
        "senderContactId": None,
        "body": "The customer is interested and will proceed.\n\n> Quoted customer history",
        "messageAt": "2026-08-15T13:00:00+10:00",
        "idempotencyKey": "internal-forward-email",
    }
    internal = client.post("/api/v1/evidence/emails", json=internal_payload)
    assert internal.status_code == 201, internal.text
    assert internal.json()["quoteHandling"] == "stripped"
    processed_internal = client.post(
        f"/api/v1/evidence/emails/{internal.json()['id']}/process",
        json={"idempotencyKey": "process-internal-forward"},
    )
    assert processed_internal.status_code == 200, processed_internal.text
    assert "buying_signal" not in {item["category"] for item in processed_internal.json()["candidates"]}
    assert {item["originClass"] for item in processed_internal.json()["candidates"]} == {"salesperson_reported"}
    assert {item["supportClass"] for item in processed_internal.json()["candidates"]} == {"context"}

    other_company = create_company(client, name="Other sender account")
    other_contact = create_contact(client, str(other_company["id"]), first_name="Taylor")
    unsafe_sender_merge = client.post(
        "/api/v1/evidence/emails",
        json={
            **inbound_payload,
            "senderContactId": other_contact["id"],
            "body": "We will proceed with the commercial review.",
            "idempotencyKey": "cross-account-sender",
        },
    )
    assert unsafe_sender_merge.status_code == 422
    assert unsafe_sender_merge.json()["code"] == "contact_company_mismatch"

    deleted = client.delete(f"/api/v1/evidence/emails/{outbound['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/v1/evidence/emails/{outbound['id']}").status_code == 404
    deleted_retry = client.post("/api/v1/evidence/emails", json=outbound_payload)
    assert deleted_retry.status_code == 409
    assert deleted_retry.json()["code"] == "email_already_deleted"
    reimport = client.post(
        "/api/v1/evidence/emails",
        json={**outbound_payload, "idempotencyKey": "deleted-email-new-key"},
    )
    assert reimport.status_code == 409
    assert reimport.json()["code"] == "duplicate_email"


def test_document_and_email_validation_fail_closed(client: TestClient) -> None:
    company = create_company(client, name="Evidence validation account")
    opportunity = create_opportunity(client, str(company["id"]), name="Validation deal")
    malformed = b"%PDF-1.7 not really a PDF"
    response = client.post(
        "/api/v1/evidence/documents",
        json={
            **_document_request(str(opportunity["id"]), str(company["id"]), malformed),
            "filename": "bad.pdf",
            "mimeType": "application/pdf",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "malformed_document"

    mismatch = client.post(
        "/api/v1/evidence/documents",
        json={
            **_document_request(str(opportunity["id"]), str(company["id"]), b"Safe requirements text", key="mismatch"),
            "filename": "wrong.pdf",
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "document_type_mismatch"

    unimplemented_document_import = client.post(
        "/api/v1/evidence/documents",
        json={
            **_document_request(
                str(opportunity["id"]),
                str(company["id"]),
                b"Future provider document",
                key="unimplemented-document-provider",
            ),
            "sourceOwnership": "system_imported",
        },
    )
    assert unimplemented_document_import.status_code == 422

    unsafe_text = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(
            str(opportunity["id"]),
            str(company["id"]),
            b"Requirement\x0bhidden control",
            key="unsafe-control-document",
        ),
    )
    assert unsafe_text.status_code == 422
    assert unsafe_text.json()["code"] == "unsafe_document"

    malware_boundary = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(
            str(opportunity["id"]),
            str(company["id"]),
            b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
            key="malware-boundary-document",
        ),
    )
    assert malware_boundary.status_code == 422
    assert malware_boundary.json()["code"] == "unsafe_document"

    unsupported_mime = client.post(
        "/api/v1/evidence/documents",
        json={
            **_document_request(
                str(opportunity["id"]),
                str(company["id"]),
                b"Unsupported binary document",
                key="unsupported-mime-document",
            ),
            "filename": "unsupported.bin",
            "mimeType": "application/octet-stream",
        },
    )
    assert unsupported_mime.status_code == 422

    invalid_direction = client.post(
        "/api/v1/evidence/emails",
        json={
            "companyId": company["id"],
            "sourceType": "customer_sent",
            "direction": "outbound",
            "body": "Customer message",
            "messageAt": datetime.now(UTC).isoformat(),
            "authorityConfirmed": True,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "invalid-direction",
        },
    )
    assert invalid_direction.status_code == 422

    unimplemented_email_import = client.post(
        "/api/v1/evidence/emails",
        json={
            "companyId": company["id"],
            "sourceType": "external_provider_import",
            "direction": "inbound",
            "body": "Future provider email",
            "messageAt": datetime.now(UTC).isoformat(),
            "authorityConfirmed": True,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "unimplemented-email-provider",
        },
    )
    assert unimplemented_email_import.status_code == 422

    unsafe_email = client.post(
        "/api/v1/evidence/emails",
        json={
            "companyId": company["id"],
            "sourceType": "manually_pasted",
            "direction": "unknown",
            "body": "Unsafe\u000bemail",
            "messageAt": datetime.now(UTC).isoformat(),
            "authorityConfirmed": True,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "unsafe-control-email",
        },
    )
    assert unsafe_email.status_code == 422
    assert unsafe_email.json()["code"] == "unsafe_email_content"


def test_valid_pdf_preserves_page_and_paragraph_locations() -> None:
    output = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}  # noqa: SLF001
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (The customer requires SSO.) Tj ET")
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(stream)  # noqa: SLF001
    writer.write(output)

    parsed = BoundedDocumentParser(max_pages=10, max_characters=10_000).parse(output.getvalue(), "application/pdf")

    assert parsed.page_count == 1
    assert parsed.fragments[0].page_number == 1
    assert parsed.fragments[0].paragraph_index == 0
    assert parsed.fragments[0].text == "The customer requires SSO."


def test_evidence_kill_switches_and_usage_limits_are_server_authoritative(tmp_path: Path) -> None:
    disabled_app = create_app(
        _settings(
            tmp_path / "disabled-storage",
            feature_document_evidence_enabled=False,
            feature_email_evidence_enabled=False,
        )
    )
    with TestClient(disabled_app) as disabled_client:
        capabilities = disabled_client.get("/api/v1/evidence/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["documentEvidence"] is False
        assert capabilities.json()["emailEvidence"] is False
        rejected = disabled_client.post(
            "/api/v1/evidence/documents",
            json=_document_request(str(uuid.uuid4()), str(uuid.uuid4()), b"blocked"),
        )
        assert rejected.status_code == 404

    limited_app = create_app(
        _settings(
            tmp_path / "limited-storage",
            private_beta_max_document_bytes=10_000,
            private_beta_max_document_uploads_per_day=1,
            private_beta_max_email_analyses_per_day=1,
        )
    )
    with TestClient(limited_app) as limited_client:
        company = create_company(limited_client, name="Evidence limit account")
        opportunity = create_opportunity(limited_client, str(company["id"]), name="Evidence limit deal")
        oversized_content = b"x" * 10_001
        oversized = limited_client.post(
            "/api/v1/evidence/documents",
            json=_document_request(
                str(opportunity["id"]),
                str(company["id"]),
                oversized_content,
                key="oversized-document",
            ),
        )
        assert oversized.status_code == 413
        assert oversized.json()["code"] == "document_too_large"

        first_document = limited_client.post(
            "/api/v1/evidence/documents",
            json=_document_request(
                str(opportunity["id"]),
                str(company["id"]),
                b"First bounded document",
                key="bounded-document-one",
            ),
        )
        assert first_document.status_code == 201
        limited_document = limited_client.post(
            "/api/v1/evidence/documents",
            json=_document_request(
                str(opportunity["id"]),
                str(company["id"]),
                b"Second bounded document",
                key="bounded-document-two",
            ),
        )
        assert limited_document.status_code == 429
        assert limited_document.json()["code"] == "daily_document_upload_limit_exceeded"

        email_payload = {
            "companyId": company["id"],
            "opportunityId": opportunity["id"],
            "sourceType": "manually_pasted",
            "direction": "unknown",
            "body": "Please proceed with security review.",
            "messageAt": "2026-08-15T11:00:00+10:00",
            "authorityConfirmed": True,
            "externalProcessingAcknowledged": True,
            "idempotencyKey": "bounded-email-one",
        }
        first_email = limited_client.post("/api/v1/evidence/emails", json=email_payload)
        assert first_email.status_code == 201
        first_process = limited_client.post(
            f"/api/v1/evidence/emails/{first_email.json()['id']}/process",
            json={"idempotencyKey": "bounded-email-process-one"},
        )
        assert first_process.status_code == 200
        second_email = limited_client.post(
            "/api/v1/evidence/emails",
            json={
                **email_payload,
                "body": "Please proceed with procurement review.",
                "idempotencyKey": "bounded-email-two",
            },
        )
        assert second_email.status_code == 201
        limited_email = limited_client.post(
            f"/api/v1/evidence/emails/{second_email.json()['id']}/process",
            json={"idempotencyKey": "bounded-email-process-two"},
        )
        assert limited_email.status_code == 429
        assert limited_email.json()["code"] == "daily_email_analysis_limit_exceeded"


def test_document_telemetry_contains_metadata_only(client: TestClient) -> None:
    company = create_company(client, name="Safe telemetry account")
    opportunity = create_opportunity(client, str(company["id"]), name="Safe telemetry deal")
    private_text = b"PRIVATE-CONTRACT-TERM-DO-NOT-LOG requires SSO."
    created = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(
            str(opportunity["id"]),
            str(company["id"]),
            private_text,
            key="safe-telemetry-document",
        ),
    )
    assert created.status_code == 201, created.text
    processed = client.post(
        f"/api/v1/evidence/documents/{created.json()['id']}/process",
        json={"idempotencyKey": "safe-telemetry-process"},
    )
    assert processed.status_code == 200, processed.text

    async def scenario() -> list[dict[str, object]]:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            events = list(
                (
                    await session.scalars(
                        select(BetaSystemEvent).where(
                            BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                            BetaSystemEvent.subject_id == uuid.UUID(created.json()["id"]),
                        )
                    )
                ).all()
            )
        await engine.dispose()
        return [event.metadata_json for event in events]

    metadata = asyncio.run(scenario())
    assert metadata
    allowed_metadata = {
        "document_type",
        "byte_size",
        "processing_attempt",
        "page_count",
        "fragment_count",
        "candidate_count",
    }
    assert all(set(item) <= allowed_metadata for item in metadata)
    assert "PRIVATE-CONTRACT-TERM-DO-NOT-LOG" not in repr(metadata)
    assert "customer-requirements.txt" not in repr(metadata)


def test_document_evidence_is_tenant_hidden(client: TestClient, app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    other_company = create_company(client, name="Other tenant evidence account")
    other_opportunity = create_opportunity(client, str(other_company["id"]), name="Other tenant evidence deal")
    app.dependency_overrides.pop(get_current_user, None)

    company = create_company(client, name="Tenant evidence account")
    opportunity = create_opportunity(client, str(company["id"]), name="Tenant evidence deal")
    content = b"The customer requires SSO integration."
    cross_tenant_attachment = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(str(other_opportunity["id"]), str(company["id"]), content, key="cross-tenant"),
    )
    assert cross_tenant_attachment.status_code == 404
    assert cross_tenant_attachment.json()["code"] == "opportunity_not_found"
    document = client.post(
        "/api/v1/evidence/documents",
        json=_document_request(str(opportunity["id"]), str(company["id"]), content, key="tenant-hidden"),
    ).json()

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(f"/api/v1/evidence/documents/{document['id']}").status_code == 404
        assert (
            client.post(
                f"/api/v1/evidence/documents/{document['id']}/process",
                json={"idempotencyKey": "cross-tenant-process"},
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_password_protected_pdf_is_rejected_before_storage() -> None:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    writer.write(output)
    parser = BoundedDocumentParser(max_pages=10, max_characters=10_000)
    try:
        parser.parse(output.getvalue(), "application/pdf")
    except PasswordProtectedDocumentError:
        return
    raise AssertionError("Password-protected PDFs must be rejected.")


@pytest.mark.parametrize(
    "stream_data",
    [
        b"q BI /W 1 /H 1 /CS /RGB /BPC 8 /F /A85 ID zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        b"q BI /W 999999999 /H 999999999 /CS /RGB /BPC 8 ID 0 EI Q",
    ],
)
def test_malformed_pdf_resources_fail_within_bounded_time(stream_data: bytes) -> None:
    output = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = DecodedStreamObject()
    stream.set_data(stream_data)
    page[NameObject("/Contents")] = writer._add_object(stream)  # noqa: SLF001
    writer.write(output)
    parser = BoundedDocumentParser(max_pages=10, max_characters=10_000)

    started = time.monotonic()
    with pytest.raises(DocumentParsingError):
        parser.parse(output.getvalue(), "application/pdf")
    assert time.monotonic() - started < 2
