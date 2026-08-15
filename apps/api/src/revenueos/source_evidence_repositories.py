from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from revenueos.models import (
    Company,
    Contact,
    DocumentFragment,
    DocumentSource,
    EmailSource,
    Evidence,
    Interaction,
    Opportunity,
    RevenueBrainSourceSnapshot,
    SourceCandidateEvidence,
)


@dataclass(frozen=True)
class DocumentSourceRecord:
    document: DocumentSource
    candidates: list[SourceCandidateEvidence]
    snapshot_id: UUID | None


@dataclass(frozen=True)
class EmailSourceRecord:
    email: EmailSource
    candidates: list[SourceCandidateEvidence]
    snapshot_id: UUID | None


class SourceEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(Company.organisation_id == organisation_id, Company.id == company_id)
            ),
        )

    async def get_opportunity(self, organisation_id: UUID, opportunity_id: UUID) -> Opportunity | None:
        return cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
            ),
        )

    async def get_interaction(self, organisation_id: UUID, interaction_id: UUID) -> Interaction | None:
        return cast(
            Interaction | None,
            await self.session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.id == interaction_id,
                    Interaction.deleted_at.is_(None),
                )
            ),
        )

    async def get_contact(self, organisation_id: UUID, contact_id: UUID) -> Contact | None:
        return cast(
            Contact | None,
            await self.session.scalar(
                select(Contact).where(Contact.organisation_id == organisation_id, Contact.id == contact_id)
            ),
        )

    async def document_by_idempotency(
        self, organisation_id: UUID, user_id: UUID, idempotency_key: str
    ) -> DocumentSource | None:
        return cast(
            DocumentSource | None,
            await self.session.scalar(
                select(DocumentSource).where(
                    DocumentSource.organisation_id == organisation_id,
                    DocumentSource.uploaded_by_user_id == user_id,
                    DocumentSource.idempotency_key == idempotency_key,
                )
            ),
        )

    async def document_by_checksum(self, organisation_id: UUID, checksum: str) -> DocumentSource | None:
        return cast(
            DocumentSource | None,
            await self.session.scalar(
                select(DocumentSource).where(
                    DocumentSource.organisation_id == organisation_id,
                    DocumentSource.checksum_sha256 == checksum,
                )
            ),
        )

    async def email_by_idempotency(
        self, organisation_id: UUID, user_id: UUID, idempotency_key: str
    ) -> EmailSource | None:
        return cast(
            EmailSource | None,
            await self.session.scalar(
                select(EmailSource).where(
                    EmailSource.organisation_id == organisation_id,
                    EmailSource.submitted_by_user_id == user_id,
                    EmailSource.idempotency_key == idempotency_key,
                )
            ),
        )

    async def email_by_checksum(self, organisation_id: UUID, checksum: str) -> EmailSource | None:
        return cast(
            EmailSource | None,
            await self.session.scalar(
                select(EmailSource).where(
                    EmailSource.organisation_id == organisation_id,
                    EmailSource.content_sha256 == checksum,
                )
            ),
        )

    async def count_documents_since(self, organisation_id: UUID, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.count(DocumentSource.id)).where(
                DocumentSource.organisation_id == organisation_id,
                DocumentSource.created_at >= since,
            )
        )
        return int(value or 0)

    async def stored_document_bytes(self, organisation_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.sum(DocumentSource.byte_size)).where(
                DocumentSource.organisation_id == organisation_id,
                DocumentSource.storage_status == "available",
                DocumentSource.deleted_at.is_(None),
            )
        )
        return int(value or 0)

    async def count_email_analyses_since(self, organisation_id: UUID, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.count(EmailSource.id)).where(
                EmailSource.organisation_id == organisation_id,
                EmailSource.created_at >= since,
                EmailSource.processing_attempts > 0,
            )
        )
        return int(value or 0)

    async def get_document(
        self,
        organisation_id: UUID,
        document_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> DocumentSourceRecord | None:
        statement = select(DocumentSource).where(
            DocumentSource.organisation_id == organisation_id,
            DocumentSource.id == document_id,
        )
        if not include_deleted:
            statement = statement.where(DocumentSource.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        document = await self.session.scalar(statement)
        if document is None:
            return None
        candidates = list(
            (
                await self.session.scalars(
                    select(SourceCandidateEvidence)
                    .where(
                        SourceCandidateEvidence.organisation_id == organisation_id,
                        SourceCandidateEvidence.document_source_id == document_id,
                    )
                    .order_by(SourceCandidateEvidence.created_at, SourceCandidateEvidence.id)
                )
            ).all()
        )
        snapshot_id = await self.session.scalar(
            select(RevenueBrainSourceSnapshot.id)
            .where(
                RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                RevenueBrainSourceSnapshot.document_source_id == document_id,
            )
            .order_by(RevenueBrainSourceSnapshot.version.desc())
            .limit(1)
        )
        return DocumentSourceRecord(document=document, candidates=candidates, snapshot_id=snapshot_id)

    async def get_email(
        self,
        organisation_id: UUID,
        email_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> EmailSourceRecord | None:
        statement = select(EmailSource).where(
            EmailSource.organisation_id == organisation_id,
            EmailSource.id == email_id,
        )
        if not include_deleted:
            statement = statement.where(EmailSource.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        email = await self.session.scalar(statement)
        if email is None:
            return None
        candidates = list(
            (
                await self.session.scalars(
                    select(SourceCandidateEvidence)
                    .where(
                        SourceCandidateEvidence.organisation_id == organisation_id,
                        SourceCandidateEvidence.email_source_id == email_id,
                    )
                    .order_by(SourceCandidateEvidence.created_at, SourceCandidateEvidence.id)
                )
            ).all()
        )
        snapshot_id = await self.session.scalar(
            select(RevenueBrainSourceSnapshot.id)
            .where(
                RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                RevenueBrainSourceSnapshot.email_source_id == email_id,
            )
            .order_by(RevenueBrainSourceSnapshot.version.desc())
            .limit(1)
        )
        return EmailSourceRecord(email=email, candidates=candidates, snapshot_id=snapshot_id)

    async def document_fragments(self, organisation_id: UUID, document_id: UUID) -> list[DocumentFragment]:
        return list(
            (
                await self.session.scalars(
                    select(DocumentFragment)
                    .where(
                        DocumentFragment.organisation_id == organisation_id,
                        DocumentFragment.document_source_id == document_id,
                        DocumentFragment.deleted_at.is_(None),
                    )
                    .order_by(DocumentFragment.paragraph_index, DocumentFragment.id)
                )
            ).all()
        )

    async def get_candidates_for_review(
        self,
        organisation_id: UUID,
        *,
        document_id: UUID | None = None,
        email_id: UUID | None = None,
    ) -> list[SourceCandidateEvidence]:
        conditions = [SourceCandidateEvidence.organisation_id == organisation_id]
        if document_id is not None:
            conditions.append(SourceCandidateEvidence.document_source_id == document_id)
        else:
            conditions.append(SourceCandidateEvidence.email_source_id == email_id)
        return list(
            (
                await self.session.scalars(
                    select(SourceCandidateEvidence)
                    .where(*conditions)
                    .order_by(SourceCandidateEvidence.created_at, SourceCandidateEvidence.id)
                    .with_for_update()
                )
            ).all()
        )

    async def accepted_candidate(self, organisation_id: UUID, candidate_id: UUID) -> SourceCandidateEvidence | None:
        return cast(
            SourceCandidateEvidence | None,
            await self.session.scalar(
                select(SourceCandidateEvidence).where(
                    SourceCandidateEvidence.organisation_id == organisation_id,
                    SourceCandidateEvidence.id == candidate_id,
                    SourceCandidateEvidence.review_state == "accepted",
                )
            ),
        )

    async def next_snapshot_version(self, organisation_id: UUID, source_evidence_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.max(RevenueBrainSourceSnapshot.version)).where(
                RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                RevenueBrainSourceSnapshot.source_evidence_id == source_evidence_id,
            )
        )
        return int(value or 0) + 1

    async def list_snapshots_for_opportunity(
        self, organisation_id: UUID, opportunity_id: UUID, *, limit: int = 20
    ) -> list[RevenueBrainSourceSnapshot]:
        return await self._eligible_snapshots(
            organisation_id,
            RevenueBrainSourceSnapshot.opportunity_id == opportunity_id,
            limit=limit,
        )

    async def list_snapshots_for_company(
        self, organisation_id: UUID, company_id: UUID, *, limit: int = 20
    ) -> list[RevenueBrainSourceSnapshot]:
        return await self._eligible_snapshots(
            organisation_id,
            RevenueBrainSourceSnapshot.company_id == company_id,
            limit=limit,
        )

    async def _eligible_snapshots(
        self, organisation_id: UUID, scope_condition: ColumnElement[bool], *, limit: int
    ) -> list[RevenueBrainSourceSnapshot]:
        rows = list(
            (
                await self.session.scalars(
                    select(RevenueBrainSourceSnapshot)
                    .join(
                        Evidence,
                        and_(
                            Evidence.organisation_id == RevenueBrainSourceSnapshot.organisation_id,
                            Evidence.id == RevenueBrainSourceSnapshot.source_evidence_id,
                        ),
                    )
                    .where(
                        RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                        scope_condition,
                        Evidence.lifecycle_status == "available",
                        Evidence.deleted_at.is_(None),
                    )
                    .order_by(
                        RevenueBrainSourceSnapshot.created_at.desc(),
                        RevenueBrainSourceSnapshot.id.desc(),
                    )
                    .limit(limit)
                )
            ).all()
        )
        eligible: list[RevenueBrainSourceSnapshot] = []
        for snapshot in rows:
            try:
                evidence_ids = [UUID(value) for value in snapshot.source_evidence_ids]
            except (TypeError, ValueError):
                continue
            if not evidence_ids:
                continue
            available = await self.session.scalar(
                select(func.count(Evidence.id)).where(
                    Evidence.organisation_id == organisation_id,
                    Evidence.id.in_(evidence_ids),
                    Evidence.validation_state == "verified",
                    Evidence.lifecycle_status == "available",
                    Evidence.deleted_at.is_(None),
                )
            )
            if int(available or 0) == len(evidence_ids):
                eligible.append(snapshot)
        return eligible
