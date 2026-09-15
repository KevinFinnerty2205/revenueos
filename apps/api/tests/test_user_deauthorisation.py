from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from revenueos.auth import (
    AuthenticationError,
    VerifiedIdentity,
    _require_current_membership_authority,
    _resolve_identity,
    identity_organisation_id,
    identity_user_id,
)
from revenueos.beta_dependencies import get_session_revoker
from revenueos.clerk_sessions import SessionRevocationResult
from revenueos.models import BetaSystemEvent, Organisation, OrganisationMembership, User

from .conftest import PRIMARY_ORGANISATION_ID, SECONDARY_ORGANISATION_ID

TARGET_USER_ID = UUID("00000000-0000-4000-8000-000000000099")
TARGET_EXTERNAL_ID = "user_deauthorisation_A1"


class RecordingSessionRevoker:
    def __init__(self, *results: SessionRevocationResult) -> None:
        self.results = list(results)
        self.external_id_pairs: list[tuple[str, str]] = []

    async def revoke_active_sessions(
        self,
        external_user_id: str,
        external_organisation_id: str,
    ) -> SessionRevocationResult:
        self.external_id_pairs.append((external_user_id, external_organisation_id))
        if self.results:
            return self.results.pop(0)
        return SessionRevocationResult(outcome="succeeded", revoked_session_count=0)


@pytest.fixture
def target_member(app: FastAPI) -> Iterator[None]:
    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)

    async def create() -> None:
        async with factory() as session:
            session.add(
                User(
                    id=TARGET_USER_ID,
                    external_auth_id=TARGET_EXTERNAL_ID,
                    email="deauthorisation@example.test",
                    display_name="Deauthorisation Target",
                )
            )
            session.add_all(
                [
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=TARGET_USER_ID,
                        role="member",
                    ),
                    OrganisationMembership(
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        user_id=TARGET_USER_ID,
                        role="member",
                    ),
                ]
            )
            await session.commit()

    async def remove() -> None:
        async with factory() as session:
            await session.execute(delete(BetaSystemEvent).where(BetaSystemEvent.subject_id == TARGET_USER_ID))
            await session.execute(
                delete(OrganisationMembership).where(OrganisationMembership.user_id == TARGET_USER_ID)
            )
            await session.execute(delete(User).where(User.id == TARGET_USER_ID))
            await session.commit()

    asyncio.run(create())
    yield
    app.dependency_overrides.pop(get_session_revoker, None)
    asyncio.run(remove())


def _identity(organisation: str, issued_at: datetime) -> VerifiedIdentity:
    return VerifiedIdentity(
        external_auth_id=TARGET_EXTERNAL_ID,
        external_organisation_id=organisation,
        display_name="Deauthorisation Target",
        email="deauthorisation@example.test",
        organisation_name="Synthetic organisation",
        role="member",
        auth_mode="clerk",
        issued_at=issued_at,
    )


def test_disable_revokes_exact_user_and_old_auth_never_revives(
    app: FastAPI,
    client: TestClient,
    target_member: None,
) -> None:
    del target_member
    revoker = RecordingSessionRevoker(
        SessionRevocationResult(outcome="succeeded", revoked_session_count=2),
        SessionRevocationResult(outcome="succeeded", revoked_session_count=0),
    )
    app.dependency_overrides[get_session_revoker] = lambda: revoker
    issued_before_disable = datetime.now(UTC) - timedelta(minutes=1)

    disabled = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["member"]["status"] == "disabled"
    assert disabled.json()["sessionRevocation"] == {
        "outcome": "succeeded",
        "revokedSessionCount": 2,
    }
    assert revoker.external_id_pairs == [(TARGET_EXTERNAL_ID, "org_dev_001")]

    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)

    async def verify_disabled_and_reenabled() -> None:
        async with factory() as session:
            primary_membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            secondary_membership = await session.get(
                OrganisationMembership,
                (SECONDARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert primary_membership is not None
            assert primary_membership.status == "disabled"
            assert primary_membership.authority_version == 2
            assert primary_membership.authentication_valid_after is not None
            disabled_watermark = primary_membership.authentication_valid_after.replace(tzinfo=UTC)
            assert secondary_membership is not None
            assert secondary_membership.status == "active"
            with pytest.raises(AuthenticationError, match="disabled"):
                _require_current_membership_authority(
                    _identity("org_dev_001", issued_before_disable),
                    primary_membership,
                )
            _require_current_membership_authority(
                _identity("org_other_001", datetime.now(UTC)),
                secondary_membership,
            )

        reenabled = client.patch(
            f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
            json={"status": "active"},
        )
        assert reenabled.status_code == 200, reenabled.text
        assert reenabled.json()["member"]["status"] == "active"
        assert revoker.external_id_pairs == [
            (TARGET_EXTERNAL_ID, "org_dev_001"),
            (TARGET_EXTERNAL_ID, "org_dev_001"),
        ]

        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert membership is not None
            assert membership.authentication_valid_after is not None
            reenabled_watermark = membership.authentication_valid_after.replace(tzinfo=UTC)
            assert reenabled_watermark > disabled_watermark
            disabled_period_identity = _identity(
                "org_dev_001",
                disabled_watermark + (reenabled_watermark - disabled_watermark) / 2,
            )
            with pytest.raises(AuthenticationError, match="predates"):
                _require_current_membership_authority(
                    _identity("org_dev_001", issued_before_disable),
                    membership,
                )
            with pytest.raises(AuthenticationError, match="predates"):
                _require_current_membership_authority(disabled_period_identity, membership)
            _require_current_membership_authority(
                _identity(
                    "org_dev_001",
                    reenabled_watermark + timedelta(seconds=1),
                ),
                membership,
            )

    asyncio.run(verify_disabled_and_reenabled())


def test_provider_failure_leaves_member_disabled_and_blocks_reenable(
    app: FastAPI,
    client: TestClient,
    target_member: None,
) -> None:
    del target_member
    failure = SessionRevocationResult(
        outcome="unknown",
        revoked_session_count=0,
        failure_code="clerk_session_revoke_outcome_unknown",
    )
    revoker = RecordingSessionRevoker(failure, failure)
    app.dependency_overrides[get_session_revoker] = lambda: revoker

    disabled = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["member"]["status"] == "disabled"
    assert disabled.json()["sessionRevocation"]["outcome"] == "unknown"

    reenabled = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"status": "active"},
    )
    assert reenabled.status_code == 503
    assert reenabled.json()["code"] == "session_revocation_unconfirmed"

    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)

    async def verify() -> None:
        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert membership is not None
            assert membership.status == "disabled"
            outcomes = list(
                (
                    await session.scalars(
                        select(BetaSystemEvent)
                        .where(
                            BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                            BetaSystemEvent.subject_id == TARGET_USER_ID,
                            BetaSystemEvent.event_type == "member_session_revocation_completed",
                        )
                        .order_by(BetaSystemEvent.created_at, BetaSystemEvent.id)
                    )
                ).all()
            )
            assert len(outcomes) == 2
            assert all(event.metadata_json["outcome"] == "unknown" for event in outcomes)
            assert all(
                "clerk" not in str(event.metadata_json).casefold()
                or "failurecode" in str(event.metadata_json).casefold()
                for event in outcomes
            )

    asyncio.run(verify())


def test_wrong_tenant_and_self_disable_never_call_session_revocation(
    app: FastAPI,
    client: TestClient,
    target_member: None,
) -> None:
    del target_member
    revoker = RecordingSessionRevoker()
    app.dependency_overrides[get_session_revoker] = lambda: revoker
    unrelated_user_id = UUID("00000000-0000-4000-8000-000000000012")

    wrong_tenant = client.patch(
        f"/api/v1/beta/admin/members/{unrelated_user_id}",
        json={"status": "disabled"},
    )
    assert wrong_tenant.status_code == 404
    self_disable = client.patch(
        "/api/v1/beta/admin/members/00000000-0000-4000-8000-000000000001",
        json={"status": "disabled"},
    )
    assert self_disable.status_code == 409
    assert self_disable.json()["code"] == "cannot_disable_self"
    assert revoker.external_id_pairs == []


def test_removed_membership_is_denied_and_restore_requires_normal_authentication(app: FastAPI) -> None:
    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)
    external_organisation_id = "org_deauthorisation_removal_A1"
    external_user_id = "user_deauthorisation_removal_A1"
    organisation_id = identity_organisation_id(external_organisation_id)
    user_id = identity_user_id(external_user_id)
    identity = VerifiedIdentity(
        external_auth_id=external_user_id,
        external_organisation_id=external_organisation_id,
        display_name="Membership Removal Target",
        email="membership-removal@example.test",
        organisation_name="Membership removal tenant",
        role="member",
        auth_mode="clerk",
        issued_at=datetime.now(UTC),
    )

    async def scenario() -> None:
        try:
            async with factory() as session:
                session.add(
                    Organisation(
                        id=organisation_id,
                        external_auth_id=external_organisation_id,
                        name="Membership removal tenant",
                        slug="membership-removal-tenant",
                    )
                )
                session.add(
                    User(
                        id=user_id,
                        external_auth_id=external_user_id,
                        email="membership-removal@example.test",
                        display_name="Membership Removal Target",
                    )
                )
                session.add(
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="member",
                    )
                )
                await session.commit()

            async with factory() as session:
                authorised = await _resolve_identity(session, identity, allow_provisioning=False)
                assert authorised.organisation_id == organisation_id
                await session.execute(
                    delete(OrganisationMembership).where(
                        OrganisationMembership.organisation_id == organisation_id,
                        OrganisationMembership.user_id == user_id,
                    )
                )
                await session.commit()

            async with factory() as session:
                with pytest.raises(AuthenticationError, match="membership has not been provisioned"):
                    await _resolve_identity(session, identity, allow_provisioning=False)
                await session.rollback()
                session.add(
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="member",
                    )
                )
                await session.commit()

            async with factory() as session:
                restored = await _resolve_identity(
                    session,
                    replace(identity, issued_at=datetime.now(UTC)),
                    allow_provisioning=False,
                )
                assert restored.organisation_id == organisation_id
        finally:
            async with factory() as session:
                await session.execute(
                    delete(OrganisationMembership).where(
                        OrganisationMembership.organisation_id == organisation_id,
                        OrganisationMembership.user_id == user_id,
                    )
                )
                await session.execute(delete(Organisation).where(Organisation.id == organisation_id))
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()

    asyncio.run(scenario())
