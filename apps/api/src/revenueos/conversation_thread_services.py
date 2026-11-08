from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.config import Settings
from revenueos.conversation_thread_contracts import (
    ConversationFrameworkCoverage,
    ConversationMemoryResponse,
    ConversationSourceContext,
    ConversationThreadAssignmentResponse,
    ConversationThreadAssignmentUpdate,
    ConversationThreadCreate,
    ConversationThreadSuggestion,
    ConversationThreadSummary,
    ConversationThreadUpdate,
)
from revenueos.conversation_thread_repositories import (
    ConversationSnapshotRecord,
    ConversationThreadAssignmentRecord,
    ConversationThreadRecord,
    ConversationThreadRepository,
)
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.interaction_repositories import InteractionRepository
from revenueos.methodology_contracts import MethodologyFieldDefinition, MethodologyStateCounts
from revenueos.methodology_services import (
    FactCandidate,
    SalesMethodologyProjectionService,
    SourceContext,
)
from revenueos.models import (
    ConversationThread,
    ConversationThreadAssignment,
    ConversationThreadAuditEvent,
    Interaction,
)
from revenueos.tenant import TenantContext


class ConversationThreadService:
    """Explicit initiative grouping and evidence-backed longitudinal coverage."""

    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = ConversationThreadRepository(session)
        self.interactions = InteractionRepository(session)
        self.methodology = SalesMethodologyProjectionService(session, tenant, settings)

    async def list_threads(self) -> list[ConversationThreadSummary]:
        records = await self.repository.list_threads(self.tenant.organisation_id, limit=100)
        return [self._thread_summary(record) for record in records]

    async def create_thread(self, request: ConversationThreadCreate) -> ConversationThreadSummary:
        initial_interaction: Interaction | None = None
        existing: ConversationThreadAssignment | None = None
        interaction_company_id: UUID | None = None
        if request.initial_interaction_id is not None:
            initial_interaction = await self._require_interaction(request.initial_interaction_id, for_update=True)
            existing = await self.repository.assignment(
                self.tenant.organisation_id,
                initial_interaction.id,
                for_update=True,
            )
            current_version = existing.lock_version if existing is not None else 0
            if request.expected_assignment_lock_version != current_version:
                raise self._assignment_conflict()
            if existing is not None and existing.thread_id is not None:
                raise PublicAPIError(
                    "conversation_thread_already_assigned",
                    "This conversation is already assigned to an initiative. Refresh before changing it.",
                    409,
                )
            interaction_company_id = await self._resolved_interaction_company_id(initial_interaction)
        company_id = request.company_id or interaction_company_id
        if request.company_id is not None:
            if await self.interactions.get_company(self.tenant.organisation_id, request.company_id) is None:
                raise PublicAPIError("company_not_found", "The selected company was not found.", 404)
            if (
                initial_interaction is not None
                and interaction_company_id is not None
                and interaction_company_id != request.company_id
            ):
                raise PublicAPIError(
                    "conversation_thread_company_mismatch",
                    "The initiative company does not match this conversation.",
                    409,
                )
        thread = ConversationThread(
            id=uuid4(),
            organisation_id=self.tenant.organisation_id,
            company_id=company_id,
            name=request.name,
            status="active",
            created_by_user_id=self.tenant.user_id,
            updated_by_user_id=self.tenant.user_id,
            lock_version=1,
        )
        self.repository.add(thread)
        self._audit(thread.id, None, "created", {"company_id": str(company_id) if company_id else None})
        if initial_interaction is not None:
            confirmation_kind = "user_confirmed"
            if existing is None:
                self.repository.add(
                    ConversationThreadAssignment(
                        id=uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        thread_id=thread.id,
                        interaction_id=initial_interaction.id,
                        confirmed_by_user_id=self.tenant.user_id,
                        confirmation_kind=confirmation_kind,
                        lock_version=1,
                    )
                )
            else:
                existing.thread_id = thread.id
                existing.confirmed_by_user_id = self.tenant.user_id
                existing.confirmation_kind = "user_corrected"
                existing.lock_version += 1
                confirmation_kind = "user_corrected"
            self._audit(
                thread.id,
                initial_interaction.id,
                "assigned",
                {"confirmation_kind": confirmation_kind},
            )
        await self._commit("The conversation initiative could not be created.")
        saved = await self.repository.thread(self.tenant.organisation_id, thread.id)
        assert saved is not None
        return self._thread_summary(saved)

    async def update_thread(
        self,
        thread_id: UUID,
        request: ConversationThreadUpdate,
    ) -> ConversationThreadSummary:
        record = await self._require_thread(thread_id, for_update=True)
        thread = record.thread
        if request.expected_lock_version != thread.lock_version:
            raise self._thread_conflict()
        if request.name is not None:
            thread.name = request.name
        if request.status is not None:
            thread.status = request.status
        thread.updated_by_user_id = self.tenant.user_id
        thread.lock_version += 1
        action = "archived" if request.status == "archived" else "updated"
        self._audit(
            thread.id,
            None,
            action,
            {"status": thread.status, "lock_version": thread.lock_version},
        )
        await self._commit("The conversation initiative could not be updated.")
        saved = await self.repository.thread(self.tenant.organisation_id, thread.id)
        assert saved is not None
        return self._thread_summary(saved)

    async def assignment(self, interaction_id: UUID) -> ConversationThreadAssignmentResponse:
        await self._require_interaction(interaction_id)
        return self._assignment_response(
            interaction_id,
            await self.repository.assignment_record(self.tenant.organisation_id, interaction_id),
        )

    async def update_assignment(
        self,
        interaction_id: UUID,
        request: ConversationThreadAssignmentUpdate,
    ) -> ConversationThreadAssignmentResponse:
        interaction = await self._require_interaction(interaction_id, for_update=True)
        existing = await self.repository.assignment(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        current_version = existing.lock_version if existing is not None else 0
        if request.expected_lock_version != current_version:
            raise self._assignment_conflict()
        if request.thread_id is None:
            if existing is not None and existing.thread_id is not None:
                previous_thread_id = existing.thread_id
                existing.thread_id = None
                existing.confirmed_by_user_id = self.tenant.user_id
                existing.confirmation_kind = "user_corrected"
                existing.lock_version += 1
                self._audit(
                    previous_thread_id,
                    interaction_id,
                    "unassigned",
                    {
                        "previous_lock_version": current_version,
                        "lock_version": existing.lock_version,
                    },
                )
                await self._commit("The conversation could not be removed from the initiative.")
            return self._assignment_response(
                interaction_id,
                await self.repository.assignment_record(self.tenant.organisation_id, interaction_id),
            )

        target = await self._require_thread(request.thread_id, for_update=True)
        if target.thread.status != "active":
            raise PublicAPIError(
                "conversation_thread_archived",
                "Archived initiatives cannot receive new conversations.",
                409,
            )
        interaction_company_id = await self._resolved_interaction_company_id(interaction)
        if (
            target.thread.company_id is not None
            and interaction_company_id is not None
            and target.thread.company_id != interaction_company_id
        ):
            raise PublicAPIError(
                "conversation_thread_company_mismatch",
                "The initiative belongs to a different company.",
                409,
            )
        if existing is None:
            self.repository.add(
                ConversationThreadAssignment(
                    id=uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    thread_id=target.thread.id,
                    interaction_id=interaction_id,
                    confirmed_by_user_id=self.tenant.user_id,
                    confirmation_kind="user_confirmed",
                    lock_version=1,
                )
            )
            self._audit(target.thread.id, interaction_id, "assigned", {"confirmation_kind": "user_confirmed"})
        elif existing.thread_id is None:
            existing.thread_id = target.thread.id
            existing.confirmed_by_user_id = self.tenant.user_id
            existing.confirmation_kind = "user_corrected"
            existing.lock_version += 1
            self._audit(
                target.thread.id,
                interaction_id,
                "assigned",
                {"confirmation_kind": "user_corrected"},
            )
        elif existing.thread_id != target.thread.id:
            previous_thread_id = existing.thread_id
            existing.thread_id = target.thread.id
            existing.confirmed_by_user_id = self.tenant.user_id
            existing.confirmation_kind = "user_corrected"
            existing.lock_version += 1
            self._audit(
                previous_thread_id,
                interaction_id,
                "unassigned",
                {"reassigned_to_thread_id": str(target.thread.id)},
            )
            self._audit(
                target.thread.id,
                interaction_id,
                "reassigned",
                {"previous_thread_id": str(previous_thread_id)},
            )
        else:
            return self._assignment_response(
                interaction_id,
                await self.repository.assignment_record(self.tenant.organisation_id, interaction_id),
            )
        await self._commit("The conversation initiative assignment could not be saved.")
        return self._assignment_response(
            interaction_id,
            await self.repository.assignment_record(self.tenant.organisation_id, interaction_id),
        )

    async def memory(self, interaction_id: UUID) -> ConversationMemoryResponse:
        interaction = await self._require_interaction(interaction_id)
        assignment_record = await self.repository.assignment_record(self.tenant.organisation_id, interaction_id)
        suggestions = await self._suggestions(interaction, assignment_record)
        selection = await self.methodology.current_selection()
        now = datetime.now(UTC)
        assignment = self._assignment_response(interaction_id, assignment_record)
        if selection.selection == "none" or selection.effective_definition is None:
            return ConversationMemoryResponse(
                state="not_configured",
                safe_message=(
                    "No framework is selected. The confirmed initiative is still preserved without CRM data."
                    if assignment.thread is not None
                    else "No framework is selected. Confirm an initiative when related conversations should share memory."
                ),
                definition=None,
                assignment=assignment,
                suggestions=tuple(suggestions),
                current_conversation=None,
                confirmed_thread=None,
                generated_at=now,
            )
        current_records = await self.repository.current_snapshot_records(
            self.tenant.organisation_id,
            interaction_id,
        )
        current = self._coverage(selection.effective_definition.fields, current_records, now)
        cumulative: ConversationFrameworkCoverage | None = None
        if assignment_record is not None and assignment_record.thread is not None:
            before_at = (
                interaction.actual_end_at or interaction.actual_start_at or interaction.scheduled_start_at or now
            )
            thread_records = await self.repository.thread_snapshot_records(
                self.tenant.organisation_id,
                assignment_record.thread.thread.id,
                before_at=before_at,
            )
            cumulative = self._coverage(selection.effective_definition.fields, thread_records, now)
        return ConversationMemoryResponse(
            state="current",
            safe_message=(
                "Current-conversation coverage is separate from the user-confirmed initiative history."
                if assignment_record is not None and assignment_record.thread is not None
                else "Current-conversation coverage is available. Confirm or create an initiative before cumulative history is used."
            ),
            definition=selection.effective_definition,
            assignment=assignment,
            suggestions=tuple(suggestions),
            current_conversation=current,
            confirmed_thread=cumulative,
            generated_at=now,
        )

    async def _suggestions(
        self,
        interaction: Interaction,
        assignment: ConversationThreadAssignmentRecord | None,
    ) -> list[ConversationThreadSuggestion]:
        company_context = await self.repository.interaction_company_context(
            self.tenant.organisation_id,
            interaction.id,
        )
        if company_context is None or company_context.ambiguous:
            return []
        interaction_company_id = company_context.company_id
        current_participants = await self.repository.participant_ids_for_interaction(
            self.tenant.organisation_id,
            interaction.id,
        )
        suggestions: list[ConversationThreadSuggestion] = []
        for record in await self.repository.list_threads(
            self.tenant.organisation_id,
            status="active",
            limit=100,
        ):
            if (
                assignment is not None
                and assignment.thread is not None
                and record.thread.id == assignment.thread.thread.id
            ):
                continue
            if (
                record.thread.company_id is not None
                and interaction_company_id is not None
                and record.thread.company_id != interaction_company_id
            ):
                continue
            score = 0
            reasons: list[str] = []
            if interaction_company_id is not None and record.thread.company_id == interaction_company_id:
                score += 2
                reasons.append("Same company")
            if current_participants:
                prior_participants = await self.repository.participant_ids_for_thread(
                    self.tenant.organisation_id,
                    record.thread.id,
                )
                shared = len(current_participants & prior_participants)
                if shared:
                    score += min(shared, 2)
                    reasons.append(f"{shared} participant{'s' if shared != 1 else ''} in common")
            if score:
                suggestions.append(
                    ConversationThreadSuggestion(
                        thread=self._thread_summary(record),
                        score=score,
                        reasons=tuple(reasons),
                    )
                )
        suggestions.sort(key=lambda item: (-item.score, item.thread.name.casefold(), str(item.thread.id)))
        return suggestions[:5]

    def _coverage(
        self,
        fields: Sequence[MethodologyFieldDefinition],
        records: list[ConversationSnapshotRecord],
        now: datetime,
    ) -> ConversationFrameworkCoverage:
        candidates: list[FactCandidate] = []
        source_contexts: list[ConversationSourceContext] = []
        for record in records:
            generated = self.methodology._interaction_snapshot_candidates([record.snapshot])
            candidates.extend(
                replace(
                    candidate,
                    source=candidate.source.model_copy(update={"supported_at": record.occurred_at}),
                )
                for candidate in generated
            )
            source_contexts.append(
                ConversationSourceContext(
                    source_id=record.snapshot.id,
                    interaction_id=record.interaction.id,
                    interaction_title=record.interaction.title,
                    occurred_at=record.occurred_at,
                )
            )
        context = SourceContext(candidates=tuple(candidates), reviews=(), fingerprint="")
        projected = tuple(self.methodology._project_field(field, context, now) for field in fields)
        counts = MethodologyStateCounts(
            confirmed=sum(item.state == "confirmed" for item in projected),
            partially_supported=sum(item.state == "partially_supported" for item in projected),
            unknown=sum(item.state == "unknown" for item in projected),
            conflicting=sum(item.state == "conflicting" for item in projected),
            stale=sum(item.state == "stale" for item in projected),
        )
        return ConversationFrameworkCoverage(
            state_counts=counts,
            items=projected,
            source_conversations=tuple(source_contexts),
        )

    async def _require_interaction(
        self,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Interaction:
        interaction = await self.repository.interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=for_update,
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        return interaction

    async def _require_thread(
        self,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThreadRecord:
        record = await self.repository.thread(
            self.tenant.organisation_id,
            thread_id,
            for_update=for_update,
        )
        if record is None:
            raise PublicAPIError("conversation_thread_not_found", "The conversation initiative was not found.", 404)
        return record

    async def _resolved_interaction_company_id(self, interaction: Interaction) -> UUID | None:
        context = await self.repository.interaction_company_context(
            self.tenant.organisation_id,
            interaction.id,
        )
        if context is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        if context.ambiguous:
            raise PublicAPIError(
                "conversation_thread_company_ambiguous",
                "This conversation has conflicting company relationships. Correct them before grouping it.",
                409,
            )
        return context.company_id

    def _assignment_response(
        self,
        interaction_id: UUID,
        record: ConversationThreadAssignmentRecord | None,
    ) -> ConversationThreadAssignmentResponse:
        if record is None:
            return ConversationThreadAssignmentResponse(
                interaction_id=interaction_id,
                thread=None,
                lock_version=0,
                confirmation_kind=None,
                confirmed_by_user_id=None,
                confirmed_at=None,
            )
        if record.thread is None:
            return ConversationThreadAssignmentResponse(
                interaction_id=interaction_id,
                thread=None,
                lock_version=record.assignment.lock_version,
                confirmation_kind=None,
                confirmed_by_user_id=None,
                confirmed_at=None,
            )
        return ConversationThreadAssignmentResponse(
            interaction_id=interaction_id,
            thread=self._thread_summary(record.thread),
            lock_version=record.assignment.lock_version,
            confirmation_kind=cast(
                Literal["user_confirmed", "user_corrected"],
                record.assignment.confirmation_kind,
            ),
            confirmed_by_user_id=record.assignment.confirmed_by_user_id,
            confirmed_at=record.assignment.updated_at,
        )

    @staticmethod
    def _thread_summary(record: ConversationThreadRecord) -> ConversationThreadSummary:
        thread = record.thread
        return ConversationThreadSummary(
            id=thread.id,
            organisation_id=thread.organisation_id,
            company_id=thread.company_id,
            name=thread.name,
            status=cast(Literal["active", "archived"], thread.status),
            interaction_count=record.interaction_count,
            last_interaction_at=record.last_interaction_at,
            lock_version=thread.lock_version,
            created_by_user_id=thread.created_by_user_id,
            updated_by_user_id=thread.updated_by_user_id,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        )

    def _audit(
        self,
        thread_id: UUID,
        interaction_id: UUID | None,
        action: str,
        metadata: dict[str, object],
    ) -> None:
        self.repository.add(
            ConversationThreadAuditEvent(
                id=uuid4(),
                organisation_id=self.tenant.organisation_id,
                thread_id=thread_id,
                interaction_id=interaction_id,
                actor_user_id=self.tenant.user_id,
                action=action,
                metadata_json=metadata,
            )
        )

    async def _commit(self, safe_message: str) -> None:
        try:
            await self.repository.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            raise PublicAPIError("conversation_thread_write_failed", safe_message, 409) from exc

    @staticmethod
    def _thread_conflict() -> PublicAPIError:
        return PublicAPIError(
            "conversation_thread_conflict",
            "This conversation initiative changed after it was loaded. Refresh and try again.",
            409,
        )

    @staticmethod
    def _assignment_conflict() -> PublicAPIError:
        return PublicAPIError(
            "conversation_thread_assignment_conflict",
            "This conversation initiative changed after it was loaded. Refresh and try again.",
            409,
        )
