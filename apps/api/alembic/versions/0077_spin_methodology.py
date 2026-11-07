"""Add SPIN to the standard sales methodology selections.

Revision ID: 0077_spin_methodology
Revises: 0076_briefing_source_observation

SPIN is an immutable code-deployed methodology definition. This migration only
expands the organisation setting allowlist; existing selections and projection
history remain unchanged.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0077_spin_methodology"
down_revision: str | None = "0076_briefing_source_observation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_selection_constraint(*, include_spin: bool) -> None:
    selections = "'none', 'meddic', 'meddicc', 'meddpicc', 'bant', 'spiced', 'custom'"
    if include_spin:
        selections = "'none', 'meddic', 'meddicc', 'meddpicc', 'bant', 'spin', 'spiced', 'custom'"
    with op.batch_alter_table("organisation_methodology_settings") as batch:
        batch.drop_constraint("ck_methodology_settings_selection", type_="check")
        batch.create_check_constraint(
            "ck_methodology_settings_selection",
            f"selection IN ({selections})",
        )


def upgrade() -> None:
    _replace_selection_constraint(include_spin=True)


def downgrade() -> None:
    # The older schema cannot represent SPIN. Fall back to notes-only rather
    # than silently claiming that a different sales methodology was selected.
    op.execute("UPDATE organisation_methodology_settings SET selection = 'none' WHERE selection = 'spin'")
    _replace_selection_constraint(include_spin=False)
