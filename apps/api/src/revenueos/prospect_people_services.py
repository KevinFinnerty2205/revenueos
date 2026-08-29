from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.crm_history import crm_creation_changes
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Contact,
    ContactFieldSource,
    ProspectContactPoint,
    ProspectPerson,
    ProspectResearchRun,
    ProspectResearchSource,
    ProspectResearchTarget,
    ProspectUsageCounter,
)
from revenueos.prospect_contracts import (
    ResearchChangeResponse,
    ResearchObservationResponse,
    ResearchRunSummary,
    ResearchSourceResponse,
)
from revenueos.prospect_people_contracts import (
    BuyingCommitteeGapResponse,
    BuyingRoleHypothesisResponse,
    BuyingRoleReviewRequest,
    ContactPointResponse,
    ContactProspectResearchLinkResponse,
    ExistingContactMatchResponse,
    PersonDiscoveryResponse,
    PersonPromotionRequest,
    PersonPromotionResponse,
    PersonResearchBriefResponse,
    PersonResearchRequest,
    ProspectPersonResponse,
    RelevantFunctionResponse,
)
from revenueos.prospect_provider import (
    PersonCandidate,
    ProspectProviderError,
    ProspectResearchProvider,
    ResearchTargetSnapshot,
    create_prospect_provider,
)
from revenueos.prospect_repositories import ACTIVE_RUN_STATUSES, USABLE_RUN_STATUSES, ProspectRepository
from revenueos.prospect_url_security import PublicUrlSafetyError, canonicalize_public_https_url
from revenueos.prospect_validation import validate_person_candidate
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.prospect_people")
PERSON_RESEARCH_SCHEMA_VERSION = 1
PERSON_HISTORY_LIMIT = 10
CustomerResearchStatus = Literal["pending", "researching", "ready", "partial", "failed"]

RELEVANT_FUNCTIONS = (
    RelevantFunctionResponse(
        function_key="technology",
        label="Technology",
        why_it_may_matter="May evaluate technical fit and technology strategy.",
    ),
    RelevantFunctionResponse(
        function_key="security",
        label="Information Security",
        why_it_may_matter="May evaluate security and privacy requirements.",
    ),
    RelevantFunctionResponse(
        function_key="finance",
        label="Finance",
        why_it_may_matter="May influence commercial approval and budget review.",
    ),
    RelevantFunctionResponse(
        function_key="procurement",
        label="Procurement",
        why_it_may_matter="May manage purchasing and supplier review.",
    ),
    RelevantFunctionResponse(
        function_key="operations",
        label="Operations",
        why_it_may_matter="May own the operational problem and implementation context.",
    ),
)


class ProspectPeopleService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        provider: ProspectResearchProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = ProspectRepository(session)
        self.provider = provider or create_prospect_provider(settings.prospect_research_provider_name)

    async def list_people(self, target_id: UUID) -> PersonDiscoveryResponse:
        await self._require_entitled()
        target = await self._ready_company_target(target_id)
        people = await self.repository.people_for_target(self.tenant.organisation_id, target.id)
        return await self._discovery_response(target, people, discovered=False)

    async def discover_people(self, target_id: UUID) -> PersonDiscoveryResponse:
        await self._require_entitled()
        target = await self._ready_company_target(target_id)
        await self.repository.lock_organisation(self.tenant.organisation_id)
        await self._reserve_discovery_usage()
        try:
            candidates = await self.provider.discover_people(
                self._target_snapshot(target),
                limit=self.settings.private_beta_max_prospect_people_per_discovery,
            )
            validated = [self._validate_candidate(target, candidate) for candidate in candidates]
        except (ProspectProviderError, PublicUrlSafetyError, ValueError) as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "people_discovery_unavailable",
                "RevenueOS couldn’t find reliable professional people for this company right now.",
                503,
            ) from exc
        if len(validated) > self.settings.private_beta_max_prospect_people_per_discovery:
            await self.repository.rollback()
            raise PublicAPIError("people_result_limit", "The people provider returned too many candidates.", 503)

        now = datetime.now(UTC)
        for candidate in validated:
            person = await self.repository.person_by_provider_identity(
                self.tenant.organisation_id,
                target.id,
                self.provider.provider_key,
                candidate.person_id,
            )
            if person is None:
                person = ProspectPerson(
                    organisation_id=self.tenant.organisation_id,
                    target_id=target.id,
                    provider_key=self.provider.provider_key,
                    provider_person_id=candidate.person_id,
                    display_name=candidate.display_name,
                    first_name=candidate.first_name,
                    last_name=candidate.last_name,
                    current_role=candidate.current_role,
                    current_company=candidate.current_company,
                    public_professional_location=candidate.public_professional_location,
                    public_profile_url=candidate.public_profile_url,
                    relevant_function=candidate.relevant_function,
                    why_may_matter=candidate.why_may_matter,
                    discovery_source=candidate.discovery_source,
                    provider_attribution=candidate.provider_attribution,
                    identity_state=candidate.identity_state,
                    employment_state=candidate.employment_state.value,
                    created_at=now,
                    updated_at=now,
                )
                self.repository.add(person)
            else:
                person.current_role = candidate.current_role
                person.current_company = candidate.current_company
                person.public_professional_location = candidate.public_professional_location
                person.public_profile_url = candidate.public_profile_url
                person.relevant_function = candidate.relevant_function
                person.why_may_matter = candidate.why_may_matter
                person.identity_state = candidate.identity_state
                person.employment_state = candidate.employment_state.value
                person.updated_at = now
        target.updated_at = now
        await self._commit("The people discovery results could not be saved.")
        people = await self.repository.people_for_target(self.tenant.organisation_id, target.id)
        logger.info(
            "people_discovery_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "target_id": str(target.id),
                "result_count": len(people),
                "provider": self.provider.provider_key,
            },
        )
        return await self._discovery_response(target, people, discovered=True)

    async def research_person(self, person_id: UUID, request: PersonResearchRequest) -> PersonResearchBriefResponse:
        await self._require_entitled()
        person = await self._ready_person(person_id, for_update=True)
        active = await self.repository.active_person_run(self.tenant.organisation_id, person.id)
        if active is not None:
            await self.repository.commit()
            return await self.get_person_research(person.id)
        fresh = await self.repository.fresh_person_run(
            self.tenant.organisation_id,
            person.id,
            fresh_after=datetime.now(UTC) - timedelta(days=self.settings.private_beta_prospect_fresh_days),
        )
        if fresh is not None:
            await self.repository.commit()
            return await self.get_person_research(person.id)
        default_key = self._fingerprint(
            "person-initial",
            str(self.tenant.organisation_id),
            str(person.target_id),
            str(person.id),
            self.provider.provider_key,
            self.provider.provider_version,
        )
        await self._queue_person_run(person, request.idempotency_key or default_key, refresh_of_run_id=None)
        return await self.get_person_research(person.id)

    async def refresh_person(self, person_id: UUID, request: PersonResearchRequest) -> PersonResearchBriefResponse:
        await self._require_entitled()
        person = await self._ready_person(person_id, for_update=True)
        active = await self.repository.active_person_run(self.tenant.organisation_id, person.id)
        if active is not None:
            await self.repository.commit()
            return await self.get_person_research(person.id)
        current = await self.repository.current_person_run(self.tenant.organisation_id, person.id)
        raw_key = request.idempotency_key or f"refresh:{uuid.uuid4()}"
        await self._queue_person_run(person, raw_key, refresh_of_run_id=current.id if current else None)
        return await self.get_person_research(person.id)

    async def get_person_research(self, person_id: UUID) -> PersonResearchBriefResponse:
        await self._require_entitled()
        person = await self._ready_person(person_id)
        runs = await self.repository.runs_for_person(self.tenant.organisation_id, person.id)
        latest = runs[0] if runs else None
        current = next((run for run in runs if run.status in USABLE_RUN_STATUSES), None)
        sources = await self.repository.sources_for_run(self.tenant.organisation_id, current.id) if current else []
        observations = (
            await self.repository.observations_for_run(self.tenant.organisation_id, current.id) if current else []
        )
        observation_links = (
            await self.repository.observation_source_links(self.tenant.organisation_id, current.id) if current else []
        )
        source_ids_by_observation: dict[UUID, list[UUID]] = {}
        for link in observation_links:
            source_ids_by_observation.setdefault(link.observation_id, []).append(link.source_id)
        hypotheses = (
            await self.repository.hypotheses_for_run(self.tenant.organisation_id, current.id) if current else []
        )
        role_links = (
            await self.repository.buying_role_source_links(self.tenant.organisation_id, current.id) if current else []
        )
        source_ids_by_role: dict[UUID, list[UUID]] = {}
        for role_link in role_links:
            source_ids_by_role.setdefault(role_link.hypothesis_id, []).append(role_link.source_id)
        contact_points = (
            await self.repository.contact_points_for_run(
                self.tenant.organisation_id,
                current.id,
                current_at=datetime.now(UTC),
            )
            if current
            else []
        )
        history = [await self._run_summary(run) for run in runs[:PERSON_HISTORY_LIMIT]]
        status, message = self._customer_status(latest, current, person)
        return PersonResearchBriefResponse(
            person=await self._person_response(person),
            status=status,
            status_message=message,
            current_run=await self._run_summary(current) if current else None,
            latest_run=await self._run_summary(latest) if latest else None,
            observations=[
                ResearchObservationResponse.model_validate(
                    {
                        "id": observation.id,
                        "observationKey": observation.observation_key,
                        "category": observation.category,
                        "statement": observation.statement,
                        "trustState": observation.trust_state,
                        "relevance": observation.relevance,
                        "observedAt": observation.observed_at,
                        "freshness": observation.freshness,
                        "sourceIds": sorted(source_ids_by_observation.get(observation.id, []), key=str),
                    }
                )
                for observation in observations
            ],
            sources=[self._source_response(source) for source in sources],
            buying_roles=[
                BuyingRoleHypothesisResponse.model_validate(
                    {
                        "id": hypothesis.id,
                        "role": hypothesis.hypothesized_role,
                        "rationale": hypothesis.rationale,
                        "trustState": hypothesis.trust_state,
                        "reviewState": hypothesis.review_state,
                        "assessmentOrigin": hypothesis.assessment_origin,
                        "sourceIds": sorted(source_ids_by_role.get(hypothesis.id, []), key=str),
                        "reviewedAt": hypothesis.reviewed_at,
                    }
                )
                for hypothesis in hypotheses
            ],
            contact_points=[
                ContactPointResponse.model_validate(
                    {
                        "id": point.id,
                        "pointType": point.point_type,
                        "value": point.value,
                        "trustState": point.trust_state,
                        "verificationMethod": point.verification_method,
                        "sourceId": point.source_id,
                        "observedAt": point.observed_at,
                        "expiresAt": point.expires_at,
                        "exportAllowed": point.export_allowed,
                    }
                )
                for point in contact_points
            ],
            changes=await self._changes(current, runs),
            history=history,
            existing_contact_matches=await self._contact_matches(person, contact_points),
        )

    async def review_buying_role(
        self,
        person_id: UUID,
        hypothesis_id: UUID,
        request: BuyingRoleReviewRequest,
    ) -> BuyingRoleHypothesisResponse:
        await self._require_entitled()
        await self._ready_person(person_id)
        hypothesis = await self.repository.hypothesis(
            self.tenant.organisation_id,
            person_id,
            hypothesis_id,
            for_update=True,
        )
        if hypothesis is None:
            raise PublicAPIError("buying_role_not_found", "The buying-role hypothesis was not found.", 404)
        hypothesis.hypothesized_role = request.role.value
        hypothesis.review_state = request.review_state.value
        hypothesis.assessment_origin = "seller_assessed"
        hypothesis.reviewed_by_user_id = self.tenant.user_id
        hypothesis.reviewed_at = datetime.now(UTC)
        hypothesis.updated_at = hypothesis.reviewed_at
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "duplicate_buying_role",
                "This person already has that buying-role hypothesis in the current research version.",
                409,
            ) from exc
        links = await self.repository.buying_role_source_links(self.tenant.organisation_id, hypothesis.run_id)
        return BuyingRoleHypothesisResponse.model_validate(
            {
                "id": hypothesis.id,
                "role": hypothesis.hypothesized_role,
                "rationale": hypothesis.rationale,
                "trustState": hypothesis.trust_state,
                "reviewState": hypothesis.review_state,
                "assessmentOrigin": hypothesis.assessment_origin,
                "sourceIds": sorted([link.source_id for link in links if link.hypothesis_id == hypothesis.id], key=str),
                "reviewedAt": hypothesis.reviewed_at,
            }
        )

    async def promote_person(
        self,
        person_id: UUID,
        request: PersonPromotionRequest,
    ) -> PersonPromotionResponse:
        await self._require_entitled()
        person = await self._ready_person(person_id, for_update=True)
        target = await self.repository.get_target(self.tenant.organisation_id, person.target_id, for_update=True)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The company research target was not found.", 404)
        if target.promoted_company_id is None:
            raise PublicAPIError(
                "company_not_in_sales",
                "Add the company to Sales before adding this person as a Contact.",
                409,
            )
        if person.promoted_contact_id is not None:
            promoted_contact = await self.repository.get_contact(
                self.tenant.organisation_id,
                person.promoted_contact_id,
            )
            if promoted_contact is None:
                raise PublicAPIError("promotion_inconsistent", "The promoted Contact could not be found.", 409)
            await self.repository.commit()
            return PersonPromotionResponse(
                status="already_promoted",
                contact_id=promoted_contact.id,
                company_id=promoted_contact.company_id,
                prospect_person_id=person.id,
                message="This public professional research is already linked to a RevenueOS Contact.",
            )
        current = await self.repository.current_person_run(self.tenant.organisation_id, person.id)
        if current is None:
            raise PublicAPIError("person_research_not_ready", "Complete person research before adding to Sales.", 409)
        points = await self.repository.contact_points_for_run(
            self.tenant.organisation_id,
            current.id,
            current_at=datetime.now(UTC),
        )
        matches = await self._contact_matches(person, points)
        if matches and request.duplicate_action is None:
            raise PublicAPIError(
                "existing_contact_match",
                "This person may already exist in RevenueOS. Review the possible Contact before continuing.",
                409,
            )

        contact: Contact
        promotion_status: Literal["created", "attached"]
        if request.duplicate_action == "attach_research":
            match = next((item for item in matches if item.id == request.existing_contact_id), None)
            if match is None:
                raise PublicAPIError("invalid_contact_match", "Choose a matching Contact from the review.", 422)
            existing = await self.repository.get_contact(self.tenant.organisation_id, match.id)
            if existing is None or existing.company_id != target.promoted_company_id:
                raise PublicAPIError("invalid_contact_match", "The selected Contact does not match this account.", 422)
            contact = existing
            promotion_status = "attached"
        else:
            if request.duplicate_action == "create_separate" and request.existing_contact_id is not None:
                raise PublicAPIError(
                    "invalid_contact_match", "A separate Contact does not use an existing Contact ID.", 422
                )
            email_point = next((point for point in points if point.point_type == "business_email"), None)
            profile_point = next(
                (point for point in points if point.point_type == "public_professional_profile"),
                None,
            )
            linkedin_url = self._linkedin_url(profile_point)
            contact = Contact(
                organisation_id=self.tenant.organisation_id,
                company_id=target.promoted_company_id,
                first_name=person.first_name,
                last_name=person.last_name,
                email=email_point.value if email_point else None,
                phone=None,
                job_title=person.current_role,
                linkedin_url=linkedin_url,
                owner_user_id=self.tenant.user_id,
            )
            self.repository.add(contact)
            await self.repository.flush()
            for change in crm_creation_changes(
                self.tenant.organisation_id,
                self.tenant.user_id,
                "contact",
                contact.id,
                "prospect_promotion",
                {
                    "company_id": contact.company_id,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "email": contact.email,
                    "job_title": contact.job_title,
                    "linkedin_url": contact.linkedin_url,
                    "status": contact.status,
                    "owner_user_id": contact.owner_user_id,
                },
            ):
                self.repository.add(change)
            promotion_status = "created"

        now = datetime.now(UTC)
        person.promoted_contact_id = contact.id
        person.promoted_by_user_id = self.tenant.user_id
        person.promoted_at = now
        person.updated_at = now
        await self._add_contact_field_sources(contact, person, points, now, attached=promotion_status == "attached")
        await self._commit("The person could not be added to Sales.")
        logger.info(
            "person_promoted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "person_id": str(person.id),
                "contact_id": str(contact.id),
                "promotion_status": promotion_status,
                "field_source_count": len(
                    await self.repository.field_sources_for_contact(self.tenant.organisation_id, contact.id)
                ),
            },
        )
        return PersonPromotionResponse(
            status=promotion_status,
            contact_id=contact.id,
            company_id=contact.company_id,
            prospect_person_id=person.id,
            message=(
                "Public professional research was linked to the existing Contact. No canonical fields were overwritten."
                if promotion_status == "attached"
                else "The Contact was added to Sales. No Opportunity, stakeholder, Methodology field or outreach was created."
            ),
        )

    async def delete_person(self, person_id: UUID) -> bool:
        await self._require_entitled()
        person = await self._ready_person(person_id, for_update=True)
        contact_preserved = person.promoted_contact_id is not None
        await self.repository.delete(person)
        await self._commit("The Prospect person research could not be deleted.")
        logger.info(
            "prospect_person_deleted",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "person_id": str(person_id),
                "promoted_contact_preserved": contact_preserved,
            },
        )
        return contact_preserved

    async def contact_research_link(self, contact_id: UUID) -> ContactProspectResearchLinkResponse:
        await self._require_entitled()
        contact = await self.repository.get_contact(self.tenant.organisation_id, contact_id)
        if contact is None:
            raise PublicAPIError("contact_not_found", "The requested Contact was not found.", 404)
        person = await self.repository.person_for_contact(self.tenant.organisation_id, contact_id)
        if person is None:
            raise PublicAPIError(
                "prospect_person_research_not_found",
                "No public professional research is linked to this Contact.",
                404,
            )
        return ContactProspectResearchLinkResponse(
            contact_id=contact.id,
            prospect_person_id=person.id,
            company_target_id=person.target_id,
            updated_at=person.updated_at,
        )

    async def _ready_company_target(self, target_id: UUID) -> ProspectResearchTarget:
        target = await self.repository.get_target(self.tenant.organisation_id, target_id)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The company research target was not found.", 404)
        if await self.repository.current_run(self.tenant.organisation_id, target.id) is None:
            raise PublicAPIError(
                "company_research_not_ready",
                "Complete company research before discovering relevant people.",
                409,
            )
        return target

    async def _ready_person(self, person_id: UUID, *, for_update: bool = False) -> ProspectPerson:
        person = await self.repository.get_person(self.tenant.organisation_id, person_id, for_update=for_update)
        if person is None:
            raise PublicAPIError("prospect_person_not_found", "The Prospect person was not found.", 404)
        target = await self.repository.get_target(self.tenant.organisation_id, person.target_id)
        if target is None:
            raise PublicAPIError("research_target_not_found", "The company research target was not found.", 404)
        return person

    async def _queue_person_run(
        self,
        person: ProspectPerson,
        raw_idempotency_key: str,
        *,
        refresh_of_run_id: UUID | None,
    ) -> ProspectResearchRun:
        existing_runs = await self.repository.runs_for_person(self.tenant.organisation_id, person.id)
        idempotency_key = self._person_idempotency_key(person.id, raw_idempotency_key)
        duplicate = next((run for run in existing_runs if run.idempotency_key == idempotency_key), None)
        if duplicate is not None:
            await self.repository.commit()
            return duplicate
        await self.repository.lock_organisation(self.tenant.organisation_id)
        if await self.repository.active_run_count(self.tenant.organisation_id) >= (
            self.settings.private_beta_max_concurrent_prospect_research
        ):
            await self.repository.rollback()
            raise PublicAPIError(
                "prospect_concurrency_limit",
                "This organisation already has the maximum number of Prospect research runs in progress.",
                429,
            )
        try:
            await self._reserve_research_usage()
            now = datetime.now(UTC)
            run = ProspectResearchRun(
                organisation_id=self.tenant.organisation_id,
                target_id=person.target_id,
                person_id=person.id,
                requested_by_user_id=self.tenant.user_id,
                refresh_of_run_id=refresh_of_run_id,
                status="pending",
                provider_key=self.provider.provider_key,
                provider_version=self.provider.provider_version,
                schema_version=PERSON_RESEARCH_SCHEMA_VERSION,
                request_fingerprint=self._fingerprint(
                    str(self.tenant.organisation_id),
                    str(person.target_id),
                    str(person.id),
                    self.provider.provider_key,
                    self.provider.provider_version,
                ),
                idempotency_key=idempotency_key,
                max_attempts=self.settings.worker_default_max_attempts,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(run)
            person.updated_at = now
            await self.repository.flush()
            await self.repository.refresh(run)
            await self.repository.commit()
        except PublicAPIError:
            await self.repository.rollback()
            raise
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.repository.runs_for_person(self.tenant.organisation_id, person.id)
            duplicate = next((item for item in concurrent if item.idempotency_key == idempotency_key), None)
            if duplicate is None:
                raise PublicAPIError("research_conflict", "The person research request conflicted.", 409) from exc
            return duplicate
        logger.info(
            "person_research_queued",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "target_id": str(person.target_id),
                "person_id": str(person.id),
                "run_id": str(run.id),
                "refresh": refresh_of_run_id is not None,
                "provider": self.provider.provider_key,
            },
        )
        return run

    async def _reserve_discovery_usage(self) -> None:
        await self._reserve_counter(
            "organisation",
            "people_discovery_count",
            self.settings.private_beta_max_people_discoveries_per_organisation_per_day,
            "organisation_people_discovery_limit",
        )
        await self._reserve_counter(
            f"user:{self.tenant.user_id}",
            "people_discovery_count",
            self.settings.private_beta_max_people_discoveries_per_user_per_day,
            "user_people_discovery_limit",
        )

    async def _reserve_research_usage(self) -> None:
        await self._reserve_counter(
            "organisation",
            "research_run_count",
            self.settings.private_beta_max_prospect_research_per_organisation_per_day,
            "organisation_prospect_daily_limit",
        )
        await self._reserve_counter(
            f"user:{self.tenant.user_id}",
            "research_run_count",
            self.settings.private_beta_max_prospect_research_per_user_per_day,
            "user_prospect_daily_limit",
        )

    async def _reserve_counter(self, scope_key: str, column_name: str, limit: int, error_code: str) -> None:
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        values: dict[str, object] = {
            "organisation_id": self.tenant.organisation_id,
            "usage_date": datetime.now(UTC).date(),
            "scope_key": scope_key,
            column_name: 1,
        }
        counter_column = getattr(ProspectUsageCounter, column_name)
        base = insert(ProspectUsageCounter).values(**values)
        statement = base.on_conflict_do_update(
            index_elements=[
                ProspectUsageCounter.organisation_id,
                ProspectUsageCounter.usage_date,
                ProspectUsageCounter.scope_key,
            ],
            set_={column_name: counter_column + 1, "updated_at": func.now()},
            where=counter_column < limit,
        ).returning(counter_column)
        if (await self.session.execute(statement)).scalar_one_or_none() is None:
            raise PublicAPIError(error_code, "The Prospect people limit has been reached. Try again tomorrow.", 429)

    async def _discovery_response(
        self,
        target: ProspectResearchTarget,
        people: list[ProspectPerson],
        *,
        discovered: bool,
    ) -> PersonDiscoveryResponse:
        represented = {person.relevant_function for person in people if person.employment_state != "no_longer_current"}
        gaps: list[BuyingCommitteeGapResponse] = []
        if "security" not in represented:
            gaps.append(
                BuyingCommitteeGapResponse.model_validate(
                    {
                        "role": "security",
                        "label": "Security",
                        "message": "No likely security stakeholder has been identified yet.",
                    }
                )
            )
        return PersonDiscoveryResponse(
            company_target_id=target.id,
            functions=list(RELEVANT_FUNCTIONS),
            people=[await self._person_response(person) for person in people],
            gaps=gaps,
            result_limit=self.settings.private_beta_max_prospect_people_per_discovery,
            message=(
                f"RevenueOS found {len(people)} people worth understanding. Buying roles remain hypotheses."
                if discovered and people
                else (
                    "RevenueOS couldn’t find reliable public professional information for this company."
                    if discovered
                    else "Find relevant people from this researched company when you are ready."
                )
            ),
        )

    async def _person_response(self, person: ProspectPerson) -> ProspectPersonResponse:
        runs = await self.repository.runs_for_person(self.tenant.organisation_id, person.id)
        latest = runs[0] if runs else None
        current = next((run for run in runs if run.status in USABLE_RUN_STATUSES), None)
        if latest is None:
            research_status = "not_started"
        elif latest.status == "pending":
            research_status = "pending"
        elif latest.status in ("fetching", "synthesizing"):
            research_status = "researching"
        elif latest.status == "failed" and current is None:
            research_status = "failed"
        elif current is not None and current.status == "partial":
            research_status = "partial"
        else:
            research_status = "ready"
        return ProspectPersonResponse.model_validate(
            {
                "id": person.id,
                "companyTargetId": person.target_id,
                "displayName": person.display_name,
                "currentRole": person.current_role,
                "currentCompany": person.current_company,
                "publicProfessionalLocation": person.public_professional_location,
                "publicProfileUrl": person.public_profile_url,
                "relevantFunction": person.relevant_function,
                "whyMayMatter": person.why_may_matter,
                "providerAttribution": person.provider_attribution,
                "identityState": person.identity_state,
                "employmentState": person.employment_state,
                "researchStatus": research_status,
                "promotedContactId": person.promoted_contact_id,
                "promotedAt": person.promoted_at,
                "createdAt": person.created_at,
                "updatedAt": person.updated_at,
            }
        )

    async def _contact_matches(
        self,
        person: ProspectPerson,
        points: Sequence[ProspectContactPoint],
    ) -> list[ExistingContactMatchResponse]:
        target = await self.repository.get_target(self.tenant.organisation_id, person.target_id)
        if target is None or target.promoted_company_id is None:
            return []
        email_point = next((point for point in points if point.point_type == "business_email"), None)
        matches: dict[UUID, ExistingContactMatchResponse] = {}
        if email_point is not None:
            exact = await self.repository.contact_by_email(self.tenant.organisation_id, str(email_point.value))
            if exact is not None and exact.company_id == target.promoted_company_id:
                matches[exact.id] = ExistingContactMatchResponse(
                    id=exact.id,
                    display_name=f"{exact.first_name} {exact.last_name}",
                    email=exact.email,
                    company_id=exact.company_id,
                    match_strength="strong",
                    match_reason="exact_business_email",
                )
        possible = await self.repository.contacts_by_name_and_company(
            self.tenant.organisation_id,
            target.promoted_company_id,
            person.first_name,
            person.last_name,
        )
        for contact in possible:
            matches.setdefault(
                contact.id,
                ExistingContactMatchResponse(
                    id=contact.id,
                    display_name=f"{contact.first_name} {contact.last_name}",
                    email=contact.email,
                    company_id=contact.company_id,
                    match_strength="possible",
                    match_reason="same_name_and_company",
                ),
            )
        return list(matches.values())

    async def _add_contact_field_sources(
        self,
        contact: Contact,
        person: ProspectPerson,
        points: Sequence[ProspectContactPoint],
        now: datetime,
        *,
        attached: bool,
    ) -> None:
        email_point = next((point for point in points if point.point_type == "business_email"), None)
        profile_point = next(
            (point for point in points if point.point_type == "public_professional_profile"),
            None,
        )
        candidates: list[tuple[str, str, str, datetime]] = []
        if (
            email_point is not None
            and contact.email is not None
            and contact.email.casefold() == email_point.value.casefold()
        ):
            candidates.append(("email", contact.email, email_point.trust_state, email_point.observed_at))
        if not attached and contact.job_title is not None:
            candidates.append(("job_title", contact.job_title, "verified", now))
        if (
            profile_point is not None
            and contact.linkedin_url is not None
            and contact.linkedin_url == profile_point.value
        ):
            candidates.append(
                ("linkedin_url", contact.linkedin_url, profile_point.trust_state, profile_point.observed_at)
            )
        for field_key, value, trust_state, observed_at in candidates:
            self.repository.add(
                ContactFieldSource(
                    organisation_id=self.tenant.organisation_id,
                    contact_id=contact.id,
                    field_key=field_key,
                    value_fingerprint=hashlib.sha256(value.casefold().encode()).hexdigest(),
                    source_type="prospect_person",
                    source_organisation_id=self.tenant.organisation_id,
                    source_prospect_person_id=person.id,
                    provider_key=person.provider_key,
                    trust_state=trust_state,
                    observed_at=observed_at,
                    verified_at=observed_at if trust_state == "verified" else None,
                    active=True,
                    created_at=now,
                )
            )

    async def _changes(
        self,
        current: ProspectResearchRun | None,
        runs: list[ProspectResearchRun],
    ) -> list[ResearchChangeResponse]:
        if current is None:
            return []
        previous = next(
            (run for run in runs if run.id == current.refresh_of_run_id and run.status in USABLE_RUN_STATUSES),
            None,
        )
        if previous is None:
            usable = [run for run in runs if run.status in USABLE_RUN_STATUSES]
            try:
                previous = usable[usable.index(current) + 1]
            except (ValueError, IndexError):
                return []
        current_items = {
            item.observation_key: item
            for item in await self.repository.observations_for_run(self.tenant.organisation_id, current.id)
        }
        previous_items = {
            item.observation_key: item
            for item in await self.repository.observations_for_run(self.tenant.organisation_id, previous.id)
        }
        changes: list[ResearchChangeResponse] = []
        for key, item in current_items.items():
            old = previous_items.get(key)
            if old is None:
                changes.append(ResearchChangeResponse(change_type="new", observation_key=key, statement=item.statement))
            elif (old.statement, old.trust_state) != (item.statement, item.trust_state):
                changes.append(
                    ResearchChangeResponse(
                        change_type="changed",
                        observation_key=key,
                        statement=item.statement,
                        previous_statement=old.statement,
                    )
                )
        for key, item in previous_items.items():
            if key not in current_items:
                changes.append(
                    ResearchChangeResponse(
                        change_type="no_longer_supported",
                        observation_key=key,
                        statement=item.statement,
                    )
                )
        return changes

    async def _run_summary(self, run: ProspectResearchRun) -> ResearchRunSummary:
        sources = await self.repository.sources_for_run(self.tenant.organisation_id, run.id)
        observations = await self.repository.observations_for_run(self.tenant.organisation_id, run.id)
        return ResearchRunSummary.model_validate(
            {
                "id": run.id,
                "status": run.status,
                "refreshOfRunId": run.refresh_of_run_id,
                "createdAt": run.created_at,
                "startedAt": run.started_at,
                "completedAt": run.completed_at,
                "sourceCount": len(sources),
                "observationCount": len(observations),
                "errorCode": run.last_error_code,
            }
        )

    @staticmethod
    def _source_response(source: ProspectResearchSource) -> ResearchSourceResponse:
        return ResearchSourceResponse.model_validate(
            {
                "id": source.id,
                "sourceType": source.source_type,
                "url": source.url,
                "canonicalUrl": source.canonical_url,
                "domain": source.domain,
                "title": source.title,
                "publisher": source.publisher,
                "publishedAt": source.published_at,
                "retrievedAt": source.retrieved_at,
                "authorityClass": source.authority_class,
            }
        )

    @staticmethod
    def _customer_status(
        latest: ProspectResearchRun | None,
        current: ProspectResearchRun | None,
        person: ProspectPerson,
    ) -> tuple[CustomerResearchStatus, str]:
        if latest is None:
            return "pending", "Professional person research has not started yet."
        if latest.status in ACTIVE_RUN_STATUSES:
            return (
                "pending" if latest.status == "pending" else "researching",
                "RevenueOS is checking bounded, permitted professional sources.",
            )
        if latest.status == "failed" and current is None:
            return "failed", "RevenueOS couldn’t find enough reliable professional information about this person."
        if latest.status == "failed" and current is not None:
            return (
                "partial" if current.status == "partial" else "ready",
                "The latest refresh failed. The previous sourced brief is still shown.",
            )
        if person.employment_state == "no_longer_current":
            return "partial", "Role may have changed. Newer information suggests this person is no longer current."
        if current is not None and current.status == "partial":
            return "partial", "Research is useful but incomplete; missing contact or activity data is not a failure."
        return "ready", "Professional research ready. Buying roles remain hypotheses, not customer-confirmed."

    async def _require_entitled(self) -> None:
        if not self.settings.feature_prospect_enabled or (
            self.settings.environment == "production" and self.settings.prospect_research_provider_name == "mock"
        ):
            raise PublicAPIError("prospect_unavailable", "RevenueOS Prospect is temporarily unavailable.", 503)
        entitlement = await self.repository.entitlement(self.tenant.organisation_id)
        if entitlement is None or not entitlement.enabled:
            raise PublicAPIError(
                "prospect_not_entitled",
                "RevenueOS Prospect is not enabled for this organisation.",
                403,
            )

    def _validate_candidate(self, target: ProspectResearchTarget, candidate: PersonCandidate) -> PersonCandidate:
        validate_person_candidate(candidate)
        if candidate.current_company.casefold() != target.name.casefold():
            raise ValueError("A person candidate was not supported as current at the researched company.")
        profile = (
            canonicalize_public_https_url(candidate.public_profile_url).url
            if candidate.public_profile_url is not None
            else None
        )
        return candidate.model_copy(update={"public_profile_url": profile})

    @staticmethod
    def _linkedin_url(point: ProspectContactPoint | None) -> str | None:
        if point is None:
            return None
        hostname = (urlsplit(point.value).hostname or "").casefold()
        return point.value if hostname == "linkedin.com" or hostname.endswith(".linkedin.com") else None

    @staticmethod
    def _target_snapshot(target: ProspectResearchTarget) -> ResearchTargetSnapshot:
        return ResearchTargetSnapshot(
            provider_candidate_id=target.provider_candidate_id,
            name=target.name,
            domain=target.normalized_domain,
            website_url=target.website_url,
            location=target.location,
            industry=target.industry,
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("conflict", message, 409) from exc

    @staticmethod
    def _person_idempotency_key(person_id: UUID, value: str) -> str:
        return f"person:{person_id}:{hashlib.sha256(value.encode()).hexdigest()}"

    @staticmethod
    def _fingerprint(*values: str) -> str:
        return hashlib.sha256("\x1f".join(values).encode()).hexdigest()
