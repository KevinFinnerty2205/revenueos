from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.beta_maintenance import (
    _delete_interaction_batch,
    _delete_meeting_batch,
    _delete_visual_objects,
)
from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory, set_tenant_database_context
from revenueos.models import (
    BetaFeedback,
    BetaSystemEvent,
    CandidateEvidence,
    CaptureSession,
    Company,
    DebriefSession,
    DebriefTurn,
    Evidence,
    EvidenceFragment,
    Interaction,
    InteractionIntelligenceSnapshot,
    Meeting,
    MeetingParticipant,
    Opportunity,
    OpportunityAuditEvent,
    OrganisationMembership,
    PreInteractionBrief,
    RevenueBrainInteractionSnapshot,
    Transcript,
    TranscriptVersion,
    VisualAsset,
    VisualCandidateEvidence,
)
from revenueos.pre_interaction_contracts import (
    BriefInteractionType,
    BriefObjective,
    BriefQuestion,
    BriefStakeholder,
    PreInteractionBriefContent,
    PreInteractionSourceReference,
)
from revenueos.visual_storage import create_visual_storage

DEMO_NAMESPACE = UUID("d7838892-ce0b-434a-a8e9-445767115063")
INTERACTION_BACKFILL_NAMESPACE = UUID("cf709ef5-e59d-4ce2-9c93-547a4a5e5990")

TRANSCRIPTS = (
    """SYNTHETIC DEMO TRANSCRIPT — no real person or customer data.\nSeller: Thanks for discussing the evaluation. What outcome matters most?\nBuyer: We need a consistent handover after sales calls. The operations lead supports a pilot, but the finance approver has not reviewed the budget.\nSeller: What timing are you working towards?\nBuyer: We would like a decision by the end of the quarter. Please send the security summary and a clear pilot plan next Tuesday.\nSeller: I will send both items next Tuesday and arrange a finance review.\nBuyer: That works. The unresolved questions are data retention and implementation effort.""",
    """SYNTHETIC DEMO TRANSCRIPT — no real person or customer data.\nSeller: Since the discovery meeting, what has changed?\nBuyer: The finance approver joined and confirmed budget for a limited pilot. Security is comfortable with the proposed controls.\nSeller: Are there remaining concerns?\nBuyer: The team is comparing the internal process with another vendor. Implementation capacity is the main risk, although the operations lead remains our champion.\nSeller: What should happen next?\nBuyer: Send the final pilot scope by Friday. We will hold a decision meeting next Wednesday.\nSeller: I will own the pilot scope and include the retention settings.""",
)

# A one-pixel synthetic PNG used only by the deterministic demo seed. It has no
# embedded text, location, camera or person metadata.
DEMO_VISUAL_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def demo_ids(organisation_id: UUID) -> tuple[UUID, UUID, tuple[UUID, UUID], tuple[UUID, UUID]]:
    prefix = str(organisation_id)
    return (
        uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:company"),
        uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:opportunity"),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:meeting-discovery"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:meeting-evaluation"),
        ),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:transcript-discovery"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:transcript-evaluation"),
        ),
    )


def demo_companion_ids(
    organisation_id: UUID,
) -> tuple[tuple[UUID, UUID, UUID], tuple[UUID, UUID, UUID], tuple[UUID, UUID, UUID], tuple[UUID, UUID, UUID]]:
    prefix = str(organisation_id)
    return (
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-interaction-face"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-interaction-phone"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-interaction-presentation"),
        ),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-meeting-face"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-meeting-phone"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-meeting-presentation"),
        ),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-participant-face"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-participant-phone"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-participant-presentation"),
        ),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-brief-face"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-brief-phone"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-brief-presentation"),
        ),
    )


def demo_interaction_ids(organisation_id: UUID) -> tuple[UUID, UUID, UUID, UUID, UUID]:
    prefix = str(organisation_id)
    _, _, meeting_ids, _ = demo_ids(organisation_id)
    companion_interaction_ids, _, _, _ = demo_companion_ids(organisation_id)
    return (
        uuid.uuid5(INTERACTION_BACKFILL_NAMESPACE, f"{prefix}:{meeting_ids[0]}"),
        uuid.uuid5(INTERACTION_BACKFILL_NAMESPACE, f"{prefix}:{meeting_ids[1]}"),
        *companion_interaction_ids,
    )


def demo_debrief_ids(organisation_id: UUID) -> tuple[UUID, ...]:
    prefix = str(organisation_id)
    labels = (
        "debrief-phone-interaction",
        "debrief-presentation-interaction",
        "debrief-site-interaction",
        "debrief-executive-interaction",
        "debrief-trade-show-interaction",
        "debrief-phone-session",
        "debrief-trade-show-session",
        "debrief-phone-source-evidence",
        "debrief-phone-accepted-evidence",
        "debrief-phone-turn",
        "debrief-phone-fragment",
        "debrief-phone-candidate",
        "debrief-phone-intelligence",
        "debrief-phone-brain",
    )
    return tuple(uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:{label}") for label in labels)


def demo_visual_ids(organisation_id: UUID) -> tuple[UUID, ...]:
    prefix = str(organisation_id)
    labels = (
        "visual-presentation-asset",
        "visual-presentation-source-evidence",
        "visual-presentation-accepted-evidence",
        "visual-presentation-candidate",
        "visual-presentation-intelligence",
        "visual-presentation-brain",
    )
    return tuple(uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:{label}") for label in labels)


def _demo_brief_content(interaction_id: UUID, interaction_type: BriefInteractionType) -> dict[str, object]:
    variants = {
        "face_to_face_meeting": {
            "headline": "Align on the pilot outcome and agree a clear next step.",
            "objective": "Confirm the most valuable outcome for the in-person discussion.",
            "question": "What would make this meeting useful from your perspective?",
            "purpose": "Confirm the customer's desired outcome before discussing next steps.",
            "success": "The intended pilot outcome and next step are clear.",
            "guidance": "Keep the objective, stakeholder priorities and success criteria easy to scan before the meeting.",
        },
        "phone_call": {
            "headline": "Use the call to agree one useful next step.",
            "objective": "Agree a concrete next step with ownership and timing.",
            "question": "What is the most useful next step we can agree on this call?",
            "purpose": "Close the call clearly without overloading a short interaction.",
            "success": "A clear next step, owner and timing are agreed.",
            "guidance": "Keep the call concise, lead with the objective and close with a confirmed next step.",
        },
        "presentation": {
            "headline": "Validate audience priorities and agree the next validation step.",
            "objective": "Confirm which questions and evidence matter most to the audience.",
            "question": "Which questions or evidence would be most useful to the audience today?",
            "purpose": "Focus the presentation on customer needs and requested validation.",
            "success": "Audience questions and a next validation step are clarified.",
            "guidance": "Treat seller-prepared material as context, not customer evidence, and close with a validation step.",
        },
    }
    variant = variants[interaction_type]
    return PreInteractionBriefContent(
        interaction_id=interaction_id,
        interaction_type=interaction_type,
        brief_version=1,
        headline=variant["headline"],
        account_context=(
            "[DEMO] Southern Cross Operations has the Revenue workflow pilot opportunity "
            "at the evaluation stage with open status. Only linked record context is used."
        ),
        recent_changes=(),
        objectives=(
            BriefObjective(
                objective=variant["objective"],
                priority="high",
                reason="This is an interaction-specific preparation recommendation.",
            ),
        ),
        questions_to_ask=(
            BriefQuestion(
                question=variant["question"],
                purpose=variant["purpose"],
                priority="high",
            ),
        ),
        stakeholder_focus=(
            BriefStakeholder(
                name="[DEMO] Alex Morgan",
                role="attendee",
                focus="Confirm Alex's priorities and role in this interaction.",
            ),
        ),
        open_commitments=(),
        risks_to_watch=(),
        success_criteria=(variant["success"],),
        interaction_guidance=variant["guidance"],
        confidence=0.55,
    ).as_json()


def _demo_brief_sources(
    interaction_id: UUID,
    company_id: UUID,
    opportunity_id: UUID,
    participant_id: UUID,
) -> list[dict[str, object]]:
    references = (
        PreInteractionSourceReference(
            section="account_context",
            capability="interaction_metadata",
            source_id=interaction_id,
            scope="interaction",
            source_classification="system_metadata",
            validation_status="not_applicable",
        ),
        PreInteractionSourceReference(
            section="account_context",
            capability="company_metadata",
            source_id=company_id,
            scope="account",
            source_classification="system_metadata",
            validation_status="not_applicable",
        ),
        PreInteractionSourceReference(
            section="account_context",
            capability="opportunity_metadata",
            source_id=opportunity_id,
            scope="opportunity",
            source_classification="system_metadata",
            validation_status="not_applicable",
        ),
        PreInteractionSourceReference(
            section="stakeholder_focus",
            capability="meeting_participants",
            source_id=participant_id,
            scope="interaction",
            source_classification="system_metadata",
            validation_status="not_applicable",
        ),
    )
    return [reference.model_dump(mode="json") for reference in references]


async def seed_demo_data(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    user_id: UUID,
    settings: Settings | None = None,
) -> dict[str, object]:
    active_settings = settings or get_settings()
    company_id, opportunity_id, meeting_ids, transcript_ids = demo_ids(organisation_id)
    interaction_ids = demo_interaction_ids(organisation_id)
    debrief_ids = demo_debrief_ids(organisation_id)
    visual_ids = demo_visual_ids(organisation_id)
    companion_interaction_ids, companion_meeting_ids, participant_ids, brief_ids = demo_companion_ids(organisation_id)
    seeded_at = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        membership = await session.get(OrganisationMembership, (organisation_id, user_id))
        if membership is None or membership.status != "active":
            raise ValueError("Demo data requires an active member of the selected organisation.")
        company = await session.get(Company, company_id)
        if company is None:
            session.add(
                Company(
                    id=company_id,
                    organisation_id=organisation_id,
                    name="[DEMO] Southern Cross Operations",
                    website="https://example.test/demo",
                    industry="Synthetic professional services",
                    employee_count=75,
                    status="prospect",
                    owner_user_id=user_id,
                )
            )
        opportunity = await session.get(Opportunity, opportunity_id)
        if opportunity is None:
            session.add(
                Opportunity(
                    id=opportunity_id,
                    organisation_id=organisation_id,
                    company_id=company_id,
                    name="[DEMO] Revenue workflow pilot",
                    stage="evaluation",
                    status="open",
                    owner_user_id=user_id,
                    description="Synthetic private-beta opportunity. No real customer or personal data.",
                )
            )
        await session.flush()
        linked_interaction_ids: list[UUID] = []
        for index, meeting_id in enumerate(meeting_ids):
            meeting = await session.get(Meeting, meeting_id)
            interaction_id = meeting.interaction_id if meeting is not None else interaction_ids[index]
            linked_interaction_ids.append(interaction_id)
            interaction = await session.get(Interaction, interaction_id)
            if interaction is None:
                session.add(
                    Interaction(
                        id=interaction_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        interaction_type="online_meeting",
                        lifecycle_status="completed",
                        title=(
                            "[DEMO] Discovery and evaluation goals" if index == 0 else "[DEMO] Pilot decision review"
                        ),
                        scheduled_start_at=seeded_at - timedelta(days=14 if index == 0 else 7),
                        actual_start_at=seeded_at - timedelta(days=14 if index == 0 else 7),
                        actual_end_at=seeded_at - timedelta(days=14 if index == 0 else 7),
                        timezone="Australia/Sydney",
                        creation_origin="meeting_compatibility",
                        created_by_user_id=user_id,
                    )
                )
            if meeting is None:
                session.add(
                    Meeting(
                        id=meeting_id,
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        title=(
                            "[DEMO] Discovery and evaluation goals" if index == 0 else "[DEMO] Pilot decision review"
                        ),
                        description="Synthetic demonstration meeting.",
                        meeting_date=seeded_at - timedelta(days=14 if index == 0 else 7),
                        meeting_type="remote",
                        status="completed",
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )
            transcript = await session.get(Transcript, transcript_ids[index])
            if transcript is None:
                transcript = Transcript(
                    id=transcript_ids[index],
                    organisation_id=organisation_id,
                    meeting_id=meeting_id,
                    raw_text=TRANSCRIPTS[index],
                    language="en-AU",
                    version=1,
                    source="manual",
                )
                session.add(transcript)
                await session.flush()
            transcript_version_id = uuid.uuid5(
                DEMO_NAMESPACE,
                f"{organisation_id}:transcript-version-{index + 1}",
            )
            if await session.get(TranscriptVersion, transcript_version_id) is None:
                session.add(
                    TranscriptVersion(
                        id=transcript_version_id,
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        meeting_id=meeting_id,
                        transcript_id=transcript_ids[index],
                        version=1,
                        raw_text=TRANSCRIPTS[index],
                        language="en-AU",
                        source="manual",
                        status="final",
                    )
                )
        companion_variants: tuple[tuple[BriefInteractionType, str, str, int], ...] = (
            ("face_to_face_meeting", "in_person", "[DEMO] On-site pilot planning", 1),
            ("phone_call", "phone", "[DEMO] Pilot next-step call", 2),
            ("presentation", "other", "[DEMO] Pilot presentation", 3),
        )
        for index, (interaction_type, meeting_type, title, days_ahead) in enumerate(companion_variants):
            interaction_id = companion_interaction_ids[index]
            meeting_id = companion_meeting_ids[index]
            participant_id = participant_ids[index]
            if await session.get(Interaction, interaction_id) is None:
                session.add(
                    Interaction(
                        id=interaction_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        interaction_type=interaction_type,
                        lifecycle_status="planned",
                        title=title,
                        scheduled_start_at=seeded_at + timedelta(days=days_ahead),
                        timezone="Australia/Sydney",
                        creation_origin="manual",
                        created_by_user_id=user_id,
                    )
                )
            if await session.get(Meeting, meeting_id) is None:
                session.add(
                    Meeting(
                        id=meeting_id,
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        title=title,
                        description="Synthetic upcoming interaction for AI Companion preparation.",
                        meeting_date=seeded_at + timedelta(days=days_ahead),
                        meeting_type=meeting_type,
                        status="scheduled",
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )
            if await session.get(MeetingParticipant, participant_id) is None:
                session.add(
                    MeetingParticipant(
                        id=participant_id,
                        organisation_id=organisation_id,
                        meeting_id=meeting_id,
                        display_name="[DEMO] Alex Morgan",
                        attendance_status="invited",
                        role="attendee",
                    )
                )
            if await session.get(PreInteractionBrief, brief_ids[index]) is None:
                fingerprint = hashlib.sha256(
                    f"demo-v4:{organisation_id}:{interaction_id}:{interaction_type}".encode()
                ).hexdigest()
                session.add(
                    PreInteractionBrief(
                        id=brief_ids[index],
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        source_context_fingerprint=fingerprint,
                        brief_version=1,
                        schema_version=1,
                        status="completed",
                        content_json=_demo_brief_content(interaction_id, interaction_type),
                        source_references_json=_demo_brief_sources(
                            interaction_id,
                            company_id,
                            opportunity_id,
                            participant_id,
                        ),
                        created_by_user_id=user_id,
                    )
                )
        debrief_interaction_ids = debrief_ids[:5]
        debrief_variants = (
            ("phone_call", "[DEMO] Completed pricing follow-up call"),
            ("presentation", "[DEMO] Completed pilot presentation"),
            ("site_visit", "[DEMO] Completed implementation site visit"),
            ("executive_lunch", "[DEMO] Completed executive lunch"),
            ("trade_show_interaction", "[DEMO] Completed trade-show conversation"),
        )
        for index, (debrief_type, title) in enumerate(debrief_variants):
            interaction_id = debrief_interaction_ids[index]
            if await session.get(Interaction, interaction_id) is None:
                completed_at = seeded_at - timedelta(hours=index + 1)
                session.add(
                    Interaction(
                        id=interaction_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        interaction_type=debrief_type,
                        lifecycle_status="completed",
                        title=title,
                        scheduled_start_at=completed_at - timedelta(minutes=30),
                        actual_start_at=completed_at - timedelta(minutes=30),
                        actual_end_at=completed_at,
                        timezone="Australia/Sydney",
                        creation_origin="manual",
                        created_by_user_id=user_id,
                    )
                )
        await session.flush()

        (
            phone_interaction_id,
            _,
            _,
            _,
            trade_show_interaction_id,
            phone_session_id,
            trade_show_session_id,
            source_evidence_id,
            accepted_evidence_id,
            turn_id,
            fragment_id,
            candidate_id,
            intelligence_id,
            brain_id,
        ) = debrief_ids
        if await session.get(CaptureSession, phone_session_id) is None:
            answer = (
                "[DEMO] Jordan confirmed the finance approver owns the pilot budget. "
                "I will send the final proposal tomorrow."
            )
            statement = "[DEMO] Jordan confirmed the finance approver owns the pilot budget."
            phone_capture = CaptureSession(
                id=phone_session_id,
                organisation_id=organisation_id,
                interaction_id=phone_interaction_id,
                capture_type="ai_debrief",
                status="completed",
                started_by_user_id=user_id,
                started_at=seeded_at - timedelta(minutes=20),
                completed_at=seeded_at - timedelta(minutes=15),
            )
            session.add(phone_capture)
            await session.flush()
            session.add(
                DebriefSession(
                    id=phone_session_id,
                    organisation_id=organisation_id,
                    interaction_id=phone_interaction_id,
                    started_by_user_id=user_id,
                    lifecycle_status="completed",
                    idempotency_key="demo-phone-debrief",
                    question_count=1,
                    max_questions=6,
                    current_question_json=None,
                    safety_confirmed_at=seeded_at - timedelta(minutes=20),
                    finished_early=True,
                    completed_at=seeded_at - timedelta(minutes=15),
                )
            )
            await session.flush()
            session.add_all(
                [
                    Evidence(
                        id=source_evidence_id,
                        organisation_id=organisation_id,
                        interaction_id=phone_interaction_id,
                        capture_session_id=phone_session_id,
                        evidence_type="user_observation",
                        origin_class="salesperson_reported",
                        support_class="reported",
                        validation_state="unreviewed",
                        captured_by_user_id=user_id,
                        captured_at=seeded_at - timedelta(minutes=19),
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                    Evidence(
                        id=accepted_evidence_id,
                        organisation_id=organisation_id,
                        interaction_id=phone_interaction_id,
                        capture_session_id=phone_session_id,
                        evidence_type="user_observation",
                        origin_class="salesperson_reported",
                        support_class="reported",
                        validation_state="verified",
                        captured_by_user_id=user_id,
                        captured_at=seeded_at - timedelta(minutes=15),
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                ]
            )
            await session.flush()
            session.add(
                DebriefTurn(
                    id=turn_id,
                    organisation_id=organisation_id,
                    interaction_id=phone_interaction_id,
                    session_id=phone_session_id,
                    evidence_id=source_evidence_id,
                    turn_number=1,
                    question_json={
                        "status": "ask",
                        "question": "How did it go?",
                        "reason": "Start naturally.",
                        "target": "other",
                        "priority": "high",
                    },
                    answer_text=answer,
                    input_mode="text",
                    idempotency_key="demo-phone-answer",
                )
            )
            await session.flush()
            session.add(
                EvidenceFragment(
                    id=fragment_id,
                    organisation_id=organisation_id,
                    evidence_id=source_evidence_id,
                    session_id=phone_session_id,
                    turn_id=turn_id,
                    locator_type="debrief_turn",
                    content_text=answer,
                )
            )
            await session.flush()
            content = {
                "schemaVersion": 1,
                "origin": "salesperson_reported",
                "sourceLabel": "Reported by you",
                "items": [
                    {
                        "candidateId": str(candidate_id),
                        "evidenceId": str(accepted_evidence_id),
                        "category": "budget",
                        "statement": statement,
                        "origin": "salesperson_reported",
                        "validationState": "verified",
                    }
                ],
            }
            session.add(
                CandidateEvidence(
                    id=candidate_id,
                    organisation_id=organisation_id,
                    interaction_id=phone_interaction_id,
                    session_id=phone_session_id,
                    source_fragment_id=fragment_id,
                    accepted_evidence_id=accepted_evidence_id,
                    evidence_category="budget",
                    statement=statement,
                    original_statement=statement,
                    statement_fingerprint=hashlib.sha256(statement.lower().encode()).hexdigest(),
                    origin_class="salesperson_reported",
                    support_class="reported",
                    validation_state="verified",
                    review_state="accepted",
                    reviewed_by_user_id=user_id,
                    reviewed_at=seeded_at - timedelta(minutes=15),
                )
            )
            session.add(
                InteractionIntelligenceSnapshot(
                    id=intelligence_id,
                    organisation_id=organisation_id,
                    interaction_id=phone_interaction_id,
                    opportunity_id=opportunity_id,
                    session_id=phone_session_id,
                    schema_version=1,
                    version=1,
                    validation_state="validated",
                    content_json=content,
                    source_evidence_ids=[str(accepted_evidence_id)],
                )
            )
            await session.flush()
            session.add(
                RevenueBrainInteractionSnapshot(
                    id=brain_id,
                    organisation_id=organisation_id,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_id=phone_interaction_id,
                    interaction_intelligence_id=intelligence_id,
                    schema_version=1,
                    version=1,
                    content_json=content,
                    source_evidence_ids=[str(accepted_evidence_id)],
                )
            )
        if await session.get(CaptureSession, trade_show_session_id) is None:
            session.add(
                CaptureSession(
                    id=trade_show_session_id,
                    organisation_id=organisation_id,
                    interaction_id=trade_show_interaction_id,
                    capture_type="voice_journal",
                    status="capturing",
                    started_by_user_id=user_id,
                    started_at=seeded_at - timedelta(minutes=5),
                )
            )
            await session.flush()
            session.add(
                DebriefSession(
                    id=trade_show_session_id,
                    organisation_id=organisation_id,
                    interaction_id=trade_show_interaction_id,
                    started_by_user_id=user_id,
                    lifecycle_status="collecting",
                    idempotency_key="demo-trade-show-voice-journal",
                    max_questions=2,
                    current_question_json={
                        "status": "ask",
                        "question": "How did it go?",
                        "reason": "Start naturally.",
                        "target": "other",
                        "priority": "high",
                    },
                    safety_confirmed_at=seeded_at - timedelta(minutes=5),
                    voice_processing_acknowledged_at=seeded_at - timedelta(minutes=5),
                )
            )
        (
            visual_id,
            visual_source_evidence_id,
            visual_accepted_evidence_id,
            visual_candidate_id,
            visual_intelligence_id,
            visual_brain_id,
        ) = visual_ids
        presentation_interaction_id = debrief_interaction_ids[1]
        visual_storage_key = f"{organisation_id}/{presentation_interaction_id}/demo-whiteboard.png"
        visual_checksum = hashlib.sha256(DEMO_VISUAL_IMAGE).hexdigest()
        await create_visual_storage(active_settings).write(
            visual_storage_key,
            DEMO_VISUAL_IMAGE,
            "image/png",
        )
        if await session.get(VisualAsset, visual_id) is None:
            captured_at = seeded_at - timedelta(hours=2)
            statement = "[DEMO] The customer requested a security workshop before the pilot decision."
            content = {
                "schemaVersion": 2,
                "origin": "ai_inferred",
                "sourceLabel": "customer whiteboard",
                "sourceOwnership": "customer_created",
                "sourceVisualId": str(visual_id),
                "visualType": "whiteboard",
                "items": [
                    {
                        "candidateId": str(visual_candidate_id),
                        "evidenceId": str(visual_accepted_evidence_id),
                        "category": "customer_request",
                        "statement": statement,
                        "origin": "ai_inferred",
                        "sourceOwnership": "customer_created",
                        "supportClassification": "direct",
                        "sourceLabel": "customer whiteboard",
                        "validationState": "verified",
                        "conflictState": "not_assessed",
                    }
                ],
            }
            session.add(
                CaptureSession(
                    id=visual_id,
                    organisation_id=organisation_id,
                    interaction_id=presentation_interaction_id,
                    capture_type="visual_capture",
                    status="completed",
                    started_by_user_id=user_id,
                    started_at=captured_at,
                    completed_at=captured_at + timedelta(minutes=2),
                )
            )
            await session.flush()
            session.add_all(
                [
                    Evidence(
                        id=visual_source_evidence_id,
                        organisation_id=organisation_id,
                        interaction_id=presentation_interaction_id,
                        capture_session_id=visual_id,
                        evidence_type="visual",
                        origin_class="customer_direct",
                        support_class="direct",
                        validation_state="unreviewed",
                        captured_by_user_id=user_id,
                        captured_at=captured_at,
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                    Evidence(
                        id=visual_accepted_evidence_id,
                        organisation_id=organisation_id,
                        interaction_id=presentation_interaction_id,
                        capture_session_id=visual_id,
                        evidence_type="visual",
                        origin_class="ai_inferred",
                        support_class="inferred",
                        validation_state="verified",
                        captured_by_user_id=user_id,
                        captured_at=captured_at,
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                ]
            )
            await session.flush()
            session.add(
                VisualAsset(
                    id=visual_id,
                    organisation_id=organisation_id,
                    interaction_id=presentation_interaction_id,
                    capture_session_id=visual_id,
                    source_evidence_id=visual_source_evidence_id,
                    captured_by_user_id=user_id,
                    visual_type="whiteboard",
                    source_ownership="customer_created",
                    context_label="[DEMO] Customer Q&A whiteboard",
                    display_filename="demo-customer-whiteboard.png",
                    storage_key=visual_storage_key,
                    mime_type="image/png",
                    byte_size=len(DEMO_VISUAL_IMAGE),
                    upload_byte_size=len(DEMO_VISUAL_IMAGE),
                    width=1,
                    height=1,
                    checksum_sha256=visual_checksum,
                    upload_checksum_sha256=visual_checksum,
                    captured_at=captured_at,
                    upload_idempotency_key="demo-presentation-whiteboard",
                    completion_idempotency_key="demo-presentation-whiteboard-complete",
                    processing_status="completed",
                    storage_status="available",
                    processing_attempts=1,
                    provider_name="mock",
                    provider_request_id=f"mock-{visual_id}",
                    upload_expires_at=captured_at + timedelta(minutes=5),
                    upload_completed_at=captured_at + timedelta(minutes=1),
                    processed_at=captured_at + timedelta(minutes=2),
                )
            )
            await session.flush()
            session.add(
                VisualCandidateEvidence(
                    id=visual_candidate_id,
                    organisation_id=organisation_id,
                    interaction_id=presentation_interaction_id,
                    source_visual_id=visual_id,
                    accepted_evidence_id=visual_accepted_evidence_id,
                    evidence_category="customer_request",
                    statement=statement,
                    original_statement=statement,
                    statement_fingerprint=hashlib.sha256(statement.lower().encode()).hexdigest(),
                    source_ownership="customer_created",
                    origin_class="ai_inferred",
                    support_classification="direct",
                    validation_state="verified",
                    review_state="accepted",
                    conflict_state="not_assessed",
                    confidence_class="low",
                    evidence_region_json={"x": 0, "y": 0, "width": 1, "height": 1},
                    reviewed_by_user_id=user_id,
                    reviewed_at=captured_at + timedelta(minutes=2),
                )
            )
            session.add(
                InteractionIntelligenceSnapshot(
                    id=visual_intelligence_id,
                    organisation_id=organisation_id,
                    interaction_id=presentation_interaction_id,
                    opportunity_id=opportunity_id,
                    session_id=visual_id,
                    schema_version=2,
                    version=1,
                    validation_state="validated",
                    content_json=content,
                    source_evidence_ids=[str(visual_accepted_evidence_id)],
                )
            )
            await session.flush()
            session.add(
                RevenueBrainInteractionSnapshot(
                    id=visual_brain_id,
                    organisation_id=organisation_id,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_id=presentation_interaction_id,
                    interaction_intelligence_id=visual_intelligence_id,
                    schema_version=2,
                    version=2,
                    content_json=content,
                    source_evidence_ids=[str(visual_accepted_evidence_id)],
                )
            )
        event = await session.scalar(
            select(BetaSystemEvent).where(
                BetaSystemEvent.organisation_id == organisation_id,
                BetaSystemEvent.event_type == "demo_data_seeded",
                BetaSystemEvent.subject_id == opportunity_id,
            )
        )
        if event is None:
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=user_id,
                    event_type="demo_data_seeded",
                    subject_id=opportunity_id,
                    metadata_json={"dataset_version": 6},
                )
            )
        else:
            event.metadata_json = {"dataset_version": 6}
    return {
        "status": "ready",
        "company_id": company_id,
        "opportunity_id": opportunity_id,
        "meeting_ids": meeting_ids,
        "interaction_ids": (*linked_interaction_ids, *companion_interaction_ids),
        "brief_ids": brief_ids,
        "debrief_interaction_ids": debrief_interaction_ids,
        "debrief_session_ids": (phone_session_id, trade_show_session_id),
        "visual_ids": visual_ids,
        "provider_calls": 0,
    }


async def reset_demo_data(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    settings: Settings | None = None,
) -> dict[str, object]:
    active_settings = settings or get_settings()
    company_id, opportunity_id, meeting_ids, _ = demo_ids(organisation_id)
    _, companion_meeting_ids, _, _ = demo_companion_ids(organisation_id)
    debrief_interaction_ids = list(demo_debrief_ids(organisation_id)[:5])
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        if session.get_bind().dialect.name == "postgresql":
            await session.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))
        await session.execute(
            update(BetaFeedback)
            .where(
                BetaFeedback.organisation_id == organisation_id,
                BetaFeedback.opportunity_id == opportunity_id,
            )
            .values(opportunity_id=None)
        )
        await _delete_meeting_batch(session, organisation_id, [*meeting_ids, *companion_meeting_ids])
        await _delete_visual_objects(session, active_settings, organisation_id, debrief_interaction_ids)
        await _delete_interaction_batch(session, organisation_id, debrief_interaction_ids)
        await session.execute(
            delete(OpportunityAuditEvent).where(
                OpportunityAuditEvent.organisation_id == organisation_id,
                OpportunityAuditEvent.opportunity_id == opportunity_id,
            )
        )
        await session.execute(
            delete(Opportunity).where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == opportunity_id,
            )
        )
        await session.execute(
            delete(Company).where(
                Company.organisation_id == organisation_id,
                Company.id == company_id,
            )
        )
        await session.execute(
            delete(BetaSystemEvent).where(
                BetaSystemEvent.organisation_id == organisation_id,
                BetaSystemEvent.event_type == "demo_data_seeded",
                BetaSystemEvent.subject_id == opportunity_id,
            )
        )
    return {"status": "reset", "provider_calls": 0}


async def _run_cli(arguments: argparse.Namespace) -> None:
    settings: Settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    if engine is None or session_factory is None:
        raise RuntimeError("Demo data maintenance requires API_DATABASE_URL.")
    try:
        if arguments.command == "seed":
            result = await seed_demo_data(
                session_factory,
                UUID(arguments.organisation_id),
                UUID(arguments.user_id),
                settings,
            )
        else:
            result = await reset_demo_data(session_factory, UUID(arguments.organisation_id), settings)
        print(json.dumps(result, default=str, sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit tenant-scoped synthetic demo data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed = subparsers.add_parser("seed")
    seed.add_argument("--organisation-id", required=True)
    seed.add_argument("--user-id", required=True)
    reset = subparsers.add_parser("reset")
    reset.add_argument("--organisation-id", required=True)
    asyncio.run(_run_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
