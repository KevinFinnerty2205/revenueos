from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.beta_maintenance import (
    _delete_document_objects,
    _delete_interaction_batch,
    _delete_meeting_batch,
    _delete_source_database_rows,
    _delete_visual_objects,
)
from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory, set_tenant_database_context
from revenueos.methodology_contracts import MethodologySelectionUpdate
from revenueos.methodology_services import SalesMethodologyProjectionService
from revenueos.models import (
    ActionAuditEvent,
    ActionProposal,
    ActionProposalVersion,
    BetaFeedback,
    BetaSystemEvent,
    CandidateEvidence,
    CaptureSession,
    Company,
    Contact,
    DebriefSession,
    DebriefTurn,
    DocumentFragment,
    DocumentSource,
    EmailSource,
    Evidence,
    EvidenceFragment,
    Interaction,
    InteractionIntelligenceSnapshot,
    InteractionMarker,
    LiveBriefProgress,
    LiveInteractionSession,
    LiveProcessingWindow,
    Meeting,
    MeetingParticipant,
    MethodologyProjection,
    MethodologyReview,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Opportunity,
    OpportunityAuditEvent,
    OrganisationMembership,
    OrganisationMethodologySetting,
    PreInteractionBrief,
    ProvisionalSignal,
    RecordingConsent,
    RecordingSession,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSourceSnapshot,
    SourceCandidateEvidence,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
    VisualAsset,
    VisualCandidateEvidence,
)
from revenueos.pre_interaction_contracts import (
    BriefInteractionType,
    BriefObjective,
    BriefParticipant,
    BriefQuestion,
    BriefStakeholder,
    PreInteractionBriefContent,
    PreInteractionSourceReference,
)
from revenueos.tenant import TenantContext
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

DEMO_DOCUMENTS = {
    "customer-rfp": (
        "rfp",
        "customer_provided",
        "[DEMO] Customer RFP.txt",
        "SYNTHETIC DEMO DOCUMENT — no real customer data.\nThe pilot budget is approved.\nThe implementation must begin in October.",
        "budget",
        "The pilot budget is approved.",
        "customer_direct",
        "direct",
        "Customer-provided document",
    ),
    "seller-proposal": (
        "proposal",
        "salesperson_provided",
        "[DEMO] Seller proposal.txt",
        "SYNTHETIC DEMO DOCUMENT — no real customer data.\nRevenueOS proposes a four-week pilot.\nPricing remains subject to customer acceptance.",
        "implementation",
        "The seller proposes a four-week pilot.",
        "seller_prepared",
        "context",
        "Seller-provided document",
    ),
}

DEMO_EMAILS = {
    "customer-inbound": (
        "customer_sent",
        "inbound",
        "[DEMO] Pilot timing",
        "SYNTHETIC DEMO EMAIL — no real customer data. We need the security response by Friday.",
        "customer_request",
        "The customer requests the security response by Friday.",
        "customer_direct",
        "direct",
        "Verified inbound customer email",
    ),
    "seller-outbound": (
        "salesperson_sent",
        "outbound",
        "[DEMO] Proposed next step",
        "SYNTHETIC DEMO EMAIL — no real customer data. I propose a pilot workshop next Tuesday.",
        "action_item",
        "The seller proposes a pilot workshop next Tuesday.",
        "salesperson_reported",
        "context",
        "Outbound salesperson email",
    ),
}


def demo_source_evidence_ids(organisation_id: UUID) -> dict[str, UUID]:
    prefix = str(organisation_id)
    labels = (
        "customer-rfp",
        "seller-proposal",
        "customer-inbound",
        "seller-outbound",
    )
    ids: dict[str, UUID] = {}
    for label in labels:
        for suffix in ("source", "capture", "source-evidence", "accepted-evidence", "candidate", "snapshot"):
            ids[f"{label}:{suffix}"] = uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:{label}:{suffix}")
        if label in DEMO_DOCUMENTS:
            ids[f"{label}:fragment"] = uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:{label}:fragment")
    return ids


async def _seed_document_email_evidence(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
    user_id: UUID,
    company_id: UUID,
    opportunity_id: UUID,
    contact_id: UUID,
    seeded_at: datetime,
) -> tuple[UUID, ...]:
    ids = demo_source_evidence_ids(organisation_id)
    storage = create_visual_storage(settings)
    source_ids: list[UUID] = []

    for index, (label, spec) in enumerate(DEMO_DOCUMENTS.items()):
        (
            document_type,
            ownership,
            filename,
            content_text,
            category,
            statement,
            origin_class,
            support_class,
            source_label,
        ) = spec
        source_id = ids[f"{label}:source"]
        source_ids.append(source_id)
        content = content_text.encode("utf-8")
        storage_key = f"{organisation_id}/documents/{source_id.hex}.txt"
        await storage.write(storage_key, content, "text/plain")
        if (
            await session.scalar(
                select(DocumentSource.id).where(
                    DocumentSource.organisation_id == organisation_id,
                    DocumentSource.id == source_id,
                )
            )
            is not None
        ):
            continue
        occurred_at = seeded_at - timedelta(days=6 - index)
        capture_id = ids[f"{label}:capture"]
        source_evidence_id = ids[f"{label}:source-evidence"]
        accepted_evidence_id = ids[f"{label}:accepted-evidence"]
        fragment_id = ids[f"{label}:fragment"]
        candidate_id = ids[f"{label}:candidate"]
        session.add_all(
            (
                CaptureSession(
                    id=capture_id,
                    organisation_id=organisation_id,
                    interaction_id=None,
                    capture_type="document_import",
                    status="completed",
                    started_by_user_id=user_id,
                    started_at=occurred_at,
                    completed_at=occurred_at,
                ),
                Evidence(
                    id=source_evidence_id,
                    organisation_id=organisation_id,
                    interaction_id=None,
                    capture_session_id=capture_id,
                    evidence_type="document",
                    origin_class=origin_class,
                    support_class=support_class,
                    validation_state="verified",
                    captured_by_user_id=user_id,
                    captured_at=occurred_at,
                    lifecycle_status="available",
                    retention_class="inherited",
                ),
            )
        )
        await session.flush()
        session.add(
            DocumentSource(
                id=source_id,
                organisation_id=organisation_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                interaction_id=None,
                capture_session_id=capture_id,
                source_evidence_id=source_evidence_id,
                uploaded_by_user_id=user_id,
                document_type=document_type,
                source_ownership=ownership,
                display_filename=filename,
                storage_key=storage_key,
                mime_type="text/plain",
                byte_size=len(content),
                checksum_sha256=hashlib.sha256(content).hexdigest(),
                document_at=occurred_at,
                idempotency_key=f"demo-{label}",
                processing_status="completed",
                storage_status="available",
                processing_attempts=1,
                page_count=1,
                extracted_character_count=len(content_text),
                provider_name="mock",
                provider_request_id=f"demo-{label}",
                authority_confirmed_at=occurred_at,
                external_processing_acknowledged_at=occurred_at,
                processed_at=occurred_at,
            )
        )
        await session.flush()
        session.add_all(
            (
                DocumentFragment(
                    id=fragment_id,
                    organisation_id=organisation_id,
                    document_source_id=source_id,
                    source_evidence_id=source_evidence_id,
                    page_number=None,
                    section=None,
                    paragraph_index=0,
                    content_text=content_text,
                ),
                Evidence(
                    id=accepted_evidence_id,
                    organisation_id=organisation_id,
                    interaction_id=None,
                    capture_session_id=capture_id,
                    evidence_type="document",
                    origin_class=origin_class,
                    support_class=support_class,
                    validation_state="verified",
                    captured_by_user_id=user_id,
                    captured_at=occurred_at,
                    lifecycle_status="available",
                    retention_class="inherited",
                ),
            )
        )
        await session.flush()
        location: dict[str, object] = {
            "reference": "Paragraph 1",
            "pageNumber": None,
            "section": None,
            "paragraphIndex": 0,
        }
        session.add(
            SourceCandidateEvidence(
                id=candidate_id,
                organisation_id=organisation_id,
                source_kind="document",
                document_source_id=source_id,
                email_source_id=None,
                source_evidence_id=source_evidence_id,
                document_fragment_id=fragment_id,
                accepted_evidence_id=accepted_evidence_id,
                evidence_category=category,
                statement=statement,
                original_statement=statement,
                statement_fingerprint=hashlib.sha256(statement.lower().encode()).hexdigest(),
                interpretation_origin="ai_inferred",
                origin_class=origin_class,
                support_class=support_class,
                source_location_json=location,
                validation_state="verified",
                review_state="accepted",
                conflict_state="not_assessed",
                reviewed_by_user_id=user_id,
                reviewed_at=occurred_at + timedelta(minutes=1),
            )
        )
        await session.flush()
        snapshot_id = ids[f"{label}:snapshot"]
        session.add(
            RevenueBrainSourceSnapshot(
                id=snapshot_id,
                organisation_id=organisation_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                interaction_id=None,
                source_kind="document",
                document_source_id=source_id,
                email_source_id=None,
                source_evidence_id=source_evidence_id,
                source_evidence_ids=[str(accepted_evidence_id)],
                content_json={
                    "schemaVersion": 1,
                    "sourceKind": "document",
                    "sourceId": str(source_id),
                    "sourceType": document_type,
                    "sourceLabel": source_label,
                    "sourceOrigin": ownership,
                    "occurredAt": occurred_at.isoformat(),
                    "items": [
                        {
                            "candidateId": str(candidate_id),
                            "evidenceId": str(accepted_evidence_id),
                            "category": category,
                            "statement": statement,
                            "sourceKind": "document",
                            "sourceId": str(source_id),
                            "sourceType": document_type,
                            "sourceLabel": source_label,
                            "sourceOrigin": ownership,
                            "originClass": origin_class,
                            "supportClass": support_class,
                            "conflictState": "not_assessed",
                            "location": location,
                        }
                    ],
                },
                schema_version=1,
                version=1,
                created_at=occurred_at + timedelta(minutes=1),
            )
        )

    for index, (label, spec) in enumerate(DEMO_EMAILS.items()):
        (
            source_type,
            direction,
            subject,
            body,
            category,
            statement,
            origin_class,
            support_class,
            source_label,
        ) = spec
        source_id = ids[f"{label}:source"]
        source_ids.append(source_id)
        if (
            await session.scalar(
                select(EmailSource.id).where(
                    EmailSource.organisation_id == organisation_id,
                    EmailSource.id == source_id,
                )
            )
            is not None
        ):
            continue
        occurred_at = seeded_at - timedelta(days=3 - index)
        capture_id = ids[f"{label}:capture"]
        source_evidence_id = ids[f"{label}:source-evidence"]
        accepted_evidence_id = ids[f"{label}:accepted-evidence"]
        candidate_id = ids[f"{label}:candidate"]
        session.add_all(
            (
                CaptureSession(
                    id=capture_id,
                    organisation_id=organisation_id,
                    interaction_id=None,
                    capture_type="email_import",
                    status="completed",
                    started_by_user_id=user_id,
                    started_at=occurred_at,
                    completed_at=occurred_at,
                ),
                Evidence(
                    id=source_evidence_id,
                    organisation_id=organisation_id,
                    interaction_id=None,
                    capture_session_id=capture_id,
                    evidence_type="email",
                    origin_class=origin_class,
                    support_class=support_class,
                    validation_state="verified",
                    captured_by_user_id=user_id,
                    captured_at=occurred_at,
                    lifecycle_status="available",
                    retention_class="inherited",
                ),
            )
        )
        await session.flush()
        session.add(
            EmailSource(
                id=source_id,
                organisation_id=organisation_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                interaction_id=None,
                capture_session_id=capture_id,
                source_evidence_id=source_evidence_id,
                submitted_by_user_id=user_id,
                sender_contact_id=contact_id if direction == "inbound" else None,
                source_type=source_type,
                direction=direction,
                sender_identity_state="verified_contact" if direction == "inbound" else "unknown",
                origin_class=origin_class,
                support_class=support_class,
                subject=subject,
                body_text=body,
                normalized_body_text=body,
                quote_handling="none",
                message_at=occurred_at,
                content_sha256=hashlib.sha256(f"{subject}\n{body}".encode()).hexdigest(),
                idempotency_key=f"demo-{label}",
                processing_status="completed",
                processing_attempts=1,
                provider_name="mock",
                provider_request_id=f"demo-{label}",
                authority_confirmed_at=occurred_at,
                external_processing_acknowledged_at=occurred_at,
                processed_at=occurred_at,
            )
        )
        await session.flush()
        session.add(
            Evidence(
                id=accepted_evidence_id,
                organisation_id=organisation_id,
                interaction_id=None,
                capture_session_id=capture_id,
                evidence_type="email",
                origin_class=origin_class,
                support_class=support_class,
                validation_state="verified",
                captured_by_user_id=user_id,
                captured_at=occurred_at,
                lifecycle_status="available",
                retention_class="inherited",
            )
        )
        await session.flush()
        location = {
            "reference": "Message paragraph 1",
            "pageNumber": None,
            "section": None,
            "paragraphIndex": 0,
        }
        session.add(
            SourceCandidateEvidence(
                id=candidate_id,
                organisation_id=organisation_id,
                source_kind="email",
                document_source_id=None,
                email_source_id=source_id,
                source_evidence_id=source_evidence_id,
                document_fragment_id=None,
                accepted_evidence_id=accepted_evidence_id,
                evidence_category=category,
                statement=statement,
                original_statement=statement,
                statement_fingerprint=hashlib.sha256(statement.lower().encode()).hexdigest(),
                interpretation_origin="ai_inferred",
                origin_class=origin_class,
                support_class=support_class,
                source_location_json=location,
                validation_state="verified",
                review_state="accepted",
                conflict_state="not_assessed",
                reviewed_by_user_id=user_id,
                reviewed_at=occurred_at + timedelta(minutes=1),
            )
        )
        await session.flush()
        snapshot_id = ids[f"{label}:snapshot"]
        session.add(
            RevenueBrainSourceSnapshot(
                id=snapshot_id,
                organisation_id=organisation_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                interaction_id=None,
                source_kind="email",
                document_source_id=None,
                email_source_id=source_id,
                source_evidence_id=source_evidence_id,
                source_evidence_ids=[str(accepted_evidence_id)],
                content_json={
                    "schemaVersion": 1,
                    "sourceKind": "email",
                    "sourceId": str(source_id),
                    "sourceType": source_type,
                    "sourceLabel": source_label,
                    "sourceOrigin": source_type,
                    "occurredAt": occurred_at.isoformat(),
                    "items": [
                        {
                            "candidateId": str(candidate_id),
                            "evidenceId": str(accepted_evidence_id),
                            "category": category,
                            "statement": statement,
                            "sourceKind": "email",
                            "sourceId": str(source_id),
                            "sourceType": source_type,
                            "sourceLabel": source_label,
                            "sourceOrigin": source_type,
                            "originClass": origin_class,
                            "supportClass": support_class,
                            "conflictState": "not_assessed",
                            "location": location,
                        }
                    ],
                },
                schema_version=1,
                version=1,
                created_at=occurred_at + timedelta(minutes=1),
            )
        )
    return tuple(source_ids)


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


def demo_phone_contact_id(organisation_id: UUID) -> UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:phone-contact")


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


def demo_marker_ids(organisation_id: UUID) -> tuple[UUID, UUID]:
    prefix = str(organisation_id)
    return (
        uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-marker-decision"),
        uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:companion-marker-follow-up"),
    )


def demo_live_ids(organisation_id: UUID) -> dict[str, UUID]:
    prefix = str(organisation_id)
    labels = (
        "interaction",
        "meeting",
        "transcript",
        "transcript-version",
        "segment-seller",
        "segment-customer-buying",
        "segment-customer-risk",
        "brief",
        "session",
        "window",
        "buying-signal",
        "risk-signal",
        "brief-progress",
        "final-capture",
        "final-intelligence",
        "brain-snapshot",
    )
    return {label: uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:live-intelligence-{label}") for label in labels}


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
        company_name="[DEMO] Southern Cross Operations",
        opportunity_name="[DEMO] Revenue workflow pilot",
        participants=(BriefParticipant(name="[DEMO] Alex Morgan", role="attendee"),),
        next_best_action="Confirm one owned and dated next step.",
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
    phone_contact_id = demo_phone_contact_id(organisation_id)
    interaction_ids = demo_interaction_ids(organisation_id)
    debrief_ids = demo_debrief_ids(organisation_id)
    visual_ids = demo_visual_ids(organisation_id)
    marker_ids = demo_marker_ids(organisation_id)
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
                    estimated_value=Decimal("420000.00"),
                    currency="AUD",
                    expected_close_date=(seeded_at + timedelta(days=14)).date(),
                    owner_user_id=user_id,
                    description="Synthetic private-beta opportunity. No real customer or personal data.",
                )
            )
        else:
            # Advance older synthetic datasets to the current Daily fixture without
            # touching any non-demo opportunity.
            opportunity.estimated_value = Decimal("420000.00")
            opportunity.currency = "AUD"
            opportunity.expected_close_date = (seeded_at + timedelta(days=14)).date()
        await session.flush()
        if await session.get(Contact, phone_contact_id) is None:
            session.add(
                Contact(
                    id=phone_contact_id,
                    organisation_id=organisation_id,
                    company_id=company_id,
                    first_name="[DEMO] Jordan",
                    last_name="Lee",
                    email="jordan.lee@example.test",
                    phone="+61 400 000 017",
                    job_title="Finance approver",
                    owner_user_id=user_id,
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
                    source="platform_generated" if index == 0 else "imported_audio",
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
                        source="platform_generated" if index == 0 else "imported_audio",
                        status="final",
                    )
                )
        await session.flush()

        teams_metadata_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-metadata-teams")
        zoom_metadata_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-metadata-zoom")
        for metadata_id, interaction_id, platform, capture_source in (
            (
                teams_metadata_id,
                linked_interaction_ids[0],
                "microsoft_teams",
                "platform_transcript",
            ),
            (
                zoom_metadata_id,
                linked_interaction_ids[1],
                "zoom",
                "platform_recording",
            ),
        ):
            if await session.get(OnlineMeetingMetadata, metadata_id) is None:
                session.add(
                    OnlineMeetingMetadata(
                        id=metadata_id,
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        meeting_platform=platform,
                        capture_source=capture_source,
                        ingestion_state="ready",
                    )
                )

        transcript_import_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-transcript-import")
        transcript_capture_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-transcript-capture")
        transcript_evidence_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-transcript-evidence")
        transcript_version_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:transcript-version-1")
        if await session.get(OnlineMeetingTranscriptImport, transcript_import_id) is None:
            session.add_all(
                (
                    CaptureSession(
                        id=transcript_capture_id,
                        organisation_id=organisation_id,
                        interaction_id=linked_interaction_ids[0],
                        capture_type="uploaded_transcript",
                        status="completed",
                        started_by_user_id=user_id,
                        started_at=seeded_at - timedelta(days=14),
                        completed_at=seeded_at - timedelta(days=14),
                    ),
                    Evidence(
                        id=transcript_evidence_id,
                        organisation_id=organisation_id,
                        interaction_id=linked_interaction_ids[0],
                        capture_session_id=transcript_capture_id,
                        evidence_type="transcript",
                        origin_class="imported_external",
                        support_class="direct",
                        validation_state="unreviewed",
                        captured_by_user_id=user_id,
                        captured_at=seeded_at - timedelta(days=14),
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                )
            )
            await session.flush()
            session.add(
                OnlineMeetingTranscriptImport(
                    id=transcript_import_id,
                    organisation_id=organisation_id,
                    interaction_id=linked_interaction_ids[0],
                    capture_session_id=transcript_capture_id,
                    evidence_id=transcript_evidence_id,
                    transcript_version_id=transcript_version_id,
                    imported_by_user_id=user_id,
                    provenance="platform_generated",
                    source_format="txt",
                    language="en-AU",
                    content_sha256=hashlib.sha256(TRANSCRIPTS[0].encode()).hexdigest(),
                    character_count=len(TRANSCRIPTS[0]),
                    timestamps_present=False,
                    speaker_labels_present=True,
                    idempotency_key="demo-teams-transcript-import",
                    imported_at=seeded_at - timedelta(days=14),
                )
            )

        recording_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-recording-import")
        recording_capture_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-recording-capture")
        recording_evidence_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-recording-evidence")
        recording_consent_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-recording-consent")
        if await session.get(RecordingSession, recording_id) is None:
            session.add_all(
                (
                    CaptureSession(
                        id=recording_capture_id,
                        organisation_id=organisation_id,
                        interaction_id=linked_interaction_ids[1],
                        capture_type="imported_audio_recording",
                        status="completed",
                        started_by_user_id=user_id,
                        started_at=seeded_at - timedelta(days=7),
                        completed_at=seeded_at - timedelta(days=7),
                    ),
                    Evidence(
                        id=recording_evidence_id,
                        organisation_id=organisation_id,
                        interaction_id=linked_interaction_ids[1],
                        capture_session_id=recording_capture_id,
                        evidence_type="recording",
                        origin_class="imported_external",
                        support_class="direct",
                        validation_state="unreviewed",
                        captured_by_user_id=user_id,
                        captured_at=seeded_at - timedelta(days=7),
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                )
            )
            await session.flush()
            session.add(
                RecordingSession(
                    id=recording_id,
                    organisation_id=organisation_id,
                    interaction_id=linked_interaction_ids[1],
                    capture_session_id=recording_capture_id,
                    source_evidence_id=recording_evidence_id,
                    created_by_user_id=user_id,
                    recording_type="imported_audio_recording",
                    recording_source="platform_recording",
                    lifecycle_status="completed",
                    consent_state="acknowledged",
                    started_at=seeded_at - timedelta(days=7, minutes=30),
                    stopped_at=seeded_at - timedelta(days=7),
                    duration_seconds=1800,
                    expected_mime_type="audio/mp4",
                    final_mime_type="audio/mp4",
                    language="en-AU",
                    total_bytes=0,
                    chunk_count=0,
                    idempotency_key="demo-zoom-recording-import",
                    upload_completed_at=seeded_at - timedelta(days=7),
                    transcription_completed_at=seeded_at - timedelta(days=7),
                    session_expires_at=seeded_at + timedelta(days=1),
                    auto_intelligence_status="disabled",
                )
            )
            await session.flush()
            session.add(
                RecordingConsent(
                    id=recording_consent_id,
                    organisation_id=organisation_id,
                    interaction_id=linked_interaction_ids[1],
                    recording_session_id=recording_id,
                    user_id=user_id,
                    notice_version=1,
                    acknowledged_at=seeded_at - timedelta(days=7),
                    consent_method="contractual_authority",
                    user_attested_authority=True,
                )
            )

        google_interaction_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-google-debrief")
        google_meeting_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-google-meeting")
        google_metadata_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-metadata-google")
        google_debrief_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-google-debrief-session")
        if await session.get(Interaction, google_interaction_id) is None:
            completed_at = seeded_at - timedelta(days=2)
            session.add_all(
                (
                    Interaction(
                        id=google_interaction_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        interaction_type="online_meeting",
                        lifecycle_status="completed",
                        title="[DEMO] Google Meet debrief fallback",
                        actual_start_at=completed_at - timedelta(minutes=25),
                        actual_end_at=completed_at,
                        timezone="Australia/Sydney",
                        creation_origin="manual",
                        created_by_user_id=user_id,
                    ),
                    Meeting(
                        id=google_meeting_id,
                        organisation_id=organisation_id,
                        interaction_id=google_interaction_id,
                        title="[DEMO] Google Meet debrief fallback",
                        description="Synthetic no-artefact scenario captured by AI Debrief.",
                        meeting_date=completed_at,
                        meeting_type="remote",
                        status="completed",
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    ),
                )
            )
            await session.flush()
        if await session.get(OnlineMeetingMetadata, google_metadata_id) is None:
            session.add(
                OnlineMeetingMetadata(
                    id=google_metadata_id,
                    organisation_id=organisation_id,
                    interaction_id=google_interaction_id,
                    meeting_platform="google_meet",
                    capture_source="ai_debrief",
                    ingestion_state="ready",
                )
            )
        if await session.get(DebriefSession, google_debrief_id) is None:
            session.add(
                CaptureSession(
                    id=google_debrief_id,
                    organisation_id=organisation_id,
                    interaction_id=google_interaction_id,
                    capture_type="ai_debrief",
                    status="completed",
                    started_by_user_id=user_id,
                    started_at=seeded_at - timedelta(days=2),
                    completed_at=seeded_at - timedelta(days=2),
                )
            )
            await session.flush()
            session.add(
                DebriefSession(
                    id=google_debrief_id,
                    organisation_id=organisation_id,
                    interaction_id=google_interaction_id,
                    started_by_user_id=user_id,
                    lifecycle_status="completed",
                    idempotency_key="demo-google-debrief-fallback",
                    question_count=0,
                    max_questions=5,
                    safety_confirmed_at=seeded_at - timedelta(days=2),
                    finished_early=True,
                    completed_at=seeded_at - timedelta(days=2),
                )
            )
        companion_variants: tuple[tuple[BriefInteractionType, str, str, timedelta], ...] = (
            ("face_to_face_meeting", "in_person", "[DEMO] On-site pilot planning", timedelta(hours=2)),
            ("phone_call", "phone", "[DEMO] Pilot next-step call", timedelta(hours=5)),
            ("presentation", "other", "[DEMO] Pilot presentation", timedelta(days=1, hours=2)),
        )
        for index, (interaction_type, meeting_type, title, starts_after) in enumerate(companion_variants):
            interaction_id = companion_interaction_ids[index]
            meeting_id = companion_meeting_ids[index]
            participant_id = participant_ids[index]
            scheduled_at = seeded_at + starts_after
            companion_interaction = await session.get(Interaction, interaction_id)
            if companion_interaction is None:
                session.add(
                    Interaction(
                        id=interaction_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        contact_id=phone_contact_id if interaction_type == "phone_call" else None,
                        interaction_type=interaction_type,
                        call_direction="outbound" if interaction_type == "phone_call" else None,
                        lifecycle_status="planned",
                        title=title,
                        scheduled_start_at=scheduled_at,
                        timezone="Australia/Sydney",
                        creation_origin="manual",
                        created_by_user_id=user_id,
                    )
                )
            elif companion_interaction.lifecycle_status == "planned":
                companion_interaction.scheduled_start_at = scheduled_at
                companion_interaction.timezone = "Australia/Sydney"
            companion_meeting = await session.get(Meeting, meeting_id)
            if companion_meeting is None:
                session.add(
                    Meeting(
                        id=meeting_id,
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        title=title,
                        description="Synthetic upcoming interaction for AI Companion preparation.",
                        meeting_date=scheduled_at,
                        meeting_type=meeting_type,
                        status="scheduled",
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )
            elif companion_meeting.status == "scheduled":
                companion_meeting.meeting_date = scheduled_at
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
                    f"demo-v6:{organisation_id}:{interaction_id}:{interaction_type}".encode()
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
                        schema_version=2,
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
        await session.flush()

        daily_actions = (
            (
                "send-security-summary",
                "Send the security summary",
                "Review the requested security summary before sharing it.",
                "proposed",
                "high",
                seeded_at - timedelta(hours=2),
            ),
            (
                "confirm-pilot-scope",
                "Confirm the pilot scope",
                "Record the approved internal pilot scope as complete when finished.",
                "approved",
                "normal",
                seeded_at + timedelta(hours=4),
            ),
        )
        for label, title, description, status, priority, due_at in daily_actions:
            action_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:daily-action:{label}")
            if await session.get(ActionProposal, action_id) is not None:
                continue
            source_fingerprint = hashlib.sha256(f"demo-daily-source:{organisation_id}:{label}".encode()).hexdigest()
            semantic_key = hashlib.sha256(f"demo-daily-semantic:{organisation_id}:{label}".encode()).hexdigest()
            content_fingerprint = hashlib.sha256(f"demo-daily-content:{organisation_id}:{label}".encode()).hexdigest()
            is_approved = status == "approved"
            session.add_all(
                (
                    ActionProposal(
                        id=action_id,
                        organisation_id=organisation_id,
                        opportunity_id=opportunity_id,
                        action_type="create_task",
                        status=status,
                        priority=priority,
                        audience="internal",
                        risk_class="internal_low_risk",
                        current_version=1,
                        approved_version=1 if is_approved else None,
                        source_fingerprint=source_fingerprint,
                        semantic_key=semantic_key,
                        created_by_user_id=user_id,
                        generated_at=seeded_at - timedelta(days=1),
                        reviewed_by_user_id=user_id if is_approved else None,
                        reviewed_at=seeded_at - timedelta(hours=1) if is_approved else None,
                        approved_at=seeded_at - timedelta(hours=1) if is_approved else None,
                    ),
                    ActionProposalVersion(
                        organisation_id=organisation_id,
                        action_id=action_id,
                        version=1,
                        title=title,
                        description=description,
                        proposed_due_at=due_at,
                        target_entity_type="opportunity",
                        target_entity_id=opportunity_id,
                        payload_json={
                            "kind": "create_task",
                            "title": title,
                            "ownerName": "Alex Morgan",
                            "ownerUserId": str(user_id),
                            "dueAt": due_at.isoformat(),
                            "context": description,
                            "linkedOpportunityId": str(opportunity_id),
                            "linkedInteractionId": None,
                        },
                        source_refs_json=[],
                        provenance_summary="Synthetic final validated demonstration evidence.",
                        content_fingerprint=content_fingerprint,
                        created_by_user_id=user_id,
                    ),
                )
            )
            # These models intentionally have no ORM relationships. Flush the
            # proposal and immutable version before adding the foreign-keyed
            # audit event so a fresh SQLite demo database cannot choose the
            # audit insert first.
            await session.flush()
            session.add(
                ActionAuditEvent(
                    organisation_id=organisation_id,
                    action_id=action_id,
                    actor_user_id=user_id,
                    event_type="approved" if is_approved else "proposed",
                    proposal_version=1,
                    metadata_json={"synthetic_demo": True},
                )
            )

        live_ids = demo_live_ids(organisation_id)
        live_completed_at = seeded_at - timedelta(hours=4)
        if await session.get(Interaction, live_ids["interaction"]) is None:
            session.add_all(
                (
                    Interaction(
                        id=live_ids["interaction"],
                        organisation_id=organisation_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        interaction_type="face_to_face_meeting",
                        lifecycle_status="completed",
                        title="[DEMO] Recorded face-to-face live review",
                        actual_start_at=live_completed_at - timedelta(minutes=35),
                        actual_end_at=live_completed_at,
                        timezone="Australia/Sydney",
                        creation_origin="manual",
                        created_by_user_id=user_id,
                    ),
                    Meeting(
                        id=live_ids["meeting"],
                        organisation_id=organisation_id,
                        interaction_id=live_ids["interaction"],
                        title="[DEMO] Recorded face-to-face live review",
                        description="Synthetic authorised progressive-source demonstration.",
                        meeting_date=live_completed_at,
                        meeting_type="in_person",
                        status="completed",
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    ),
                    Transcript(
                        id=live_ids["transcript"],
                        organisation_id=organisation_id,
                        meeting_id=live_ids["meeting"],
                        raw_text="SYNTHETIC DEMO FINAL TRANSCRIPT — no real customer data.",
                        language="en-AU",
                        version=1,
                        source="manual",
                    ),
                    PreInteractionBrief(
                        id=live_ids["brief"],
                        organisation_id=organisation_id,
                        interaction_id=live_ids["interaction"],
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        source_context_fingerprint=hashlib.sha256(f"demo-live:{organisation_id}".encode()).hexdigest(),
                        brief_version=1,
                        schema_version=2,
                        status="completed",
                        content_json=_demo_brief_content(
                            live_ids["interaction"],
                            "face_to_face_meeting",
                        ),
                        source_references_json=[],
                        created_by_user_id=user_id,
                    ),
                )
            )
            await session.flush()
            session.add(
                TranscriptVersion(
                    id=live_ids["transcript-version"],
                    organisation_id=organisation_id,
                    interaction_id=live_ids["interaction"],
                    meeting_id=live_ids["meeting"],
                    transcript_id=live_ids["transcript"],
                    version=2,
                    raw_text="Progressive segment envelope; segment rows are the bounded source.",
                    language="en-AU",
                    source="progressive",
                    status="final",
                )
            )
            await session.flush()
            session.add_all(
                (
                    TranscriptSegment(
                        id=live_ids["segment-seller"],
                        organisation_id=organisation_id,
                        transcript_version_id=live_ids["transcript-version"],
                        sequence_number=0,
                        start_ms=0,
                        end_ms=8_000,
                        speaker_label="Speaker 1",
                        speaker_role="salesperson",
                        text="Our platform reduces cost and supports rapid rollout.",
                    ),
                    TranscriptSegment(
                        id=live_ids["segment-customer-buying"],
                        organisation_id=organisation_id,
                        transcript_version_id=live_ids["transcript-version"],
                        sequence_number=1,
                        start_ms=8_000,
                        end_ms=16_000,
                        speaker_label="Speaker 2",
                        speaker_role="customer",
                        text="We are ready to move forward and would like an October rollout.",
                    ),
                    TranscriptSegment(
                        id=live_ids["segment-customer-risk"],
                        organisation_id=organisation_id,
                        transcript_version_id=live_ids["transcript-version"],
                        sequence_number=2,
                        start_ms=16_000,
                        end_ms=24_000,
                        speaker_label="Speaker 2",
                        speaker_role="customer",
                        text="Security review may take four weeks.",
                    ),
                    CaptureSession(
                        id=live_ids["final-capture"],
                        organisation_id=organisation_id,
                        interaction_id=live_ids["interaction"],
                        capture_type="ai_debrief",
                        status="completed",
                        started_by_user_id=user_id,
                        started_at=live_completed_at,
                        completed_at=live_completed_at + timedelta(minutes=5),
                    ),
                )
            )
            await session.flush()
            final_content = {
                "schemaVersion": 1,
                "origin": "salesperson_reported",
                "items": [
                    {
                        "category": "buying_signal",
                        "statement": "The customer requested an October rollout.",
                    },
                    {
                        "category": "risk",
                        "statement": "Security review requires approximately four weeks.",
                    },
                ],
            }
            session.add(
                InteractionIntelligenceSnapshot(
                    id=live_ids["final-intelligence"],
                    organisation_id=organisation_id,
                    interaction_id=live_ids["interaction"],
                    opportunity_id=opportunity_id,
                    session_id=live_ids["final-capture"],
                    schema_version=1,
                    version=1,
                    validation_state="validated",
                    content_json=final_content,
                    source_evidence_ids=[],
                )
            )
            await session.flush()
            session.add(
                RevenueBrainInteractionSnapshot(
                    id=live_ids["brain-snapshot"],
                    organisation_id=organisation_id,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_id=live_ids["interaction"],
                    interaction_intelligence_id=live_ids["final-intelligence"],
                    schema_version=1,
                    version=1,
                    content_json=final_content,
                    source_evidence_ids=[],
                )
            )
            session.add(
                LiveInteractionSession(
                    id=live_ids["session"],
                    organisation_id=organisation_id,
                    interaction_id=live_ids["interaction"],
                    transcript_version_id=live_ids["transcript-version"],
                    brief_id=live_ids["brief"],
                    final_intelligence_id=live_ids["final-intelligence"],
                    created_by_user_id=user_id,
                    status="completed",
                    source_kind="progressive_transcript",
                    last_processed_sequence=2,
                    last_processed_at=live_completed_at,
                    processed_character_count=151,
                    processing_request_count=1,
                    started_at=live_completed_at - timedelta(minutes=30),
                    stopped_at=live_completed_at,
                    reconciled_at=live_completed_at + timedelta(minutes=5),
                    retention_expires_at=seeded_at + timedelta(days=30),
                )
            )
            await session.flush()
            buying_statement = "Customer asked about an October rollout."
            risk_statement = "Security review may take four weeks."
            session.add_all(
                (
                    LiveProcessingWindow(
                        id=live_ids["window"],
                        organisation_id=organisation_id,
                        live_session_id=live_ids["session"],
                        trigger_idempotency_key="demo-live-window-1",
                        window_fingerprint=hashlib.sha256(b"demo-live-window-1").hexdigest(),
                        first_sequence=0,
                        last_sequence=2,
                        segment_count=3,
                        character_count=151,
                        status="completed",
                        signal_count=2,
                        completed_at=live_completed_at,
                    ),
                    ProvisionalSignal(
                        id=live_ids["buying-signal"],
                        organisation_id=organisation_id,
                        interaction_id=live_ids["interaction"],
                        live_session_id=live_ids["session"],
                        transcript_version_id=live_ids["transcript-version"],
                        signal_type="buying_signal",
                        statement=buying_statement,
                        lifecycle_status="promoted_candidate",
                        is_provisional=True,
                        priority="high",
                        evidence_strength="customer_attributed",
                        resolution_status="revised",
                        signal_fingerprint=hashlib.sha256(buying_statement.lower().encode()).hexdigest(),
                        subject_fingerprint=hashlib.sha256(b"buying-signal").hexdigest(),
                        source_sequence_start=1,
                        source_sequence_end=1,
                        detected_at=live_completed_at - timedelta(minutes=15),
                        last_updated_at=live_completed_at + timedelta(minutes=5),
                    ),
                    ProvisionalSignal(
                        id=live_ids["risk-signal"],
                        organisation_id=organisation_id,
                        interaction_id=live_ids["interaction"],
                        live_session_id=live_ids["session"],
                        transcript_version_id=live_ids["transcript-version"],
                        signal_type="risk",
                        statement=risk_statement,
                        lifecycle_status="promoted_candidate",
                        is_provisional=True,
                        priority="high",
                        evidence_strength="customer_attributed",
                        resolution_status="revised",
                        signal_fingerprint=hashlib.sha256(risk_statement.lower().encode()).hexdigest(),
                        subject_fingerprint=hashlib.sha256(b"security-risk").hexdigest(),
                        source_sequence_start=2,
                        source_sequence_end=2,
                        detected_at=live_completed_at - timedelta(minutes=10),
                        last_updated_at=live_completed_at + timedelta(minutes=5),
                    ),
                    LiveBriefProgress(
                        id=live_ids["brief-progress"],
                        organisation_id=organisation_id,
                        live_session_id=live_ids["session"],
                        item_type="objective",
                        item_index=0,
                        item_fingerprint=hashlib.sha256(
                            b"Confirm the most valuable outcome for the in-person discussion."
                        ).hexdigest(),
                        progress_status="possibly_addressed",
                        source_sequence_end=1,
                    ),
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
                        contact_id=phone_contact_id if debrief_type == "phone_call" else None,
                        interaction_type=debrief_type,
                        call_direction="outbound" if debrief_type == "phone_call" else None,
                        call_outcome="connected" if debrief_type == "phone_call" else None,
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

        executive_interaction_id = debrief_interaction_ids[3]
        marker_fixtures = (
            (marker_ids[0], "decision", 480_000, "demo-companion-decision"),
            (marker_ids[1], "follow_up", None, "demo-companion-follow-up"),
        )
        for marker_id, marker_type, offset_ms, idempotency_key in marker_fixtures:
            if await session.get(InteractionMarker, marker_id) is None:
                session.add(
                    InteractionMarker(
                        id=marker_id,
                        organisation_id=organisation_id,
                        interaction_id=executive_interaction_id,
                        created_by_user_id=user_id,
                        marker_type=marker_type,
                        recording_offset_ms=offset_ms,
                        idempotency_key=idempotency_key,
                    )
                )

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
                    max_questions=5,
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
        source_evidence_ids = await _seed_document_email_evidence(
            session,
            active_settings,
            organisation_id,
            user_id,
            company_id,
            opportunity_id,
            phone_contact_id,
            seeded_at,
        )
        methodology_intelligence_id = uuid.uuid5(
            DEMO_NAMESPACE,
            f"{organisation_id}:methodology-final-intelligence",
        )
        methodology_brain_id = uuid.uuid5(
            DEMO_NAMESPACE,
            f"{organisation_id}:methodology-brain-snapshot",
        )
        methodology_evidence_id = uuid.uuid5(
            DEMO_NAMESPACE,
            f"{organisation_id}:methodology-final-evidence",
        )
        methodology_content = {
            "schemaVersion": 2,
            "origin": "validated_intelligence",
            "sourceLabel": "Final synthetic pilot review",
            "items": [
                {
                    "category": "stakeholder",
                    "statement": "The operations lead remains the internal champion.",
                    "sourceOwnership": "customer_created",
                    "supportClassification": "direct",
                    "sourceLabel": "Final synthetic pilot review",
                    "conflictState": "not_assessed",
                },
                {
                    "category": "competitor",
                    "statement": "The customer is comparing another vendor and the status quo.",
                    "sourceOwnership": "customer_created",
                    "supportClassification": "direct",
                    "sourceLabel": "Final synthetic pilot review",
                    "conflictState": "not_assessed",
                },
                {
                    "category": "procurement",
                    "statement": "Procurement is involved, but the final contracting path is unclear.",
                    "sourceOwnership": "imported_external",
                    "supportClassification": "context",
                    "sourceLabel": "Final synthetic pilot review",
                    "conflictState": "not_assessed",
                },
                {
                    "category": "decision",
                    "statement": "The approval process date conflicts with the previously supplied decision date.",
                    "sourceOwnership": "customer_created",
                    "supportClassification": "direct",
                    "sourceLabel": "Final synthetic pilot review",
                    "conflictState": "conflicting",
                },
            ],
        }
        if await session.get(Evidence, methodology_evidence_id) is None:
            session.add(
                Evidence(
                    id=methodology_evidence_id,
                    organisation_id=organisation_id,
                    interaction_id=linked_interaction_ids[1],
                    capture_session_id=recording_capture_id,
                    evidence_type="transcript",
                    origin_class="customer_direct",
                    support_class="direct",
                    validation_state="verified",
                    captured_by_user_id=user_id,
                    captured_at=seeded_at - timedelta(days=7),
                    lifecycle_status="available",
                    retention_class="inherited",
                )
            )
            await session.flush()
        if await session.get(InteractionIntelligenceSnapshot, methodology_intelligence_id) is None:
            session.add(
                InteractionIntelligenceSnapshot(
                    id=methodology_intelligence_id,
                    organisation_id=organisation_id,
                    interaction_id=linked_interaction_ids[1],
                    opportunity_id=opportunity_id,
                    session_id=recording_capture_id,
                    schema_version=2,
                    version=1,
                    validation_state="validated",
                    content_json=methodology_content,
                    source_evidence_ids=[str(methodology_evidence_id)],
                )
            )
            await session.flush()
        if await session.get(RevenueBrainInteractionSnapshot, methodology_brain_id) is None:
            session.add(
                RevenueBrainInteractionSnapshot(
                    id=methodology_brain_id,
                    organisation_id=organisation_id,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_id=linked_interaction_ids[1],
                    interaction_intelligence_id=methodology_intelligence_id,
                    schema_version=2,
                    version=3,
                    content_json=methodology_content,
                    source_evidence_ids=[str(methodology_evidence_id)],
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
                    metadata_json={"dataset_version": 13},
                )
            )
        else:
            event.metadata_json = {"dataset_version": 13}
    methodology_versions = await _seed_methodology_views(
        session_factory,
        organisation_id,
        user_id,
        active_settings,
        opportunity_id,
    )
    return {
        "status": "ready",
        "company_id": company_id,
        "opportunity_id": opportunity_id,
        "contact_id": phone_contact_id,
        "meeting_ids": meeting_ids,
        "interaction_ids": (*linked_interaction_ids, *companion_interaction_ids),
        "online_meeting_interaction_ids": (
            linked_interaction_ids[0],
            linked_interaction_ids[1],
            google_interaction_id,
        ),
        "brief_ids": brief_ids,
        "debrief_interaction_ids": debrief_interaction_ids,
        "debrief_session_ids": (phone_session_id, trade_show_session_id),
        "visual_ids": visual_ids,
        "source_evidence_ids": source_evidence_ids,
        "marker_ids": marker_ids,
        "live_interaction_id": live_ids["interaction"],
        "methodology_projection_versions": methodology_versions,
        "provider_calls": 0,
    }


async def _seed_methodology_views(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    user_id: UUID,
    settings: Settings,
    opportunity_id: UUID,
) -> tuple[int, ...]:
    """Seed a BANT-to-MEDDPICC switch using only deterministic final evidence."""

    tenant = TenantContext(organisation_id=organisation_id, user_id=user_id, role="admin")
    async with session_factory() as session:
        await set_tenant_database_context(session, organisation_id)
        existing_keys = set(
            await session.scalars(
                select(MethodologyProjection.definition_key).where(
                    MethodologyProjection.organisation_id == organisation_id,
                    MethodologyProjection.opportunity_id == opportunity_id,
                )
            )
        )
        service = SalesMethodologyProjectionService(session, tenant, settings)
        if "bant" not in existing_keys:
            await service.select_methodology(MethodologySelectionUpdate(selection="bant"))
            await service.generate(opportunity_id)
        if "meddpicc" not in existing_keys:
            await service.select_methodology(MethodologySelectionUpdate(selection="meddpicc"))
            await service.generate(opportunity_id)
        else:
            setting = await session.get(OrganisationMethodologySetting, organisation_id)
            if setting is None:
                session.add(
                    OrganisationMethodologySetting(
                        organisation_id=organisation_id,
                        selection="meddpicc",
                        updated_by_user_id=user_id,
                    )
                )
            elif setting.selection != "meddpicc" or setting.custom_definition_id is not None:
                setting.selection = "meddpicc"
                setting.custom_definition_id = None
                setting.updated_by_user_id = user_id
                setting.updated_at = datetime.now(UTC)
            await session.commit()
        versions = await session.scalars(
            select(MethodologyProjection.projection_version)
            .where(
                MethodologyProjection.organisation_id == organisation_id,
                MethodologyProjection.opportunity_id == opportunity_id,
            )
            .order_by(MethodologyProjection.projection_version)
        )
        return tuple(versions)


async def reset_demo_data(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    settings: Settings | None = None,
) -> dict[str, object]:
    active_settings = settings or get_settings()
    company_id, opportunity_id, meeting_ids, _ = demo_ids(organisation_id)
    phone_contact_id = demo_phone_contact_id(organisation_id)
    _, companion_meeting_ids, _, _ = demo_companion_ids(organisation_id)
    live_ids = demo_live_ids(organisation_id)
    google_meeting_id = uuid.uuid5(DEMO_NAMESPACE, f"{organisation_id}:online-google-meeting")
    debrief_interaction_ids = list(demo_debrief_ids(organisation_id)[:5])
    source_ids = demo_source_evidence_ids(organisation_id)
    document_ids = [source_ids[f"{label}:source"] for label in DEMO_DOCUMENTS]
    email_ids = [source_ids[f"{label}:source"] for label in DEMO_EMAILS]
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
        await _delete_meeting_batch(
            session,
            organisation_id,
            [*meeting_ids, *companion_meeting_ids, google_meeting_id, live_ids["meeting"]],
        )
        await _delete_visual_objects(session, active_settings, organisation_id, debrief_interaction_ids)
        await _delete_interaction_batch(session, organisation_id, debrief_interaction_ids)
        await _delete_document_objects(session, active_settings, organisation_id, document_ids)
        await _delete_source_database_rows(session, organisation_id, document_ids, email_ids)
        await session.execute(
            delete(OpportunityAuditEvent).where(
                OpportunityAuditEvent.organisation_id == organisation_id,
                OpportunityAuditEvent.opportunity_id == opportunity_id,
            )
        )
        await session.execute(
            delete(MethodologyReview).where(
                MethodologyReview.organisation_id == organisation_id,
                MethodologyReview.opportunity_id == opportunity_id,
            )
        )
        await session.execute(
            delete(MethodologyProjection).where(
                MethodologyProjection.organisation_id == organisation_id,
                MethodologyProjection.opportunity_id == opportunity_id,
            )
        )
        await session.execute(
            delete(OrganisationMethodologySetting).where(
                OrganisationMethodologySetting.organisation_id == organisation_id,
            )
        )
        await session.execute(
            delete(Opportunity).where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == opportunity_id,
            )
        )
        await session.execute(
            delete(Contact).where(
                Contact.organisation_id == organisation_id,
                Contact.id == phone_contact_id,
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
