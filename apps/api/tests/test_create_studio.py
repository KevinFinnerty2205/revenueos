from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import zipfile
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.util import Inches
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.create_pptx import (
    BoundedPptxProcessor,
    MalformedPptxError,
    PptxLimitError,
    PptxLimits,
    RenderSlide,
    UnsafePptxError,
    UnsupportedPptxError,
)
from revenueos.create_worker import CreateWorkerService, create_processor
from revenueos.visual_storage import create_visual_storage

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_business_api import create_company, create_contact, create_opportunity
from .test_business_cases import _create_approved_model, _inputs
from .test_meeting_api import cast_auth_dependency, secondary_user


def _pptx() -> bytes:
    presentation = Presentation()
    title = presentation.slides.add_slide(presentation.slide_layouts[0])
    title.shapes.title.text = "Summit Access Systems"
    title.placeholders[1].text = "Approved company presentation"
    synthetic_logo = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9YEksEIAAAAASUVORK5CYII="
    )
    title.shapes.add_picture(io.BytesIO(synthetic_logo), Inches(11.4), Inches(0.35), Inches(0.55))
    for heading, body in (
        ("Agenda", "Customer context\nApproved capabilities\nProposed approach\nNext steps"),
        (
            "Product platform",
            "Centralised access administration\nPolicy-based controls\nCustomer-owned implementation checkpoints",
        ),
        (
            "Approved customer story",
            "A synthetic customer consolidated access workflows using the approved Summit delivery process.",
        ),
        ("Proposed solution", "Approved capability and implementation approach"),
        ("Implementation process", "Align\nValidate\nExpand"),
        ("Next steps", "Agree the next customer-owned implementation workshop"),
        (
            "Customer-safe legal notice",
            "Illustrative synthetic content only. Final scope is subject to an executed agreement.",
        ),
    ):
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = heading
        slide.placeholders[1].text = body
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


def _limits() -> PptxLimits:
    return PptxLimits(
        max_bytes=50_000_000,
        max_slides=100,
        max_entries=2_000,
        max_expanded_bytes=250_000_000,
        max_media_assets=500,
        max_media_bytes=10_000_000,
        max_xml_bytes=5_000_000,
        max_extracted_characters=250_000,
    )


def _rewrite_pptx(
    source: bytes,
    *,
    additions: dict[str, bytes] | None = None,
    replacements: dict[str, bytes] | None = None,
) -> bytes:
    additions = additions or {}
    replacements = replacements or {}
    target = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(source)) as original,
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as modified,
    ):
        for info in original.infolist():
            modified.writestr(info.filename, replacements.get(info.filename, original.read(info)))
        for name, content in additions.items():
            modified.writestr(name, content)
    return target.getvalue()


def _run_worker(app: FastAPI) -> bool:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    settings = app.state.settings

    async def run() -> bool:
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        worker = CreateWorkerService(
            factory,
            settings,
            storage=create_visual_storage(settings),
            processor=create_processor(settings),
        )
        try:
            return await worker.run_once("create-test-worker")
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _upload(client: TestClient) -> dict[str, object]:
    content = _pptx()
    response = client.post(
        "/api/v1/create/templates",
        json={
            "name": "Approved sales story",
            "fileName": "approved-sales-story.pptx",
            "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "contentBase64": base64.b64encode(content).decode(),
            "checksumSha256": hashlib.sha256(content).hexdigest(),
            "authorityAttested": True,
            "attestationVersion": 1,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _review_and_approve(client: TestClient, template: dict[str, object]) -> dict[str, object]:
    version = template["latestVersion"]
    assert isinstance(version, dict)
    for raw_slide in version["slides"]:
        assert isinstance(raw_slide, dict)
        is_locked_required = raw_slide["category"] in {"title", "appendix"}
        response = client.patch(
            f"/api/v1/create/template-slides/{raw_slide['id']}",
            json={
                "category": raw_slide["category"],
                "reuseState": "approved",
                "modificationPolicy": "locked" if is_locked_required else "text_placeholders_only",
                "customerSafe": True,
                "required": is_locked_required,
                "exactTextRequired": is_locked_required,
                "approvedDescription": "Approved for customer-facing reuse.",
                "placeholderMappings": {},
            },
        )
        assert response.status_code == 200, response.text
    response = client.post(
        f"/api/v1/create/templates/{template['id']}/versions/{version['id']}/approve",
        json={"confirmed": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_pptx_processor_rejects_active_content_and_external_relationships() -> None:
    processor = BoundedPptxProcessor(_limits())
    source = _pptx()
    parsed = processor.parse(source)
    assert len(parsed.slides) == 8

    unsafe = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(source)) as original,
        zipfile.ZipFile(
            unsafe,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as modified,
    ):
        for info in original.infolist():
            modified.writestr(info.filename, original.read(info))
        modified.writestr("ppt/vbaProject.bin", b"not executable in RevenueOS")
    with pytest.raises(UnsafePptxError):
        processor.parse(unsafe.getvalue())

    rendered = processor.render(
        source,
        (RenderSlide(slide_number=2, replacements={}),),
        title="Customer-safe export",
        organisation_name="Must not be embedded",
    )
    exported = Presentation(io.BytesIO(rendered))
    assert len(exported.slides) == 1
    assert exported.core_properties.title == "Customer-safe export"
    assert exported.core_properties.author == "RevenueOS"
    assert exported.core_properties.last_modified_by == "RevenueOS"
    with zipfile.ZipFile(io.BytesIO(rendered)) as archive:
        slide_parts = [
            name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ]
        assert len(slide_parts) == 1
        xml_parts = {name: archive.read(name) for name in archive.namelist() if name.endswith(".xml")}
        package_text = b"\n".join(xml_parts.values())
    assert b"Product platform" not in package_text
    assert b"Implementation process" not in package_text
    assert b"Customer-safe legal notice" not in package_text
    assert b"TitlesOfParts" not in xml_parts["docProps/app.xml"]
    assert b"Must not be embedded" not in package_text


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.xml",
        "ppt/activeX/activeX1.xml",
        "ppt/embeddings/oleObject1.bin",
        "ppt/fonts/font1.fntdata",
        "ppt/vbaProject.bin",
    ],
)
def test_pptx_processor_rejects_unsafe_package_paths(unsafe_path: str) -> None:
    with pytest.raises(UnsafePptxError):
        BoundedPptxProcessor(_limits()).parse(_rewrite_pptx(_pptx(), additions={unsafe_path: b"untrusted"}))


def test_pptx_processor_rejects_external_relationships_entities_and_unsafe_media() -> None:
    source = _pptx()
    rel_path = "ppt/slides/_rels/slide1.xml.rels"
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        relationships = archive.read(rel_path).replace(
            b"</Relationships>",
            (
                b'<Relationship Id="rExternal" '
                b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                b'Target="https://untrusted.example/" TargetMode="External"/></Relationships>'
            ),
        )
        presentation_xml = archive.read("ppt/presentation.xml")
    processor = BoundedPptxProcessor(_limits())
    with pytest.raises(UnsafePptxError):
        processor.parse(_rewrite_pptx(source, replacements={rel_path: relationships}))
    with pytest.raises(UnsafePptxError):
        processor.parse(
            _rewrite_pptx(
                source,
                replacements={
                    "ppt/presentation.xml": b'<!DOCTYPE p [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                    + presentation_xml
                },
            )
        )
    with pytest.raises(UnsupportedPptxError):
        processor.parse(_rewrite_pptx(source, additions={"ppt/media/image999.svg": b"<svg/>"}))


def test_pptx_processor_enforces_slide_media_and_decompression_limits() -> None:
    source = _pptx()
    strict_slides = replace(_limits(), max_slides=1)
    with pytest.raises(PptxLimitError):
        BoundedPptxProcessor(strict_slides).parse(source)
    strict_media = replace(_limits(), max_media_bytes=8)
    with pytest.raises(PptxLimitError):
        BoundedPptxProcessor(strict_media).parse(
            _rewrite_pptx(source, additions={"ppt/media/image999.png": b"\x89PNG\r\n\x1a\n0"})
        )
    with pytest.raises(PptxLimitError):
        BoundedPptxProcessor(_limits()).parse(_rewrite_pptx(source, additions={"ppt/unused.xml": b"x" * 1_100_000}))
    empty = io.BytesIO()
    Presentation().save(empty)
    with pytest.raises(MalformedPptxError):
        BoundedPptxProcessor(_limits()).parse(empty.getvalue())


def test_pptx_processor_marks_hidden_slides_unsafe_for_reuse_and_excludes_notes() -> None:
    presentation = Presentation(io.BytesIO(_pptx()))
    presentation.slides._sldIdLst[1].set("show", "0")  # noqa: SLF001 - fixture-only Open XML flag
    presentation.slides[0].notes_slide.notes_text_frame.text = "Internal presenter note"
    content = io.BytesIO()
    presentation.save(content)

    parsed = BoundedPptxProcessor(_limits()).parse(content.getvalue())
    assert parsed.slides[1].hidden is True
    assert parsed.slides[1].reuse_state == "excluded"
    assert parsed.slides[1].customer_safe is False
    assert "hidden_slides_excluded" in parsed.warning_codes
    assert "speaker_notes_excluded" in parsed.warning_codes


def test_create_template_plan_generation_review_approval_and_private_download(
    client: TestClient,
    app: FastAPI,
) -> None:
    availability = client.get("/api/v1/create/availability")
    assert availability.status_code == 200
    assert availability.json()["state"] == "available"

    queued = _upload(client)
    assert queued["latestVersion"]["processingState"] == "processing"  # type: ignore[index]
    assert _run_worker(app)
    template = client.get(f"/api/v1/create/templates/{queued['id']}").json()
    assert template["latestVersion"]["processingState"] == "ready"
    assert template["latestVersion"]["slideCount"] == 8
    template = _review_and_approve(client, template)
    assert template["latestVersion"]["approvalState"] == "approved"

    company = create_company(client, name="Create Customer")
    opportunity = create_opportunity(client, str(company["id"]), name="Secure rollout")
    contact = create_contact(client, str(company["id"]), first_name="Taylor")
    created = client.post(
        "/api/v1/create/presentations",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "objective": "solution_overview",
            "audience": [
                {
                    "contactId": contact["id"],
                    "audienceType": "executive",
                }
            ],
            "templateVersionId": template["latestVersion"]["id"],
            "focusInstruction": "Keep the implementation discussion concise.",
            "idempotencyKey": "create-plan-1",
        },
    )
    assert created.status_code == 201, created.text
    presentation = created.json()
    assert presentation["state"] == "draft_plan"
    assert presentation["accountName"] == "Create Customer"
    assert presentation["plan"][0]["required"] is True
    assert any(
        item["category"] == "appendix" and item["required"] and item["exactTextRequired"]
        for item in presentation["plan"]
    )

    generated = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/generate",
        json={"idempotencyKey": "create-generate-1"},
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["state"] == "generating"
    assert _run_worker(app)
    presentation = client.get(f"/api/v1/create/presentations/{presentation['id']}").json()
    assert presentation["state"] == "needs_review"
    assert presentation["currentVersion"]["slides"]
    assert all(claim["origin"] == "approved_company_content" for claim in presentation["currentVersion"]["claims"])

    editable = next(
        slide
        for slide in presentation["currentVersion"]["slides"]
        if slide["modificationPolicy"] == "text_placeholders_only"
    )
    blocked = client.patch(
        f"/api/v1/create/presentations/{presentation['id']}/slides/{editable['planItemId']}",
        json={
            "title": "Internal recommendation",
            "bodyBlocks": ["Manager coaching says the win probability is 75%."],
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "internal_only_content"

    edited = client.patch(
        f"/api/v1/create/presentations/{presentation['id']}/slides/{editable['planItemId']}",
        json={
            "title": editable["title"],
            "bodyBlocks": ["Confirm the customer-owned implementation workshop."],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["state"] == "generating"
    assert _run_worker(app)
    presentation = client.get(f"/api/v1/create/presentations/{presentation['id']}").json()
    edited_claim = next(
        claim for claim in presentation["currentVersion"]["claims"] if claim["planItemId"] == editable["planItemId"]
    )
    assert edited_claim["origin"] == "user_edited"
    assert edited_claim["reviewState"] == "pending"
    reviewed = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/review",
        json={"decisions": [{"claimId": edited_claim["id"], "action": "keep"}]},
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/approve",
        json={"confirmed": True},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["currentVersion"]["downloadAvailable"] is True

    grant = client.post(f"/api/v1/create/presentations/{presentation['id']}/download-grant")
    assert grant.status_code == 200, grant.text
    downloaded = client.get(grant.json()["downloadUrl"])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert downloaded.headers["cache-control"] == "private, no-store"
    rendered = Presentation(io.BytesIO(downloaded.content))
    rendered_text = "\n".join(shape.text for slide in rendered.slides for shape in slide.shapes if shape.has_text_frame)
    assert "Confirm the customer-owned implementation workshop." in rendered_text
    assert "win probability" not in rendered_text.casefold()
    assert rendered.core_properties.title == presentation["title"]
    assert rendered.core_properties.comments == ""

    app.state.settings.private_beta_max_create_presentations_per_user_per_day = 1
    quota_denied = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/generate",
        json={
            "idempotencyKey": "create-generate-over-user-limit",
            "explicitRegenerate": True,
        },
    )
    assert quota_denied.status_code == 429
    assert quota_denied.json()["code"] == "create_user_daily_limit"
    app.state.settings.private_beta_max_create_presentations_per_user_per_day = 10
    app.state.settings.private_beta_max_create_presentations_per_organisation_per_day = 1
    organisation_quota_denied = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/generate",
        json={
            "idempotencyKey": "create-generate-over-organisation-limit",
            "explicitRegenerate": True,
        },
    )
    assert organisation_quota_denied.status_code == 429
    assert organisation_quota_denied.json()["code"] == "create_organisation_daily_limit"

    member = AuthenticatedUser(
        user_id=PRIMARY_USER_ID,
        external_auth_id="user_dev_001",
        display_name="Create Member",
        email="member@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(member)
    assert client.get(f"/api/v1/create/templates/{template['id']}").status_code == 200
    source = _pptx()
    member_upload = client.post(
        "/api/v1/create/templates",
        json={
            "name": "Member cannot upload",
            "fileName": "member.pptx",
            "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "contentBase64": base64.b64encode(source).decode(),
            "checksumSha256": hashlib.sha256(source).hexdigest(),
            "authorityAttested": True,
            "attestationVersion": 1,
        },
    )
    assert member_upload.status_code == 403
    member_plan = client.post(
        "/api/v1/create/presentations",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "objective": "executive_presentation",
            "audience": [{"name": "Operations leadership", "audienceType": "executive"}],
            "templateVersionId": template["latestVersion"]["id"],
            "idempotencyKey": "create-member-plan-1",
        },
    )
    assert member_plan.status_code == 201, member_plan.text


def test_approved_business_case_flows_into_create_with_exact_scenario_provenance(
    client: TestClient,
    app: FastAPI,
) -> None:
    company = create_company(client, name="Business Case Customer")
    opportunity = create_opportunity(client, str(company["id"]), name="Access transformation")
    model = _create_approved_model(client)
    created_case = client.post(
        "/api/v1/create/business-cases",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "modelVersionId": model["latestVersion"]["id"],
            "currency": "AUD",
            "idempotencyKey": "create-integration-case-1",
        },
    )
    assert created_case.status_code == 201, created_case.text
    business_case = created_case.json()
    calculated = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={
            "inputs": _inputs(),
            "scenarios": [
                {"name": "conservative", "overrides": [{"key": "minutes_future", "value": "10"}]},
                {"name": "upside", "overrides": [{"key": "minutes_future", "value": "2"}]},
            ],
            "idempotencyKey": "create-integration-calculate-1",
        },
    )
    assert calculated.status_code == 200, calculated.text
    approved_case = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/approve",
        json={"confirmed": True},
    )
    assert approved_case.status_code == 200, approved_case.text
    case_version = approved_case.json()["currentVersion"]

    queued = _upload(client)
    assert _run_worker(app)
    template = client.get(f"/api/v1/create/templates/{queued['id']}").json()
    template = _review_and_approve(client, template)
    presentation_response = client.post(
        "/api/v1/create/presentations",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "objective": "business_case",
            "audience": [{"name": "Finance leadership", "audienceType": "finance"}],
            "templateVersionId": template["latestVersion"]["id"],
            "businessCaseVersionId": case_version["id"],
            "businessCaseScenario": "all",
            "idempotencyKey": "create-business-case-plan-1",
        },
    )
    assert presentation_response.status_code == 201, presentation_response.text
    presentation = presentation_response.json()
    assert presentation["businessCaseId"] == business_case["id"]
    assert presentation["businessCaseVersionId"] == case_version["id"]
    assert presentation["businessCaseScenario"] == "all"
    assert any("approved_business_case" in item["sourceClasses"] for item in presentation["plan"])

    generated = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/generate",
        json={"idempotencyKey": "create-business-case-generate-1"},
    )
    assert generated.status_code == 200, generated.text
    assert _run_worker(app)
    presentation = client.get(f"/api/v1/create/presentations/{presentation['id']}").json()
    business_claims = [
        claim for claim in presentation["currentVersion"]["claims"] if claim["origin"] == "approved_business_case"
    ]
    assert business_claims
    assert all(claim["sourceIds"] == [case_version["id"]] for claim in business_claims)
    claim_text = " ".join(claim["claim"] for claim in business_claims)
    assert "conservative assumptions" in claim_text
    assert "base-case assumptions" in claim_text
    assert "upside assumptions" in claim_text
    assert "Material assumption" in claim_text
    assert "not a guarantee of future results" in claim_text
    assert "safe_divide" not in claim_text
    approved_presentation = client.post(
        f"/api/v1/create/presentations/{presentation['id']}/approve",
        json={"confirmed": True},
    )
    assert approved_presentation.status_code == 200, approved_presentation.text

    superseded = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={"inputs": _inputs(rekey_cost="0"), "idempotencyKey": "create-integration-calculate-2"},
    )
    assert superseded.status_code == 200, superseded.text
    blocked_export = client.post(f"/api/v1/create/presentations/{presentation['id']}/download-grant")
    assert blocked_export.status_code == 409
    assert blocked_export.json()["code"] == "claim_source_changed"

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    cross_tenant = client.get(f"/api/v1/create/templates/{template['id']}")
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["code"] == "template_not_found"


def test_create_entitlement_fails_closed_and_is_admin_managed(client: TestClient) -> None:
    disabled = client.patch("/api/v1/create/admin/entitlement", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["state"] == "not_in_plan"
    denied = client.get("/api/v1/create/templates")
    assert denied.status_code == 403
    assert denied.json()["code"] == "create_not_entitled"
    enabled = client.patch("/api/v1/create/admin/entitlement", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["state"] == "available"
