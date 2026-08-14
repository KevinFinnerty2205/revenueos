from __future__ import annotations

import asyncio
import binascii
import hashlib
import json
import struct
import zlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.beta_maintenance import generate_export, reconcile_visual_storage, run_retention
from revenueos.config import Settings
from revenueos.main import create_app
from revenueos.models import BetaSystemEvent, Contact, Evidence, Interaction, VisualAsset
from revenueos.visual_images import UnsafeVisualError, validate_and_sanitise_visual
from revenueos.visual_storage import VisualGrantSigner, VisualStorageError, create_visual_storage

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL, TEST_VISUAL_STORAGE
from .test_business_api import create_company, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, secondary_user


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", binascii.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _png(*, width: int = 1, height: int = 1, include_location_text: bool = False) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(b"\x00" + (b"\x00\x80\xff" * width) for _ in range(height))
    ancillary = _chunk(b"tEXt", b"GPS=33.8688S,151.2093E") if include_location_text else b""
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + ancillary
        + _chunk(b"IDAT", zlib.compress(rows))
        + _chunk(b"IEND", b"")
    )


def _completed_interaction(
    client: TestClient,
    *,
    interaction_type: str = "workshop",
) -> tuple[str, str, str]:
    company_id = str(create_company(client, name=f"Visual {interaction_type} account")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name=f"Visual {interaction_type} opportunity")["id"])
    interaction_id = str(
        create_interaction(
            client,
            title=f"Visual {interaction_type}",
            interaction_type=interaction_type,
            company_id=company_id,
            opportunity_id=opportunity_id,
        )["id"]
    )
    completed = client.post(f"/api/v1/interactions/{interaction_id}/complete", json={})
    assert completed.status_code == 200, completed.text
    return interaction_id, opportunity_id, company_id


def _create_and_upload(
    client: TestClient,
    interaction_id: str,
    image: bytes,
    *,
    visual_type: str = "whiteboard",
    source_ownership: str = "customer_created",
    context_label: str | None = "Customer requested an implementation workshop",
    key: str = "visual-upload-1",
    declared_mime_type: str = "image/png",
    expected_completion_status: int = 200,
) -> dict[str, object]:
    checksum = hashlib.sha256(image).hexdigest()
    created = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json={
            "visualType": visual_type,
            "sourceOwnership": source_ownership,
            "contextLabel": context_label,
            "filename": "../../customer-board.png",
            "mimeType": declared_mime_type,
            "byteSize": len(image),
            "checksumSha256": checksum,
            "capturedAt": "2026-08-14T10:00:00+10:00",
            "consentConfirmed": True,
            "idempotencyKey": key,
        },
    )
    assert created.status_code == 201, created.text
    upload = created.json()
    assert ".." not in upload["filename"]
    content = client.put(
        upload["uploadUrl"],
        content=image,
        headers={"Content-Type": declared_mime_type},
    )
    assert content.status_code == 204, content.text
    completed = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{upload['id']}/complete",
        json={"checksumSha256": checksum, "idempotencyKey": f"complete-{key}"},
    )
    assert completed.status_code == expected_completion_status, completed.text
    return completed.json()


def _process(client: TestClient, interaction_id: str, visual_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/process",
        json={"idempotencyKey": f"process-{visual_id}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_visual_upload_is_private_idempotent_sanitised_and_review_gated(client: TestClient) -> None:
    interaction_id, opportunity_id, company_id = _completed_interaction(client)
    image = _png(include_location_text=True)
    uploaded = _create_and_upload(client, interaction_id, image)
    visual_id = str(uploaded["id"])
    assert uploaded["processingStatus"] == "uploaded"
    assert uploaded["width"] == 1
    assert uploaded["height"] == 1
    assert uploaded["byteSize"] < len(image)
    assert uploaded["checksumSha256"] != hashlib.sha256(image).hexdigest()
    assert uploaded["downloadUrl"].startswith("/api/v1/interactions/")  # type: ignore[union-attr]

    repeated_completion = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/complete",
        json={
            "checksumSha256": hashlib.sha256(image).hexdigest(),
            "idempotencyKey": "complete-visual-upload-1",
        },
    )
    assert repeated_completion.status_code == 200
    assert repeated_completion.json()["id"] == visual_id

    downloaded = client.get(str(uploaded["downloadUrl"]))
    assert downloaded.status_code == 200
    assert b"GPS=" not in downloaded.content
    assert downloaded.headers["cache-control"].startswith("private, no-store")
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    same_request = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json={
            "visualType": "whiteboard",
            "sourceOwnership": "customer_created",
            "contextLabel": "Customer requested an implementation workshop",
            "filename": "customer-board.png",
            "mimeType": "image/png",
            "byteSize": len(image),
            "checksumSha256": hashlib.sha256(image).hexdigest(),
            "capturedAt": "2026-08-14T10:00:00+10:00",
            "consentConfirmed": True,
            "idempotencyKey": "visual-upload-1",
        },
    )
    assert same_request.status_code == 201
    assert same_request.json()["id"] == visual_id

    processed = _process(client, interaction_id, visual_id)
    assert processed["processingStatus"] == "review"
    assert processed["interactionIntelligenceId"] is None
    assert processed["revenueBrainSnapshotId"] is None
    candidates = processed["candidates"]
    assert candidates
    assert all(candidate["origin"] == "ai_inferred" for candidate in candidates)
    assert all(candidate["validationState"] == "unreviewed" for candidate in candidates)

    reviewed = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/review",
        json={
            "decisions": [
                {
                    "candidateId": candidate["id"],
                    "decision": "accept",
                    "statement": "Customer requested a reviewed implementation workshop.",
                }
                for candidate in candidates
            ],
            "idempotencyKey": "review-visual-1",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["interactionUpdated"] is True
    assert reviewed.json()["revenueBrainUpdated"] is True

    workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    visual_intelligence = workspace.json()["visualIntelligence"]
    assert visual_intelligence["items"][0]["origin"] == "ai_inferred"
    assert visual_intelligence["items"][0]["sourceOwnership"] == "customer_created"
    assert visual_intelligence["items"][0]["validationState"] == "verified"

    brain = client.get(f"/api/v1/accounts/{company_id}/brain/visual-evidence")
    assert brain.status_code == 200, brain.text
    assert brain.json()[0]["interactionId"] == interaction_id
    assert "image" not in brain.text.casefold()

    deleted = client.delete(f"/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"id": visual_id, "deleted": True, "retryRequired": False}
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()["visualIntelligence"] is None
    assert client.get(f"/api/v1/accounts/{company_id}/brain/visual-evidence").json() == []


def test_presentation_business_card_and_site_photo_apply_conservative_source_rules(
    client: TestClient,
) -> None:
    presentation_id, _, _ = _completed_interaction(client, interaction_type="presentation")
    seller_slide = _create_and_upload(
        client,
        presentation_id,
        _png(),
        visual_type="presentation_slide",
        source_ownership="salesperson_created",
        context_label="Our deck says the customer will purchase this quarter",
        key="seller-slide",
    )
    processed_slide = _process(client, presentation_id, str(seller_slide["id"]))
    assert processed_slide["processingStatus"] == "completed"
    assert processed_slide["candidates"] == []
    assert processed_slide["interactionIntelligenceId"] is None

    card = _create_and_upload(
        client,
        presentation_id,
        _png(),
        visual_type="business_card",
        source_ownership="customer_created",
        context_label="Jordan Lee, jordan@example.test",
        key="business-card",
    )
    processed_card = _process(client, presentation_id, str(card["id"]))
    assert {item["category"] for item in processed_card["candidates"]} == {"contact_detail"}
    card_review = client.post(
        f"/api/v1/interactions/{presentation_id}/visual-evidence/{card['id']}/review",
        json={
            "decisions": [
                {"candidateId": item["id"], "decision": "accept", "statement": item["statement"]}
                for item in processed_card["candidates"]
            ],
            "idempotencyKey": "review-business-card",
        },
    )
    assert card_review.status_code == 200
    assert card_review.json()["interactionUpdated"] is False

    site_id, opportunity_id, _ = _completed_interaction(client, interaction_type="site_visit")
    site = _create_and_upload(
        client,
        site_id,
        _png(),
        visual_type="site_photo",
        source_ownership="unknown_origin",
        context_label="The loading bay may require a narrower equipment frame",
        key="site-photo",
    )
    processed_site = _process(client, site_id, str(site["id"]))
    assert {item["category"] for item in processed_site["candidates"]} == {"technical_constraint"}
    assert {item["supportClassification"] for item in processed_site["candidates"]} == {"observed"}
    assert "customer-confirmed" not in str(processed_site).casefold()
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()["visualIntelligence"] is None
    site_review = client.post(
        f"/api/v1/interactions/{site_id}/visual-evidence/{site['id']}/review",
        json={
            "decisions": [
                {"candidateId": item["id"], "decision": "accept", "statement": item["statement"]}
                for item in processed_site["candidates"]
            ],
            "idempotencyKey": "review-site-photo",
        },
    )
    assert site_review.status_code == 200, site_review.text
    assert site_review.json()["interactionUpdated"] is True
    site_workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()["visualIntelligence"]
    assert site_workspace["items"][0]["supportClassification"] == "observed"
    assert site_workspace["sourceLabel"] == "site photo (observed)"

    async def contact_count() -> int:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            count = int(
                await session.scalar(
                    select(func.count()).select_from(Contact).where(Contact.organisation_id == PRIMARY_ORGANISATION_ID)
                )
                or 0
            )
        await engine.dispose()
        return count

    assert asyncio.run(contact_count()) == 0


def test_visual_count_quota_stops_additional_uploads() -> None:
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        log_level="WARNING",
        cors_origins="http://localhost:3000",
        visual_storage_directory=str(TEST_VISUAL_STORAGE),
        private_beta_max_visuals_per_interaction=1,
    )
    with TestClient(create_app(settings)) as quota_client:
        interaction_id, _, _ = _completed_interaction(quota_client)
        image = _png()
        checksum = hashlib.sha256(image).hexdigest()
        payload = {
            "visualType": "whiteboard",
            "sourceOwnership": "customer_created",
            "contextLabel": "Customer workshop",
            "filename": "customer-workshop.png",
            "mimeType": "image/png",
            "byteSize": len(image),
            "checksumSha256": checksum,
            "capturedAt": "2026-08-14T10:00:00+10:00",
            "consentConfirmed": True,
            "idempotencyKey": "quota-visual-1",
        }
        first = quota_client.post(
            f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
            json=payload,
        )
        assert first.status_code == 201, first.text
        second = quota_client.post(
            f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
            json={**payload, "idempotencyKey": "quota-visual-2"},
        )
        assert second.status_code == 429
        assert second.json()["code"] == "visual_count_limit_exceeded"


def test_daily_visual_processing_quota_counts_attempts() -> None:
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        log_level="WARNING",
        cors_origins="http://localhost:3000",
        visual_storage_directory=str(TEST_VISUAL_STORAGE),
        private_beta_max_visual_ai_requests_per_day=1,
    )
    with TestClient(create_app(settings)) as quota_client:
        interaction_id, _, _ = _completed_interaction(quota_client)
        first = _create_and_upload(quota_client, interaction_id, _png(), key="daily-processing-1")
        assert _process(quota_client, interaction_id, str(first["id"]))["processingStatus"] == "review"
        second = _create_and_upload(quota_client, interaction_id, _png(), key="daily-processing-2")
        limited = quota_client.post(
            f"/api/v1/interactions/{interaction_id}/visual-evidence/{second['id']}/process",
            json={"idempotencyKey": "daily-processing-limit"},
        )
        assert limited.status_code == 429
        assert limited.json()["code"] == "daily_visual_processing_limit_exceeded"


def test_visual_consent_feature_flag_bounds_and_private_grants_fail_closed(
    app: FastAPI,
    client: TestClient,
) -> None:
    interaction_id, _, _ = _completed_interaction(client)
    image = _png()
    payload = {
        "visualType": "architecture_diagram",
        "sourceOwnership": "jointly_created",
        "contextLabel": "Jointly created architecture",
        "filename": "../../diagram.exe",
        "mimeType": "image/png",
        "byteSize": len(image),
        "checksumSha256": hashlib.sha256(image).hexdigest(),
        "capturedAt": "2026-08-14T10:00:00+10:00",
        "consentConfirmed": False,
        "idempotencyKey": "consent-required",
    }
    consent_denied = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json=payload,
    )
    assert consent_denied.status_code == 422
    unsupported = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json={
            **payload,
            "consentConfirmed": True,
            "mimeType": "image/gif",
            "idempotencyKey": "unsupported-mime",
        },
    )
    assert unsupported.status_code == 422
    oversized = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json={
            **payload,
            "consentConfirmed": True,
            "byteSize": 10_000_001,
            "idempotencyKey": "oversized",
        },
    )
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "image_too_large"

    interrupted = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json={
            **payload,
            "consentConfirmed": True,
            "idempotencyKey": "interrupted-upload",
        },
    )
    assert interrupted.status_code == 201
    incomplete = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{interrupted.json()['id']}/complete",
        json={
            "checksumSha256": payload["checksumSha256"],
            "idempotencyKey": "interrupted-complete",
        },
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["code"] == "visual_upload_incomplete"

    uploaded = _create_and_upload(
        client,
        interaction_id,
        image,
        visual_type="architecture_diagram",
        source_ownership="jointly_created",
        key="private-grants",
    )
    visual_id = UUID(str(uploaded["id"]))
    base_content_path = str(uploaded["downloadUrl"]).split("?", 1)[0]
    signer = VisualGrantSigner(app.state.settings.visual_storage_signing_secret.get_secret_value())
    expired = signer.issue(
        PRIMARY_ORGANISATION_ID,
        PRIMARY_USER_ID,
        visual_id,
        "download",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    wrong_resource = signer.issue(
        PRIMARY_ORGANISATION_ID,
        PRIMARY_USER_ID,
        UUID("00000000-0000-4000-8000-000000000099"),
        "download",
        datetime.now(UTC) + timedelta(minutes=1),
    )
    assert client.get(f"{base_content_path}?token={expired}").status_code == 403
    assert client.get(f"{base_content_path}?token={wrong_resource}").status_code == 403

    disabled_settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        visual_storage_directory=str(TEST_VISUAL_STORAGE),
        feature_visual_evidence_enabled=False,
    )
    with TestClient(create_app(disabled_settings)) as disabled_client:
        assert disabled_client.get(f"/api/v1/interactions/{interaction_id}/visual-evidence").status_code == 404

    storage = create_visual_storage(app.state.settings)
    with pytest.raises(VisualStorageError):
        asyncio.run(storage.write("../escape.png", image, "image/png"))


def test_visual_review_accept_edit_reject_double_submit_and_provenance_persist(
    client: TestClient,
) -> None:
    interaction_id, opportunity_id, _ = _completed_interaction(client)
    uploaded = _create_and_upload(
        client,
        interaction_id,
        _png(),
        visual_type="workshop_output",
        source_ownership="jointly_created",
        context_label="Customer requested an October timeline but raised a blocker",
        key="mixed-review",
    )
    processed = _process(client, interaction_id, str(uploaded["id"]))
    assert len(processed["candidates"]) == 3
    decisions = [
        {
            "candidateId": candidate["id"],
            "decision": "accept" if index == 0 else "reject",
            **({"statement": "Customer requested a reviewed October workshop."} if index == 0 else {}),
        }
        for index, candidate in enumerate(processed["candidates"])
    ]
    payload = {"decisions": decisions, "idempotencyKey": "mixed-review-submit"}
    first = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{uploaded['id']}/review",
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["acceptedCount"] == 1
    assert first.json()["rejectedCount"] == 2
    accepted = next(item for item in first.json()["candidates"] if item["reviewState"] == "accepted")
    assert accepted["statement"] == "Customer requested a reviewed October workshop."
    assert accepted["sourceOwnership"] == "jointly_created"
    assert accepted["origin"] == "ai_inferred"
    second = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{uploaded['id']}/review",
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["acceptedCount"] == 1
    workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()["visualIntelligence"]
    assert len(workspace["items"]) == 1
    assert workspace["items"][0]["sourceOwnership"] == "jointly_created"


def test_visual_upload_rejects_spoofing_polyglots_and_cross_tenant_access(
    app: FastAPI,
    client: TestClient,
) -> None:
    interaction_id, _, _ = _completed_interaction(client)
    image = _png()
    spoofed = _create_and_upload(
        client,
        interaction_id,
        image,
        key="mime-spoof",
        declared_mime_type="image/jpeg",
        expected_completion_status=422,
    )
    assert spoofed["code"] == "mime_mismatch"

    polyglot = image + b"<script>alert(1)</script>"
    checksum = hashlib.sha256(polyglot).hexdigest()
    created = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/uploads",
        json={
            "visualType": "screenshot",
            "sourceOwnership": "unknown_origin",
            "filename": "unsafe.png",
            "mimeType": "image/png",
            "byteSize": len(polyglot),
            "checksumSha256": checksum,
            "capturedAt": "2026-08-14T10:00:00Z",
            "consentConfirmed": True,
            "idempotencyKey": "polyglot",
        },
    )
    assert created.status_code == 201
    visual_id = created.json()["id"]
    assert (
        client.put(
            created.json()["uploadUrl"],
            content=polyglot,
            headers={"Content-Type": "image/png"},
        ).status_code
        == 204
    )
    rejected = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}/complete",
        json={"checksumSha256": checksum, "idempotencyKey": "polyglot-complete"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "image_polyglot"

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    hidden = client.get(f"/api/v1/interactions/{interaction_id}/visual-evidence")
    hidden_detail = client.get(f"/api/v1/interactions/{interaction_id}/visual-evidence/{visual_id}")
    app.dependency_overrides.pop(get_current_user)
    assert hidden.status_code == 404
    assert hidden_detail.status_code == 404


def test_unknown_origin_remains_context_after_user_review(client: TestClient) -> None:
    interaction_id, opportunity_id, _ = _completed_interaction(client)
    uploaded = _create_and_upload(
        client,
        interaction_id,
        _png(),
        visual_type="screenshot",
        source_ownership="unknown_origin",
        context_label="An unverified screenshot may show an implementation request",
        key="unknown-origin",
    )
    processed = _process(client, interaction_id, str(uploaded["id"]))
    assert processed["candidates"]
    assert {item["supportClassification"] for item in processed["candidates"]} == {"context"}
    reviewed = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{uploaded['id']}/review",
        json={
            "decisions": [
                {
                    "candidateId": item["id"],
                    "decision": "accept",
                    "statement": item["statement"],
                }
                for item in processed["candidates"]
            ],
            "idempotencyKey": "review-unknown-origin",
        },
    )
    assert reviewed.status_code == 200
    intelligence = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace").json()["visualIntelligence"]
    assert intelligence["items"][0]["sourceOwnership"] == "unknown_origin"
    assert intelligence["items"][0]["supportClassification"] == "context"


def test_visual_metadata_and_logs_never_store_image_or_context_content(
    client: TestClient,
    caplog: object,
) -> None:
    secret_context = "PRIVATE_VISUAL_CONTEXT_DO_NOT_LOG"
    interaction_id, _, _ = _completed_interaction(client)
    uploaded = _create_and_upload(
        client,
        interaction_id,
        _png(),
        context_label=secret_context,
        key="log-safety",
    )
    _process(client, interaction_id, str(uploaded["id"]))

    async def metadata() -> tuple[list[dict[str, object]], int, int]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            events = list(
                await session.scalars(
                    select(BetaSystemEvent).where(BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID)
                )
            )
            visual_count = int(await session.scalar(select(func.count()).select_from(VisualAsset)) or 0)
            evidence_count = int(await session.scalar(select(func.count()).select_from(Evidence)) or 0)
        await engine.dispose()
        return [event.metadata_json for event in events], visual_count, evidence_count

    events, visual_count, evidence_count = asyncio.run(metadata())
    assert visual_count == 1 and evidence_count >= 1
    assert all(secret_context not in str(item) for item in events)
    assert secret_context not in str(getattr(caplog, "text", ""))


def test_jpeg_exif_segment_is_removed_before_storage() -> None:
    app1 = b"\xff\xe1\x00\x08GPS123"
    frame = b"\xff\xc0\x00\x08\x08\x00\x02\x00\x03\x01"
    scan = b"\xff\xda\x00\x02\xff\xd9"
    image = b"\xff\xd8" + app1 + frame + scan
    validated = validate_and_sanitise_visual(
        image,
        declared_mime_type="image/jpeg",
        declared_byte_size=len(image),
        declared_checksum=hashlib.sha256(image).hexdigest(),
        max_bytes=10_000,
        max_dimension=100,
        max_pixels=10_000,
    )
    assert validated.width == 3 and validated.height == 2
    assert validated.metadata_stripped is True
    assert b"GPS123" not in validated.content


def test_png_decoder_rejects_dimension_mismatch_bombs_and_configured_dimensions() -> None:
    bomb = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(b"\x00" + (b"\x00" * 10_000)))
        + _chunk(b"IEND", b"")
    )
    with pytest.raises(UnsafeVisualError, match="does not match"):
        validate_and_sanitise_visual(
            bomb,
            declared_mime_type="image/png",
            declared_byte_size=len(bomb),
            declared_checksum=hashlib.sha256(bomb).hexdigest(),
            max_bytes=100_000,
            max_dimension=100,
            max_pixels=10_000,
        )
    too_wide = _png(width=101)
    with pytest.raises(UnsafeVisualError, match="dimensions"):
        validate_and_sanitise_visual(
            too_wide,
            declared_mime_type="image/png",
            declared_byte_size=len(too_wide),
            declared_checksum=hashlib.sha256(too_wide).hexdigest(),
            max_bytes=100_000,
            max_dimension=100,
            max_pixels=10_000,
        )


def test_visual_export_and_retention_cover_metadata_candidates_and_private_object(
    app: FastAPI,
    client: TestClient,
) -> None:
    interaction_id, _, _ = _completed_interaction(client)
    uploaded = _create_and_upload(
        client,
        interaction_id,
        _png(),
        context_label="Customer requested a security workshop",
        key="export-retention",
    )
    processed = _process(client, interaction_id, str(uploaded["id"]))
    reviewed = client.post(
        f"/api/v1/interactions/{interaction_id}/visual-evidence/{uploaded['id']}/review",
        json={
            "decisions": [
                {
                    "candidateId": item["id"],
                    "decision": "accept",
                    "statement": item["statement"],
                }
                for item in processed["candidates"]
            ],
            "idempotencyKey": "review-export-retention",
        },
    )
    assert reviewed.status_code == 200
    export_request = client.post("/api/v1/beta/admin/exports")
    assert export_request.status_code == 202

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        export_path = await generate_export(
            factory,
            app.state.settings,
            PRIMARY_ORGANISATION_ID,
            UUID(export_request.json()["id"]),
        )
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        exported_visual = next(item for item in payload["visualAssets"] if item["id"] == uploaded["id"])
        assert exported_visual["source_ownership"] == "customer_created"
        assert exported_visual["imageExportStatus"] == "not_requested"
        assert "imageBase64" not in exported_visual
        assert "storage_key" not in exported_visual
        assert "provider_request_id" not in exported_visual
        assert any(
            item["source_visual_id"] == uploaded["id"] and item["review_state"] == "accepted"
            for item in payload["visualCandidateEvidence"]
        )

        old = datetime.now(UTC) - timedelta(days=200)
        async with factory() as session:
            interaction = await session.get(Interaction, UUID(interaction_id))
            asset = await session.get(VisualAsset, UUID(str(uploaded["id"])))
            assert interaction is not None and asset is not None
            storage_path = TEST_VISUAL_STORAGE / asset.storage_key
            assert storage_path.is_file()
            interaction.scheduled_start_at = old
            interaction.actual_end_at = old
            interaction.created_at = old
            interaction.updated_at = old
            await session.commit()

        dry_run = await run_retention(
            factory,
            app.state.settings,
            PRIMARY_ORGANISATION_ID,
            dry_run=True,
            batch_size=10,
        )
        assert dry_run.removed["visual_assets"] == 1
        assert storage_path.is_file()
        removed = await run_retention(
            factory,
            app.state.settings,
            PRIMARY_ORGANISATION_ID,
            dry_run=False,
            batch_size=10,
        )
        assert removed.removed["visual_assets"] == 1
        assert removed.removed["visual_candidate_evidence"] >= 1
        assert not storage_path.exists()
        async with factory() as session:
            assert await session.get(VisualAsset, UUID(str(uploaded["id"]))) is None
        await engine.dispose()

    asyncio.run(scenario())


def test_visual_storage_reconciliation_detects_and_repairs_missing_and_orphaned_objects(
    app: FastAPI,
    client: TestClient,
) -> None:
    interaction_id, _, _ = _completed_interaction(client)
    uploaded = _create_and_upload(client, interaction_id, _png(), key="reconcile-visual")
    visual_id = UUID(str(uploaded["id"]))

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = app.state.settings
        storage = create_visual_storage(settings)
        async with factory() as session:
            asset = await session.get(VisualAsset, visual_id)
            assert asset is not None
            await storage.delete(asset.storage_key)
        orphan_key = f"{PRIMARY_ORGANISATION_ID}/{interaction_id}/orphan.png"
        await storage.write(orphan_key, _png(), "image/png")

        report = await reconcile_visual_storage(
            factory,
            settings,
            PRIMARY_ORGANISATION_ID,
            repair=False,
        )
        assert report.missing_objects
        assert report.orphaned_objects == (orphan_key,)
        assert report.repaired_missing_objects == 0

        repaired = await reconcile_visual_storage(
            factory,
            settings,
            PRIMARY_ORGANISATION_ID,
            repair=True,
        )
        assert repaired.repaired_missing_objects == 1
        assert repaired.removed_orphaned_objects == 1
        assert orphan_key not in await storage.list_keys(f"{PRIMARY_ORGANISATION_ID}/")
        async with factory() as session:
            asset = await session.get(VisualAsset, visual_id)
            assert asset is not None
            assert asset.storage_status == "missing"
            assert asset.processing_status == "failed"
            source = await session.get(Evidence, asset.source_evidence_id)
            assert source is not None and source.lifecycle_status == "excluded"
        await engine.dispose()

    asyncio.run(scenario())
