from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_case_contracts import (
    CalculationInputResponse,
    CalculationOutputResponse,
    ScenarioCalculationResponse,
)
from revenueos.config import Settings
from revenueos.create_contracts import (
    ApprovedContentItemResponse,
    CreateAvailabilityResponse,
    CreateEntitlementUpdate,
    PresentationApprovalRequest,
    PresentationBriefRequest,
    PresentationDownloadGrantResponse,
    PresentationGenerateRequest,
    PresentationListResponse,
    PresentationPlanItemResponse,
    PresentationPlanUpdateRequest,
    PresentationResponse,
    PresentationReviewRequest,
    PresentationSlideEditRequest,
    PresentationVersionResponse,
    TemplateApprovalRequest,
    TemplateListResponse,
    TemplateSlideResponse,
    TemplateSlideUpdate,
    TemplateSummaryResponse,
    TemplateTextBlockResponse,
    TemplateUploadRequest,
    TemplateVersionResponse,
)
from revenueos.create_pptx import (
    CREATE_PPTX_PROFILE_VERSION,
    PPTX_MIME_TYPE,
    BoundedPptxProcessor,
    PptxProcessingError,
)
from revenueos.create_repositories import CreateRepository
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    CreateApprovedContentItem,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreateDownloadGrant,
    CreatePresentation,
    CreatePresentationVersion,
    CreateTemplate,
    CreateTemplateSlide,
    CreateTemplateVersion,
    Opportunity,
    OrganisationModuleEntitlement,
)
from revenueos.tenant import TenantContext
from revenueos.visual_storage import VisualObjectMissingError, VisualStorage, VisualStorageError

logger = logging.getLogger("revenueos.create")

_SAFE_CUSTOMER_CATEGORIES = frozenset(
    {
        "customer_request",
        "technical_requirement",
        "contractual_requirement",
        "timeline",
        "implementation",
        "decision",
        "action_item",
        "commitment",
        "open_question",
        "security_legal",
    }
)
_SAFE_PUBLIC_CATEGORIES = frozenset(
    {
        "company_profile",
        "industry",
        "location",
        "size",
        "business_model",
        "product_service",
        "strategic_initiative",
        "expansion",
        "hiring",
        "leadership_change",
        "technology",
        "regulatory",
        "partnership",
        "customer_market",
        "trigger",
        "potential_fit",
    }
)
_INTERNAL_COPY = re.compile(
    r"\b(win probability|deal probability|forecast category|manager coaching|private note|"
    r"internal risk|contactability|suppression|champion hypothesis|competitive trap|"
    r"methodology score|close confidence)\b",
    re.IGNORECASE,
)
_OBJECTIVE_LABELS = {
    "introductory_meeting": "Introductory meeting",
    "discovery_follow_up": "Discovery follow-up",
    "solution_overview": "Solution overview",
    "technical_workshop": "Technical workshop",
    "executive_presentation": "Executive presentation",
    "proposal_presentation": "Proposal presentation",
    "business_case": "Business case",
    "event_follow_up": "Event follow-up",
}
_OBJECTIVE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "introductory_meeting": ("title", "agenda", "company_overview", "problem", "solution", "next_steps"),
    "discovery_follow_up": ("title", "agenda", "problem", "solution", "proof_point", "next_steps"),
    "solution_overview": ("title", "agenda", "solution", "product", "capability", "case_study", "next_steps"),
    "technical_workshop": ("title", "agenda", "architecture", "capability", "process", "next_steps"),
    "executive_presentation": ("title", "agenda", "problem", "solution", "proof_point", "next_steps"),
    "proposal_presentation": ("title", "problem", "solution", "process", "proof_point", "next_steps"),
    "business_case": ("title", "problem", "solution", "proof_point", "process", "next_steps"),
    "event_follow_up": ("title", "agenda", "problem", "solution", "next_steps"),
}


class CreateService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        storage: VisualStorage,
        processor: BoundedPptxProcessor,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.storage = storage
        self.processor = processor
        self.repository = CreateRepository(session)

    async def availability(self) -> CreateAvailabilityResponse:
        entitlement = await self.repository.entitlement(self.tenant.organisation_id)
        enabled = bool(self.settings.feature_create_enabled and entitlement and entitlement.enabled)
        if not self.settings.feature_create_enabled:
            state: Literal["available", "temporarily_unavailable", "not_in_plan"] = "temporarily_unavailable"
            message = "Create is temporarily unavailable in this environment."
        elif entitlement is None or not entitlement.enabled:
            state = "not_in_plan"
            message = "Create is not enabled for this organisation."
        else:
            state = "available"
            message = "Create is ready for approved PowerPoint templates."
        return CreateAvailabilityResponse(
            state=state,
            enabled=enabled,
            can_manage=self.tenant.can_manage(),
            can_upload_templates=enabled and self.tenant.can_manage(),
            can_create_presentations=enabled,
            message=message,
            description="Build reviewed, traceable sales presentations from approved company content.",
        )

    async def update_entitlement(self, request: CreateEntitlementUpdate) -> CreateAvailabilityResponse:
        self._require_admin()
        if request.enabled and not self.settings.feature_create_enabled:
            raise PublicAPIError(
                "create_unavailable",
                "RevenueOS Create cannot be enabled in this environment.",
                503,
            )
        now = datetime.now(UTC)
        entitlement = await self.repository.entitlement(self.tenant.organisation_id)
        if entitlement is None:
            entitlement = OrganisationModuleEntitlement(
                organisation_id=self.tenant.organisation_id,
                module_key="create",
                enabled=request.enabled,
                source="manual_private_beta",
                configured_by_user_id=self.tenant.user_id,
                enabled_at=now if request.enabled else None,
                disabled_at=now if not request.enabled else None,
            )
            self.repository.add(entitlement)
        else:
            entitlement.enabled = request.enabled
            entitlement.configured_by_user_id = self.tenant.user_id
            entitlement.enabled_at = now if request.enabled else entitlement.enabled_at
            entitlement.disabled_at = None if request.enabled else now
        await self._commit("The Create entitlement could not be saved.")
        self._audit("create_entitlement_changed", enabled=request.enabled)
        return await self.availability()

    async def upload_template(self, request: TemplateUploadRequest) -> TemplateSummaryResponse:
        await self._require_entitled()
        self._require_admin()
        try:
            content = base64.b64decode(request.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise PublicAPIError("invalid_pptx", "The selected PPTX could not be read.", 422) from exc
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != request.checksum_sha256:
            raise PublicAPIError("checksum_mismatch", "The uploaded file checksum did not match.", 422)
        duplicate = await self.repository.template_version_by_checksum(self.tenant.organisation_id, checksum)
        if duplicate is not None:
            raise PublicAPIError(
                "duplicate_template_version",
                "This exact PPTX has already been uploaded.",
                409,
            )
        try:
            parsed = self.processor.parse(content)
        except PptxProcessingError as exc:
            raise PublicAPIError(exc.code, "The PPTX did not pass the secure template checks.", 422) from exc

        template: CreateTemplate | None
        if request.template_id is None:
            if await self.repository.active_template_count(self.tenant.organisation_id) >= (
                self.settings.private_beta_max_create_templates
            ):
                raise PublicAPIError("create_template_limit", "The active template limit has been reached.", 429)
            if await self.repository.template_by_name(self.tenant.organisation_id, request.name) is not None:
                raise PublicAPIError("template_name_conflict", "A template with this name already exists.", 409)
            template = CreateTemplate(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                name=request.name,
                state="active",
                created_by_user_id=self.tenant.user_id,
            )
            self.repository.add(template)
            await self.session.flush()
        else:
            template = await self.repository.template(self.tenant.organisation_id, request.template_id)
            if template is None or template.state != "active":
                raise PublicAPIError("template_not_found", "The template was not found.", 404)
            if await self.repository.template_version_count(self.tenant.organisation_id, template.id) >= (
                self.settings.private_beta_max_create_template_versions
            ):
                raise PublicAPIError(
                    "create_template_version_limit",
                    "The template version limit has been reached.",
                    429,
                )
        version_number = await self.repository.template_version_count(self.tenant.organisation_id, template.id) + 1
        version_id = uuid.uuid4()
        storage_key = f"{self.tenant.organisation_id}/create/templates/{template.id}/{version_id}.pptx"
        now = datetime.now(UTC)
        try:
            await self.storage.write(storage_key, content, PPTX_MIME_TYPE)
        except VisualStorageError as exc:
            raise PublicAPIError("create_storage_unavailable", "The template could not be stored.", 503) from exc
        version = CreateTemplateVersion(
            id=version_id,
            organisation_id=self.tenant.organisation_id,
            template_id=template.id,
            version=version_number,
            uploaded_by_user_id=self.tenant.user_id,
            processing_state="processing",
            approval_state="pending",
            display_filename=request.file_name,
            storage_key=storage_key,
            storage_status="available",
            mime_type=PPTX_MIME_TYPE,
            byte_size=len(content),
            checksum_sha256=checksum,
            processing_schema_version=1,
            slide_count=0,
            warning_codes_json=[],
            manifest_json={"preflightSlideCount": len(parsed.slides)},
            compatibility_state="needs_attention",
            compatibility_details_json=["slide_review_required"],
            validation_profile_version=CREATE_PPTX_PROFILE_VERSION,
            authority_attestation_version=request.attestation_version,
            authority_attested_by_user_id=self.tenant.user_id,
            authority_attested_at=now,
            processing_attempts=0,
        )
        self.repository.add(version)
        try:
            await self._commit("The template could not be queued for processing.")
        except PublicAPIError:
            await self.storage.delete(storage_key)
            raise
        self._audit(
            "create_template_uploaded",
            template_id=str(template.id),
            template_version_id=str(version.id),
            byte_size=len(content),
            slide_count=len(parsed.slides),
        )
        return await self.get_template(template.id)

    async def list_templates(self) -> TemplateListResponse:
        await self._require_entitled()
        items = [
            await self._template_response(item) for item in await self.repository.templates(self.tenant.organisation_id)
        ]
        return TemplateListResponse(
            items=items,
            can_upload=self.tenant.can_manage(),
            max_active_templates=self.settings.private_beta_max_create_templates,
        )

    async def get_template(self, template_id: UUID) -> TemplateSummaryResponse:
        await self._require_entitled()
        template = await self.repository.template(self.tenant.organisation_id, template_id)
        if template is None:
            raise PublicAPIError("template_not_found", "The template was not found.", 404)
        return await self._template_response(template)

    async def update_slide(self, slide_id: UUID, request: TemplateSlideUpdate) -> TemplateSummaryResponse:
        await self._require_entitled()
        self._require_admin()
        slide = await self.repository.slide(self.tenant.organisation_id, slide_id)
        if slide is None:
            raise PublicAPIError("template_slide_not_found", "The template slide was not found.", 404)
        version = await self.repository.template_version(self.tenant.organisation_id, slide.template_version_id)
        if version is None or version.processing_state not in {"ready", "partial"}:
            raise PublicAPIError("template_not_reviewable", "Template processing has not completed.", 409)
        if version.approval_state == "approved":
            raise PublicAPIError("template_version_immutable", "An approved template version cannot be changed.", 409)
        valid_shape_ids = {
            str(item.get("shapeId"))
            for item in slide.text_blocks_json
            if isinstance(item, dict) and isinstance(item.get("shapeId"), int)
        }
        if not set(request.placeholder_mappings).issubset(valid_shape_ids):
            raise PublicAPIError("invalid_placeholder", "A mapped placeholder was not found on the slide.", 422)
        if slide.hidden and request.reuse_state == "approved":
            raise PublicAPIError("hidden_slide", "Hidden source slides cannot be approved for reuse.", 422)
        if request.category == "pricing_placeholder" and request.reuse_state == "approved":
            raise PublicAPIError(
                "pricing_out_of_scope",
                "Pricing slides cannot be approved for Create in this work order.",
                422,
            )
        compatibility_issue = _slide_compatibility_issue(slide, request)
        if request.reuse_state == "approved" and compatibility_issue is not None:
            raise PublicAPIError(
                compatibility_issue,
                "This slide needs standard editable PowerPoint placeholders or must be reused without changes.",
                422,
            )
        slide.category = request.category
        slide.reuse_state = request.reuse_state
        slide.modification_policy = request.modification_policy
        slide.customer_safe = request.customer_safe
        slide.required = request.required
        slide.exact_text_required = request.exact_text_required
        slide.approved_description = request.approved_description
        slide.placeholder_mappings_json = dict(request.placeholder_mappings)
        slide.reviewed_by_user_id = self.tenant.user_id
        slide.reviewed_at = datetime.now(UTC)
        version.compatibility_state = "needs_attention"
        version.compatibility_details_json = ["template_approval_required"]
        version.validated_at = None
        await self._commit("The template slide review could not be saved.")
        self._audit("create_template_slide_reviewed", slide_id=str(slide.id), reuse_state=slide.reuse_state)
        return await self.get_template(slide.template_id)

    async def approve_template(
        self,
        template_id: UUID,
        version_id: UUID,
        request: TemplateApprovalRequest,
    ) -> TemplateSummaryResponse:
        del request
        await self._require_entitled()
        self._require_admin()
        template = await self.repository.template(self.tenant.organisation_id, template_id)
        version = await self.repository.template_version(self.tenant.organisation_id, version_id)
        if template is None or version is None or version.template_id != template.id:
            raise PublicAPIError("template_not_found", "The template version was not found.", 404)
        if version.processing_state not in {"ready", "partial"}:
            raise PublicAPIError("template_not_reviewable", "Template processing has not completed.", 409)
        slides = await self.repository.slides(self.tenant.organisation_id, version.id)
        if not slides or any(slide.reuse_state == "pending" for slide in slides):
            raise PublicAPIError(
                "template_review_incomplete",
                "Review every slide before approving this template version.",
                409,
            )
        approved = [slide for slide in slides if slide.reuse_state == "approved"]
        if not approved:
            raise PublicAPIError("template_has_no_approved_slides", "Approve at least one customer-safe slide.", 409)
        if any(not slide.customer_safe for slide in approved):
            raise PublicAPIError("template_contains_unsafe_slide", "Only customer-safe slides can be approved.", 409)
        compatibility_issues = [issue for slide in approved if (issue := _stored_slide_compatibility_issue(slide))]
        title_slides = [slide for slide in approved if slide.category == "title"]
        if not title_slides:
            compatibility_issues.append("pptx_title_slide_required")
        elif not any(
            slide.modification_policy not in {"locked", "reuse_as_is"}
            and _stored_slide_compatibility_issue(slide) is None
            for slide in title_slides
        ):
            compatibility_issues.append("pptx_title_placeholders_required")
        if compatibility_issues:
            version.compatibility_state = "needs_attention"
            version.compatibility_details_json = cast(list[object], sorted(set(compatibility_issues)))
            version.validated_at = None
            await self._commit("The template compatibility result could not be saved.")
            raise PublicAPIError(
                "template_needs_attention",
                "This template needs standard title, audience and content placeholders before it can be approved.",
                409,
            )
        now = datetime.now(UTC)
        for slide in approved:
            text = _approved_slide_text(slide)[:12_000]
            if not text:
                text = slide.title
            item = await self.repository.content_item_for_slide(self.tenant.organisation_id, slide.id)
            if item is None:
                item = CreateApprovedContentItem(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    template_id=template.id,
                    template_version_id=version.id,
                    slide_id=slide.id,
                    content_type=slide.category,
                    title=slide.title,
                    approved_text=text,
                    status="approved",
                    modification_policy=slide.modification_policy,
                    customer_safe=True,
                    exact_text_required=slide.exact_text_required,
                    approved_by_user_id=self.tenant.user_id,
                    approved_at=now,
                )
                self.repository.add(item)
            else:
                item.status = "approved"
                item.title = slide.title
                item.approved_text = text
                item.modification_policy = slide.modification_policy
                item.customer_safe = True
                item.exact_text_required = slide.exact_text_required
                item.approved_by_user_id = self.tenant.user_id
                item.approved_at = now
                item.revoked_at = None
        version.approval_state = "approved"
        version.compatibility_state = "compatible"
        version.compatibility_details_json = []
        version.validation_profile_version = CREATE_PPTX_PROFILE_VERSION
        version.validated_at = now
        version.approved_by_user_id = self.tenant.user_id
        version.approved_at = now
        await self._commit("The template could not be approved.")
        self._audit(
            "create_template_approved",
            template_id=str(template.id),
            template_version_id=str(version.id),
            approved_slide_count=len(approved),
        )
        return await self.get_template(template.id)

    async def create_presentation(self, request: PresentationBriefRequest) -> PresentationResponse:
        await self._require_entitled()
        existing = await self.repository.presentation_by_key(
            self.tenant.organisation_id,
            self.tenant.user_id,
            request.idempotency_key,
        )
        if existing is not None:
            return await self._presentation_response(existing)
        company = await self.repository.company(self.tenant.organisation_id, request.account_id)
        if company is None:
            raise PublicAPIError("account_not_found", "Choose a canonical RevenueOS Account.", 404)
        opportunity: Opportunity | None = None
        if request.opportunity_id is not None:
            opportunity = await self.repository.opportunity(self.tenant.organisation_id, request.opportunity_id)
            if opportunity is None or opportunity.company_id != company.id:
                raise PublicAPIError(
                    "opportunity_account_mismatch",
                    "The Opportunity must belong to the selected Account.",
                    422,
                )
        template_version = await self.repository.template_version(
            self.tenant.organisation_id,
            request.template_version_id,
        )
        if template_version is None or template_version.approval_state != "approved":
            raise PublicAPIError("template_not_approved", "Choose an approved template version.", 422)
        if not _template_version_is_current(template_version):
            raise PublicAPIError(
                "template_revalidation_required",
                "This template needs review against the current PowerPoint compatibility profile.",
                409,
            )
        template = await self.repository.template(self.tenant.organisation_id, template_version.template_id)
        if template is None or template.state != "active":
            raise PublicAPIError("template_not_approved", "Choose an active approved template.", 422)
        audience = await self._validated_audience(request, company)
        business_case_selection = await self._validated_business_case_selection(
            request.business_case_version_id,
            company,
            opportunity,
        )
        context = await self._build_context(
            company,
            opportunity,
            business_case_selection,
            request.business_case_scenario,
        )
        plan = await self._build_plan(
            template_version,
            request.objective,
            context,
            request.focus_instruction,
        )
        fingerprint = _json_fingerprint(context)
        title = request.title or f"{company.name} — {_OBJECTIVE_LABELS[request.objective]}"
        presentation = CreatePresentation(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            account_id=company.id,
            opportunity_id=opportunity.id if opportunity else None,
            template_id=template.id,
            template_version_id=template_version.id,
            business_case_id=business_case_selection[0].id if business_case_selection else None,
            business_case_version_id=business_case_selection[1].id if business_case_selection else None,
            business_case_scenario=request.business_case_scenario,
            created_by_user_id=self.tenant.user_id,
            title=title,
            objective=request.objective,
            audience_json=audience,
            focus_instruction=request.focus_instruction,
            state="draft_plan",
            review_state="pending",
            plan_json=plan,
            source_context_fingerprint=fingerprint,
            idempotency_key=request.idempotency_key,
        )
        self.repository.add(presentation)
        await self._commit("The presentation plan could not be created.")
        self._audit(
            "create_presentation_planned",
            presentation_id=str(presentation.id),
            account_id=str(company.id),
            opportunity_id=str(opportunity.id) if opportunity else None,
            slide_count=sum(bool(item.get("included")) for item in plan),
        )
        if business_case_selection is not None:
            self._audit(
                "business_case_used_in_create",
                presentation_id=str(presentation.id),
                business_case_id=str(business_case_selection[0].id),
                business_case_version_id=str(business_case_selection[1].id),
                scenario=request.business_case_scenario,
            )
        return await self._presentation_response(presentation)

    async def list_presentations(self) -> PresentationListResponse:
        await self._require_entitled()
        items = [
            await self._presentation_response(item)
            for item in await self.repository.presentations(self.tenant.organisation_id)
        ]
        return PresentationListResponse(
            items=items,
            can_create=True,
            max_presentations_per_user_per_day=(self.settings.private_beta_max_create_presentations_per_user_per_day),
            max_presentations_per_organisation_per_day=(
                self.settings.private_beta_max_create_presentations_per_organisation_per_day
            ),
        )

    async def get_presentation(self, presentation_id: UUID) -> PresentationResponse:
        await self._require_entitled()
        presentation = await self.repository.presentation(self.tenant.organisation_id, presentation_id)
        if presentation is None:
            raise PublicAPIError("presentation_not_found", "The presentation was not found.", 404)
        return await self._presentation_response(presentation)

    async def update_plan(
        self,
        presentation_id: UUID,
        request: PresentationPlanUpdateRequest,
    ) -> PresentationResponse:
        await self._require_entitled()
        presentation = await self._draft_presentation(presentation_id)
        existing: dict[UUID, dict[str, object]] = {
            UUID(str(item["id"])): {str(key): value for key, value in item.items()}
            for item in presentation.plan_json
            if isinstance(item, dict) and item.get("id")
        }
        supplied = {item.id for item in request.items}
        if supplied != set(existing):
            raise PublicAPIError("invalid_plan", "The plan no longer matches this presentation.", 409)
        for item in request.items:
            current = existing[item.id]
            if bool(current.get("required")) and not item.included:
                raise PublicAPIError("required_slide", "Required template slides cannot be removed.", 422)
            current["included"] = item.included
            current["order"] = item.order
        for slide_id in request.add_slide_ids:
            slide = await self.repository.slide(self.tenant.organisation_id, slide_id)
            if (
                slide is None
                or slide.template_version_id != presentation.template_version_id
                or slide.reuse_state != "approved"
                or not slide.customer_safe
            ):
                raise PublicAPIError("invalid_plan_slide", "Only approved slides from this template can be added.", 422)
            if any(str(item.get("templateSlideId")) == str(slide.id) for item in existing.values()):
                continue
            new_item = self._plan_item(slide, len(existing) + 1, ["approved_company_content"])
            existing[UUID(str(new_item["id"]))] = new_item
        included = [item for item in existing.values() if bool(item.get("included"))]
        if len(included) > self.settings.private_beta_max_create_slides:
            raise PublicAPIError("create_slide_limit", "A presentation can contain at most 30 slides.", 422)
        presentation.plan_json = cast(
            list[object],
            sorted(existing.values(), key=lambda item: cast(int, item.get("order", 999))),
        )
        presentation.review_state = "pending"
        await self._commit("The presentation plan could not be saved.")
        self._audit("create_presentation_plan_updated", presentation_id=str(presentation.id), slide_count=len(included))
        return await self._presentation_response(presentation)

    async def generate(
        self,
        presentation_id: UUID,
        request: PresentationGenerateRequest,
    ) -> PresentationResponse:
        await self._require_entitled()
        presentation = await self.repository.presentation(self.tenant.organisation_id, presentation_id)
        if presentation is None:
            raise PublicAPIError("presentation_not_found", "The presentation was not found.", 404)
        current = await self.repository.latest_presentation_version(self.tenant.organisation_id, presentation.id)
        if current is not None and current.idempotency_key == request.idempotency_key:
            return await self._presentation_response(presentation)
        if presentation.state == "generating":
            raise PublicAPIError("presentation_generation_in_progress", "Presentation generation is in progress.", 409)
        if current is not None and not request.explicit_regenerate:
            raise PublicAPIError(
                "explicit_regeneration_required",
                "Confirm regeneration to create a new immutable version.",
                409,
            )
        included = [item for item in presentation.plan_json if isinstance(item, dict) and item.get("included")]
        if not included:
            raise PublicAPIError("empty_plan", "Include at least one slide before generating.", 422)
        template_version = await self.repository.template_version(
            self.tenant.organisation_id,
            presentation.template_version_id,
        )
        if template_version is None or not _template_version_is_current(template_version):
            raise PublicAPIError(
                "template_revalidation_required",
                "The source template must be reviewed against the current PowerPoint compatibility profile.",
                409,
            )
        company = await self.repository.company(self.tenant.organisation_id, presentation.account_id)
        opportunity = (
            await self.repository.opportunity(self.tenant.organisation_id, presentation.opportunity_id)
            if presentation.opportunity_id
            else None
        )
        if company is None:
            raise PublicAPIError("account_not_found", "The linked Account is no longer available.", 409)
        business_case_selection = await self._validated_business_case_selection(
            presentation.business_case_version_id,
            company,
            opportunity,
        )
        context = await self._build_context(
            company,
            opportunity,
            business_case_selection,
            cast(Literal["base", "all"] | None, presentation.business_case_scenario),
        )
        fingerprint = _json_fingerprint(context)
        await self._reserve_generation_quota()
        version = CreatePresentationVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            presentation_id=presentation.id,
            template_id=presentation.template_id,
            template_version_id=presentation.template_version_id,
            version=(current.version + 1 if current else 1),
            created_by_user_id=self.tenant.user_id,
            state="generating",
            review_state="pending",
            plan_snapshot_json=[dict(item) for item in included],
            audience_snapshot_json=list(presentation.audience_json),
            source_context_json=context,
            source_context_fingerprint=fingerprint,
            generated_content_json=[],
            claim_manifest_json=[],
            warning_codes_json=[],
            renderer_version="deterministic_pptx_v1",
            generation_schema_version=1,
            idempotency_key=request.idempotency_key,
            processing_attempts=0,
            storage_status="pending",
        )
        self.repository.add(version)
        presentation.state = "generating"
        presentation.review_state = "pending"
        presentation.source_context_fingerprint = fingerprint
        await self._commit("The presentation could not be queued for generation.")
        self._audit(
            "create_presentation_generation_queued",
            presentation_id=str(presentation.id),
            version_id=str(version.id),
            version=version.version,
        )
        return await self._presentation_response(presentation)

    async def edit_slide(
        self,
        presentation_id: UUID,
        plan_item_id: UUID,
        request: PresentationSlideEditRequest,
    ) -> PresentationResponse:
        await self._require_entitled()
        presentation, version = await self._reviewable_version(presentation_id)
        slides = [dict(item) for item in version.generated_content_json if isinstance(item, dict)]
        slide = next((item for item in slides if str(item.get("planItemId")) == str(plan_item_id)), None)
        if slide is None:
            raise PublicAPIError("generated_slide_not_found", "The generated slide was not found.", 404)
        source_slide = await self.repository.slide(
            self.tenant.organisation_id,
            UUID(str(slide.get("templateSlideId"))),
        )
        if source_slide is None:
            raise PublicAPIError("source_slide_not_found", "The approved source slide is no longer available.", 409)
        if slide.get("modificationPolicy") in {"locked", "reuse_as_is"}:
            raise PublicAPIError("slide_locked", "This approved slide must remain unchanged.", 409)
        roles = _effective_placeholder_roles(source_slide)
        if request.body_blocks and not roles.intersection(_CONTENT_PLACEHOLDER_ROLES):
            raise PublicAPIError(
                "slide_body_not_editable",
                "This slide does not have an editable content placeholder.",
                409,
            )
        combined = "\n".join((request.title, *request.body_blocks))
        if _INTERNAL_COPY.search(combined):
            raise PublicAPIError(
                "internal_only_content",
                "That edit contains internal-only sales language and cannot appear in customer content.",
                422,
            )
        await self._reserve_generation_quota()
        slide["title"] = request.title
        slide["bodyBlocks"] = request.body_blocks
        slide["reviewState"] = "needs_review"
        slide["warningCodes"] = ["user_edited_content"]
        claims = [
            dict(item)
            for item in version.claim_manifest_json
            if isinstance(item, dict) and str(item.get("planItemId")) != str(plan_item_id)
        ]
        source_title = presentation.title if source_slide.category == "title" else source_slide.title
        if request.title != source_title:
            claims.append(
                {
                    "id": str(uuid.uuid4()),
                    "planItemId": str(plan_item_id),
                    "blockIndex": 0,
                    "claim": request.title,
                    "contentType": "user_edit_title",
                    "origin": "user_edited",
                    "supportState": "user_responsible",
                    "customerSafeClassification": "requires_review",
                    "sourceIds": [],
                    "sourceLabels": ["Edited by you"],
                    "freshness": "current",
                    "paraphraseAllowed": False,
                    "exactTextRequired": False,
                    "reviewState": "pending",
                }
            )
        claims.extend(
            {
                "id": str(uuid.uuid4()),
                "planItemId": str(plan_item_id),
                "blockIndex": block_index,
                "claim": block,
                "contentType": "user_edit",
                "origin": "user_edited",
                "supportState": "user_responsible",
                "customerSafeClassification": "requires_review",
                "sourceIds": [],
                "sourceLabels": ["Edited by you"],
                "freshness": "current",
                "paraphraseAllowed": False,
                "exactTextRequired": False,
                "reviewState": "pending",
            }
            for block_index, block in enumerate(request.body_blocks)
        )
        version.generated_content_json = cast(list[object], slides)
        version.claim_manifest_json = cast(list[object], claims)
        self._invalidate_and_queue(presentation, version)
        await self._commit("The slide edit could not be saved.")
        self._audit(
            "create_presentation_slide_edited",
            presentation_id=str(presentation.id),
            version_id=str(version.id),
            plan_item_id=str(plan_item_id),
        )
        return await self._presentation_response(presentation)

    async def review_claims(
        self,
        presentation_id: UUID,
        request: PresentationReviewRequest,
    ) -> PresentationResponse:
        await self._require_entitled()
        presentation, version = await self._reviewable_version(presentation_id)
        claims = [dict(item) for item in version.claim_manifest_json if isinstance(item, dict)]
        claim_map = {str(item.get("id")): item for item in claims}
        removed = False
        slides = [dict(item) for item in version.generated_content_json if isinstance(item, dict)]
        for decision in request.decisions:
            claim = claim_map.get(str(decision.claim_id))
            if claim is None or claim.get("reviewState") not in {"pending", "kept"}:
                raise PublicAPIError("claim_not_reviewable", "A selected claim is no longer reviewable.", 409)
            claim["reviewState"] = "kept" if decision.action == "keep" else "removed"
            if decision.action == "remove":
                removed = True
                slide = next(
                    (item for item in slides if str(item.get("planItemId")) == str(claim.get("planItemId"))),
                    None,
                )
                if slide is not None:
                    if claim.get("contentType") == "user_edit_title":
                        source_slide = await self.repository.slide(
                            self.tenant.organisation_id,
                            UUID(str(slide.get("templateSlideId"))),
                        )
                        if source_slide is None:
                            raise PublicAPIError(
                                "source_slide_not_found",
                                "The approved source slide is no longer available.",
                                409,
                            )
                        slide["title"] = presentation.title if source_slide.category == "title" else source_slide.title
                    else:
                        blocks = [str(value) for value in cast(list[object], slide.get("bodyBlocks", []))]
                        block_index = cast(int, claim.get("blockIndex", -1))
                        claim_text = str(claim.get("claim", ""))
                        if 0 <= block_index < len(blocks) and blocks[block_index] == claim_text:
                            blocks.pop(block_index)
                        elif claim_text in blocks:
                            blocks.remove(claim_text)
                        slide["bodyBlocks"] = blocks
        version.claim_manifest_json = cast(list[object], claims)
        version.generated_content_json = cast(list[object], slides)
        version.review_state = "pending"
        version.approved_by_user_id = None
        version.approved_at = None
        presentation.review_state = "pending"
        if removed:
            await self._reserve_generation_quota()
            self._invalidate_and_queue(presentation, version)
        await self._commit("The claim review could not be saved.")
        self._audit(
            "create_presentation_claims_reviewed",
            presentation_id=str(presentation.id),
            version_id=str(version.id),
            decision_count=len(request.decisions),
        )
        return await self._presentation_response(presentation)

    async def approve_presentation(
        self,
        presentation_id: UUID,
        request: PresentationApprovalRequest,
    ) -> PresentationResponse:
        del request
        await self._require_entitled()
        presentation, version = await self._reviewable_version(presentation_id)
        if version.state != "needs_review" or version.storage_status != "available":
            raise PublicAPIError("presentation_not_ready", "Wait for the presentation to finish rendering.", 409)
        if version.validation_profile_version != CREATE_PPTX_PROFILE_VERSION or version.validated_at is None:
            raise PublicAPIError(
                "generated_validation_failed",
                "The presentation could not be safely finalised. Generate a new version.",
                409,
            )
        claims = [item for item in version.claim_manifest_json if isinstance(item, dict)]
        if any(item.get("reviewState") == "pending" for item in claims):
            raise PublicAPIError(
                "claim_review_incomplete",
                "Review every reported, inferred or edited claim before approval.",
                409,
            )
        template_version = await self.repository.template_version(
            self.tenant.organisation_id,
            presentation.template_version_id,
        )
        if template_version is None or not _template_version_is_current(template_version):
            raise PublicAPIError("template_approval_changed", "The source template is no longer approved.", 409)
        source_slides = {
            slide.id: slide
            for slide in await self.repository.slides(self.tenant.organisation_id, presentation.template_version_id)
        }
        for item in version.plan_snapshot_json:
            if not isinstance(item, dict):
                raise PublicAPIError("invalid_plan_snapshot", "The source plan could not be validated.", 409)
            slide = source_slides.get(UUID(str(item.get("templateSlideId"))))
            if slide is None or slide.reuse_state != "approved" or not slide.customer_safe:
                raise PublicAPIError("source_approval_changed", "Approved source content has changed.", 409)
        await self._revalidate_claim_sources(version)
        now = datetime.now(UTC)
        version.state = "ready"
        version.review_state = "approved"
        version.approved_by_user_id = self.tenant.user_id
        version.approved_at = now
        presentation.state = "ready"
        presentation.review_state = "approved"
        await self._commit("The presentation could not be approved.")
        self._audit(
            "create_presentation_approved",
            presentation_id=str(presentation.id),
            version_id=str(version.id),
        )
        return await self._presentation_response(presentation)

    async def download_grant(self, presentation_id: UUID) -> PresentationDownloadGrantResponse:
        await self._require_entitled()
        presentation = await self.repository.presentation(self.tenant.organisation_id, presentation_id)
        if presentation is None:
            raise PublicAPIError("presentation_not_found", "The presentation was not found.", 404)
        version = await self.repository.latest_presentation_version(self.tenant.organisation_id, presentation.id)
        template_version = await self.repository.template_version(
            self.tenant.organisation_id,
            presentation.template_version_id,
        )
        if (
            version is None
            or template_version is None
            or not _template_version_is_current(template_version)
            or version.state != "ready"
            or version.review_state != "approved"
            or version.storage_status != "available"
            or version.pptx_storage_key is None
            or version.validation_profile_version != CREATE_PPTX_PROFILE_VERSION
            or version.validated_at is None
        ):
            raise PublicAPIError("presentation_not_approved", "Approve the current version before download.", 409)
        await self._revalidate_claim_sources(version)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.visual_signed_url_ttl_seconds)
        token = secrets.token_urlsafe(32)
        self.repository.add(
            CreateDownloadGrant(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                presentation_version_id=version.id,
                user_id=self.tenant.user_id,
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                approval_fingerprint=_approval_fingerprint(version),
                expires_at=expires_at,
            )
        )
        await self._commit("The PowerPoint download could not be prepared.")
        return PresentationDownloadGrantResponse(
            download_url=f"/api/v1/create/presentations/{presentation.id}/download",
            grant_token=token,
            expires_at=expires_at,
            file_name=f"{_safe_file_name(presentation.title)}.pptx",
        )

    async def download(self, presentation_id: UUID, token: str) -> tuple[bytes, str]:
        await self._require_entitled()
        now = datetime.now(UTC)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        grant = await self.repository.download_grant_by_hash(
            self.tenant.organisation_id,
            self.tenant.user_id,
            token_hash,
        )
        presentation = await self.repository.presentation(self.tenant.organisation_id, presentation_id)
        if presentation is None:
            raise PublicAPIError("presentation_not_found", "The presentation was not found.", 404)
        version = await self.repository.latest_presentation_version(self.tenant.organisation_id, presentation.id)
        template_version = await self.repository.template_version(
            self.tenant.organisation_id,
            presentation.template_version_id,
        )
        if (
            grant is None
            or version is None
            or template_version is None
            or not _template_version_is_current(template_version)
            or grant.presentation_version_id != version.id
            or version.state != "ready"
            or version.review_state != "approved"
            or version.storage_status != "available"
            or version.pptx_storage_key is None
            or version.validation_profile_version != CREATE_PPTX_PROFILE_VERSION
            or version.validated_at is None
            or _as_utc(grant.expires_at) <= now
            or grant.consumed_at is not None
            or grant.revoked_at is not None
            or grant.approval_fingerprint != _approval_fingerprint(version)
        ):
            raise PublicAPIError("invalid_download_grant", "The download link is invalid or has expired.", 403)
        await self._revalidate_claim_sources(version)
        try:
            content = await self.storage.read(version.pptx_storage_key)
        except VisualObjectMissingError as exc:
            raise PublicAPIError(
                "presentation_file_unavailable",
                "This presentation file is unavailable. Generate a new version or contact support.",
                409,
            ) from exc
        except VisualStorageError as exc:
            raise PublicAPIError(
                "create_storage_unavailable", "The presentation is temporarily unavailable.", 503
            ) from exc
        if version.checksum_sha256 is None or not secrets.compare_digest(
            hashlib.sha256(content).hexdigest(),
            version.checksum_sha256,
        ):
            raise PublicAPIError(
                "presentation_file_integrity_failed",
                "This presentation file is unavailable. Generate a new version or contact support.",
                409,
            )
        consumed = await self.repository.consume_download_grant(
            self.tenant.organisation_id,
            self.tenant.user_id,
            grant.id,
            version.id,
            now,
        )
        if not consumed:
            await self.session.rollback()
            raise PublicAPIError("invalid_download_grant", "The download link is invalid or has expired.", 403)
        await self.session.commit()
        self._audit(
            "create_presentation_downloaded",
            presentation_id=str(presentation.id),
            version_id=str(version.id),
            result="success",
        )
        return content, f"{_safe_file_name(presentation.title)}.pptx"

    async def _build_context(
        self,
        company: Company,
        opportunity: Opportunity | None,
        business_case_selection: tuple[CreateBusinessCase, CreateBusinessCaseVersion] | None = None,
        business_case_scenario: Literal["base", "all"] | None = None,
    ) -> dict[str, object]:
        items: list[dict[str, object]] = [
            {
                "id": str(company.id),
                "category": "account_name",
                "statement": company.name,
                "origin": "system_metadata",
                "supportState": "strong",
                "customerSafeClassification": "customer_safe",
                "sourceLabel": "RevenueOS Account",
                "freshness": "current",
                "paraphraseAllowed": False,
                "exactTextRequired": True,
            }
        ]
        if opportunity is not None:
            items.append(
                {
                    "id": str(opportunity.id),
                    "category": "opportunity_name",
                    "statement": opportunity.name,
                    "origin": "system_metadata",
                    "supportState": "strong",
                    "customerSafeClassification": "customer_safe",
                    "sourceLabel": "RevenueOS Opportunity",
                    "freshness": "current",
                    "paraphraseAllowed": False,
                    "exactTextRequired": True,
                }
            )
        seen: set[str] = set()
        snapshots = await self.repository.revenue_brain_snapshots(
            self.tenant.organisation_id,
            company.id,
            opportunity.id if opportunity else None,
        )
        for snapshot in snapshots:
            raw_items = snapshot.content_json.get("items")
            if not isinstance(raw_items, list):
                continue
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                statement = raw.get("statement")
                category = raw.get("category")
                evidence_id = raw.get("evidenceId")
                if (
                    not isinstance(statement, str)
                    or not isinstance(category, str)
                    or category not in _SAFE_CUSTOMER_CATEGORIES
                    or not evidence_id
                    or statement in seen
                    or _INTERNAL_COPY.search(statement)
                ):
                    continue
                origin_class = str(raw.get("originClass", "seller_prepared"))
                origin = "customer_direct" if origin_class == "customer_direct" else "salesperson_reported"
                support = (
                    "strong" if origin == "customer_direct" and raw.get("supportClass") == "direct" else "reported"
                )
                items.append(
                    {
                        "id": str(evidence_id),
                        "category": category,
                        "statement": statement[:800],
                        "origin": origin,
                        "supportState": support,
                        "customerSafeClassification": (
                            "customer_safe" if origin == "customer_direct" else "requires_review"
                        ),
                        "sourceLabel": str(raw.get("sourceLabel", "Reviewed evidence"))[:200],
                        "freshness": "current",
                        "paraphraseAllowed": True,
                        "exactTextRequired": False,
                    }
                )
                seen.add(statement)
                if len(items) >= 14:
                    break
            if len(items) >= 14:
                break
        for observation, source in await self.repository.public_observations(
            self.tenant.organisation_id,
            company.id,
        ):
            if (
                observation.category not in _SAFE_PUBLIC_CATEGORIES
                or observation.trust_state == "unknown"
                or observation.statement in seen
                or _INTERNAL_COPY.search(observation.statement)
            ):
                continue
            inferred = observation.trust_state == "inferred"
            items.append(
                {
                    "id": str(observation.id),
                    "category": observation.category,
                    "statement": observation.statement,
                    "origin": "prospect_public",
                    "supportState": "inferred" if inferred else "strong",
                    "customerSafeClassification": "requires_review" if inferred else "customer_safe",
                    "sourceLabel": source.publisher if source is not None else "Public company research",
                    "freshness": "unknown" if observation.freshness == "time_sensitive" else "current",
                    "paraphraseAllowed": True,
                    "exactTextRequired": False,
                }
            )
            seen.add(observation.statement)
            if len(items) >= 20:
                break
        if business_case_selection is not None:
            business_case, business_case_version = business_case_selection
            try:
                inputs = [CalculationInputResponse.model_validate(item) for item in business_case_version.inputs_json]
                scenarios = [
                    ScenarioCalculationResponse.model_validate(item) for item in business_case_version.scenarios_json
                ]
            except ValidationError as exc:
                raise PublicAPIError(
                    "business_case_snapshot_invalid",
                    "The approved Business Case snapshot could not be used.",
                    409,
                ) from exc
            selected_names = {"base"} if business_case_scenario != "all" else {"base", "conservative", "upside"}
            selected_scenarios = [item for item in scenarios if item.name in selected_names]
            selected_scenarios.sort(key=lambda item: ("conservative", "base", "upside").index(item.name))
            for scenario in selected_scenarios:
                outputs = [item for item in scenario.outputs if item.customer_facing]
                outputs.sort(key=lambda item: (not item.highlight, item.label.casefold()))
                for output in outputs[:6]:
                    items.append(
                        {
                            "id": str(business_case_version.id),
                            "category": "business_case_output",
                            "statement": _business_case_output_statement(
                                output,
                                scenario.name,
                                business_case.currency,
                            ),
                            "origin": "approved_business_case",
                            "supportState": "approved",
                            "customerSafeClassification": "customer_safe",
                            "sourceLabel": (
                                f"Approved Business Case v{business_case_version.version} — {business_case.title}"
                            ),
                            "freshness": "current",
                            "paraphraseAllowed": False,
                            "exactTextRequired": True,
                            "scenario": scenario.name,
                        }
                    )
            for input_item in [item for item in inputs if item.material and item.customer_facing][:4]:
                items.append(
                    {
                        "id": str(business_case_version.id),
                        "category": "business_case_assumption",
                        "statement": _business_case_assumption_statement(
                            input_item,
                            business_case.currency,
                        ),
                        "origin": "approved_business_case",
                        "supportState": "approved",
                        "customerSafeClassification": "customer_safe",
                        "sourceLabel": (
                            f"Approved Business Case v{business_case_version.version} — {business_case.title}"
                        ),
                        "freshness": "current",
                        "paraphraseAllowed": False,
                        "exactTextRequired": True,
                        "scenario": "base",
                    }
                )
            model_version = await self.repository.value_model_version(
                self.tenant.organisation_id,
                business_case_version.model_version_id,
            )
            customer_disclaimer = (
                model_version.definition_json.get("customerDisclaimer") if model_version is not None else None
            )
            if isinstance(customer_disclaimer, str) and customer_disclaimer.strip():
                items.append(
                    {
                        "id": str(business_case_version.id),
                        "category": "business_case_disclaimer",
                        "statement": customer_disclaimer,
                        "origin": "approved_business_case",
                        "supportState": "approved",
                        "customerSafeClassification": "customer_safe",
                        "sourceLabel": (
                            f"Approved Business Case v{business_case_version.version} — {business_case.title}"
                        ),
                        "freshness": "current",
                        "paraphraseAllowed": False,
                        "exactTextRequired": True,
                        "scenario": "base",
                    }
                )
        return {
            "schemaVersion": 1,
            "policy": "customer_safe_create_context_v1",
            "accountId": str(company.id),
            "opportunityId": str(opportunity.id) if opportunity else None,
            "items": items,
            "excludedClasses": [
                "raw_transcripts",
                "private_notes",
                "risk",
                "forecast",
                "probability",
                "coaching",
                "contactability",
                "suppression",
                "opportunity_financials",
            ],
        }

    async def _build_plan(
        self,
        template_version: CreateTemplateVersion,
        objective: str,
        context: dict[str, object],
        focus_instruction: str | None,
    ) -> list[dict[str, object]]:
        slides = [
            slide
            for slide in await self.repository.slides(self.tenant.organisation_id, template_version.id)
            if slide.reuse_state == "approved" and slide.customer_safe
        ]
        preferred = list(_OBJECTIVE_CATEGORIES[objective])
        focus = (focus_instruction or "").casefold()
        focus_categories: list[str] = []
        for keywords, category in (
            (("technical", "architecture", "security", "integration"), "architecture"),
            (("implementation", "delivery", "rollout"), "process"),
            (("proof", "evidence", "outcome"), "proof_point"),
            (("customer story", "case study"), "case_study"),
            (("next step", "action"), "next_steps"),
        ):
            if any(keyword in focus for keyword in keywords) and category not in focus_categories:
                focus_categories.append(category)
        preferred = [*focus_categories, *(item for item in preferred if item not in focus_categories)]
        ranked = sorted(
            slides,
            key=lambda slide: (
                not slide.required,
                preferred.index(slide.category) if slide.category in preferred else len(preferred),
                slide.slide_number,
            ),
        )
        origins = {
            str(item.get("origin")) for item in cast(list[object], context.get("items", [])) if isinstance(item, dict)
        }
        dynamic_origins = [
            value
            for value in (
                "approved_business_case",
                "customer_direct",
                "salesperson_reported",
                "prospect_public",
            )
            if value in origins
        ]
        plan: list[dict[str, object]] = []
        for slide in ranked[: min(12, self.settings.private_beta_max_create_slides)]:
            source_classes = ["approved_company_content"]
            if slide.category in {"title", "agenda", "problem", "solution", "next_steps"}:
                source_classes.extend(dynamic_origins)
            plan.append(self._plan_item(slide, len(plan) + 1, source_classes))
        return plan

    async def _revalidate_claim_sources(self, version: CreatePresentationVersion) -> None:
        grouped: dict[str, set[UUID]] = {
            "approved_company_content": set(),
            "approved_business_case": set(),
            "customer_evidence": set(),
            "prospect_public": set(),
        }
        for claim in version.claim_manifest_json:
            if not isinstance(claim, dict) or claim.get("reviewState") == "removed":
                continue
            origin = str(claim.get("origin"))
            if origin == "approved_company_content":
                group = "approved_company_content"
            elif origin == "approved_business_case":
                group = "approved_business_case"
            elif origin in {"customer_direct", "salesperson_reported", "validated_intelligence"}:
                group = "customer_evidence"
            elif origin == "prospect_public":
                group = "prospect_public"
            else:
                continue
            raw_ids = claim.get("sourceIds")
            if not isinstance(raw_ids, list):
                raise PublicAPIError("source_manifest_invalid", "A claim source manifest is invalid.", 409)
            try:
                grouped[group].update(UUID(str(value)) for value in raw_ids)
            except ValueError as exc:
                raise PublicAPIError("source_manifest_invalid", "A claim source manifest is invalid.", 409) from exc
        for group, source_ids in grouped.items():
            existing = await self.repository.existing_source_ids(
                self.tenant.organisation_id,
                group,
                source_ids,
            )
            if existing != source_ids:
                raise PublicAPIError(
                    "claim_source_changed",
                    "A claim source is no longer available; regenerate before approval.",
                    409,
                )

    @staticmethod
    def _plan_item(slide: CreateTemplateSlide, order: int, sources: list[str]) -> dict[str, object]:
        return PresentationPlanItemResponse.model_validate(
            {
                "id": uuid.uuid4(),
                "templateSlideId": slide.id,
                "order": order,
                "title": slide.title,
                "category": slide.category,
                "required": slide.required,
                "exactTextRequired": slide.exact_text_required,
                "modificationPolicy": slide.modification_policy,
                "sourceClasses": sources,
                "included": True,
            }
        ).model_dump(mode="json", by_alias=True)

    async def _validated_audience(self, request: PresentationBriefRequest, company: Company) -> list[object]:
        contact_ids = [item.contact_id for item in request.audience if item.contact_id is not None]
        contacts = await self.repository.contacts(self.tenant.organisation_id, contact_ids)
        contacts_by_id = {item.id: item for item in contacts}
        if len(contacts_by_id) != len(set(contact_ids)) or any(
            contact.company_id != company.id for contact in contacts
        ):
            raise PublicAPIError("audience_account_mismatch", "Audience Contacts must belong to the Account.", 422)
        audience: list[object] = []
        for item in request.audience:
            data = item.model_dump(mode="json", by_alias=True)
            if item.contact_id is not None:
                contact = contacts_by_id[item.contact_id]
                data["name"] = f"{contact.first_name} {contact.last_name}"
                data["role"] = item.role or contact.job_title
            audience.append(data)
        return audience

    async def _reserve_generation_quota(self) -> None:
        today = datetime.now(UTC).date()
        organisation_reserved = await self.repository.reserve_generation_counter(
            self.tenant.organisation_id,
            today,
            "organisation",
            self.settings.private_beta_max_create_presentations_per_organisation_per_day,
        )
        if not organisation_reserved:
            raise PublicAPIError(
                "create_organisation_daily_limit",
                "The organisation daily presentation limit has been reached.",
                429,
            )
        user_reserved = await self.repository.reserve_generation_counter(
            self.tenant.organisation_id,
            today,
            f"user:{self.tenant.user_id}",
            self.settings.private_beta_max_create_presentations_per_user_per_day,
        )
        if not user_reserved:
            raise PublicAPIError("create_user_daily_limit", "Your daily presentation limit has been reached.", 429)

    async def _draft_presentation(self, presentation_id: UUID) -> CreatePresentation:
        presentation = await self.repository.presentation(self.tenant.organisation_id, presentation_id)
        if presentation is None:
            raise PublicAPIError("presentation_not_found", "The presentation was not found.", 404)
        if presentation.state != "draft_plan":
            raise PublicAPIError(
                "plan_immutable", "Generated plans are immutable; regenerate to make a new version.", 409
            )
        return presentation

    async def _reviewable_version(
        self,
        presentation_id: UUID,
    ) -> tuple[CreatePresentation, CreatePresentationVersion]:
        presentation = await self.repository.presentation(self.tenant.organisation_id, presentation_id)
        if presentation is None:
            raise PublicAPIError("presentation_not_found", "The presentation was not found.", 404)
        version = await self.repository.latest_presentation_version(self.tenant.organisation_id, presentation.id)
        if version is None or version.state not in {"needs_review", "ready"}:
            raise PublicAPIError("presentation_not_reviewable", "The presentation is not ready for review.", 409)
        if version.review_state == "approved":
            raise PublicAPIError(
                "presentation_version_immutable",
                "An approved presentation version cannot be changed.",
                409,
            )
        return presentation, version

    def _invalidate_and_queue(
        self,
        presentation: CreatePresentation,
        version: CreatePresentationVersion,
    ) -> None:
        version.state = "generating"
        version.review_state = "pending"
        version.approved_by_user_id = None
        version.approved_at = None
        version.storage_status = "pending"
        version.validation_profile_version = None
        version.validated_at = None
        version.processing_attempts = 0
        version.worker_id = None
        version.lease_expires_at = None
        presentation.state = "generating"
        presentation.review_state = "pending"

    async def _presentation_response(self, presentation: CreatePresentation) -> PresentationResponse:
        # Database-managed update timestamps are expired after UPDATE even when
        # expire_on_commit is disabled; refresh before building the API model.
        await self.session.refresh(presentation)
        company = await self.repository.company(self.tenant.organisation_id, presentation.account_id)
        opportunity = (
            await self.repository.opportunity(self.tenant.organisation_id, presentation.opportunity_id)
            if presentation.opportunity_id
            else None
        )
        template = await self.repository.template(self.tenant.organisation_id, presentation.template_id)
        template_version = await self.repository.template_version(
            self.tenant.organisation_id,
            presentation.template_version_id,
        )
        if company is None or template is None or template_version is None:
            raise PublicAPIError("presentation_reference_missing", "A presentation reference is unavailable.", 409)
        current = await self.repository.latest_presentation_version(self.tenant.organisation_id, presentation.id)
        return PresentationResponse.model_validate(
            {
                "id": presentation.id,
                "title": presentation.title,
                "accountId": presentation.account_id,
                "accountName": company.name,
                "opportunityId": presentation.opportunity_id,
                "opportunityName": opportunity.name if opportunity else None,
                "objective": presentation.objective,
                "audience": presentation.audience_json,
                "focusInstruction": presentation.focus_instruction,
                "templateVersionId": presentation.template_version_id,
                "templateName": template.name,
                "templateVersion": template_version.version,
                "businessCaseId": presentation.business_case_id,
                "businessCaseVersionId": presentation.business_case_version_id,
                "businessCaseScenario": presentation.business_case_scenario,
                "state": presentation.state,
                "reviewState": presentation.review_state,
                "plan": presentation.plan_json,
                "currentVersion": self._presentation_version_response(current) if current else None,
                "createdByUserId": presentation.created_by_user_id,
                "createdAt": presentation.created_at,
                "updatedAt": presentation.updated_at,
            }
        )

    @staticmethod
    def _presentation_version_response(version: CreatePresentationVersion) -> PresentationVersionResponse:
        return PresentationVersionResponse.model_validate(
            {
                "id": version.id,
                "version": version.version,
                "state": version.state,
                "reviewState": version.review_state,
                "slides": version.generated_content_json,
                "claims": version.claim_manifest_json,
                "warningCodes": version.warning_codes_json,
                "safeFailureCode": version.safe_failure_code,
                "validationProfileVersion": version.validation_profile_version,
                "validatedAt": version.validated_at,
                "generatedAt": version.generated_at,
                "approvedAt": version.approved_at,
                "downloadAvailable": (
                    version.state == "ready"
                    and version.review_state == "approved"
                    and version.storage_status == "available"
                    and version.validation_profile_version == CREATE_PPTX_PROFILE_VERSION
                    and version.validated_at is not None
                ),
                "createdAt": version.created_at,
            }
        )

    async def _template_response(self, template: CreateTemplate) -> TemplateSummaryResponse:
        version = await self.repository.latest_template_version(self.tenant.organisation_id, template.id)
        if version is None:
            raise PublicAPIError("template_version_not_found", "The template version was not found.", 404)
        return TemplateSummaryResponse.model_validate(
            {
                "id": template.id,
                "name": template.name,
                "state": template.state,
                "latestVersion": await self._template_version_response(version),
                "createdAt": template.created_at,
                "updatedAt": template.updated_at,
            }
        )

    async def _template_version_response(self, version: CreateTemplateVersion) -> TemplateVersionResponse:
        slides = await self.repository.slides(self.tenant.organisation_id, version.id)
        content = await self.repository.content_items(self.tenant.organisation_id, version.id)
        return TemplateVersionResponse.model_validate(
            {
                "id": version.id,
                "templateId": version.template_id,
                "version": version.version,
                "processingState": version.processing_state,
                "approvalState": version.approval_state,
                "fileName": version.display_filename,
                "byteSize": version.byte_size,
                "checksumSha256": version.checksum_sha256,
                "slideCount": version.slide_count,
                "approvedSlideCount": sum(item.reuse_state == "approved" for item in slides),
                "requiredSlideCount": sum(item.required for item in slides),
                "widthEmu": version.width_emu,
                "heightEmu": version.height_emu,
                "warningCodes": version.warning_codes_json,
                "safeFailureCode": version.safe_failure_code,
                "compatibilityState": version.compatibility_state,
                "compatibilityDetails": [str(item) for item in version.compatibility_details_json],
                "validationProfileVersion": version.validation_profile_version,
                "validatedAt": version.validated_at,
                "authorityAttestationVersion": version.authority_attestation_version,
                "authorityAttestedAt": version.authority_attested_at,
                "processedAt": version.processed_at,
                "approvedAt": version.approved_at,
                "slides": [self._slide_response(item) for item in slides],
                "contentItems": [self._content_response(item) for item in content],
                "createdAt": version.created_at,
            }
        )

    @staticmethod
    def _slide_response(slide: CreateTemplateSlide) -> TemplateSlideResponse:
        blocks: list[TemplateTextBlockResponse] = []
        mappings = {str(key): str(value) for key, value in slide.placeholder_mappings_json.items()}
        for raw in slide.text_blocks_json:
            if not isinstance(raw, dict):
                continue
            data = dict(raw)
            shape_id = data.get("shapeId")
            if isinstance(shape_id, int) and str(shape_id) in mappings:
                data["mappedRole"] = mappings[str(shape_id)]
                data["editable"] = True
            blocks.append(TemplateTextBlockResponse.model_validate(data))
        return TemplateSlideResponse.model_validate(
            {
                "id": slide.id,
                "slideNumber": slide.slide_number,
                "title": slide.title,
                "category": slide.category,
                "reuseState": slide.reuse_state,
                "modificationPolicy": slide.modification_policy,
                "customerSafe": slide.customer_safe,
                "required": slide.required,
                "exactTextRequired": slide.exact_text_required,
                "hidden": slide.hidden,
                "approvedDescription": slide.approved_description,
                "textBlocks": blocks,
                "createdAt": slide.created_at,
                "updatedAt": slide.updated_at,
            }
        )

    @staticmethod
    def _content_response(item: CreateApprovedContentItem) -> ApprovedContentItemResponse:
        return ApprovedContentItemResponse.model_validate(
            {
                "id": item.id,
                "slideId": item.slide_id,
                "contentType": item.content_type,
                "title": item.title,
                "approvedText": item.approved_text,
                "status": item.status,
                "modificationPolicy": item.modification_policy,
                "customerSafe": item.customer_safe,
                "exactTextRequired": item.exact_text_required,
                "approvedByUserId": item.approved_by_user_id,
                "approvedAt": item.approved_at,
            }
        )

    async def _validated_business_case_selection(
        self,
        version_id: UUID | None,
        company: Company,
        opportunity: Opportunity | None,
    ) -> tuple[CreateBusinessCase, CreateBusinessCaseVersion] | None:
        if version_id is None:
            return None
        selected = await self.repository.approved_business_case_version(
            self.tenant.organisation_id,
            version_id,
        )
        if selected is None:
            raise PublicAPIError(
                "business_case_not_approved",
                "Choose the current approved Business Case version.",
                422,
            )
        business_case, _ = selected
        if business_case.account_id != company.id:
            raise PublicAPIError(
                "business_case_account_mismatch",
                "The Business Case must belong to the selected Account.",
                422,
            )
        if business_case.opportunity_id is not None and (
            opportunity is None or business_case.opportunity_id != opportunity.id
        ):
            raise PublicAPIError(
                "business_case_opportunity_mismatch",
                "The Business Case must belong to the selected Opportunity.",
                422,
            )
        return selected

    async def _require_entitled(self) -> None:
        if not self.settings.feature_create_enabled:
            raise PublicAPIError("create_unavailable", "RevenueOS Create is temporarily unavailable.", 503)
        entitlement = await self.repository.entitlement(self.tenant.organisation_id)
        if entitlement is None or not entitlement.enabled:
            raise PublicAPIError("create_not_entitled", "Create is not enabled for this organisation.", 403)

    def _require_admin(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Administrator access is required.", 403)

    async def _commit(self, message: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("create_conflict", message, 409) from exc

    def _audit(self, event: str, **metadata: object) -> None:
        logger.info(
            event,
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                **metadata,
            },
        )


_CONTENT_PLACEHOLDER_ROLES = frozenset({"customer_context", "approved_content", "next_steps", "open_questions"})


def _effective_placeholder_roles(
    slide: CreateTemplateSlide,
    explicit_mappings: dict[str, str] | None = None,
) -> set[str]:
    mappings = {str(key): str(value) for key, value in slide.placeholder_mappings_json.items()}
    if explicit_mappings is not None:
        mappings = {str(key): str(value) for key, value in explicit_mappings.items()}
    roles = set(mappings.values())
    for item in slide.text_blocks_json:
        if not isinstance(item, dict):
            continue
        shape_id = item.get("shapeId")
        role = mappings.get(str(shape_id)) if isinstance(shape_id, int) else None
        if role is None and isinstance(item.get("mappedRole"), str):
            role = str(item["mappedRole"])
        if role:
            roles.add(role)
    return roles


def _has_unmapped_text_block(
    slide: CreateTemplateSlide,
    explicit_mappings: dict[str, str] | None = None,
) -> bool:
    mappings = {str(key): str(value) for key, value in slide.placeholder_mappings_json.items()}
    if explicit_mappings is not None:
        mappings = explicit_mappings
    for item in slide.text_blocks_json:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        shape_id = item.get("shapeId")
        role = mappings.get(str(shape_id)) if isinstance(shape_id, int) else None
        if role is None and isinstance(item.get("mappedRole"), str):
            role = str(item["mappedRole"])
        if role is None:
            return True
    return False


def _slide_compatibility_issue(slide: CreateTemplateSlide, request: TemplateSlideUpdate) -> str | None:
    if request.modification_policy in {"locked", "reuse_as_is"}:
        return None
    roles = _effective_placeholder_roles(
        slide, {str(key): value for key, value in request.placeholder_mappings.items()}
    )
    if request.category == "title":
        if not {"presentation_title", "audience"}.issubset(roles):
            return "pptx_title_placeholders_required"
    elif not roles.intersection(_CONTENT_PLACEHOLDER_ROLES):
        return "pptx_content_placeholder_required"
    if _has_unmapped_text_block(
        slide,
        {str(key): value for key, value in request.placeholder_mappings.items()},
    ):
        return "pptx_unmapped_text_requires_lock"
    return None


def _stored_slide_compatibility_issue(slide: CreateTemplateSlide) -> str | None:
    if slide.modification_policy in {"locked", "reuse_as_is"}:
        return None
    roles = _effective_placeholder_roles(slide)
    if slide.category == "title":
        if not {"presentation_title", "audience"}.issubset(roles):
            return "pptx_title_placeholders_required"
    elif not roles.intersection(_CONTENT_PLACEHOLDER_ROLES):
        return "pptx_content_placeholder_required"
    if _has_unmapped_text_block(slide):
        return "pptx_unmapped_text_requires_lock"
    return None


def _approved_slide_text(slide: CreateTemplateSlide) -> str:
    blocks = [item for item in slide.text_blocks_json if isinstance(item, dict)]
    if slide.modification_policy in {"locked", "reuse_as_is"}:
        selected = blocks
    else:
        mappings = {str(key): str(value) for key, value in slide.placeholder_mappings_json.items()}
        selected = [
            item
            for item in blocks
            if (
                mappings.get(str(item.get("shapeId")))
                or (str(item.get("mappedRole")) if item.get("mappedRole") is not None else None)
            )
            in _CONTENT_PLACEHOLDER_ROLES
        ]
    return "\n".join(str(item.get("text", "")).strip() for item in selected if str(item.get("text", "")).strip())


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _approval_fingerprint(version: CreatePresentationVersion) -> str:
    if version.approved_at is None or version.checksum_sha256 is None:
        return ""
    approved_at = _as_utc(version.approved_at).isoformat()
    return hashlib.sha256(f"v1:{version.id}:{approved_at}:{version.checksum_sha256}".encode()).hexdigest()


def _template_version_is_current(version: CreateTemplateVersion) -> bool:
    return (
        version.approval_state == "approved"
        and version.compatibility_state == "compatible"
        and version.validation_profile_version == CREATE_PPTX_PROFILE_VERSION
        and version.validated_at is not None
    )


def _json_fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip(" .")
    return cleaned[:120] or "RevenueOS presentation"


def _business_case_output_statement(
    output: CalculationOutputResponse,
    scenario: str,
    currency: str,
) -> str:
    scenario_label = {
        "base": "base-case",
        "conservative": "conservative",
        "upside": "upside",
    }[scenario]
    if output.display_value is None:
        return (
            f"Under the {scenario_label} assumptions, {output.label.lower()} is not achieved under the approved model."
        )
    return (
        f"Under the {scenario_label} assumptions, the approved model estimates "
        f"{output.label.lower()} at {_business_case_value(output.display_value, output.unit, currency)}."
    )


def _business_case_assumption_statement(value: CalculationInputResponse, currency: str) -> str:
    return (
        f"Material assumption — {value.label}: {_business_case_value(value.value, value.unit, currency)} "
        f"({value.source_label})."
    )


def _business_case_value(value: str, unit: str, currency: str) -> str:
    if unit == "currency":
        return f"{currency} {value}"
    if unit == "currency_per_year":
        return f"{currency} {value} per year"
    if unit == "currency_per_hour":
        return f"{currency} {value} per hour"
    if unit == "percentage":
        return f"{value}%"
    suffixes = {
        "hours": "hours",
        "hours_per_year": "hours per year",
        "minutes": "minutes",
        "days": "days",
        "months": "months",
        "years": "years",
    }
    suffix = suffixes.get(unit)
    return f"{value} {suffix}" if suffix else value
