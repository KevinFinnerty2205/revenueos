"""Add Create output validation and one-time download grants.

Revision ID: 0049_create_trust
Revises: 0048_manager_intelligence

WO-039B versions the supported PPTX profile, records structural output validation
and replaces signed query downloads with hashed, single-use application grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_create_trust"
down_revision: str | None = "0048_manager_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    with op.batch_alter_table("create_template_versions") as batch:
        batch.add_column(
            sa.Column("compatibility_state", sa.String(length=24), server_default="needs_attention", nullable=False)
        )
        batch.add_column(
            sa.Column("compatibility_details_json", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch.add_column(sa.Column("validation_profile_version", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_create_template_versions_compatibility",
            "compatibility_state IN ('compatible', 'needs_attention', 'unsupported')",
        )
        batch.create_check_constraint(
            "ck_create_template_versions_profile",
            "validation_profile_version = 1",
        )

    with op.batch_alter_table("create_presentation_versions") as batch:
        batch.add_column(sa.Column("validation_profile_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_create_presentation_versions_profile",
            "validation_profile_version IS NULL OR validation_profile_version = 1",
        )

    op.create_table(
        "create_download_grants",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("organisation_id", uuid_type, nullable=False),
        sa.Column("presentation_version_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("approval_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "length(token_hash) = 64 AND token_hash = lower(token_hash)",
            name="ck_create_download_grants_token_hash",
        ),
        sa.CheckConstraint(
            "length(approval_fingerprint) = 64 AND approval_fingerprint = lower(approval_fingerprint)",
            name="ck_create_download_grants_approval_fingerprint",
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="ck_create_download_grants_consumed",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_create_download_grants_revoked",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_create_download_grants_expiry",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id", "presentation_version_id"],
            ["create_presentation_versions.organisation_id", "create_presentation_versions.id"],
            name="fk_create_download_grants_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id", "user_id"],
            ["organisation_memberships.organisation_id", "organisation_memberships.user_id"],
            name="fk_create_download_grants_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "id", name="uq_create_download_grants_org_id"),
        sa.UniqueConstraint("token_hash", name="uq_create_download_grants_token_hash"),
    )
    op.create_index(
        "ix_create_download_grants_org_expiry",
        "create_download_grants",
        ["organisation_id", "expires_at"],
    )
    op.create_index(
        "ix_create_download_grants_org_version",
        "create_download_grants",
        ["organisation_id", "presentation_version_id", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE create_download_grants ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE create_download_grants FORCE ROW LEVEL SECURITY")
        op.execute(
            """CREATE POLICY create_download_grants_tenant_isolation
            ON create_download_grants
            USING (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)
            WITH CHECK (organisation_id = NULLIF(current_setting('app.organisation_id', true), '')::uuid)"""
        )


def downgrade() -> None:
    op.drop_index("ix_create_download_grants_org_version", table_name="create_download_grants")
    op.drop_index("ix_create_download_grants_org_expiry", table_name="create_download_grants")
    op.drop_table("create_download_grants")
    with op.batch_alter_table("create_presentation_versions") as batch:
        batch.drop_constraint("ck_create_presentation_versions_profile", type_="check")
        batch.drop_column("validated_at")
        batch.drop_column("validation_profile_version")
    with op.batch_alter_table("create_template_versions") as batch:
        batch.drop_constraint("ck_create_template_versions_profile", type_="check")
        batch.drop_constraint("ck_create_template_versions_compatibility", type_="check")
        batch.drop_column("validated_at")
        batch.drop_column("validation_profile_version")
        batch.drop_column("compatibility_details_json")
        batch.drop_column("compatibility_state")
