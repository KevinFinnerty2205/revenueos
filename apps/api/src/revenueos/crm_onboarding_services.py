from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, cast
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.crm_contracts import (
    CRMEntityType,
    CRMImportConfirmRequest,
    CRMImportConfirmResponse,
    CRMImportDisposition,
    CRMImportPreviewRequest,
    CRMImportPreviewResponse,
    CRMImportRowResponse,
    validate_custom_url,
)
from revenueos.crm_import import CRMImportError, ParsedCRMImport, ParsedCRMImportRow, decode_crm_csv, parse_crm_csv
from revenueos.crm_services import CRMService
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    Contact,
    ContactSuppression,
    CRMCustomFieldDefinition,
    CRMCustomFieldValue,
    CRMImportBatch,
    CRMImportRow,
    CRMRecordChange,
    Opportunity,
    OpportunityStageEvent,
    OrganisationCRMSetting,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    SalesPipeline,
    SalesPipelineStage,
)
from revenueos.pipeline_repositories import legacy_stage_for
from revenueos.prospect_url_security import PublicUrlSafetyError, normalise_company_website
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.crm_import")

ACCOUNT_FIELDS = frozenset({"name", "website", "industry", "location", "employee_count", "status", "owner"})
CONTACT_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "phone",
        "job_title",
        "linkedin_url",
        "status",
        "account_domain",
        "account_name",
        "owner",
        "do_not_contact",
    }
)
OPPORTUNITY_FIELDS = frozenset(
    {
        "name",
        "account_domain",
        "account_name",
        "stage",
        "estimated_value",
        "currency",
        "expected_close_date",
        "description",
        "owner",
    }
)


@dataclass(frozen=True)
class ImportContext:
    members: frozenset[UUID]
    companies_by_domain: dict[str, Company]
    companies_by_name: dict[str, list[Company]]
    contacts_by_email: dict[str, Contact]
    contacts_by_name_account: dict[tuple[UUID, str, str], list[Contact]]
    opportunities_by_name_account: dict[tuple[UUID, str], list[Opportunity]]
    pipeline: SalesPipeline | None
    stages: dict[UUID, SalesPipelineStage]
    custom_fields: dict[UUID, CRMCustomFieldDefinition]


@dataclass(frozen=True)
class ResolvedImportRow:
    source_row: int
    disposition: CRMImportDisposition
    issue_code: str | None
    canonical_entity_id: UUID | None
    values: dict[str, object]


class CRMOnboardingService:
    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings

    async def preview(self, request: CRMImportPreviewRequest) -> CRMImportPreviewResponse:
        await self._require_admin_native_crm()
        parsed = self._parse(request)
        mapping_fingerprint = self._mapping_fingerprint(request)
        context = await self._context(request)
        rows = self._resolve_rows(request, parsed, context)
        now = datetime.now(UTC)
        batch = await self.session.scalar(
            select(CRMImportBatch)
            .where(
                CRMImportBatch.organisation_id == self.tenant.organisation_id,
                CRMImportBatch.entity_type == request.entity_type,
                CRMImportBatch.file_fingerprint == parsed.file_fingerprint,
                CRMImportBatch.mapping_fingerprint == mapping_fingerprint,
            )
            .with_for_update()
        )
        if batch is not None and batch.state == "confirmed":
            return await self._response(batch, confirmed=True)
        if batch is None:
            batch = CRMImportBatch(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                entity_type=request.entity_type,
                requested_by_user_id=self.tenant.user_id,
                state="previewed",
                file_fingerprint=parsed.file_fingerprint,
                mapping_fingerprint=mapping_fingerprint,
                file_size_bytes=parsed.file_size_bytes,
                row_count=len(rows),
                actionable_row_count=sum(row.disposition == "new" for row in rows),
                imported_row_count=0,
                expires_at=now + timedelta(hours=1),
            )
            self.session.add(batch)
            await self.session.flush()
        else:
            await self.session.execute(
                delete(CRMImportRow).where(
                    CRMImportRow.organisation_id == self.tenant.organisation_id,
                    CRMImportRow.batch_id == batch.id,
                )
            )
            batch.requested_by_user_id = self.tenant.user_id
            batch.state = "previewed"
            batch.file_size_bytes = parsed.file_size_bytes
            batch.row_count = len(rows)
            batch.actionable_row_count = sum(row.disposition == "new" for row in rows)
            batch.imported_row_count = 0
            batch.expires_at = now + timedelta(hours=1)
            batch.confirmed_at = None
        for row in rows:
            self.session.add(
                CRMImportRow(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    batch_id=batch.id,
                    source_row=row.source_row,
                    disposition=row.disposition,
                    issue_code=row.issue_code,
                    canonical_entity_id=row.canonical_entity_id,
                )
            )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.session.scalar(
                select(CRMImportBatch).where(
                    CRMImportBatch.organisation_id == self.tenant.organisation_id,
                    CRMImportBatch.entity_type == request.entity_type,
                    CRMImportBatch.file_fingerprint == parsed.file_fingerprint,
                    CRMImportBatch.mapping_fingerprint == mapping_fingerprint,
                )
            )
            if concurrent is None:
                raise PublicAPIError(
                    "crm_import_conflict", "The CRM import preview conflicted with another change.", 409
                ) from exc
            return await self._response(concurrent, confirmed=concurrent.state == "confirmed")
        logger.info(
            "crm_import_previewed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "import_id": str(batch.id),
                "entity_type": request.entity_type,
                "row_count": batch.row_count,
                "actionable_row_count": batch.actionable_row_count,
            },
        )
        return await self._response(batch, confirmed=False)

    async def confirm(self, request: CRMImportConfirmRequest) -> CRMImportConfirmResponse:
        await self._require_admin_native_crm()
        batch = await self.session.scalar(
            select(CRMImportBatch)
            .where(
                CRMImportBatch.organisation_id == self.tenant.organisation_id,
                CRMImportBatch.id == request.batch_id,
            )
            .with_for_update()
        )
        if batch is None:
            raise PublicAPIError("crm_import_not_found", "The CRM import preview was not found.", 404)
        if batch.state == "confirmed":
            return CRMImportConfirmResponse.model_validate((await self._response(batch, confirmed=True)).model_dump())
        now = datetime.now(UTC)
        expires_at = batch.expires_at if batch.expires_at.tzinfo is not None else batch.expires_at.replace(tzinfo=UTC)
        if batch.state != "previewed" or expires_at <= now:
            batch.state = "expired"
            await self.session.commit()
            raise PublicAPIError("crm_import_expired", "This CRM import preview expired. Preview the CSV again.", 410)
        parsed = self._parse(request)
        mapping_fingerprint = self._mapping_fingerprint(request)
        if (
            batch.entity_type != request.entity_type
            or batch.file_fingerprint != parsed.file_fingerprint
            or batch.mapping_fingerprint != mapping_fingerprint
        ):
            raise PublicAPIError("crm_import_changed", "The CSV or mapping changed after preview.", 409)
        context = await self._context(request)
        resolved = self._resolve_rows(request, parsed, context)
        persisted = list(
            (
                await self.session.scalars(
                    select(CRMImportRow)
                    .where(
                        CRMImportRow.organisation_id == self.tenant.organisation_id,
                        CRMImportRow.batch_id == batch.id,
                    )
                    .order_by(CRMImportRow.source_row)
                    .with_for_update()
                )
            ).all()
        )
        expected = [(row.source_row, row.disposition, row.canonical_entity_id) for row in persisted]
        current = [(row.source_row, row.disposition, row.canonical_entity_id) for row in resolved]
        if expected != current:
            raise PublicAPIError("crm_import_stale", "CRM records changed after preview. Preview the CSV again.", 409)
        persisted_by_source = {row.source_row: row for row in persisted}
        imported_count = 0
        for row in resolved:
            stored = persisted_by_source[row.source_row]
            if row.disposition != "new":
                stored.disposition = "skipped"
                continue
            entity_id = await self._import_row(request.entity_type, row, context, batch.id)
            stored.disposition = "imported"
            stored.canonical_entity_id = entity_id
            imported_count += 1
        batch.state = "confirmed"
        batch.imported_row_count = imported_count
        batch.confirmed_at = now
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError(
                "crm_import_conflict", "CRM data changed while the import was being confirmed.", 409
            ) from exc
        logger.info(
            "crm_import_confirmed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "import_id": str(batch.id),
                "entity_type": request.entity_type,
                "row_count": batch.row_count,
                "imported_row_count": imported_count,
            },
        )
        response = await self._response(batch, confirmed=True)
        return CRMImportConfirmResponse.model_validate(response.model_dump())

    def _parse(self, request: CRMImportPreviewRequest) -> ParsedCRMImport:
        self._validate_mapping(request)
        try:
            content = decode_crm_csv(request.file_name, request.content_base64)
            return parse_crm_csv(content, request.column_mapping)
        except CRMImportError as exc:
            status = 413 if exc.code in {"file_too_large", "too_many_rows", "too_many_columns"} else 422
            raise PublicAPIError(exc.code, exc.message, status) from exc

    def _validate_mapping(self, request: CRMImportPreviewRequest) -> None:
        allowed = {
            "account": ACCOUNT_FIELDS,
            "contact": CONTACT_FIELDS,
            "opportunity": OPPORTUNITY_FIELDS,
        }[request.entity_type]
        targets = {target for target in request.column_mapping.values() if target is not None}
        invalid = [target for target in targets if target not in allowed and not target.startswith("custom:")]
        if invalid:
            raise PublicAPIError("invalid_crm_import_mapping", "The CSV maps to an unsupported CRM field.", 422)
        required = {
            "account": {"name"},
            "contact": {"first_name", "last_name"},
            "opportunity": {"name", "stage"},
        }[request.entity_type]
        if not required.issubset(targets):
            raise PublicAPIError("incomplete_crm_import_mapping", "Map every required CRM field.", 422)
        if request.entity_type in {"contact", "opportunity"} and not ({"account_domain", "account_name"} & targets):
            raise PublicAPIError("incomplete_crm_import_mapping", "Map an Account domain or Account name column.", 422)
        if request.entity_type == "opportunity" and request.pipeline_id is None:
            raise PublicAPIError("pipeline_mapping_required", "Choose the pipeline for this Opportunity import.", 422)
        if request.entity_type != "opportunity" and (request.pipeline_id or request.stage_value_mapping):
            raise PublicAPIError("unexpected_stage_mapping", "Stage mapping is only accepted for Opportunities.", 422)
        if "owner" not in targets and request.owner_value_mapping:
            raise PublicAPIError("unexpected_owner_mapping", "Owner-value mapping requires an Owner column.", 422)

    def _mapping_fingerprint(self, request: CRMImportPreviewRequest) -> str:
        payload = {
            "entityType": request.entity_type,
            "columnMapping": sorted(request.column_mapping.items()),
            "defaultOwnerUserId": str(request.default_owner_user_id),
            "ownerValueMapping": sorted((key, str(value)) for key, value in request.owner_value_mapping.items()),
            "pipelineId": str(request.pipeline_id) if request.pipeline_id else None,
            "stageValueMapping": sorted((key, str(value)) for key, value in request.stage_value_mapping.items()),
        }
        return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()

    async def _context(self, request: CRMImportPreviewRequest) -> ImportContext:
        members = frozenset(
            await self.session.scalars(
                select(OrganisationMembership.user_id).where(
                    OrganisationMembership.organisation_id == self.tenant.organisation_id,
                    OrganisationMembership.status == "active",
                )
            )
        )
        if request.default_owner_user_id not in members or any(
            owner_id not in members for owner_id in request.owner_value_mapping.values()
        ):
            raise PublicAPIError(
                "invalid_owner_mapping", "Every imported owner must be an active organisation member.", 422
            )
        companies = list(
            await self.session.scalars(select(Company).where(Company.organisation_id == self.tenant.organisation_id))
        )
        contacts = list(
            await self.session.scalars(select(Contact).where(Contact.organisation_id == self.tenant.organisation_id))
        )
        opportunities = list(
            await self.session.scalars(
                select(Opportunity).where(Opportunity.organisation_id == self.tenant.organisation_id)
            )
        )
        companies_by_name: dict[str, list[Company]] = {}
        for company in companies:
            companies_by_name.setdefault(company.name.strip().casefold(), []).append(company)
        contacts_by_name_account: dict[tuple[UUID, str, str], list[Contact]] = {}
        for contact in contacts:
            contacts_by_name_account.setdefault(
                (contact.company_id, contact.first_name.casefold(), contact.last_name.casefold()), []
            ).append(contact)
        opportunities_by_name_account: dict[tuple[UUID, str], list[Opportunity]] = {}
        for opportunity in opportunities:
            if opportunity.company_id is not None and opportunity.status == "open" and opportunity.archived_at is None:
                opportunities_by_name_account.setdefault(
                    (opportunity.company_id, opportunity.name.casefold()), []
                ).append(opportunity)
        pipeline = None
        stages: dict[UUID, SalesPipelineStage] = {}
        if request.pipeline_id is not None:
            pipeline = await self.session.scalar(
                select(SalesPipeline).where(
                    SalesPipeline.organisation_id == self.tenant.organisation_id,
                    SalesPipeline.id == request.pipeline_id,
                    SalesPipeline.active.is_(True),
                )
            )
            if pipeline is None:
                raise PublicAPIError("invalid_pipeline_mapping", "The selected pipeline is not active.", 422)
            stage_rows = list(
                await self.session.scalars(
                    select(SalesPipelineStage).where(
                        SalesPipelineStage.organisation_id == self.tenant.organisation_id,
                        SalesPipelineStage.pipeline_id == pipeline.id,
                        SalesPipelineStage.active.is_(True),
                    )
                )
            )
            stages = {stage.id: stage for stage in stage_rows}
            if any(
                stage_id not in stages or stages[stage_id].stage_type != "open"
                for stage_id in request.stage_value_mapping.values()
            ):
                raise PublicAPIError(
                    "invalid_stage_mapping", "Every imported stage must map to an active open stage.", 422
                )
        custom_fields = {
            definition.id: definition
            for definition in await self.session.scalars(
                select(CRMCustomFieldDefinition).where(
                    CRMCustomFieldDefinition.organisation_id == self.tenant.organisation_id,
                    CRMCustomFieldDefinition.entity_type == request.entity_type,
                    CRMCustomFieldDefinition.active.is_(True),
                )
            )
        }
        for target in request.column_mapping.values():
            if target is None or not target.startswith("custom:"):
                continue
            try:
                definition_id = UUID(target.removeprefix("custom:"))
            except ValueError as exc:
                raise PublicAPIError("invalid_custom_field_mapping", "A custom-field mapping is invalid.", 422) from exc
            if definition_id not in custom_fields:
                raise PublicAPIError("invalid_custom_field_mapping", "A mapped custom field is not active.", 422)
        return ImportContext(
            members=members,
            companies_by_domain={
                company.normalized_domain: company for company in companies if company.normalized_domain is not None
            },
            companies_by_name=companies_by_name,
            contacts_by_email={contact.email.casefold(): contact for contact in contacts if contact.email},
            contacts_by_name_account=contacts_by_name_account,
            opportunities_by_name_account=opportunities_by_name_account,
            pipeline=pipeline,
            stages=stages,
            custom_fields=custom_fields,
        )

    def _resolve_rows(
        self,
        request: CRMImportPreviewRequest,
        parsed: ParsedCRMImport,
        context: ImportContext,
    ) -> list[ResolvedImportRow]:
        rows: list[ResolvedImportRow] = []
        seen_strong: set[str] = set()
        for row in parsed.rows:
            try:
                resolved = self._resolve_row(request, row, context, seen_strong)
            except (ValueError, PublicUrlSafetyError, EmailNotValidError, InvalidOperation):
                resolved = ResolvedImportRow(row.source_row, "invalid", "invalid_field_value", None, {})
            rows.append(resolved)
        return rows

    def _resolve_row(
        self,
        request: CRMImportPreviewRequest,
        row: ParsedCRMImportRow,
        context: ImportContext,
        seen_strong: set[str],
    ) -> ResolvedImportRow:
        values = row.values
        owner_id = request.default_owner_user_id
        if owner_value := values.get("owner"):
            owner_id = request.owner_value_mapping.get(owner_value, UUID(int=0))
            if owner_id not in context.members:
                return ResolvedImportRow(row.source_row, "invalid", "owner_mapping_missing", None, {})
        typed: dict[str, object] = {"owner_user_id": owner_id}
        if request.entity_type == "account":
            name = self._bounded(values.get("name"), 200, required=True)
            assert name is not None
            typed["name"] = name
            website = values.get("website")
            domain = None
            if website:
                canonical = normalise_company_website(website)
                typed["website"] = canonical.url
                typed["normalized_domain"] = canonical.domain
                domain = canonical.domain
            typed["industry"] = self._bounded(values.get("industry"), 120)
            typed["location"] = self._bounded(values.get("location"), 200)
            typed["employee_count"] = self._integer(values.get("employee_count"))
            status = values.get("status", "prospect").casefold()
            if status not in {"prospect", "active", "inactive"}:
                raise ValueError
            typed["status"] = status
            self._custom_values(values, typed, context)
            if domain:
                key = f"account-domain:{domain}"
                if key in seen_strong:
                    return ResolvedImportRow(row.source_row, "possible_duplicate", "duplicate_in_file", None, {})
                seen_strong.add(key)
                if existing := context.companies_by_domain.get(domain):
                    return ResolvedImportRow(row.source_row, "matches_existing", None, existing.id, {})
            account_matches = context.companies_by_name.get(name.casefold(), [])
            if account_matches:
                return ResolvedImportRow(
                    row.source_row, "possible_duplicate", "exact_name_match", account_matches[0].id, {}
                )
            return ResolvedImportRow(
                row.source_row, "new", "formula_like_text" if row.formula_like else None, None, typed
            )

        company = self._account(values, context)
        if company is None:
            return ResolvedImportRow(row.source_row, "invalid", "account_not_found", None, {})
        typed["company_id"] = company.id
        if request.entity_type == "contact":
            first_name = self._bounded(values.get("first_name"), 100, required=True)
            last_name = self._bounded(values.get("last_name"), 100, required=True)
            assert first_name is not None and last_name is not None
            typed.update(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": self._bounded(values.get("phone"), 50),
                    "job_title": self._bounded(values.get("job_title"), 150),
                    "linkedin_url": self._url(values.get("linkedin_url")),
                }
            )
            status = values.get("status", "active").casefold()
            if status not in {"active", "left_company"}:
                raise ValueError
            typed["status"] = status
            email = None
            if values.get("email"):
                email = validate_email(values["email"], check_deliverability=False).normalized.casefold()
                typed["email"] = email
                key = f"contact-email:{email}"
                if key in seen_strong:
                    return ResolvedImportRow(row.source_row, "possible_duplicate", "duplicate_in_file", None, {})
                seen_strong.add(key)
                if existing_contact := context.contacts_by_email.get(email):
                    return ResolvedImportRow(row.source_row, "matches_existing", None, existing_contact.id, {})
            typed["do_not_contact"] = self._boolean(values.get("do_not_contact"))
            self._custom_values(values, typed, context)
            contact_matches = context.contacts_by_name_account.get(
                (company.id, first_name.casefold(), last_name.casefold()), []
            )
            if contact_matches:
                return ResolvedImportRow(
                    row.source_row,
                    "possible_duplicate",
                    "exact_name_account_match",
                    contact_matches[0].id,
                    {},
                )
            return ResolvedImportRow(
                row.source_row, "new", "formula_like_text" if row.formula_like else None, None, typed
            )

        name = self._bounded(values.get("name"), 200, required=True)
        assert name is not None
        source_stage = values.get("stage")
        if source_stage is None or source_stage not in request.stage_value_mapping:
            return ResolvedImportRow(row.source_row, "invalid", "stage_mapping_missing", None, {})
        stage = context.stages[request.stage_value_mapping[source_stage]]
        amount = self._decimal(values.get("estimated_value"))
        currency = values.get("currency")
        if (amount is None) != (currency is None):
            raise ValueError
        if currency is not None:
            currency = currency.strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError
        typed.update(
            {
                "name": name,
                "pipeline_id": context.pipeline.id if context.pipeline else None,
                "pipeline_stage_id": stage.id,
                "stage": legacy_stage_for(stage),
                "status": "open",
                "estimated_value": amount,
                "currency": currency,
                "expected_close_date": self._date(values.get("expected_close_date")),
                "description": self._bounded(values.get("description"), 2_000),
            }
        )
        self._custom_values(values, typed, context)
        opportunity_matches = context.opportunities_by_name_account.get((company.id, name.casefold()), [])
        if opportunity_matches:
            return ResolvedImportRow(
                row.source_row, "possible_duplicate", "open_opportunity_match", opportunity_matches[0].id, {}
            )
        return ResolvedImportRow(row.source_row, "new", "formula_like_text" if row.formula_like else None, None, typed)

    def _account(self, values: dict[str, str], context: ImportContext) -> Company | None:
        if domain_value := values.get("account_domain"):
            domain = normalise_company_website(domain_value).domain
            return context.companies_by_domain.get(domain)
        if name := values.get("account_name"):
            matches = context.companies_by_name.get(name.casefold(), [])
            return matches[0] if len(matches) == 1 else None
        return None

    def _custom_values(
        self,
        values: dict[str, str],
        typed: dict[str, object],
        context: ImportContext,
    ) -> None:
        custom: dict[UUID, str | Decimal | date | bool] = {}
        for key, raw_value in values.items():
            if not key.startswith("custom:"):
                continue
            definition_id = UUID(key.removeprefix("custom:"))
            definition = context.custom_fields[definition_id]
            custom[definition_id] = CRMService._validate_value(definition, raw_value)
        typed["custom_values"] = custom

    async def _import_row(
        self,
        entity_type: CRMEntityType,
        row: ResolvedImportRow,
        context: ImportContext,
        batch_id: UUID,
    ) -> UUID:
        values = dict(row.values)
        custom_values = cast(dict[UUID, str | Decimal | date | bool], values.pop("custom_values", {}))
        do_not_contact = bool(values.pop("do_not_contact", False))
        record: Company | Contact | Opportunity
        if entity_type == "account":
            record = Company(organisation_id=self.tenant.organisation_id, **values)
        elif entity_type == "contact":
            record = Contact(organisation_id=self.tenant.organisation_id, **values)
        else:
            record = Opportunity(
                organisation_id=self.tenant.organisation_id,
                stage_entered_at=None,
                stage_tracking_started_at=None,
                **values,
            )
        self.session.add(record)
        await self.session.flush()
        for field_key, value in values.items():
            if value is not None:
                self.session.add(self._change(entity_type, record.id, field_key, value))
        for definition_id, value in custom_values.items():
            definition = context.custom_fields[definition_id]
            custom = CRMCustomFieldValue(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                definition_id=definition_id,
                entity_type=entity_type,
                entity_id=record.id,
                source="crm_import",
                changed_by_user_id=self.tenant.user_id,
            )
            CRMService._assign_typed_value(custom, definition.field_type, value)
            self.session.add(custom)
            self.session.add(self._change(entity_type, record.id, f"custom.{definition.field_key}", value))
        if isinstance(record, Opportunity):
            stage = context.stages[record.pipeline_stage_id]  # type: ignore[index]
            self.session.add(
                OpportunityStageEvent(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    opportunity_id=record.id,
                    to_pipeline_id=record.pipeline_id,
                    to_stage_id=stage.id,
                    to_stage_name=stage.name,
                    to_stage_type=stage.stage_type,
                    changed_by_user_id=self.tenant.user_id,
                    source="import_baseline",
                    is_baseline=True,
                    idempotency_key=f"crm-import:{batch_id}:{row.source_row}",
                )
            )
        if isinstance(record, Contact) and do_not_contact and record.email:
            fingerprint = hmac.new(
                self.settings.outreach_suppression_hmac_key.get_secret_value().encode(),
                record.email.casefold().encode(),
                hashlib.sha256,
            ).hexdigest()
            self.session.add(
                ContactSuppression(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    contact_id=record.id,
                    email_fingerprint=fingerprint,
                    reason="manual_do_not_contact",
                    source="user",
                    active=True,
                    created_by_user_id=self.tenant.user_id,
                )
            )
        return record.id

    def _change(self, entity_type: CRMEntityType, entity_id: UUID, field_key: str, value: object) -> CRMRecordChange:
        json_value: object = str(value) if isinstance(value, (UUID, Decimal, date, datetime)) else value
        return CRMRecordChange(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_key=field_key,
            old_value_json=None,
            new_value_json=json_value,
            source="crm_import",
            changed_by_user_id=self.tenant.user_id,
        )

    async def _response(self, batch: CRMImportBatch, *, confirmed: bool) -> CRMImportPreviewResponse:
        rows = list(
            await self.session.scalars(
                select(CRMImportRow)
                .where(
                    CRMImportRow.organisation_id == self.tenant.organisation_id,
                    CRMImportRow.batch_id == batch.id,
                )
                .order_by(CRMImportRow.source_row)
            )
        )
        return CRMImportPreviewResponse(
            batch_id=batch.id,
            entity_type=cast(CRMEntityType, batch.entity_type),
            state=cast(
                Literal["previewed", "confirmed", "expired", "failed"], "confirmed" if confirmed else batch.state
            ),
            expires_at=batch.expires_at,
            row_count=batch.row_count,
            actionable_row_count=batch.actionable_row_count,
            imported_row_count=batch.imported_row_count,
            rows=[
                CRMImportRowResponse(
                    source_row=row.source_row,
                    disposition=cast(CRMImportDisposition, row.disposition),
                    issue_code=row.issue_code,
                    canonical_entity_id=row.canonical_entity_id,
                )
                for row in rows
            ],
        )

    async def _require_admin_native_crm(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Administrator access is required for CRM import.", 403)
        if not self.settings.feature_native_crm_enabled:
            raise PublicAPIError("crm_temporarily_unavailable", "CRM administration is temporarily unavailable.", 503)
        entitlement = await self.session.scalar(
            select(OrganisationModuleEntitlement).where(
                OrganisationModuleEntitlement.organisation_id == self.tenant.organisation_id,
                OrganisationModuleEntitlement.module_key == "crm",
                OrganisationModuleEntitlement.enabled.is_(True),
            )
        )
        setting = await self.session.scalar(
            select(OrganisationCRMSetting).where(
                OrganisationCRMSetting.organisation_id == self.tenant.organisation_id,
                OrganisationCRMSetting.mode == "native",
            )
        )
        if entitlement is None or setting is None:
            raise PublicAPIError("native_crm_required", "Choose and enable Native CRM before importing data.", 409)

    @staticmethod
    def _bounded(value: str | None, maximum: int, *, required: bool = False) -> str | None:
        if value is None or not value.strip():
            if required:
                raise ValueError
            return None
        cleaned = value.strip()
        if len(cleaned) > maximum:
            raise ValueError
        return cleaned

    @staticmethod
    def _integer(value: str | None) -> int | None:
        if value is None:
            return None
        result = int(value)
        if result < 0:
            raise ValueError
        return result

    @staticmethod
    def _decimal(value: str | None) -> Decimal | None:
        if value is None:
            return None
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result >= Decimal("10000000000000000"):
            raise ValueError
        return result.quantize(Decimal("0.01"))

    @staticmethod
    def _date(value: str | None) -> date | None:
        return date.fromisoformat(value) if value else None

    @staticmethod
    def _url(value: str | None) -> str | None:
        return validate_custom_url(value) if value else None

    @staticmethod
    def _boolean(value: str | None) -> bool:
        if value is None or value.casefold() in {"", "false", "no", "0", "n"}:
            return False
        if value.casefold() in {"true", "yes", "1", "y"}:
            return True
        raise ValueError
