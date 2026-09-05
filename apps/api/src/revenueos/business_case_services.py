from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Literal, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_case_contracts import (
    BusinessCaseApprovalRequest,
    BusinessCaseArchiveRequest,
    BusinessCaseCalculateRequest,
    BusinessCaseCreateRequest,
    BusinessCaseInputValue,
    BusinessCaseListResponse,
    BusinessCaseResponse,
    BusinessCaseReviewState,
    BusinessCaseState,
    BusinessCaseVersionResponse,
    CalculationInputResponse,
    CalculationOutputResponse,
    ModelState,
    ModelVersionState,
    ScenarioCalculationResponse,
    ScenarioOverride,
    SensitivityResponse,
    SensitivityRowResponse,
    ValueModelApprovalRequest,
    ValueModelArchiveRequest,
    ValueModelCreateRequest,
    ValueModelDefinition,
    ValueModelInputDefinition,
    ValueModelListResponse,
    ValueModelResponse,
    ValueModelVersionCreateRequest,
    ValueModelVersionResponse,
)
from revenueos.business_case_repositories import BusinessCaseRepository
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Company,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreateValueModel,
    CreateValueModelVersion,
    Opportunity,
)
from revenueos.tenant import TenantContext
from revenueos.value_model_engine import (
    ENGINE_VERSION,
    FormulaError,
    InputSpec,
    OutputSpec,
    ValidatedModel,
    calculate,
    load_validated_model,
    validate_model,
)

logger = logging.getLogger("revenueos.business_cases")

SUPPORTED_CURRENCIES = frozenset(
    {"AUD", "CAD", "CHF", "CNY", "DKK", "EUR", "GBP", "HKD", "INR", "JPY", "NOK", "NZD", "SEK", "SGD", "USD", "ZAR"}
)
MAX_ACTIVE_MODELS = 50
MAX_MODEL_VERSIONS = 50
MAX_ACTIVE_CASES_PER_ACCOUNT = 20
MAX_CASE_VERSIONS = 100

_ALLOWED_ORIGINS = {
    "reviewed_manual": {"salesperson_reported", "organisation_assumption", "user_entered", "unknown"},
    "customer_or_manual": {"validated_customer_evidence", "salesperson_reported", "user_entered"},
    "approved_org_only": {"organisation_assumption", "approved_company_data"},
    "public_or_manual": {"prospect_public", "salesperson_reported", "user_entered", "unknown"},
}


class BusinessCaseService:
    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = BusinessCaseRepository(session)

    async def list_value_models(self) -> ValueModelListResponse:
        await self._require_entitled(write=False)
        models = await self.repository.value_models(self.tenant.organisation_id, self.tenant.can_manage())
        items: list[ValueModelResponse] = []
        for model in models:
            version = await self.repository.latest_value_model_version(
                self.tenant.organisation_id,
                model.id,
                approved_only=not self.tenant.can_manage(),
            )
            if version is not None:
                items.append(self._model_response(model, version))
        return ValueModelListResponse(items=items, can_manage=self.tenant.can_manage())

    async def create_value_model(self, request: ValueModelCreateRequest) -> ValueModelResponse:
        await self._require_entitled()
        self._require_admin()
        existing = await self.repository.value_model_by_key(
            self.tenant.organisation_id, self.tenant.user_id, request.idempotency_key
        )
        if existing is not None:
            version = await self.repository.latest_value_model_version(self.tenant.organisation_id, existing.id)
            if version is None:
                raise PublicAPIError("value_model_unavailable", "The value model could not be loaded.", 409)
            return self._model_response(existing, version)
        if await self.repository.active_value_model_count(self.tenant.organisation_id) >= MAX_ACTIVE_MODELS:
            raise PublicAPIError("value_model_limit", "The active value-model limit has been reached.", 429)
        if await self.repository.value_model_by_name(self.tenant.organisation_id, request.name) is not None:
            raise PublicAPIError("value_model_name_conflict", "A value model with this name already exists.", 409)
        validated, definition_json, fingerprint = self._validated_definition(request.definition)
        model = CreateValueModel(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            name=request.name,
            description=request.description,
            state="active",
            created_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
        )
        version = CreateValueModelVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            model_id=model.id,
            version=1,
            state="draft",
            definition_json=definition_json,
            canonical_ast_json=validated.canonical_ast,
            formula_engine_version=ENGINE_VERSION,
            fingerprint=fingerprint,
            created_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
        )
        self.repository.add(model)
        self.repository.add(version)
        await self._commit("The value model could not be created.")
        self._audit(
            "value_model_created",
            model_id=model.id,
            version=1,
            inputs=len(request.definition.inputs),
            outputs=len(request.definition.outputs),
        )
        return self._model_response(model, version)

    async def get_value_model(self, model_id: UUID) -> ValueModelResponse:
        await self._require_entitled(write=False)
        model = await self.repository.value_model(self.tenant.organisation_id, model_id)
        if model is None or model.state == "archived" and not self.tenant.can_manage():
            raise PublicAPIError("value_model_not_found", "The value model was not found.", 404)
        version = await self.repository.latest_value_model_version(
            self.tenant.organisation_id, model.id, approved_only=not self.tenant.can_manage()
        )
        if version is None:
            raise PublicAPIError("value_model_not_found", "The value model was not found.", 404)
        return self._model_response(model, version)

    async def create_value_model_version(
        self,
        model_id: UUID,
        request: ValueModelVersionCreateRequest,
    ) -> ValueModelResponse:
        await self._require_entitled()
        self._require_admin()
        model = await self.repository.value_model(self.tenant.organisation_id, model_id)
        if model is None or model.state != "active":
            raise PublicAPIError("value_model_not_found", "The value model was not found.", 404)
        existing = await self.repository.value_model_version_by_key(
            self.tenant.organisation_id, model.id, request.idempotency_key
        )
        if existing is not None:
            return self._model_response(model, existing)
        count = await self.repository.value_model_version_count(self.tenant.organisation_id, model.id)
        if count >= MAX_MODEL_VERSIONS:
            raise PublicAPIError("value_model_version_limit", "The value-model version limit has been reached.", 429)
        validated, definition_json, fingerprint = self._validated_definition(request.definition)
        if request.name is not None and request.name.casefold() != model.name.casefold():
            duplicate = await self.repository.value_model_by_name(self.tenant.organisation_id, request.name)
            if duplicate is not None and duplicate.id != model.id:
                raise PublicAPIError("value_model_name_conflict", "A value model with this name already exists.", 409)
            model.name = request.name
        if request.description is not None:
            model.description = request.description
        version = CreateValueModelVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            model_id=model.id,
            version=count + 1,
            state="draft",
            definition_json=definition_json,
            canonical_ast_json=validated.canonical_ast,
            formula_engine_version=ENGINE_VERSION,
            fingerprint=fingerprint,
            created_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
        )
        self.repository.add(version)
        await self._commit("The value-model version could not be created.")
        self._audit("value_model_version_created", model_id=model.id, version=version.version)
        return self._model_response(model, version)

    async def approve_value_model(
        self,
        model_id: UUID,
        version_id: UUID,
        _: ValueModelApprovalRequest,
    ) -> ValueModelResponse:
        await self._require_entitled()
        self._require_admin()
        model, version = await self._model_and_version(model_id, version_id)
        if model.state != "active" or version.state != "draft":
            raise PublicAPIError("value_model_not_approvable", "Only an active draft version can be approved.", 409)
        definition = self._definition(version)
        self._validated_definition(definition)
        expired = [
            item.label
            for item in definition.inputs
            if item.review_expires_on and item.review_expires_on < datetime.now(UTC).date()
        ]
        if expired:
            raise PublicAPIError("assumption_review_expired", "An approved assumption review date has passed.", 409)
        version.state = "approved"
        version.approved_by_user_id = self.tenant.user_id
        version.approved_at = datetime.now(UTC)
        await self._commit("The value model could not be approved.")
        self._audit(
            "value_model_approved",
            model_id=model.id,
            version=version.version,
            inputs=len(definition.inputs),
            outputs=len(definition.outputs),
        )
        return self._model_response(model, version)

    async def archive_value_model(
        self,
        model_id: UUID,
        _: ValueModelArchiveRequest,
    ) -> ValueModelResponse:
        await self._require_entitled()
        self._require_admin()
        model = await self.repository.value_model(self.tenant.organisation_id, model_id)
        if model is None:
            raise PublicAPIError("value_model_not_found", "The value model was not found.", 404)
        model.state = "archived"
        model.archived_at = datetime.now(UTC)
        await self._commit("The value model could not be archived.")
        version = await self.repository.latest_value_model_version(self.tenant.organisation_id, model.id)
        if version is None:
            raise PublicAPIError("value_model_unavailable", "The value model could not be loaded.", 409)
        self._audit("value_model_archived", model_id=model.id)
        return self._model_response(model, version)

    async def list_business_cases(
        self,
        account_id: UUID | None = None,
        opportunity_id: UUID | None = None,
        approved_only: bool = False,
    ) -> BusinessCaseListResponse:
        await self._require_entitled(write=False)
        cases = await self.repository.business_cases(
            self.tenant.organisation_id,
            account_id=account_id,
            opportunity_id=opportunity_id,
            approved_only=approved_only,
        )
        items = [await self._case_response(item) for item in cases]
        return BusinessCaseListResponse(items=items, can_create=True)

    async def create_business_case(self, request: BusinessCaseCreateRequest) -> BusinessCaseResponse:
        await self._require_entitled()
        existing = await self.repository.business_case_by_key(
            self.tenant.organisation_id, self.tenant.user_id, request.idempotency_key
        )
        if existing is not None:
            return await self._case_response(existing)
        if request.currency not in SUPPORTED_CURRENCIES:
            raise PublicAPIError("unsupported_case_currency", "Choose a supported ISO 4217 case currency.", 422)
        account = await self.repository.company(self.tenant.organisation_id, request.account_id)
        if account is None:
            raise PublicAPIError("account_not_found", "The Account was not found.", 404)
        opportunity = await self._case_opportunity(request.opportunity_id, account.id)
        version = await self.repository.value_model_version(self.tenant.organisation_id, request.model_version_id)
        if version is None or version.state != "approved":
            raise PublicAPIError("approved_value_model_required", "Choose an approved value-model version.", 409)
        model = await self.repository.value_model(self.tenant.organisation_id, version.model_id)
        latest = await self.repository.latest_value_model_version(
            self.tenant.organisation_id, version.model_id, approved_only=True
        )
        if model is None or model.state != "active" or latest is None or latest.id != version.id:
            raise PublicAPIError(
                "approved_value_model_required", "Choose the latest approved value-model version.", 409
            )
        if (
            await self.repository.active_case_count_for_account(self.tenant.organisation_id, account.id)
            >= MAX_ACTIVE_CASES_PER_ACCOUNT
        ):
            raise PublicAPIError(
                "business_case_limit", "The active Business Case limit for this Account has been reached.", 429
            )
        title = request.title or f"{account.name} {model.name} Business Case"
        business_case = CreateBusinessCase(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            account_id=account.id,
            opportunity_id=opportunity.id if opportunity else None,
            model_id=model.id,
            model_version_id=version.id,
            created_by_user_id=self.tenant.user_id,
            title=title,
            currency=request.currency,
            state="draft",
            idempotency_key=request.idempotency_key,
        )
        self.repository.add(business_case)
        await self._commit("The Business Case could not be created.")
        self._audit(
            "business_case_created", case_id=business_case.id, model_id=model.id, opportunity=opportunity is not None
        )
        return await self._case_response(business_case)

    async def get_business_case(self, case_id: UUID) -> BusinessCaseResponse:
        await self._require_entitled(write=False)
        business_case = await self._case(case_id)
        return await self._case_response(business_case, revalidate_sources=True)

    async def calculate_business_case(
        self,
        case_id: UUID,
        request: BusinessCaseCalculateRequest,
    ) -> BusinessCaseResponse:
        await self._require_entitled()
        calculation_started = perf_counter()
        business_case = await self._case(case_id)
        if business_case.state == "archived":
            raise PublicAPIError("business_case_archived", "An archived Business Case cannot be recalculated.", 409)
        existing = await self.repository.business_case_version_by_key(
            self.tenant.organisation_id, business_case.id, request.idempotency_key
        )
        if existing is not None:
            return await self._case_response(business_case)
        model_version = await self.repository.value_model_version(
            self.tenant.organisation_id, business_case.model_version_id
        )
        if model_version is None or model_version.state != "approved":
            raise PublicAPIError(
                "value_model_version_unavailable", "The approved value-model version is unavailable.", 409
            )
        definition = self._definition(model_version)
        definition_json = cast(dict[str, object], definition.model_dump(mode="json", by_alias=True))
        expected_fingerprint = self._hash_json(
            {
                "engineVersion": ENGINE_VERSION,
                "definition": definition_json,
                "canonicalAst": model_version.canonical_ast_json,
            }
        )
        if expected_fingerprint != model_version.fingerprint or model_version.formula_engine_version != ENGINE_VERSION:
            raise PublicAPIError(
                "value_model_integrity_failed", "The approved value model failed its integrity check.", 409
            )
        try:
            engine_model = load_validated_model(
                [
                    InputSpec(
                        key=item.key,
                        unit=item.unit,
                        minimum=item.minimum,
                        maximum=item.maximum,
                    )
                    for item in definition.inputs
                ],
                [
                    OutputSpec(
                        key=item.key,
                        unit=item.unit,
                        formula=item.formula,
                        display_precision=item.display_precision,
                    )
                    for item in definition.outputs
                ],
                model_version.canonical_ast_json,
            )
        except FormulaError as exc:
            raise PublicAPIError(
                "value_model_integrity_failed",
                "The approved value model failed its integrity check.",
                409,
            ) from exc
        account = await self.repository.company(self.tenant.organisation_id, business_case.account_id)
        if account is None:
            raise PublicAPIError("account_not_found", "The Account was not found.", 404)
        opportunity = await self._case_opportunity(business_case.opportunity_id, account.id)
        input_rows, values, fingerprint_inputs = await self._validate_inputs(
            definition, request.inputs, account, opportunity, business_case
        )
        scenario_rows: list[ScenarioCalculationResponse] = [
            ScenarioCalculationResponse(
                name="base",
                overrides=[],
                outputs=self._calculate_outputs(engine_model, definition, values),
            )
        ]
        scenario_fingerprint: list[dict[str, object]] = []
        for scenario in request.scenarios:
            scenario_values = dict(values)
            overrides: list[ScenarioOverride] = []
            for override in scenario.overrides:
                item = self._input_definition(definition, override.key)
                if not item.sensitivity_eligible:
                    raise PublicAPIError(
                        "scenario_input_not_allowed", f"{item.label} is not approved for scenarios.", 422
                    )
                value = self._validated_input_decimal(item, override.value)
                scenario_values[item.key] = value
                overrides.append(ScenarioOverride(key=item.key, value=self._decimal_string(value)))
            scenario_rows.append(
                ScenarioCalculationResponse(
                    name=scenario.name,
                    overrides=overrides,
                    outputs=self._calculate_outputs(engine_model, definition, scenario_values),
                )
            )
            scenario_fingerprint.append(
                {"name": scenario.name, "overrides": [item.model_dump(mode="json") for item in overrides]}
            )
        sensitivity = self._calculate_sensitivity(engine_model, definition, values, request)
        fingerprint_payload = {
            "modelVersionId": str(model_version.id),
            "modelFingerprint": model_version.fingerprint,
            "currency": await self._case_currency(business_case),
            "inputs": fingerprint_inputs,
            "scenarios": scenario_fingerprint,
            "sensitivity": request.sensitivity.model_dump(mode="json") if request.sensitivity else None,
        }
        calculation_fingerprint = self._hash_json(fingerprint_payload)
        latest = await self.repository.latest_business_case_version(self.tenant.organisation_id, business_case.id)
        if latest is not None and latest.calculation_fingerprint == calculation_fingerprint:
            return await self._case_response(business_case)
        if latest is not None and latest.version >= MAX_CASE_VERSIONS:
            raise PublicAPIError(
                "business_case_version_limit", "The Business Case version limit has been reached.", 429
            )
        currency = cast(str, fingerprint_payload["currency"])
        now = datetime.now(UTC)
        version = CreateBusinessCaseVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            case_id=business_case.id,
            model_id=model_version.model_id,
            model_version_id=model_version.id,
            version=(latest.version + 1) if latest else 1,
            currency=currency,
            formula_engine_version=ENGINE_VERSION,
            model_fingerprint=model_version.fingerprint,
            calculation_fingerprint=calculation_fingerprint,
            inputs_json=[item.model_dump(mode="json", by_alias=True) for item in input_rows],
            scenarios_json=[item.model_dump(mode="json", by_alias=True) for item in scenario_rows],
            sensitivity_json=sensitivity.model_dump(mode="json", by_alias=True) if sensitivity else None,
            lineage_json=self._lineage(definition, model_version, scenario_rows),
            review_state="pending",
            created_by_user_id=self.tenant.user_id,
            idempotency_key=request.idempotency_key,
            created_at=now,
        )
        self.repository.add(version)
        business_case.state = "needs_review" if any(item.freshness == "stale" for item in input_rows) else "calculated"
        await self._commit("The Business Case could not be calculated.")
        self._audit(
            "business_case_calculated",
            case_id=business_case.id,
            version=version.version,
            input_count=len(input_rows),
            output_count=len(definition.outputs),
            scenario_count=len(scenario_rows),
            sensitivity_rows=len(sensitivity.rows) if sensitivity else 0,
            duration_ms=round((perf_counter() - calculation_started) * 1000),
        )
        return await self._case_response(business_case)

    async def approve_business_case(
        self,
        case_id: UUID,
        _: BusinessCaseApprovalRequest,
    ) -> BusinessCaseResponse:
        await self._require_entitled()
        business_case = await self._case(case_id)
        version = await self.repository.latest_business_case_version(self.tenant.organisation_id, business_case.id)
        if version is None or version.review_state != "pending" or business_case.state != "calculated":
            raise PublicAPIError(
                "business_case_not_approvable", "Calculate and review the current Business Case first.", 409
            )
        if await self._source_review_required(version):
            business_case.state = "needs_review"
            await self._commit("The Business Case source state could not be updated.")
            raise PublicAPIError(
                "business_case_sources_need_review", "One or more Business Case inputs need review.", 409
            )
        version.review_state = "approved"
        version.approved_by_user_id = self.tenant.user_id
        version.approved_at = datetime.now(UTC)
        business_case.state = "approved"
        await self._commit("The Business Case could not be approved.")
        self._audit("business_case_approved", case_id=business_case.id, version=version.version)
        return await self._case_response(business_case)

    async def archive_business_case(
        self,
        case_id: UUID,
        _: BusinessCaseArchiveRequest,
    ) -> BusinessCaseResponse:
        await self._require_entitled()
        business_case = await self._case(case_id)
        business_case.state = "archived"
        business_case.archived_at = datetime.now(UTC)
        await self._commit("The Business Case could not be archived.")
        self._audit("business_case_archived", case_id=business_case.id)
        return await self._case_response(business_case)

    async def _validate_inputs(
        self,
        definition: ValueModelDefinition,
        supplied: list[BusinessCaseInputValue],
        account: Company,
        opportunity: Opportunity | None,
        business_case: CreateBusinessCase,
    ) -> tuple[list[CalculationInputResponse], dict[str, Decimal], list[dict[str, object]]]:
        supplied_by_key = {item.key: item for item in supplied}
        expected = {item.key for item in definition.inputs}
        missing = expected - set(supplied_by_key)
        unknown = set(supplied_by_key) - expected
        if missing:
            item = self._input_definition(definition, sorted(missing)[0])
            raise PublicAPIError(
                "business_case_input_missing", f"{item.label} is required; RevenueOS will not invent it.", 422
            )
        if unknown:
            raise PublicAPIError(
                "business_case_input_unknown", "An input is not part of the approved value model.", 422
            )
        now = datetime.now(UTC)
        rows: list[CalculationInputResponse] = []
        values: dict[str, Decimal] = {}
        fingerprint: list[dict[str, object]] = []
        for definition_item in sorted(definition.inputs, key=lambda item: item.display_order):
            request_item = supplied_by_key[definition_item.key]
            value = self._validated_input_decimal(definition_item, request_item.value)
            if request_item.origin not in _ALLOWED_ORIGINS[definition_item.source_policy]:
                raise PublicAPIError(
                    "input_origin_not_allowed", f"{definition_item.label} does not allow that source type.", 422
                )
            source_id, source_label, observed_at = await self._validate_input_origin(
                definition_item,
                request_item,
                value,
                account,
                opportunity,
                business_case,
                now,
            )
            freshness: Literal["current", "stale", "unknown", "deleted_source"] = "current"
            observed_at = self._as_utc(observed_at)
            if definition_item.max_source_age_days and observed_at < now - timedelta(
                days=definition_item.max_source_age_days
            ):
                freshness = "stale"
            calculation_value = value / Decimal("100") if definition_item.unit == "percentage" else value
            rows.append(
                CalculationInputResponse(
                    key=definition_item.key,
                    label=definition_item.label,
                    value=self._decimal_string(value),
                    calculation_value=self._decimal_string(calculation_value),
                    unit=definition_item.unit,
                    origin=request_item.origin,
                    source_id=source_id,
                    source_label=source_label,
                    assumption=request_item.origin in {"organisation_assumption", "user_entered", "unknown"},
                    material=definition_item.material,
                    customer_facing=definition_item.customer_facing,
                    observed_at=observed_at,
                    freshness=freshness,
                )
            )
            values[definition_item.key] = value
            fingerprint.append(
                {
                    "key": definition_item.key,
                    "value": self._decimal_string(value),
                    "origin": request_item.origin,
                    "sourceId": str(source_id) if source_id else None,
                    "observedAt": request_item.observed_at.isoformat() if request_item.observed_at else None,
                }
            )
        return rows, values, fingerprint

    async def _validate_input_origin(
        self,
        definition: ValueModelInputDefinition,
        supplied: BusinessCaseInputValue,
        value: Decimal,
        account: Company,
        opportunity: Opportunity | None,
        business_case: CreateBusinessCase,
        now: datetime,
    ) -> tuple[UUID | None, str, datetime]:
        if definition.assumption_locked and (
            supplied.origin != definition.default_origin or value != definition.default_value
        ):
            raise PublicAPIError("locked_assumption", f"{definition.label} is an approved locked assumption.", 422)
        if supplied.origin == "organisation_assumption":
            if definition.default_origin != "organisation_assumption" or value != definition.default_value:
                raise PublicAPIError(
                    "unapproved_assumption", f"{definition.label} must use its visible approved assumption.", 422
                )
            return None, "Approved organisation assumption", supplied.observed_at or now
        if supplied.origin == "approved_company_data":
            if definition.default_origin == "approved_company_data" and value == definition.default_value:
                return None, "Approved company data", supplied.observed_at or now
            if (
                definition.key == "employee_count"
                and account.employee_count is not None
                and value == account.employee_count
            ):
                return account.id, "Canonical Account employee count", supplied.observed_at or account.updated_at
            raise PublicAPIError(
                "approved_company_value_mismatch", f"{definition.label} does not match approved company data.", 422
            )
        if supplied.origin == "validated_customer_evidence":
            raise PublicAPIError(
                "typed_numeric_evidence_unavailable",
                "Current Evidence has no reviewed typed numeric value for automatic use; enter the number as seller-reported and link the source.",
                422,
            )
        if supplied.origin == "prospect_public":
            raise PublicAPIError(
                "typed_public_number_unavailable",
                "Public ranges or text cannot become an exact Business Case input automatically; enter a reviewed assumption instead.",
                422,
            )
        if supplied.origin == "salesperson_reported":
            observed_at = supplied.observed_at or now
            if supplied.source_id is not None:
                evidence = await self.repository.evidence(self.tenant.organisation_id, supplied.source_id)
                if evidence is None or evidence.lifecycle_status != "available":
                    raise PublicAPIError("input_source_unavailable", "The linked Evidence source is unavailable.", 409)
                observed_at = supplied.observed_at or evidence.captured_at
                return evidence.id, "Linked Evidence; numeric value entered by seller", observed_at
            return None, "Reported by you", observed_at
        if supplied.source_id is not None:
            raise PublicAPIError("input_source_not_allowed", "That input origin cannot carry a source identifier.", 422)
        if supplied.origin == "user_entered":
            return None, "Entered by you", supplied.observed_at or now
        if supplied.origin == "unknown":
            return None, "Source unknown — review required", supplied.observed_at or now
        raise PublicAPIError("input_origin_invalid", "The input origin is not supported.", 422)

    def _calculate_outputs(
        self,
        model: ValidatedModel,
        definition: ValueModelDefinition,
        values: dict[str, Decimal],
    ) -> list[CalculationOutputResponse]:
        try:
            result = calculate(model, values)
        except FormulaError as exc:
            raise PublicAPIError(exc.code, str(exc), 422) from exc
        definitions = {item.key: item for item in definition.outputs}
        return [
            CalculationOutputResponse(
                key=item.key,
                label=definitions[item.key].label,
                description=definitions[item.key].description,
                unit=item.unit,
                exact_value=item.exact_value,
                display_value=item.display_value,
                unavailable_reason=item.unavailable_reason,
                formula=item.formula,
                input_dependencies=list(item.input_dependencies),
                output_dependencies=list(item.output_dependencies),
                customer_facing=definitions[item.key].customer_facing,
                highlight=definitions[item.key].highlight,
            )
            for item in result.outputs
        ]

    def _calculate_sensitivity(
        self,
        model: ValidatedModel,
        definition: ValueModelDefinition,
        base_values: dict[str, Decimal],
        request: BusinessCaseCalculateRequest,
    ) -> SensitivityResponse | None:
        if request.sensitivity is None:
            return None
        input_definition = self._input_definition(definition, request.sensitivity.input_key)
        if not input_definition.sensitivity_eligible:
            raise PublicAPIError(
                "sensitivity_input_not_allowed", f"{input_definition.label} is not approved for sensitivity.", 422
            )
        rows: list[SensitivityRowResponse] = []
        for raw in request.sensitivity.values:
            value = self._validated_input_decimal(input_definition, raw)
            values = dict(base_values)
            values[input_definition.key] = value
            rows.append(
                SensitivityRowResponse(
                    input_value=self._decimal_string(value),
                    outputs=self._calculate_outputs(model, definition, values),
                )
            )
        return SensitivityResponse(input_key=input_definition.key, rows=rows)

    async def _case_response(
        self,
        business_case: CreateBusinessCase,
        revalidate_sources: bool = False,
    ) -> BusinessCaseResponse:
        await self.session.refresh(business_case)
        current = await self.repository.latest_business_case_version(self.tenant.organisation_id, business_case.id)
        effective_needs_review = False
        if revalidate_sources and current is not None and business_case.state == "approved":
            effective_needs_review = await self._source_review_required(current)
            if effective_needs_review:
                business_case.state = "needs_review"
                await self._commit("The Business Case source state could not be updated.")
                await self.session.refresh(business_case)
        account = await self.repository.company(self.tenant.organisation_id, business_case.account_id)
        opportunity = (
            await self.repository.opportunity(self.tenant.organisation_id, business_case.opportunity_id)
            if business_case.opportunity_id
            else None
        )
        model = await self.repository.value_model(self.tenant.organisation_id, business_case.model_id)
        model_version = await self.repository.value_model_version(
            self.tenant.organisation_id,
            business_case.model_version_id,
        )
        if account is None or model is None or model_version is None:
            raise PublicAPIError("business_case_unavailable", "The Business Case could not be loaded.", 409)
        try:
            model_definition = ValueModelDefinition.model_validate(model_version.definition_json)
        except ValidationError as exc:
            raise PublicAPIError(
                "value_model_snapshot_invalid", "The Value Model snapshot failed validation.", 409
            ) from exc
        version_response = await self._case_version_response(current) if current else None
        if effective_needs_review and version_response is not None:
            version_response.review_state = "needs_review"
        return BusinessCaseResponse(
            id=business_case.id,
            title=business_case.title,
            account_id=business_case.account_id,
            account_name=account.name,
            opportunity_id=business_case.opportunity_id,
            opportunity_name=opportunity.name if opportunity else None,
            model_id=business_case.model_id,
            model_name=model.name,
            model_version_id=model_version.id,
            model_version=model_version.version,
            model_definition=model_definition,
            currency=business_case.currency,
            state=cast(BusinessCaseState, business_case.state),
            current_version=version_response,
            created_by_user_id=business_case.created_by_user_id,
            created_at=business_case.created_at,
            updated_at=business_case.updated_at,
        )

    async def _case_version_response(
        self,
        version: CreateBusinessCaseVersion,
    ) -> BusinessCaseVersionResponse:
        model_version = await self.repository.value_model_version(self.tenant.organisation_id, version.model_version_id)
        if model_version is None:
            raise PublicAPIError("value_model_version_unavailable", "The value-model version is unavailable.", 409)
        try:
            inputs = [CalculationInputResponse.model_validate(item) for item in version.inputs_json]
            scenarios = [ScenarioCalculationResponse.model_validate(item) for item in version.scenarios_json]
            sensitivity = (
                SensitivityResponse.model_validate(version.sensitivity_json) if version.sensitivity_json else None
            )
        except ValidationError as exc:
            raise PublicAPIError(
                "business_case_snapshot_invalid", "The Business Case snapshot failed validation.", 409
            ) from exc
        return BusinessCaseVersionResponse(
            id=version.id,
            version=version.version,
            currency=version.currency,
            model_version_id=version.model_version_id,
            model_version=model_version.version,
            formula_engine_version=cast(Literal["bounded_decimal_v1"], version.formula_engine_version),
            model_fingerprint=version.model_fingerprint,
            calculation_fingerprint=version.calculation_fingerprint,
            inputs=inputs,
            scenarios=scenarios,
            sensitivity=sensitivity,
            review_state=cast(BusinessCaseReviewState, version.review_state),
            approved_by_user_id=version.approved_by_user_id,
            approved_at=version.approved_at,
            created_by_user_id=version.created_by_user_id,
            created_at=version.created_at,
        )

    async def _source_review_required(self, version: CreateBusinessCaseVersion) -> bool:
        now = datetime.now(UTC)
        model_version = await self.repository.value_model_version(
            self.tenant.organisation_id,
            version.model_version_id,
        )
        if model_version is None:
            return True
        try:
            definition = self._definition(model_version)
        except PublicAPIError:
            return True
        definitions = {item.key: item for item in definition.inputs}
        business_case: CreateBusinessCase | None = None
        account: Company | None = None
        for raw in version.inputs_json:
            try:
                item = CalculationInputResponse.model_validate(raw)
            except ValidationError:
                return True
            if item.freshness in {"stale", "deleted_source"} or item.origin == "unknown":
                return True
            if item.source_id is not None and item.origin == "salesperson_reported":
                evidence = await self.repository.evidence(self.tenant.organisation_id, item.source_id)
                if evidence is None or evidence.lifecycle_status != "available":
                    return True
            if item.source_id is not None and item.origin == "approved_company_data":
                if business_case is None:
                    business_case = await self.repository.business_case(
                        self.tenant.organisation_id,
                        version.case_id,
                    )
                if business_case is None or item.source_id != business_case.account_id:
                    return True
                if account is None:
                    account = await self.repository.company(
                        self.tenant.organisation_id,
                        business_case.account_id,
                    )
                if (
                    account is None
                    or item.key != "employee_count"
                    or account.employee_count is None
                    or Decimal(item.value) != Decimal(account.employee_count)
                ):
                    return True
            if self._as_utc(item.observed_at) > now + timedelta(minutes=5):
                return True
            input_definition = definitions.get(item.key)
            if input_definition is None:
                return True
            if (
                input_definition.max_source_age_days is not None
                and self._as_utc(item.observed_at) + timedelta(days=input_definition.max_source_age_days) < now
            ):
                return True
            if input_definition.review_expires_on is not None and input_definition.review_expires_on < now.date():
                return True
        return False

    def _validated_definition(
        self,
        definition: ValueModelDefinition,
    ) -> tuple[ValidatedModel, dict[str, object], str]:
        if any(not item.required for item in definition.inputs):
            raise PublicAPIError(
                "optional_inputs_not_supported",
                "Every v1 value-model input must be explicit and required; hidden optional defaults are not supported.",
                422,
            )
        try:
            validated = validate_model(
                [
                    InputSpec(
                        key=item.key,
                        unit=item.unit,
                        minimum=item.minimum,
                        maximum=item.maximum,
                    )
                    for item in definition.inputs
                ],
                [
                    OutputSpec(
                        key=item.key,
                        unit=item.unit,
                        formula=item.formula,
                        display_precision=item.display_precision,
                    )
                    for item in definition.outputs
                ],
            )
        except FormulaError as exc:
            raise PublicAPIError(exc.code, str(exc), 422) from exc
        definition_json = cast(dict[str, object], definition.model_dump(mode="json", by_alias=True))
        fingerprint = self._hash_json(
            {"engineVersion": ENGINE_VERSION, "definition": definition_json, "canonicalAst": validated.canonical_ast}
        )
        return validated, definition_json, fingerprint

    def _definition(self, version: CreateValueModelVersion) -> ValueModelDefinition:
        try:
            return ValueModelDefinition.model_validate(version.definition_json)
        except ValidationError as exc:
            raise PublicAPIError(
                "value_model_definition_invalid", "The value-model definition failed validation.", 409
            ) from exc

    async def _model_and_version(
        self,
        model_id: UUID,
        version_id: UUID,
    ) -> tuple[CreateValueModel, CreateValueModelVersion]:
        model = await self.repository.value_model(self.tenant.organisation_id, model_id)
        version = await self.repository.value_model_version(self.tenant.organisation_id, version_id)
        if model is None or version is None or version.model_id != model.id:
            raise PublicAPIError("value_model_not_found", "The value model was not found.", 404)
        return model, version

    def _model_response(
        self,
        model: CreateValueModel,
        version: CreateValueModelVersion,
    ) -> ValueModelResponse:
        definition = self._definition(version)
        return ValueModelResponse(
            id=model.id,
            name=model.name,
            description=model.description,
            state=cast(ModelState, model.state),
            latest_version=ValueModelVersionResponse(
                id=version.id,
                version=version.version,
                state=cast(ModelVersionState, version.state),
                definition=definition,
                formula_engine_version=cast(Literal["bounded_decimal_v1"], version.formula_engine_version),
                fingerprint=version.fingerprint,
                approved_by_user_id=version.approved_by_user_id,
                approved_at=version.approved_at,
                created_by_user_id=version.created_by_user_id,
                created_at=version.created_at,
            ),
            can_manage=self.tenant.can_manage(),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _validated_input_decimal(self, definition: ValueModelInputDefinition, raw: str) -> Decimal:
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise PublicAPIError("invalid_decimal", f"{definition.label} must be a decimal number.", 422) from exc
        if not value.is_finite() or len(value.as_tuple().digits) > 28:
            raise PublicAPIError("decimal_out_of_range", f"{definition.label} is outside the supported range.", 422)
        if definition.minimum is not None and value < definition.minimum:
            raise PublicAPIError("input_below_minimum", f"{definition.label} is below its approved minimum.", 422)
        if definition.maximum is not None and value > definition.maximum:
            raise PublicAPIError("input_above_maximum", f"{definition.label} is above its approved maximum.", 422)
        if definition.value_type in {"integer", "count"} and value != value.to_integral_value():
            raise PublicAPIError("integer_input_required", f"{definition.label} must be a whole number.", 422)
        raw_exponent = value.as_tuple().exponent
        exponent = -raw_exponent if isinstance(raw_exponent, int) and raw_exponent < 0 else 0
        if exponent > definition.decimal_precision:
            raise PublicAPIError(
                "input_precision_exceeded",
                f"{definition.label} allows at most {definition.decimal_precision} decimal places.",
                422,
            )
        return value

    @staticmethod
    def _input_definition(definition: ValueModelDefinition, key: str) -> ValueModelInputDefinition:
        item = next((candidate for candidate in definition.inputs if candidate.key == key), None)
        if item is None:
            raise PublicAPIError(
                "business_case_input_unknown", "An input is not part of the approved value model.", 422
            )
        return item

    async def _case(self, case_id: UUID) -> CreateBusinessCase:
        value = await self.repository.business_case(self.tenant.organisation_id, case_id)
        if value is None:
            raise PublicAPIError("business_case_not_found", "The Business Case was not found.", 404)
        return value

    async def _case_opportunity(self, opportunity_id: UUID | None, account_id: UUID) -> Opportunity | None:
        if opportunity_id is None:
            return None
        opportunity = await self.repository.opportunity(self.tenant.organisation_id, opportunity_id)
        if opportunity is None:
            raise PublicAPIError("opportunity_not_found", "The Opportunity was not found.", 404)
        if opportunity.company_id != account_id:
            raise PublicAPIError(
                "opportunity_account_mismatch", "The Opportunity does not belong to the selected Account.", 409
            )
        return opportunity

    async def _case_currency(self, business_case: CreateBusinessCase) -> str:
        return business_case.currency

    def _lineage(
        self,
        definition: ValueModelDefinition,
        model_version: CreateValueModelVersion,
        scenarios: list[ScenarioCalculationResponse],
    ) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "modelVersionId": str(model_version.id),
            "modelFingerprint": model_version.fingerprint,
            "formulaEngineVersion": ENGINE_VERSION,
            "outputs": {
                scenario.name: [
                    {
                        "key": output.key,
                        "formula": output.formula,
                        "inputDependencies": output.input_dependencies,
                        "outputDependencies": output.output_dependencies,
                    }
                    for output in scenario.outputs
                ]
                for scenario in scenarios
            },
            "materialInputKeys": [item.key for item in definition.inputs if item.material],
        }

    async def _require_entitled(self, *, write: bool = True) -> None:
        commercial = CommercialService(self.session, self.settings)
        if write:
            if not self.settings.feature_create_enabled:
                raise PublicAPIError("create_unavailable", "RevenueOS Create is temporarily unavailable.", 503)
            await commercial.require_module_write(self.tenant.organisation_id, "create")
            return
        access = await commercial.module_access(self.tenant.organisation_id, "create")
        if access == "none":
            raise PublicAPIError(
                "create_not_in_plan", "Create isn't included in your organisation's current plan.", 403
            )

    def _require_admin(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "An organisation administrator must manage value models.", 403)

    async def _commit(self, message: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("business_case_conflict", message, 409) from exc

    @staticmethod
    def _hash_json(value: object) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _decimal_string(value: Decimal) -> str:
        return format(value, "f")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.utcoffset() is None else value.astimezone(UTC)

    def _audit(self, event: str, **metadata: object) -> None:
        logger.info(
            event,
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                **metadata,
            },
        )
