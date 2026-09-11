"""Add immutable organisation Terms acceptance evidence.

Revision ID: 0063_terms_acceptance
Revises: 0062_live_stripe_billing

WO-054 records explicit organisation-administrator acceptance of one exact,
server-controlled Terms release. The event is tenant isolated, immutable and
deleted only through the approved organisation-deletion workflow.

This revision also conditionally repairs schema items added to already-applied
historical migration files before 0063 was created. Fresh databases already
contain those items, so the repair is a no-op there.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0063_terms_acceptance"
down_revision: str | None = "0062_live_stripe_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "terms_acceptances"


def _lower_hex_64(column_name: str) -> str:
    remainder = column_name
    for character in "0123456789abcdef":
        remainder = f"replace({remainder}, '{character}', '')"
    return f"length({column_name}) = 64 AND {column_name} = lower({column_name}) AND {remainder} = ''"


def _create_unresolved_checkout_index() -> None:
    op.create_index(
        "uq_billing_operations_org_unresolved_checkout",
        "billing_operations",
        ["organisation_id", "provider_mode"],
        unique=True,
        postgresql_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
        sqlite_where=sa.text("operation_type = 'checkout' AND status IN ('pending', 'unknown')"),
    )


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _checks(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(op.get_bind()).get_check_constraints(table_name)
        if constraint["name"] is not None
    }


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name) if index["name"] is not None}


def _repair_deal_room_public_projections() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.revenueos_public_deal_room(
            requested_token_hash text
        )
        RETURNS TABLE (snapshot_json json, revision integer, published_at timestamptz, expires_at timestamptz)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT jsonb_build_object(
                       'schemaVersion', revisions.snapshot_json::jsonb -> 'schemaVersion',
                       'revision', to_jsonb(revisions.revision),
                       'publishedAt', to_jsonb(revisions.published_at),
                       'sellerCompanyName', revisions.snapshot_json::jsonb -> 'sellerCompanyName',
                       'customerCompanyName', revisions.snapshot_json::jsonb -> 'customerCompanyName',
                       'opportunityName', revisions.snapshot_json::jsonb -> 'opportunityName',
                       'overview', revisions.snapshot_json::jsonb -> 'overview',
                       'businessCase',
                       CASE
                           WHEN jsonb_typeof(revisions.snapshot_json::jsonb -> 'businessCase') = 'object'
                           THEN jsonb_build_object(
                               'title', revisions.snapshot_json::jsonb #> '{businessCase,title}',
                               'version', revisions.snapshot_json::jsonb #> '{businessCase,version}',
                               'currency', revisions.snapshot_json::jsonb #> '{businessCase,currency}',
                               'scenarios',
                               COALESCE(
                                   (
                                       SELECT jsonb_agg(
                                           jsonb_build_object(
                                               'name', scenario.value -> 'name',
                                               'outputs',
                                               COALESCE(
                                                   (
                                                       SELECT jsonb_agg(
                                                           jsonb_build_object(
                                                               'label', output.value -> 'label',
                                                               'value', output.value -> 'value',
                                                               'unit', output.value -> 'unit'
                                                           )
                                                       )
                                                       FROM jsonb_array_elements(
                                                           COALESCE(
                                                               scenario.value -> 'outputs',
                                                               '[]'::jsonb
                                                           )
                                                       ) AS output(value)
                                                   ),
                                                   '[]'::jsonb
                                               )
                                           )
                                       )
                                       FROM jsonb_array_elements(
                                           COALESCE(
                                               revisions.snapshot_json::jsonb #> '{businessCase,scenarios}',
                                               '[]'::jsonb
                                           )
                                       ) AS scenario(value)
                                   ),
                                   '[]'::jsonb
                               )
                           )
                           ELSE 'null'::jsonb
                       END,
                       'commercialSummary', revisions.snapshot_json::jsonb -> 'commercialSummary',
                       'stakeholders',
                       COALESCE(
                           (
                               SELECT jsonb_agg(
                                   jsonb_build_object(
                                       'id', stakeholder.value -> 'id',
                                       'name', stakeholder.value -> 'name',
                                       'role', stakeholder.value -> 'role',
                                       'company', stakeholder.value -> 'company',
                                       'party', stakeholder.value -> 'party'
                                   )
                               )
                               FROM jsonb_array_elements(
                                   COALESCE(
                                       revisions.snapshot_json::jsonb -> 'stakeholders',
                                       '[]'::jsonb
                                   )
                               ) AS stakeholder(value)
                           ),
                           '[]'::jsonb
                       ),
                       'milestones',
                       COALESCE(
                           (
                               SELECT jsonb_agg(
                                   jsonb_build_object(
                                       'id', milestone.value -> 'id',
                                       'title', milestone.value -> 'title',
                                       'ownerParty', milestone.value -> 'ownerParty',
                                       'targetDate', milestone.value -> 'targetDate',
                                       'status', milestone.value -> 'status',
                                       'note', milestone.value -> 'note'
                                   )
                               )
                               FROM jsonb_array_elements(
                                   COALESCE(
                                       revisions.snapshot_json::jsonb -> 'milestones',
                                       '[]'::jsonb
                                   )
                               ) AS milestone(value)
                           ),
                           '[]'::jsonb
                       ),
                       'resources',
                       COALESCE(
                           (
                               SELECT jsonb_agg(
                                   jsonb_build_object(
                                       'id', snapshot_resource.value -> 'id',
                                       'kind', snapshot_resource.value -> 'kind',
                                       'title', snapshot_resource.value -> 'title',
                                       'url', snapshot_resource.value -> 'url',
                                       'downloadAvailable', snapshot_resource.value -> 'downloadAvailable'
                                   )
                               )
                               FROM jsonb_array_elements(
                                   COALESCE(
                                       revisions.snapshot_json::jsonb -> 'resources',
                                       '[]'::jsonb
                                   )
                               ) AS snapshot_resource(value)
                           ),
                           '[]'::jsonb
                       ),
                       'nextMeetingAt', revisions.snapshot_json::jsonb -> 'nextMeetingAt'
                   )::json,
                   revisions.revision,
                   revisions.published_at,
                   links.expires_at
            FROM public.deal_room_access_links AS links
            JOIN public.deal_rooms AS rooms
              ON rooms.organisation_id = links.organisation_id
             AND rooms.id = links.room_id
            JOIN public.deal_room_revisions AS revisions
              ON revisions.organisation_id = rooms.organisation_id
             AND revisions.room_id = rooms.id
             AND revisions.id = rooms.published_revision_id
            JOIN public.opportunities AS opportunities
              ON opportunities.organisation_id = rooms.organisation_id
             AND opportunities.id = rooms.opportunity_id
            JOIN public.organisations AS organisations
              ON organisations.id = rooms.organisation_id
            WHERE requested_token_hash ~ '^[0-9a-f]{64}$'
              AND links.token_hash = requested_token_hash
              AND links.revoked_at IS NULL
              AND (links.expires_at IS NULL OR links.expires_at > CURRENT_TIMESTAMP)
              AND rooms.status = 'published'
              AND opportunities.status = 'open'
              AND opportunities.archived_at IS NULL
            LIMIT 1
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.revenueos_public_deal_room_resource(
            requested_token_hash text,
            requested_resource_id text
        )
        RETURNS TABLE (
            storage_key text,
            checksum_sha256 text,
            byte_size bigint,
            resource_title text
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT versions.pptx_storage_key,
                   versions.checksum_sha256,
                   versions.byte_size,
                   resource.value ->> 'title'
            FROM public.deal_room_access_links AS links
            JOIN public.deal_rooms AS rooms
              ON rooms.organisation_id = links.organisation_id
             AND rooms.id = links.room_id
            JOIN public.deal_room_revisions AS revisions
              ON revisions.organisation_id = rooms.organisation_id
             AND revisions.room_id = rooms.id
             AND revisions.id = rooms.published_revision_id
            JOIN public.opportunities AS opportunities
              ON opportunities.organisation_id = rooms.organisation_id
             AND opportunities.id = rooms.opportunity_id
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(revisions.snapshot_json::jsonb -> 'resources', '[]'::jsonb)
            ) AS resource(value)
            JOIN public.create_presentation_versions AS versions
              ON versions.organisation_id = rooms.organisation_id
             AND versions.id::text = resource.value ->> 'presentationVersionId'
            JOIN public.create_presentations AS presentations
              ON presentations.organisation_id = versions.organisation_id
             AND presentations.id = versions.presentation_id
            WHERE requested_token_hash ~ '^[0-9a-f]{64}$'
              AND links.token_hash = requested_token_hash
              AND links.revoked_at IS NULL
              AND (links.expires_at IS NULL OR links.expires_at > CURRENT_TIMESTAMP)
              AND rooms.status = 'published'
              AND opportunities.status = 'open'
              AND opportunities.archived_at IS NULL
              AND resource.value ->> 'id' = requested_resource_id
              AND resource.value ->> 'kind' = 'presentation'
              AND versions.state = 'ready'
              AND versions.review_state = 'approved'
              AND versions.storage_status = 'available'
              AND versions.pptx_storage_key IS NOT NULL
              AND versions.checksum_sha256 IS NOT NULL
              AND presentations.opportunity_id = rooms.opportunity_id
              AND presentations.archived_at IS NULL
            LIMIT 1
        $$
        """
    )
    op.execute("GRANT EXECUTE ON FUNCTION public.revenueos_public_deal_room(text) TO PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.revenueos_public_deal_room_resource(text, text) TO PUBLIC")


def _repair_postgresql_historical_drift() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    if "provider_minor_units_per_major" not in _columns("credit_action_price_versions"):
        op.add_column(
            "credit_action_price_versions",
            sa.Column("provider_minor_units_per_major", sa.Integer(), server_default="100", nullable=False),
        )
        op.drop_constraint(
            "ck_credit_prices_provider_cost",
            "credit_action_price_versions",
            type_="check",
        )
        op.create_check_constraint(
            "ck_credit_prices_provider_cost",
            "credit_action_price_versions",
            "provider_cost_minor_units >= 0 AND provider_currency <> '' "
            "AND provider_minor_units_per_major > 0 AND provider_minor_units_per_major <= 1000000 "
            "AND other_variable_cost_micros >= 0",
        )

    if "trial_grant" not in _columns("credit_lots"):
        op.add_column(
            "credit_lots",
            sa.Column("trial_grant", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if "ck_credit_lots_trial_grant" not in _checks("credit_lots"):
        op.create_check_constraint(
            "ck_credit_lots_trial_grant",
            "credit_lots",
            "NOT trial_grant OR (credit_type = 'promotional' AND expires_at IS NOT NULL)",
        )
    if "uq_credit_lots_org_trial_grant" not in _indexes("credit_lots"):
        op.create_index(
            "uq_credit_lots_org_trial_grant",
            "credit_lots",
            ["organisation_id"],
            unique=True,
            postgresql_where=sa.text("trial_grant"),
        )

    crm_columns = _columns("crm_conflicts")
    if "oryntela_version_at" not in crm_columns:
        op.add_column("crm_conflicts", sa.Column("oryntela_version_at", sa.DateTime(timezone=True)))
    if "external_version" not in crm_columns:
        op.add_column("crm_conflicts", sa.Column("external_version", sa.String(length=255)))
        op.execute("UPDATE crm_conflicts SET external_version = 'legacy-unversioned'")
        op.alter_column("crm_conflicts", "external_version", nullable=False)
    if "mapping_version" not in crm_columns:
        op.add_column(
            "crm_conflicts",
            sa.Column("mapping_version", sa.Integer(), server_default="1", nullable=False),
        )
    if "authority" not in crm_columns:
        op.add_column("crm_conflicts", sa.Column("authority", sa.String(length=32)))
        op.execute("UPDATE crm_conflicts SET authority = 'review_before_sync'")
        op.alter_column("crm_conflicts", "authority", nullable=False)
    if "observed_at" not in crm_columns:
        op.add_column("crm_conflicts", sa.Column("observed_at", sa.DateTime(timezone=True)))
        op.execute("UPDATE crm_conflicts SET observed_at = created_at")
        op.alter_column(
            "crm_conflicts",
            "observed_at",
            nullable=False,
            server_default=sa.func.now(),
        )
    if "resolved_value_json" not in crm_columns:
        op.add_column("crm_conflicts", sa.Column("resolved_value_json", sa.JSON()))
    if "resolved_fingerprint" not in crm_columns:
        resolved_count = int(
            op.get_bind().execute(sa.text("SELECT count(*) FROM crm_conflicts WHERE status <> 'open'")).scalar_one()
        )
        if resolved_count:
            raise RuntimeError(
                "Historical CRM conflict drift includes resolved rows; reconcile their resolution evidence before migration."
            )
        op.add_column("crm_conflicts", sa.Column("resolved_fingerprint", sa.String(length=64)))

    crm_checks = _checks("crm_conflicts")
    if "ck_crm_conflicts_authority" not in crm_checks:
        op.create_check_constraint(
            "ck_crm_conflicts_authority",
            "crm_conflicts",
            "authority IN ('crm_authoritative', 'revenueos_authoritative', 'review_before_sync')",
        )
    if "ck_crm_conflicts_mapping_version" not in crm_checks:
        op.create_check_constraint("ck_crm_conflicts_mapping_version", "crm_conflicts", "mapping_version > 0")
    if "ck_crm_conflicts_fingerprints" not in crm_checks:
        op.create_check_constraint(
            "ck_crm_conflicts_fingerprints",
            "crm_conflicts",
            "length(oryntela_fingerprint) = 64 AND length(provider_fingerprint) = 64",
        )
    lifecycle = next(
        (
            constraint["sqltext"]
            for constraint in inspect(op.get_bind()).get_check_constraints("crm_conflicts")
            if constraint["name"] == "ck_crm_conflicts_lifecycle"
        ),
        "",
    )
    if "resolved_fingerprint" not in lifecycle:
        op.drop_constraint("ck_crm_conflicts_lifecycle", "crm_conflicts", type_="check")
        op.create_check_constraint(
            "ck_crm_conflicts_lifecycle",
            "crm_conflicts",
            "(status = 'open' AND resolution IS NULL AND resolved_at IS NULL AND resolved_by_user_id IS NULL "
            "AND resolved_fingerprint IS NULL) OR "
            "(status <> 'open' AND resolution IS NOT NULL AND resolved_at IS NOT NULL "
            "AND resolved_by_user_id IS NOT NULL AND length(resolved_fingerprint) = 64)",
        )

    if "uq_closed_won_handover_sources_unversioned_reference" not in _indexes("closed_won_handover_sources"):
        op.create_index(
            "uq_closed_won_handover_sources_unversioned_reference",
            "closed_won_handover_sources",
            ["organisation_id", "revision_id", "source_type", "source_id"],
            unique=True,
            postgresql_where=sa.text("source_version_id IS NULL"),
        )

    _repair_deal_room_public_projections()

    publication_guard = (
        op.get_bind()
        .execute(sa.text("SELECT to_regprocedure('public.revenueos_deal_room_publication_pointer_guard()')"))
        .scalar_one_or_none()
    )
    if publication_guard is None:
        op.execute(
            """
            CREATE FUNCTION public.revenueos_deal_room_publication_pointer_guard()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog, public
            AS $$
            BEGIN
                IF NEW.published_revision_id IS NOT NULL
                   AND (
                       TG_OP = 'INSERT'
                       OR NEW.published_revision_id IS DISTINCT FROM OLD.published_revision_id
                   ) THEN
                    PERFORM 1
                      FROM public.deal_room_revisions AS revisions
                     WHERE revisions.organisation_id = NEW.organisation_id
                       AND revisions.room_id = NEW.id
                       AND revisions.id = NEW.published_revision_id;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'Published Deal Room revision must belong to the same room';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        op.execute("REVOKE ALL ON FUNCTION public.revenueos_deal_room_publication_pointer_guard() FROM PUBLIC")

    publication_trigger = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgrelid = 'public.deal_rooms'::regclass "
                "AND tgname = 'deal_rooms_publication_pointer_guard'"
            )
        )
        .scalar_one_or_none()
    )
    if publication_trigger is None:
        op.execute(
            """CREATE TRIGGER deal_rooms_publication_pointer_guard
            BEFORE INSERT OR UPDATE OF published_revision_id ON deal_rooms
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_deal_room_publication_pointer_guard()"""
        )


def _create_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(f"ALTER TABLE {TABLE_NAME} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {TABLE_NAME} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {TABLE_NAME}_tenant_isolation
            ON {TABLE_NAME}
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )
        op.execute(
            """
            CREATE FUNCTION public.revenueos_terms_acceptance_immutable()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog, public
            AS $$
            BEGIN
                IF TG_OP = 'DELETE'
                   AND current_setting('app.beta_maintenance', true) = 'approved' THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'Terms acceptance evidence is immutable';
            END;
            $$
            """
        )
        op.execute(
            f"""CREATE TRIGGER {TABLE_NAME}_immutable
            BEFORE UPDATE OR DELETE ON {TABLE_NAME}
            FOR EACH ROW EXECUTE FUNCTION public.revenueos_terms_acceptance_immutable()"""
        )
        op.execute("REVOKE ALL ON FUNCTION public.revenueos_terms_acceptance_immutable() FROM PUBLIC")
    elif dialect == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"""CREATE TRIGGER {TABLE_NAME}_immutable_{operation.lower()}
                BEFORE {operation} ON {TABLE_NAME}
                BEGIN SELECT RAISE(ABORT, 'Terms acceptance evidence is immutable'); END"""
            )


def _drop_security() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE_NAME}_immutable ON {TABLE_NAME}")
        op.execute(f"DROP POLICY IF EXISTS {TABLE_NAME}_tenant_isolation ON {TABLE_NAME}")
        op.execute("DROP FUNCTION IF EXISTS public.revenueos_terms_acceptance_immutable()")
    elif dialect == "sqlite":
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS {TABLE_NAME}_immutable_{operation}")


def upgrade() -> None:
    _repair_postgresql_historical_drift()
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        TABLE_NAME,
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("accepted_by_user_id", uuid_type, nullable=False),
        sa.Column("release_status", sa.String(length=16), nullable=False),
        sa.Column("terms_version", sa.String(length=80), nullable=False),
        sa.Column("terms_sha256", sa.String(length=64), nullable=False),
        sa.Column("terms_effective_date", sa.Date()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acceptance_source", sa.String(length=40), nullable=False),
        sa.Column("privacy_notice_version", sa.String(length=80), nullable=False),
        sa.Column("privacy_notice_sha256", sa.String(length=64), nullable=False),
        sa.Column("privacy_notice_effective_date", sa.Date()),
        sa.Column("privacy_notice_presented_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("release_status IN ('draft', 'approved')", name="ck_terms_acceptances_release_status"),
        sa.CheckConstraint(
            "(release_status = 'draft' AND terms_effective_date IS NULL "
            "AND privacy_notice_effective_date IS NULL) OR "
            "(release_status = 'approved' AND terms_effective_date IS NOT NULL "
            "AND privacy_notice_effective_date IS NOT NULL)",
            name="ck_terms_acceptances_release_date",
        ),
        sa.CheckConstraint(
            "length(trim(terms_version)) BETWEEN 1 AND 80",
            name="ck_terms_acceptances_terms_version",
        ),
        sa.CheckConstraint(
            _lower_hex_64("terms_sha256"),
            name="ck_terms_acceptances_terms_hash",
        ),
        sa.CheckConstraint(
            "acceptance_source IN ('trial_onboarding', 'subscription_checkout', 'administrative_onboarding')",
            name="ck_terms_acceptances_source",
        ),
        sa.CheckConstraint(
            "length(trim(privacy_notice_version)) BETWEEN 1 AND 80",
            name="ck_terms_acceptances_privacy_version",
        ),
        sa.CheckConstraint(
            _lower_hex_64("privacy_notice_sha256"),
            name="ck_terms_acceptances_privacy_hash",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "accepted_by_user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_terms_acceptances_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_terms_acceptances_org_id"),
        sa.UniqueConstraint(
            "organisation_id",
            "terms_version",
            name="uq_terms_acceptances_org_terms_version",
        ),
    )
    op.create_index(
        "ix_terms_acceptances_org_time",
        TABLE_NAME,
        ["organisation_id", "accepted_at", "id"],
    )
    op.drop_index("uq_billing_operations_org_unresolved_checkout", table_name="billing_operations")
    with op.batch_alter_table("billing_operations") as batch:
        batch.add_column(sa.Column("terms_acceptance_id", uuid_type))
        batch.create_foreign_key(
            "fk_billing_operations_terms_acceptance",
            TABLE_NAME,
            ["organisation_id", "terms_acceptance_id"],
            ["organisation_id", "id"],
            ondelete="RESTRICT",
        )
    _create_unresolved_checkout_index()
    _create_security()


def downgrade() -> None:
    op.drop_index("uq_billing_operations_org_unresolved_checkout", table_name="billing_operations")
    with op.batch_alter_table("billing_operations") as batch:
        batch.drop_constraint("fk_billing_operations_terms_acceptance", type_="foreignkey")
        batch.drop_column("terms_acceptance_id")
    _create_unresolved_checkout_index()
    _drop_security()
    op.drop_index("ix_terms_acceptances_org_time", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
