from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_contracts import (
    AdminOverviewResponse,
    CapabilitiesResponse,
    DataNoticeResponse,
    DataRequestResponse,
    FeedbackCreate,
    FeedbackResponse,
    MemberResponse,
    OnboardingResponse,
    OnboardingUpdate,
    OrganisationDeletionRequest,
    RetentionPolicy,
    RetentionSettingsResponse,
    SystemEventResponse,
    UsageResponse,
)
from revenueos.config import Settings
from revenueos.contracts import OrganisationSummary, UserSummary
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    AIUsageCounter,
    Base,
    BetaDataRequest,
    BetaFeedback,
    BetaSystemEvent,
    DataNoticeAcknowledgement,
    Meeting,
    OnboardingProgress,
    Opportunity,
    Organisation,
    OrganisationBetaSettings,
    OrganisationMembership,
    User,
)
from revenueos.tenant import TenantContext

NOTICE_TEXT = (
    "You must have authority to add or process meeting and post-interaction debrief content.",
    "A Voice Journal records your own post-interaction report, not the customer meeting. Short voice answers may be sent to the configured transcription provider when external processing is enabled.",
    "When OpenAI is explicitly enabled, transcript or debrief content may be sent to OpenAI for processing. Mock mode keeps processing internal.",
    "Generated intelligence may contain errors and must be reviewed before it is relied on or shared.",
)
RETENTION_TO_DAYS: dict[RetentionPolicy, int | None] = {
    "days_30": 30,
    "days_90": 90,
    "days_180": 180,
    "manual": None,
}


class BetaService:
    """Tenant-scoped private-beta policy and metadata operations."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings

    def require_admin(self) -> None:
        if self.tenant.role != "admin":
            raise PublicAPIError("forbidden", "Administrator access is required.", 403)

    async def get_notice(self) -> DataNoticeResponse:
        acknowledgement = await self.session.scalar(
            select(DataNoticeAcknowledgement).where(
                DataNoticeAcknowledgement.organisation_id == self.tenant.organisation_id,
                DataNoticeAcknowledgement.user_id == self.tenant.user_id,
                DataNoticeAcknowledgement.notice_version == self.settings.private_beta_data_notice_version,
            )
        )
        return DataNoticeResponse(
            version=self.settings.private_beta_data_notice_version,
            acknowledged=acknowledgement is not None,
            acknowledged_at=acknowledgement.acknowledged_at if acknowledgement is not None else None,
            provider_mode=self.settings.ai_provider_name,
            external_processing_enabled=self.settings.ai_provider_name == "openai",
            notice=list(NOTICE_TEXT),
        )

    async def acknowledge_notice(self) -> DataNoticeResponse:
        existing = await self.get_notice()
        if existing.acknowledged:
            return existing
        acknowledgement = DataNoticeAcknowledgement(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            notice_version=self.settings.private_beta_data_notice_version,
        )
        self.session.add(acknowledgement)
        self._add_event("data_notice_acknowledged", subject_id=acknowledgement.id)
        try:
            await self.session.flush()
            await self.session.refresh(acknowledgement)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent = await self.get_notice()
            if not concurrent.acknowledged:
                raise PublicAPIError(
                    "persistence_failure",
                    "The data-notice acknowledgement could not be saved.",
                    500,
                ) from exc
            return concurrent
        return DataNoticeResponse(
            version=self.settings.private_beta_data_notice_version,
            acknowledged=True,
            acknowledged_at=acknowledgement.acknowledged_at,
            provider_mode=self.settings.ai_provider_name,
            external_processing_enabled=self.settings.ai_provider_name == "openai",
            notice=list(NOTICE_TEXT),
        )

    async def require_notice_acknowledgement(self) -> None:
        notice = await self.get_notice()
        if not notice.acknowledged:
            raise PublicAPIError(
                "data_notice_acknowledgement_required",
                "Review and acknowledge the private beta data notice before adding transcripts or generating intelligence.",
                428,
            )

    def validate_transcript_length(self, character_count: int) -> None:
        if character_count > self.settings.private_beta_max_transcript_characters:
            raise PublicAPIError(
                "transcript_too_large",
                f"Transcript text must be {self.settings.private_beta_max_transcript_characters:,} characters or fewer.",
                413,
            )

    async def get_retention(self) -> RetentionSettingsResponse:
        record = await self.session.get(OrganisationBetaSettings, self.tenant.organisation_id)
        days = record.retention_days if record is not None else self.settings.private_beta_default_retention_days
        return RetentionSettingsResponse(
            policy=self._retention_policy(days),
            default_applied=record is None,
        )

    async def update_retention(self, policy: RetentionPolicy) -> RetentionSettingsResponse:
        self.require_admin()
        record = await self.session.get(OrganisationBetaSettings, self.tenant.organisation_id)
        if record is None:
            record = OrganisationBetaSettings(
                organisation_id=self.tenant.organisation_id,
                retention_days=RETENTION_TO_DAYS[policy],
            )
            self.session.add(record)
        else:
            record.retention_days = RETENTION_TO_DAYS[policy]
        self._add_event("retention_policy_changed", metadata={"policy": policy})
        await self._commit("The retention setting could not be saved.")
        return RetentionSettingsResponse(policy=policy, default_applied=False)

    async def get_onboarding(self) -> OnboardingResponse:
        record = await self.session.get(
            OnboardingProgress,
            (self.tenant.organisation_id, self.tenant.user_id),
        )
        if record is None:
            return OnboardingResponse(current_step=0, skipped=False, completed=False, completed_at=None)
        return self._onboarding_response(record)

    async def update_onboarding(self, request: OnboardingUpdate) -> OnboardingResponse:
        record = await self.session.get(
            OnboardingProgress,
            (self.tenant.organisation_id, self.tenant.user_id),
        )
        if record is None:
            record = OnboardingProgress(
                organisation_id=self.tenant.organisation_id,
                user_id=self.tenant.user_id,
            )
            self.session.add(record)
        if request.action == "skip":
            record.skipped = True
            record.current_step = 9
            record.completed_at = datetime.now(UTC)
        elif request.action == "complete":
            record.skipped = False
            record.current_step = 9
            record.completed_at = datetime.now(UTC)
        else:
            current_step = record.current_step or 0
            next_step = request.current_step if request.current_step is not None else current_step + 1
            if next_step < current_step:
                raise PublicAPIError("invalid_onboarding_step", "Onboarding progress cannot move backwards.", 422)
            record.current_step = min(next_step, 9)
            if record.current_step == 9:
                record.completed_at = datetime.now(UTC)
        await self._commit("Onboarding progress could not be saved.")
        return self._onboarding_response(record)

    async def submit_feedback(self, request: FeedbackCreate) -> FeedbackResponse:
        start = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
        count = await self.session.scalar(
            select(func.count())
            .select_from(BetaFeedback)
            .where(
                BetaFeedback.organisation_id == self.tenant.organisation_id,
                BetaFeedback.user_id == self.tenant.user_id,
                BetaFeedback.created_at >= start,
            )
        )
        if int(count or 0) >= self.settings.private_beta_feedback_per_user_per_day:
            raise PublicAPIError(
                "feedback_rate_limit_exceeded",
                "Today’s feedback limit has been reached. Please try again tomorrow.",
                429,
            )
        if request.meeting_id is not None:
            meeting = await self.session.scalar(
                select(Meeting.id).where(
                    Meeting.organisation_id == self.tenant.organisation_id,
                    Meeting.id == request.meeting_id,
                    Meeting.deleted_at.is_(None),
                )
            )
            if meeting is None:
                raise PublicAPIError("meeting_not_found", "The feedback meeting was not found.", 404)
        if request.opportunity_id is not None:
            opportunity = await self.session.scalar(
                select(Opportunity.id).where(
                    Opportunity.organisation_id == self.tenant.organisation_id,
                    Opportunity.id == request.opportunity_id,
                )
            )
            if opportunity is None:
                raise PublicAPIError("opportunity_not_found", "The feedback opportunity was not found.", 404)
        feedback = BetaFeedback(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            category=request.category,
            rating=request.rating,
            message=request.message,
            current_route=request.current_route,
            meeting_id=request.meeting_id,
            opportunity_id=request.opportunity_id,
        )
        self.session.add(feedback)
        self._add_event("beta_feedback_submitted", subject_id=feedback.id, metadata={"category": request.category})
        await self._commit_and_refresh(feedback, "Feedback could not be submitted.")
        return FeedbackResponse.model_validate(feedback)

    async def list_feedback(self, limit: int = 100) -> list[FeedbackResponse]:
        self.require_admin()
        records = await self.session.scalars(
            select(BetaFeedback)
            .where(BetaFeedback.organisation_id == self.tenant.organisation_id)
            .order_by(BetaFeedback.created_at.desc(), BetaFeedback.id.desc())
            .limit(limit)
        )
        return [FeedbackResponse.model_validate(record) for record in records.all()]

    async def reserve_generation(self) -> None:
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        base_statement = insert(AIUsageCounter).values(
            organisation_id=self.tenant.organisation_id,
            usage_date=datetime.now(UTC).date(),
            generation_count=1,
            provider_request_count=0,
        )
        statement = base_statement.on_conflict_do_update(
            index_elements=[AIUsageCounter.organisation_id, AIUsageCounter.usage_date],
            set_={
                "generation_count": AIUsageCounter.generation_count + 1,
                "updated_at": func.now(),
            },
            where=AIUsageCounter.generation_count < self.settings.private_beta_max_generations_per_day,
        ).returning(AIUsageCounter.generation_count)
        result = await self.session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise PublicAPIError(
                "daily_generation_limit_exceeded",
                "This organisation has reached today’s intelligence generation limit. Try again tomorrow or contact an administrator.",
                429,
            )

    async def reserve_provider_request(self) -> None:
        if self.settings.ai_provider_name != "openai":
            return
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        base_statement = insert(AIUsageCounter).values(
            organisation_id=self.tenant.organisation_id,
            usage_date=datetime.now(UTC).date(),
            generation_count=0,
            provider_request_count=1,
        )
        statement = base_statement.on_conflict_do_update(
            index_elements=[AIUsageCounter.organisation_id, AIUsageCounter.usage_date],
            set_={
                "provider_request_count": AIUsageCounter.provider_request_count + 1,
                "updated_at": func.now(),
            },
            where=AIUsageCounter.provider_request_count < self.settings.private_beta_max_openai_requests_per_day,
        ).returning(AIUsageCounter.provider_request_count)
        result = await self.session.execute(statement)
        if result.scalar_one_or_none() is None:
            raise PublicAPIError(
                "daily_provider_limit_exceeded",
                "This organisation has reached today’s external AI request limit. Try again tomorrow.",
                429,
            )

    async def get_usage(self) -> UsageResponse:
        today = datetime.now(UTC).date()
        counter = await self.session.get(AIUsageCounter, (self.tenant.organisation_id, today))
        return UsageResponse(
            date=today.isoformat(),
            generations=counter.generation_count if counter is not None else 0,
            generation_limit=self.settings.private_beta_max_generations_per_day,
            provider_requests=counter.provider_request_count if counter is not None else 0,
            provider_request_limit=self.settings.private_beta_max_openai_requests_per_day,
        )

    def capabilities(self) -> CapabilitiesResponse:
        return CapabilitiesResponse(
            feature_flags=self.settings.safe_feature_flags(),
            notice_version=self.settings.private_beta_data_notice_version,
            max_transcript_characters=self.settings.private_beta_max_transcript_characters,
        )

    def require_feature(self, feature_name: str) -> None:
        enabled = self.settings.safe_feature_flags().get(feature_name, False)
        if not enabled:
            raise PublicAPIError("feature_unavailable", "This feature is not enabled for the private beta.", 404)

    async def create_export_request(self) -> DataRequestResponse:
        self.require_admin()
        self.require_feature("dataExport")
        return await self._create_data_request("export", confirmed=True)

    async def create_deletion_request(self, request: OrganisationDeletionRequest) -> DataRequestResponse:
        self.require_admin()
        self.require_feature("organisationDeletion")
        organisation = await self.session.get(Organisation, self.tenant.organisation_id)
        if organisation is None or request.confirmation != f"DELETE {organisation.slug}":
            raise PublicAPIError(
                "invalid_deletion_confirmation",
                "The organisation deletion confirmation phrase did not match.",
                422,
            )
        return await self._create_data_request("organisation_deletion", confirmed=True)

    async def list_data_requests(self) -> list[DataRequestResponse]:
        self.require_admin()
        records = await self.session.scalars(
            select(BetaDataRequest)
            .where(BetaDataRequest.organisation_id == self.tenant.organisation_id)
            .order_by(BetaDataRequest.created_at.desc(), BetaDataRequest.id.desc())
            .limit(100)
        )
        return [self._data_request_response(record) for record in records.all()]

    async def export_path(self, request_id: UUID) -> Path:
        self.require_admin()
        self.require_feature("dataExport")
        record = await self.session.scalar(
            select(BetaDataRequest).where(
                BetaDataRequest.organisation_id == self.tenant.organisation_id,
                BetaDataRequest.id == request_id,
                BetaDataRequest.request_type == "export",
            )
        )
        if record is None or record.status != "completed" or record.output_path is None:
            raise PublicAPIError("export_not_ready", "The export is not ready for download.", 409)
        if not self._is_future(record.expires_at):
            raise PublicAPIError("export_expired", "The temporary export has expired.", 410)
        root = Path(self.settings.private_beta_export_directory).resolve()
        path = Path(record.output_path).resolve()
        if root not in path.parents or path.name != f"revenueos-export-{record.id}.json":
            raise PublicAPIError("export_unavailable", "The export file is unavailable.", 404)
        return path

    async def update_member_status(self, user_id: UUID, status: str) -> MemberResponse:
        self.require_admin()
        membership = await self.session.get(OrganisationMembership, (self.tenant.organisation_id, user_id))
        if membership is None:
            raise PublicAPIError("member_not_found", "The organisation member was not found.", 404)
        if user_id == self.tenant.user_id and status == "disabled":
            raise PublicAPIError("cannot_disable_self", "An administrator cannot disable their own membership.", 409)
        membership.status = status
        self._add_event("member_status_changed", subject_id=user_id, metadata={"status": status})
        await self._commit("The member status could not be changed.")
        user = await self.session.get(User, user_id)
        assert user is not None
        return self._member_response(membership, user)

    async def admin_overview(self) -> AdminOverviewResponse:
        self.require_admin()
        organisation = await self.session.get(Organisation, self.tenant.organisation_id)
        if organisation is None:
            raise PublicAPIError("organisation_not_found", "The organisation was not found.", 404)
        rows = (
            await self.session.execute(
                select(OrganisationMembership, User)
                .join(User, User.id == OrganisationMembership.user_id)
                .where(OrganisationMembership.organisation_id == self.tenant.organisation_id)
                .order_by(User.display_name, User.id)
            )
        ).all()
        members = [self._member_response(membership, user) for membership, user in rows]
        acknowledgements = await self.session.scalar(
            select(func.count())
            .select_from(DataNoticeAcknowledgement)
            .where(
                DataNoticeAcknowledgement.organisation_id == self.tenant.organisation_id,
                DataNoticeAcknowledgement.notice_version == self.settings.private_beta_data_notice_version,
            )
        )
        events = await self.session.scalars(
            select(BetaSystemEvent)
            .where(BetaSystemEvent.organisation_id == self.tenant.organisation_id)
            .order_by(BetaSystemEvent.created_at.desc(), BetaSystemEvent.id.desc())
            .limit(20)
        )
        return AdminOverviewResponse(
            organisation=OrganisationSummary.model_validate(organisation),
            members=members,
            retention=await self.get_retention(),
            notice_version=self.settings.private_beta_data_notice_version,
            acknowledgement_count=int(acknowledgements or 0),
            active_member_count=sum(member.status == "active" for member in members),
            feature_flags=self.settings.safe_feature_flags(),
            usage=await self.get_usage(),
            recent_events=[SystemEventResponse.model_validate(event) for event in events.all()],
            data_requests=await self.list_data_requests(),
        )

    async def _create_data_request(self, request_type: str, *, confirmed: bool) -> DataRequestResponse:
        existing = await self.session.scalar(
            select(BetaDataRequest)
            .where(
                BetaDataRequest.organisation_id == self.tenant.organisation_id,
                BetaDataRequest.request_type == request_type,
                BetaDataRequest.status.in_(("pending", "processing")),
            )
            .order_by(BetaDataRequest.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            return self._data_request_response(existing)
        record = BetaDataRequest(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            requested_by_user_id=self.tenant.user_id,
            request_type=request_type,
            status="pending",
            confirmed_at=datetime.now(UTC) if confirmed else None,
        )
        self.session.add(record)
        self._add_event(f"{request_type}_requested", subject_id=record.id)
        await self._commit_and_refresh(record, "The data request could not be created.")
        return self._data_request_response(record)

    def _add_event(
        self,
        event_type: str,
        *,
        subject_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type=event_type,
                subject_id=subject_id,
                metadata_json=metadata or {},
            )
        )

    async def _commit(self, safe_message: str) -> None:
        try:
            await self.session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_failure", safe_message, 500) from exc

    async def _commit_and_refresh(self, entity: Base, safe_message: str) -> None:
        try:
            await self.session.flush()
            await self.session.refresh(entity)
            await self.session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError("persistence_failure", safe_message, 500) from exc

    @staticmethod
    def _retention_policy(days: int | None) -> RetentionPolicy:
        return cast(RetentionPolicy, {30: "days_30", 90: "days_90", 180: "days_180", None: "manual"}[days])

    @staticmethod
    def _onboarding_response(record: OnboardingProgress) -> OnboardingResponse:
        return OnboardingResponse(
            current_step=record.current_step,
            skipped=record.skipped,
            completed=record.completed_at is not None,
            completed_at=record.completed_at,
        )

    @staticmethod
    def _member_response(membership: OrganisationMembership, user: User) -> MemberResponse:
        role: Literal["admin", "member"] = "admin" if membership.role == "admin" else "member"
        status: Literal["active", "disabled"] = (
            "disabled" if membership.status == "disabled" or user.status == "disabled" else "active"
        )
        return MemberResponse(
            user=UserSummary.model_validate(user),
            role=role,
            status=status,
            joined_at=membership.created_at,
        )

    @staticmethod
    def _data_request_response(record: BetaDataRequest) -> DataRequestResponse:
        return DataRequestResponse(
            id=record.id,
            request_type=cast(Literal["export", "organisation_deletion"], record.request_type),
            status=cast(Literal["pending", "processing", "completed", "failed"], record.status),
            requested_at=record.created_at,
            completed_at=record.completed_at,
            expires_at=record.expires_at,
            download_available=(
                record.request_type == "export"
                and record.status == "completed"
                and BetaService._is_future(record.expires_at)
            ),
            failure_code=record.failure_code,
        )

    @staticmethod
    def _is_future(value: datetime | None) -> bool:
        if value is None:
            return False
        comparable = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return comparable > datetime.now(UTC)
