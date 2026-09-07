from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    Contact,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreatePresentation,
    CreatePresentationVersion,
    DealRoom,
    DealRoomAccessLink,
    DealRoomRevision,
    Opportunity,
    Organisation,
)


@dataclass(frozen=True)
class PublicProjectionRecord:
    snapshot: dict[str, object]
    revision: int
    published_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True)
class PublicPresentationRecord:
    storage_key: str
    checksum_sha256: str
    byte_size: int
    resource_title: str


class DealRoomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, entity: object) -> None:
        self.session.add(entity)

    async def organisation(self, organisation_id: UUID) -> Organisation | None:
        return await self.session.get(Organisation, organisation_id)

    async def opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> Opportunity | None:
        statement = select(Opportunity).where(
            Opportunity.organisation_id == organisation_id,
            Opportunity.id == opportunity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Opportunity | None, await self.session.scalar(statement))

    async def company(self, organisation_id: UUID, company_id: UUID | None) -> Company | None:
        if company_id is None:
            return None
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == organisation_id,
                    Company.id == company_id,
                    Company.archived_at.is_(None),
                )
            ),
        )

    async def room_for_opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> DealRoom | None:
        statement = select(DealRoom).where(
            DealRoom.organisation_id == organisation_id,
            DealRoom.opportunity_id == opportunity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(DealRoom | None, await self.session.scalar(statement))

    async def revisions(self, organisation_id: UUID, room_id: UUID) -> list[DealRoomRevision]:
        return list(
            (
                await self.session.scalars(
                    select(DealRoomRevision)
                    .where(
                        DealRoomRevision.organisation_id == organisation_id,
                        DealRoomRevision.room_id == room_id,
                    )
                    .order_by(DealRoomRevision.revision.desc())
                )
            ).all()
        )

    async def active_link(self, organisation_id: UUID, room_id: UUID) -> DealRoomAccessLink | None:
        return cast(
            DealRoomAccessLink | None,
            await self.session.scalar(
                select(DealRoomAccessLink)
                .where(
                    DealRoomAccessLink.organisation_id == organisation_id,
                    DealRoomAccessLink.room_id == room_id,
                    DealRoomAccessLink.revoked_at.is_(None),
                )
                .order_by(DealRoomAccessLink.created_at.desc())
                .limit(1)
            ),
        )

    async def approved_business_cases(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> list[tuple[CreateBusinessCase, CreateBusinessCaseVersion]]:
        result = await self.session.execute(
            select(CreateBusinessCase, CreateBusinessCaseVersion)
            .join(
                CreateBusinessCaseVersion,
                and_(
                    CreateBusinessCaseVersion.organisation_id == CreateBusinessCase.organisation_id,
                    CreateBusinessCaseVersion.case_id == CreateBusinessCase.id,
                ),
            )
            .where(
                CreateBusinessCase.organisation_id == organisation_id,
                CreateBusinessCase.opportunity_id == opportunity_id,
                CreateBusinessCase.archived_at.is_(None),
                CreateBusinessCaseVersion.review_state == "approved",
                CreateBusinessCaseVersion.approved_at.is_not(None),
            )
            .order_by(CreateBusinessCase.updated_at.desc(), CreateBusinessCaseVersion.version.desc())
        )
        return list(result.tuples().all())

    async def approved_business_case(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        version_id: UUID,
    ) -> tuple[CreateBusinessCase, CreateBusinessCaseVersion] | None:
        row = (
            await self.session.execute(
                select(CreateBusinessCase, CreateBusinessCaseVersion)
                .join(
                    CreateBusinessCaseVersion,
                    and_(
                        CreateBusinessCaseVersion.organisation_id == CreateBusinessCase.organisation_id,
                        CreateBusinessCaseVersion.case_id == CreateBusinessCase.id,
                    ),
                )
                .where(
                    CreateBusinessCase.organisation_id == organisation_id,
                    CreateBusinessCase.opportunity_id == opportunity_id,
                    CreateBusinessCase.archived_at.is_(None),
                    CreateBusinessCaseVersion.id == version_id,
                    CreateBusinessCaseVersion.review_state == "approved",
                    CreateBusinessCaseVersion.approved_at.is_not(None),
                )
            )
        ).first()
        return cast(tuple[CreateBusinessCase, CreateBusinessCaseVersion] | None, row)

    async def approved_presentations(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> list[tuple[CreatePresentation, CreatePresentationVersion]]:
        result = await self.session.execute(
            select(CreatePresentation, CreatePresentationVersion)
            .join(
                CreatePresentationVersion,
                and_(
                    CreatePresentationVersion.organisation_id == CreatePresentation.organisation_id,
                    CreatePresentationVersion.presentation_id == CreatePresentation.id,
                ),
            )
            .where(
                CreatePresentation.organisation_id == organisation_id,
                CreatePresentation.opportunity_id == opportunity_id,
                CreatePresentation.archived_at.is_(None),
                CreatePresentationVersion.state == "ready",
                CreatePresentationVersion.review_state == "approved",
                CreatePresentationVersion.storage_status == "available",
                CreatePresentationVersion.pptx_storage_key.is_not(None),
                CreatePresentationVersion.approved_at.is_not(None),
            )
            .order_by(CreatePresentation.updated_at.desc(), CreatePresentationVersion.version.desc())
        )
        return list(result.tuples().all())

    async def approved_presentation(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        version_id: UUID,
    ) -> tuple[CreatePresentation, CreatePresentationVersion] | None:
        row = (
            await self.session.execute(
                select(CreatePresentation, CreatePresentationVersion)
                .join(
                    CreatePresentationVersion,
                    and_(
                        CreatePresentationVersion.organisation_id == CreatePresentation.organisation_id,
                        CreatePresentationVersion.presentation_id == CreatePresentation.id,
                    ),
                )
                .where(
                    CreatePresentation.organisation_id == organisation_id,
                    CreatePresentation.opportunity_id == opportunity_id,
                    CreatePresentation.archived_at.is_(None),
                    CreatePresentationVersion.id == version_id,
                    CreatePresentationVersion.state == "ready",
                    CreatePresentationVersion.review_state == "approved",
                    CreatePresentationVersion.storage_status == "available",
                    CreatePresentationVersion.pptx_storage_key.is_not(None),
                    CreatePresentationVersion.checksum_sha256.is_not(None),
                    CreatePresentationVersion.approved_at.is_not(None),
                )
            )
        ).first()
        return cast(tuple[CreatePresentation, CreatePresentationVersion] | None, row)

    async def contact(
        self,
        organisation_id: UUID,
        company_id: UUID | None,
        contact_id: UUID,
    ) -> Contact | None:
        if company_id is None:
            return None
        return cast(
            Contact | None,
            await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == organisation_id,
                    Contact.company_id == company_id,
                    Contact.id == contact_id,
                    Contact.archived_at.is_(None),
                )
            ),
        )

    async def public_projection(self, token_hash: str, now: datetime) -> PublicProjectionRecord | None:
        if self.session.get_bind().dialect.name == "postgresql":
            pg_row = (
                (
                    await self.session.execute(
                        text(
                            "SELECT snapshot_json, revision, published_at, expires_at "
                            "FROM public.revenueos_public_deal_room(:token_hash)"
                        ),
                        {"token_hash": token_hash},
                    )
                )
                .mappings()
                .first()
            )
            if pg_row is None:
                return None
            return PublicProjectionRecord(
                snapshot=cast(dict[str, object], pg_row["snapshot_json"]),
                revision=int(pg_row["revision"]),
                published_at=cast(datetime, pg_row["published_at"]),
                expires_at=cast(datetime | None, pg_row["expires_at"]),
            )
        sqlite_row = (
            await self.session.execute(
                select(DealRoomRevision, DealRoomAccessLink)
                .join(
                    DealRoom,
                    and_(
                        DealRoom.organisation_id == DealRoomRevision.organisation_id,
                        DealRoom.published_revision_id == DealRoomRevision.id,
                    ),
                )
                .join(
                    DealRoomAccessLink,
                    and_(
                        DealRoomAccessLink.organisation_id == DealRoom.organisation_id,
                        DealRoomAccessLink.room_id == DealRoom.id,
                    ),
                )
                .join(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == DealRoom.organisation_id,
                        Opportunity.id == DealRoom.opportunity_id,
                    ),
                )
                .where(
                    DealRoomAccessLink.token_hash == token_hash,
                    DealRoomAccessLink.revoked_at.is_(None),
                    (DealRoomAccessLink.expires_at.is_(None) | (DealRoomAccessLink.expires_at > now)),
                    DealRoom.status == "published",
                    Opportunity.status == "open",
                    Opportunity.archived_at.is_(None),
                )
                .limit(1)
            )
        ).first()
        if sqlite_row is None:
            return None
        revision, link = cast(tuple[DealRoomRevision, DealRoomAccessLink], sqlite_row)
        return PublicProjectionRecord(
            snapshot=revision.snapshot_json,
            revision=revision.revision,
            published_at=revision.published_at,
            expires_at=link.expires_at,
        )

    async def public_presentation(
        self,
        token_hash: str,
        resource_id: UUID,
        now: datetime,
    ) -> PublicPresentationRecord | None:
        if self.session.get_bind().dialect.name == "postgresql":
            pg_row = (
                (
                    await self.session.execute(
                        text(
                            "SELECT storage_key, checksum_sha256, byte_size, resource_title "
                            "FROM public.revenueos_public_deal_room_resource"
                            "(:token_hash, :resource_id)"
                        ),
                        {"token_hash": token_hash, "resource_id": str(resource_id)},
                    )
                )
                .mappings()
                .first()
            )
            if pg_row is None:
                return None
            return PublicPresentationRecord(
                storage_key=str(pg_row["storage_key"]),
                checksum_sha256=str(pg_row["checksum_sha256"]),
                byte_size=int(pg_row["byte_size"]),
                resource_title=str(pg_row["resource_title"]),
            )
        projection = await self.public_projection(token_hash, now)
        if projection is None:
            return None
        resources = projection.snapshot.get("resources", [])
        if not isinstance(resources, list):
            return None
        selected = next(
            (
                item
                for item in resources
                if isinstance(item, dict) and item.get("id") == str(resource_id) and item.get("kind") == "presentation"
            ),
            None,
        )
        if selected is None:
            return None
        try:
            version_id = UUID(str(selected.get("presentationVersionId")))
        except (TypeError, ValueError):
            return None
        sqlite_row = (
            await self.session.execute(
                select(CreatePresentationVersion, CreatePresentation)
                .join(
                    CreatePresentation,
                    and_(
                        CreatePresentation.organisation_id == CreatePresentationVersion.organisation_id,
                        CreatePresentation.id == CreatePresentationVersion.presentation_id,
                    ),
                )
                .join(
                    DealRoom,
                    and_(
                        DealRoom.organisation_id == CreatePresentation.organisation_id,
                        DealRoom.opportunity_id == CreatePresentation.opportunity_id,
                    ),
                )
                .join(
                    DealRoomAccessLink,
                    and_(
                        DealRoomAccessLink.organisation_id == DealRoom.organisation_id,
                        DealRoomAccessLink.room_id == DealRoom.id,
                    ),
                )
                .join(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == DealRoom.organisation_id,
                        Opportunity.id == DealRoom.opportunity_id,
                    ),
                )
                .where(
                    CreatePresentationVersion.id == version_id,
                    DealRoomAccessLink.token_hash == token_hash,
                    DealRoomAccessLink.revoked_at.is_(None),
                    (DealRoomAccessLink.expires_at.is_(None) | (DealRoomAccessLink.expires_at > now)),
                    DealRoom.status == "published",
                    Opportunity.status == "open",
                    Opportunity.archived_at.is_(None),
                    CreatePresentationVersion.state == "ready",
                    CreatePresentationVersion.review_state == "approved",
                    CreatePresentationVersion.storage_status == "available",
                    CreatePresentationVersion.pptx_storage_key.is_not(None),
                    CreatePresentationVersion.checksum_sha256.is_not(None),
                    CreatePresentation.archived_at.is_(None),
                )
            )
        ).first()
        if sqlite_row is None:
            return None
        version, _presentation = cast(tuple[CreatePresentationVersion, CreatePresentation], sqlite_row)
        assert version.pptx_storage_key is not None
        assert version.checksum_sha256 is not None
        return PublicPresentationRecord(
            storage_key=version.pptx_storage_key,
            checksum_sha256=version.checksum_sha256,
            byte_size=int(version.byte_size or 0),
            resource_title=str(selected.get("title") or "Presentation"),
        )
