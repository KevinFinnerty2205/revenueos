"""Preserve membership authentication boundaries across re-enable.

Revision ID: 0064_deauthorisation
Revises: 0063_terms_acceptance

WO-054 keeps organisation membership authority server-side. A disable advances
the authority version and records the earliest acceptable authentication time,
so a JWT issued before disablement cannot regain access after re-enable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0064_deauthorisation"
down_revision: str | None = "0063_terms_acceptance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organisation_memberships") as batch:
        batch.add_column(sa.Column("authority_version", sa.Integer(), server_default=sa.text("1"), nullable=False))
        batch.add_column(sa.Column("authentication_valid_after", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_memberships_authority_version",
            "authority_version > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("organisation_memberships") as batch:
        batch.drop_constraint("ck_memberships_authority_version", type_="check")
        batch.drop_column("authentication_valid_after")
        batch.drop_column("authority_version")
