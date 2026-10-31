from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
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


def test_admin_can_promote_and_demote_member_with_durable_authority_and_content_free_audit(
    app: FastAPI,
    client: TestClient,
    target_member: None,
) -> None:
    del target_member
    revoker = RecordingSessionRevoker()
    app.dependency_overrides[get_session_revoker] = lambda: revoker
    issued_before_change = datetime.now(UTC) - timedelta(minutes=1)

    promoted = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["member"]["role"] == "admin"
    assert promoted.json()["member"]["status"] == "active"
    assert promoted.json()["sessionRevocation"] == {
        "outcome": "not_required",
        "revokedSessionCount": 0,
    }
    assert revoker.external_id_pairs == []

    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)

    async def verify_promotion() -> datetime:
        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert membership is not None
            assert membership.role == "admin"
            assert membership.status == "active"
            assert membership.authority_version == 2
            assert membership.authentication_valid_after is not None
            watermark: datetime = membership.authentication_valid_after.replace(tzinfo=UTC)
            with pytest.raises(AuthenticationError, match="predates"):
                _require_current_membership_authority(
                    _identity("org_dev_001", issued_before_change),
                    membership,
                )
            events = list(
                (
                    await session.scalars(
                        select(BetaSystemEvent).where(
                            BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                            BetaSystemEvent.subject_id == TARGET_USER_ID,
                            BetaSystemEvent.event_type == "member_role_changed",
                        )
                    )
                ).all()
            )
            assert len(events) == 1
            assert events[0].metadata_json == {
                "previousRole": "member",
                "role": "admin",
                "authorityVersion": 2,
            }
            assert TARGET_EXTERNAL_ID not in str(events[0].metadata_json)

        return watermark

    promotion_watermark = asyncio.run(verify_promotion())

    unchanged = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"role": "admin"},
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["member"]["role"] == "admin"
    assert unchanged.json()["sessionRevocation"]["outcome"] == "not_required"

    async def verify_noop() -> None:
        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert membership is not None
            assert membership.authority_version == 2
            assert membership.authentication_valid_after is not None
            assert membership.authentication_valid_after.replace(tzinfo=UTC) == promotion_watermark
            event_count = await session.scalar(
                select(func.count())
                .select_from(BetaSystemEvent)
                .where(
                    BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                    BetaSystemEvent.subject_id == TARGET_USER_ID,
                    BetaSystemEvent.event_type == "member_role_changed",
                )
            )
            assert event_count == 1

    asyncio.run(verify_noop())

    demoted = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"role": "member"},
    )
    assert demoted.status_code == 200, demoted.text
    assert demoted.json()["member"]["role"] == "member"

    async def verify_demotion() -> None:
        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert membership is not None
            assert membership.role == "member"
            assert membership.authority_version == 3
            assert membership.authentication_valid_after is not None
            assert membership.authentication_valid_after.replace(tzinfo=UTC) > promotion_watermark
            events = list(
                (
                    await session.scalars(
                        select(BetaSystemEvent)
                        .where(
                            BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                            BetaSystemEvent.subject_id == TARGET_USER_ID,
                            BetaSystemEvent.event_type == "member_role_changed",
                        )
                        .order_by(BetaSystemEvent.created_at, BetaSystemEvent.id)
                    )
                ).all()
            )
            events_by_role = {event.metadata_json["role"]: event.metadata_json for event in events}
            assert set(events_by_role) == {"admin", "member"}
            assert events_by_role["member"] == {
                "previousRole": "admin",
                "role": "member",
                "authorityVersion": 3,
            }

    asyncio.run(verify_demotion())


def test_reviewed_membership_role_is_not_overwritten_by_a_stale_provider_claim(app: FastAPI) -> None:
    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)
    external_organisation_id = "org_role_authority_A1"
    external_user_id = "user_role_authority_A1"
    organisation_id = identity_organisation_id(external_organisation_id)
    user_id = identity_user_id(external_user_id)
    authority_changed_at = datetime.now(UTC) - timedelta(seconds=1)
    identity = VerifiedIdentity(
        external_auth_id=external_user_id,
        external_organisation_id=external_organisation_id,
        display_name="Role Authority Target",
        email="role-authority@example.test",
        organisation_name="Role authority tenant",
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
                        name="Role authority tenant",
                        slug="role-authority-tenant",
                    )
                )
                session.add(
                    User(
                        id=user_id,
                        external_auth_id=external_user_id,
                        email="role-authority@example.test",
                        display_name="Role Authority Target",
                    )
                )
                session.add(
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="admin",
                        authority_version=2,
                        authentication_valid_after=authority_changed_at,
                    )
                )
                await session.commit()

            async with factory() as session:
                resolved = await _resolve_identity(session, identity, allow_provisioning=True)
                assert resolved.role == "admin"

            async with factory() as session:
                membership = await session.get(OrganisationMembership, (organisation_id, user_id))
                assert membership is not None
                assert membership.role == "admin"
                assert membership.authority_version == 2
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


def test_member_role_change_blocks_last_admin_self_demotion_and_ambiguous_commands(
    app: FastAPI,
    client: TestClient,
    target_member: None,
) -> None:
    del target_member
    primary_user_id = "00000000-0000-4000-8000-000000000001"

    last_admin = client.patch(
        f"/api/v1/beta/admin/members/{primary_user_id}",
        json={"role": "member"},
    )
    assert last_admin.status_code == 409
    assert last_admin.json()["code"] == "last_active_admin_required"

    promoted = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200, promoted.text
    self_demotion = client.patch(
        f"/api/v1/beta/admin/members/{primary_user_id}",
        json={"role": "member"},
    )
    assert self_demotion.status_code == 409
    assert self_demotion.json()["code"] == "cannot_demote_self"

    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)

    async def set_primary_user_status(status: str) -> None:
        async with factory() as session:
            primary_user = await session.get(User, UUID(primary_user_id))
            assert primary_user is not None
            primary_user.status = status
            await session.commit()

    asyncio.run(set_primary_user_status("disabled"))
    try:
        disabled_user_not_counted = client.patch(
            f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
            json={"role": "member"},
        )
    finally:
        asyncio.run(set_primary_user_status("active"))
    assert disabled_user_not_counted.status_code == 409
    assert disabled_user_not_counted.json()["code"] == "last_active_admin_required"

    assert (
        client.patch(
            f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
            json={},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
            json={"role": "member", "status": "disabled"},
        ).status_code
        == 422
    )


def test_member_disable_preserves_last_active_admin_and_ignores_disabled_users(
    app: FastAPI,
    client: TestClient,
    target_member: None,
) -> None:
    del target_member
    primary_user_id = UUID("00000000-0000-4000-8000-000000000001")
    revoker = RecordingSessionRevoker()
    app.dependency_overrides[get_session_revoker] = lambda: revoker

    promoted = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200, promoted.text

    factory = app.state.session_factory
    assert isinstance(factory, async_sessionmaker)

    async def set_primary_user_status(status: str) -> None:
        async with factory() as session:
            primary_user = await session.get(User, primary_user_id)
            assert primary_user is not None
            primary_user.status = status
            await session.commit()

    asyncio.run(set_primary_user_status("disabled"))
    try:
        refused = client.patch(
            f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
            json={"status": "disabled"},
        )
    finally:
        asyncio.run(set_primary_user_status("active"))

    assert refused.status_code == 409
    assert refused.json()["code"] == "last_active_admin_required"
    assert revoker.external_id_pairs == []

    async def verify_refusal_was_atomic() -> None:
        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, TARGET_USER_ID),
            )
            assert membership is not None
            assert membership.role == "admin"
            assert membership.status == "active"
            assert membership.authority_version == 2

    asyncio.run(verify_refusal_was_atomic())

    disabled = client.patch(
        f"/api/v1/beta/admin/members/{TARGET_USER_ID}",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["member"]["role"] == "admin"
    assert disabled.json()["member"]["status"] == "disabled"
    assert revoker.external_id_pairs == [(TARGET_EXTERNAL_ID, "org_dev_001")]


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
