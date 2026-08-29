from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.config import Settings
from revenueos.create_pptx import (
    PPTX_MIME_TYPE,
    BoundedPptxProcessor,
    PptxProcessingError,
    RenderSlide,
)
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    Company,
    CreateApprovedContentItem,
    CreatePresentation,
    CreatePresentationVersion,
    CreateTemplateSlide,
    CreateTemplateVersion,
    Opportunity,
    Organisation,
)
from revenueos.visual_storage import VisualStorage, VisualStorageError, create_visual_storage

logger = logging.getLogger("revenueos.create_worker")
_DISCOVERY_LIMIT = 1000


@dataclass(frozen=True)
class ClaimedCreateWork:
    organisation_id: UUID
    work_type: str
    work_id: UUID
    worker_id: str


class CreateWorkerService:
    """Leased deterministic PPTX processing inside the existing durable worker."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        storage: VisualStorage | None = None,
        processor: BoundedPptxProcessor | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._storage = storage or create_visual_storage(settings)
        self._processor = processor or create_processor(settings)

    async def run_once(self, worker_id: str) -> bool:
        if not self._settings.feature_create_enabled:
            return False
        processed = False
        for organisation_id in await self.discover_eligible_organisations():
            claim = await self.claim_next(organisation_id, worker_id)
            if claim is None:
                continue
            processed = True
            await self.execute_claimed(claim)
        return processed

    async def discover_eligible_organisations(self) -> list[UUID]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                values = await session.scalars(
                    text(
                        """SELECT organisation_id
                        FROM public.revenueos_create_worker_eligible_organisations(
                            :eligible_at,
                            :result_limit
                        )"""
                    ),
                    {"eligible_at": now, "result_limit": _DISCOVERY_LIMIT},
                )
                return [UUID(str(item)) for item in values.all()]
            eligible = (
                select(CreateTemplateVersion.organisation_id)
                .where(
                    CreateTemplateVersion.processing_state == "processing",
                    CreateTemplateVersion.processing_attempts < self._settings.private_beta_create_processing_retries,
                    or_(
                        CreateTemplateVersion.lease_expires_at.is_(None),
                        CreateTemplateVersion.lease_expires_at <= now,
                    ),
                )
                .union(
                    select(CreatePresentationVersion.organisation_id).where(
                        CreatePresentationVersion.state == "generating",
                        CreatePresentationVersion.processing_attempts
                        < self._settings.private_beta_create_processing_retries,
                        or_(
                            CreatePresentationVersion.lease_expires_at.is_(None),
                            CreatePresentationVersion.lease_expires_at <= now,
                        ),
                    )
                )
            )
            values = await session.scalars(
                select(Organisation.id)
                .where(Organisation.id.in_(eligible))
                .order_by(Organisation.id)
                .limit(_DISCOVERY_LIMIT)
            )
            return list(values.all())

    async def claim_next(self, organisation_id: UUID, worker_id: str) -> ClaimedCreateWork | None:
        now = datetime.now(UTC)
        lease = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            template = await session.scalar(
                select(CreateTemplateVersion)
                .where(
                    CreateTemplateVersion.organisation_id == organisation_id,
                    CreateTemplateVersion.processing_state == "processing",
                    CreateTemplateVersion.processing_attempts < self._settings.private_beta_create_processing_retries,
                    or_(
                        CreateTemplateVersion.lease_expires_at.is_(None),
                        CreateTemplateVersion.lease_expires_at <= now,
                    ),
                )
                .order_by(CreateTemplateVersion.created_at, CreateTemplateVersion.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if template is not None:
                template.processing_attempts += 1
                template.worker_id = worker_id
                template.lease_expires_at = lease
                template.safe_failure_code = None
                return ClaimedCreateWork(organisation_id, "template", template.id, worker_id)
            version = await session.scalar(
                select(CreatePresentationVersion)
                .where(
                    CreatePresentationVersion.organisation_id == organisation_id,
                    CreatePresentationVersion.state == "generating",
                    CreatePresentationVersion.processing_attempts
                    < self._settings.private_beta_create_processing_retries,
                    or_(
                        CreatePresentationVersion.lease_expires_at.is_(None),
                        CreatePresentationVersion.lease_expires_at <= now,
                    ),
                )
                .order_by(CreatePresentationVersion.created_at, CreatePresentationVersion.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if version is None:
                return None
            version.processing_attempts += 1
            version.worker_id = worker_id
            version.lease_expires_at = lease
            version.safe_failure_code = None
            return ClaimedCreateWork(organisation_id, "presentation", version.id, worker_id)

    async def execute_claimed(self, claim: ClaimedCreateWork) -> None:
        try:
            if claim.work_type == "template":
                await self._process_template(claim)
            else:
                await self._process_presentation(claim)
        except (PptxProcessingError, VisualStorageError) as exc:
            await self._record_failure(claim, getattr(exc, "code", "create_storage_failure"))
        except (KeyError, TypeError, ValueError, UnicodeError):
            await self._record_failure(claim, "create_manifest_invalid")
        except SQLAlchemyError:
            await self._record_failure(claim, "create_persistence_unavailable")

    async def _process_template(self, claim: ClaimedCreateWork) -> None:
        async with self._session_factory() as session:
            await set_tenant_database_context(session, claim.organisation_id)
            version = await session.scalar(
                select(CreateTemplateVersion).where(
                    CreateTemplateVersion.organisation_id == claim.organisation_id,
                    CreateTemplateVersion.id == claim.work_id,
                    CreateTemplateVersion.processing_state == "processing",
                    CreateTemplateVersion.worker_id == claim.worker_id,
                )
            )
            if version is None:
                return
            source = await self._storage.read(version.storage_key)
            parsed = self._processor.parse(source)
            # This is an idempotent retry boundary. A failed transaction can
            # never leave a partial slide manifest behind.
            existing = await session.scalars(
                select(CreateTemplateSlide).where(
                    CreateTemplateSlide.organisation_id == claim.organisation_id,
                    CreateTemplateSlide.template_version_id == version.id,
                )
            )
            for slide in existing.all():
                await session.delete(slide)
            await session.flush()
            for parsed_slide in parsed.slides:
                session.add(
                    CreateTemplateSlide(
                        id=uuid.uuid4(),
                        organisation_id=claim.organisation_id,
                        template_id=version.template_id,
                        template_version_id=version.id,
                        slide_number=parsed_slide.slide_number,
                        title=parsed_slide.title,
                        category=parsed_slide.category,
                        reuse_state=parsed_slide.reuse_state,
                        modification_policy=parsed_slide.modification_policy,
                        customer_safe=parsed_slide.customer_safe,
                        required=parsed_slide.required,
                        exact_text_required=parsed_slide.exact_text_required,
                        hidden=parsed_slide.hidden,
                        text_blocks_json=[
                            {
                                "shapeId": block.shape_id,
                                "shapeName": block.shape_name,
                                "text": block.text,
                                "placeholderType": block.placeholder_type,
                                "editable": block.editable,
                                "mappedRole": block.mapped_role,
                            }
                            for block in parsed_slide.text_blocks
                        ],
                        placeholder_mappings_json={},
                    )
                )
            version.slide_count = len(parsed.slides)
            version.width_emu = parsed.width_emu
            version.height_emu = parsed.height_emu
            version.warning_codes_json = list(parsed.warning_codes)
            version.manifest_json = {
                "schemaVersion": 1,
                "slideCount": len(parsed.slides),
                "warningCodes": list(parsed.warning_codes),
            }
            version.processing_state = "partial" if parsed.warning_codes else "ready"
            version.worker_id = None
            version.lease_expires_at = None
            version.processed_at = datetime.now(UTC)
            await session.commit()
        logger.info(
            "create_template_processed",
            extra={
                "organisation_id": str(claim.organisation_id),
                "template_version_id": str(claim.work_id),
                "worker_id": claim.worker_id,
            },
        )

    async def _process_presentation(self, claim: ClaimedCreateWork) -> None:
        async with self._session_factory() as session:
            await set_tenant_database_context(session, claim.organisation_id)
            version = await session.scalar(
                select(CreatePresentationVersion).where(
                    CreatePresentationVersion.organisation_id == claim.organisation_id,
                    CreatePresentationVersion.id == claim.work_id,
                    CreatePresentationVersion.state == "generating",
                    CreatePresentationVersion.worker_id == claim.worker_id,
                )
            )
            if version is None:
                return
            presentation = await session.scalar(
                select(CreatePresentation).where(
                    CreatePresentation.organisation_id == claim.organisation_id,
                    CreatePresentation.id == version.presentation_id,
                )
            )
            template_version = await session.scalar(
                select(CreateTemplateVersion).where(
                    CreateTemplateVersion.organisation_id == claim.organisation_id,
                    CreateTemplateVersion.id == version.template_version_id,
                    CreateTemplateVersion.approval_state == "approved",
                )
            )
            organisation = await session.scalar(select(Organisation).where(Organisation.id == claim.organisation_id))
            if presentation is None or template_version is None or organisation is None:
                raise ValueError("Missing Create source reference.")
            slide_rows = list(
                (
                    await session.scalars(
                        select(CreateTemplateSlide).where(
                            CreateTemplateSlide.organisation_id == claim.organisation_id,
                            CreateTemplateSlide.template_version_id == template_version.id,
                        )
                    )
                ).all()
            )
            slide_map = {slide.id: slide for slide in slide_rows}
            content_rows = list(
                (
                    await session.scalars(
                        select(CreateApprovedContentItem).where(
                            CreateApprovedContentItem.organisation_id == claim.organisation_id,
                            CreateApprovedContentItem.template_version_id == template_version.id,
                            CreateApprovedContentItem.status == "approved",
                        )
                    )
                ).all()
            )
            content_map = {item.slide_id: item for item in content_rows}
            company = await session.scalar(
                select(Company).where(
                    Company.organisation_id == claim.organisation_id,
                    Company.id == presentation.account_id,
                )
            )
            opportunity = (
                await session.scalar(
                    select(Opportunity).where(
                        Opportunity.organisation_id == claim.organisation_id,
                        Opportunity.id == presentation.opportunity_id,
                    )
                )
                if presentation.opportunity_id
                else None
            )
            if company is None:
                raise ValueError("Missing Create Account.")
            if version.generated_content_json:
                generated = [dict(item) for item in version.generated_content_json if isinstance(item, dict)]
                claims = [dict(item) for item in version.claim_manifest_json if isinstance(item, dict)]
            else:
                generated, claims = _compose(
                    presentation,
                    version,
                    slide_map,
                    content_map,
                )
            render_slides = _render_manifest(
                generated,
                slide_map,
                presentation,
                company,
                opportunity,
            )
            source = await self._storage.read(template_version.storage_key)
            output = self._processor.render(
                source,
                tuple(render_slides),
                title=presentation.title,
                organisation_name=organisation.name,
            )
            if len(output) > self._settings.private_beta_max_pptx_bytes:
                raise PptxProcessingError
            storage_key = f"{claim.organisation_id}/create/presentations/{presentation.id}/{version.id}.pptx"
            await self._storage.write(storage_key, output, PPTX_MIME_TYPE)
            version.generated_content_json = cast(list[object], generated)
            version.claim_manifest_json = cast(list[object], claims)
            warnings = {"review_required"}
            if any(item.get("reviewState") == "pending" for item in claims):
                warnings.add("reported_or_inferred_claims_present")
            version.warning_codes_json = cast(list[object], sorted(warnings))
            version.pptx_storage_key = storage_key
            version.storage_status = "available"
            version.byte_size = len(output)
            version.checksum_sha256 = hashlib.sha256(output).hexdigest()
            version.state = "needs_review"
            version.review_state = "pending"
            version.generated_at = datetime.now(UTC)
            version.worker_id = None
            version.lease_expires_at = None
            version.safe_failure_code = None
            presentation.state = "needs_review"
            presentation.review_state = "pending"
            await session.commit()
        logger.info(
            "create_presentation_rendered",
            extra={
                "organisation_id": str(claim.organisation_id),
                "presentation_version_id": str(claim.work_id),
                "worker_id": claim.worker_id,
                "byte_size": len(output),
                "slide_count": len(generated),
                "claim_count": len(claims),
            },
        )

    async def _record_failure(self, claim: ClaimedCreateWork, code: str) -> None:
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, claim.organisation_id)
            if claim.work_type == "template":
                item = await session.scalar(
                    select(CreateTemplateVersion).where(
                        CreateTemplateVersion.organisation_id == claim.organisation_id,
                        CreateTemplateVersion.id == claim.work_id,
                        CreateTemplateVersion.worker_id == claim.worker_id,
                    )
                )
                if item is None:
                    return
                item.safe_failure_code = code[:100]
                item.worker_id = None
                item.lease_expires_at = None
                if item.processing_attempts >= self._settings.private_beta_create_processing_retries:
                    item.processing_state = "failed"
            else:
                version = await session.scalar(
                    select(CreatePresentationVersion).where(
                        CreatePresentationVersion.organisation_id == claim.organisation_id,
                        CreatePresentationVersion.id == claim.work_id,
                        CreatePresentationVersion.worker_id == claim.worker_id,
                    )
                )
                if version is None:
                    return
                version.safe_failure_code = code[:100]
                version.worker_id = None
                version.lease_expires_at = None
                if version.processing_attempts >= self._settings.private_beta_create_processing_retries:
                    version.state = "failed"
                    presentation = await session.scalar(
                        select(CreatePresentation).where(
                            CreatePresentation.organisation_id == claim.organisation_id,
                            CreatePresentation.id == version.presentation_id,
                        )
                    )
                    if presentation is not None:
                        presentation.state = "failed"
        logger.warning(
            "create_work_failed",
            extra={
                "organisation_id": str(claim.organisation_id),
                "work_type": claim.work_type,
                "work_id": str(claim.work_id),
                "error_code": code[:100],
                "worker_id": claim.worker_id,
            },
        )


def create_processor(settings: Settings) -> BoundedPptxProcessor:
    from revenueos.create_pptx import PptxLimits

    return BoundedPptxProcessor(
        PptxLimits(
            max_bytes=settings.private_beta_max_pptx_bytes,
            max_slides=settings.private_beta_max_pptx_slides,
            max_entries=settings.private_beta_max_pptx_zip_entries,
            max_expanded_bytes=settings.private_beta_max_pptx_expanded_bytes,
            max_media_assets=settings.private_beta_max_pptx_media_assets,
            max_media_bytes=settings.private_beta_max_pptx_media_bytes,
            max_xml_bytes=settings.private_beta_max_pptx_xml_bytes,
            max_extracted_characters=settings.private_beta_max_pptx_extracted_characters,
        )
    )


def _compose(
    presentation: CreatePresentation,
    version: CreatePresentationVersion,
    slides: dict[UUID, CreateTemplateSlide],
    content: dict[UUID, CreateApprovedContentItem],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    context_items = [
        dict(item)
        for item in cast(list[object], version.source_context_json.get("items", []))
        if isinstance(item, dict)
    ]
    dynamic = [
        item
        for item in context_items
        if item.get("origin")
        in {"customer_direct", "salesperson_reported", "prospect_public", "approved_business_case"}
    ]
    generated: list[dict[str, object]] = []
    claims: list[dict[str, object]] = []
    for raw_plan in version.plan_snapshot_json:
        if not isinstance(raw_plan, dict):
            raise ValueError("Invalid plan item.")
        plan = dict(raw_plan)
        plan_id = UUID(str(plan["id"]))
        slide_id = UUID(str(plan["templateSlideId"]))
        slide = slides.get(slide_id)
        approved = content.get(slide_id)
        if slide is None or approved is None or slide.reuse_state != "approved" or not slide.customer_safe:
            raise ValueError("Source slide is no longer approved.")
        exact = slide.exact_text_required or slide.modification_policy in {"locked", "reuse_as_is"}
        body: list[str]
        body_sources: list[dict[str, object]]
        if exact:
            body = [approved.approved_text]
            body_sources = [
                {
                    "id": str(approved.id),
                    "origin": "approved_company_content",
                    "supportState": "approved",
                    "customerSafeClassification": "customer_safe",
                    "sourceLabel": "Approved company content",
                    "freshness": "current",
                    "paraphraseAllowed": False,
                    "exactTextRequired": True,
                    "category": approved.content_type,
                }
            ]
        else:
            selected = _context_for_category(str(slide.category), dynamic)
            if selected:
                limit = 6 if any(item.get("origin") == "approved_business_case" for item in selected) else 4
                body_sources = selected[:limit]
                body = [str(item["statement"]) for item in body_sources]
            else:
                body = [approved.approved_text]
                body_sources = [
                    {
                        "id": str(approved.id),
                        "origin": "approved_company_content",
                        "supportState": "approved",
                        "customerSafeClassification": "customer_safe",
                        "sourceLabel": "Approved company content",
                        "freshness": "current",
                        "paraphraseAllowed": True,
                        "exactTextRequired": False,
                        "category": approved.content_type,
                    }
                ]
        warning_codes: set[str] = set()
        review_state = "ready"
        for block_index, source in enumerate(body_sources):
            needs_review = source.get("customerSafeClassification") == "requires_review"
            if needs_review:
                review_state = "needs_review"
                warning_codes.add("claim_review_required")
            source_id = UUID(str(source["id"]))
            claims.append(
                {
                    "id": str(uuid.uuid4()),
                    "planItemId": str(plan_id),
                    "blockIndex": block_index,
                    "claim": body[block_index],
                    "contentType": str(source.get("category", slide.category)),
                    "origin": source["origin"],
                    "supportState": source["supportState"],
                    "customerSafeClassification": source["customerSafeClassification"],
                    "sourceIds": [str(source_id)],
                    "sourceLabels": [str(source["sourceLabel"])],
                    "freshness": source["freshness"],
                    "paraphraseAllowed": bool(source["paraphraseAllowed"]),
                    "exactTextRequired": bool(source["exactTextRequired"]),
                    "reviewState": "pending" if needs_review else "not_required",
                }
            )
        generated.append(
            {
                "planItemId": str(plan_id),
                "templateSlideId": str(slide.id),
                "order": int(plan["order"]),
                "title": presentation.title if slide.category == "title" else slide.title,
                "bodyBlocks": body,
                "required": slide.required,
                "modificationPolicy": slide.modification_policy,
                "reviewState": review_state,
                "warningCodes": sorted(warning_codes),
            }
        )
    generated.sort(key=lambda item: cast(int, item["order"]))
    return generated, claims


def _context_for_category(category: str, items: list[dict[str, object]]) -> list[dict[str, object]]:
    if category == "problem":
        allowed = {"customer_request", "technical_requirement", "contractual_requirement", "trigger"}
    elif category == "next_steps":
        allowed = {"decision", "action_item", "commitment", "open_question", "timeline"}
    elif category in {"agenda", "solution"}:
        allowed = {
            "customer_request",
            "technical_requirement",
            "implementation",
            "strategic_initiative",
            "business_case_output",
            "business_case_disclaimer",
        }
    elif category in {"proof_point", "pricing_placeholder", "appendix"}:
        allowed = {"business_case_output", "business_case_assumption", "business_case_disclaimer"}
    elif category == "process":
        allowed = {"implementation", "business_case_assumption"}
    else:
        return []
    matched = [item for item in items if item.get("category") in allowed]
    scenario_heads: list[dict[str, object]] = []
    scenario_head_ids: set[int] = set()
    seen_scenarios: set[str] = set()
    for item in matched:
        scenario = item.get("scenario")
        if (
            item.get("category") == "business_case_output"
            and isinstance(scenario, str)
            and scenario not in seen_scenarios
        ):
            scenario_heads.append(item)
            scenario_head_ids.add(id(item))
            seen_scenarios.add(scenario)
    disclaimers = [item for item in matched if item.get("category") == "business_case_disclaimer"]
    assumptions = [item for item in matched if item.get("category") == "business_case_assumption"]
    prioritised_ids = {id(item) for item in [*scenario_heads, *disclaimers, *assumptions[:1]]}
    return [
        *scenario_heads,
        *disclaimers,
        *assumptions[:1],
        *(item for item in matched if id(item) not in prioritised_ids),
    ]


def _render_manifest(
    generated: list[dict[str, object]],
    slides: dict[UUID, CreateTemplateSlide],
    presentation: CreatePresentation,
    company: Company,
    opportunity: Opportunity | None,
) -> list[RenderSlide]:
    result: list[RenderSlide] = []
    audience = ", ".join(
        str(item.get("name") or item.get("role") or item.get("audienceType") or "Audience")
        for item in presentation.audience_json
        if isinstance(item, dict)
    )
    for generated_slide in generated:
        slide_id = UUID(str(generated_slide["templateSlideId"]))
        slide = slides[slide_id]
        replacements: dict[int, str] = {}
        if slide.modification_policy not in {"locked", "reuse_as_is"}:
            mappings = {str(key): str(value) for key, value in slide.placeholder_mappings_json.items()}
            for block in slide.text_blocks_json:
                if not isinstance(block, dict) or not isinstance(block.get("shapeId"), int):
                    continue
                shape_id = cast(int, block["shapeId"])
                role = mappings.get(str(shape_id)) or block.get("mappedRole")
                body = "\n".join(str(item) for item in cast(list[object], generated_slide.get("bodyBlocks", [])))
                values = {
                    "presentation_title": str(generated_slide["title"]),
                    "account_name": company.name,
                    "opportunity_name": opportunity.name if opportunity else "",
                    "audience": audience,
                    "customer_context": body,
                    "approved_content": body,
                    "next_steps": body,
                    "open_questions": body,
                }
                if isinstance(role, str) and role in values:
                    replacements[shape_id] = values[role]
        result.append(RenderSlide(slide.slide_number, replacements))
    return result
