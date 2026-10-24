"""Repair the shared PostgreSQL published-campaign update guard.

Revision ID: 0065_campaign_trigger_guard
Revises: 0064_deauthorisation

The original PostgreSQL trigger function is shared by campaign versions,
sequence steps and audience rows. Direct field access in a compound condition
attempted to resolve ``OLD.status`` for audience rows, which do not have that
column. Reading relation-specific values through JSONB keeps the shared trigger
safe while preserving the published-version immutability rules and the narrow
contact-detachment exception used by Contact deletion.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0065_campaign_trigger_guard"
down_revision: str | None = "0064_deauthorisation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REPAIRED_FUNCTION = """
CREATE OR REPLACE FUNCTION public.revenueos_reject_published_campaign_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    old_row jsonb := to_jsonb(OLD);
    new_row jsonb := to_jsonb(NEW);
BEGIN
    IF TG_TABLE_NAME = 'engage_campaign_versions'
       AND old_row ->> 'status' = 'published' THEN
        RAISE EXCEPTION 'Published campaign versions are immutable';
    END IF;
    IF TG_TABLE_NAME = 'engage_campaign_audience'
       AND old_row ->> 'contact_id' IS NOT NULL
       AND new_row ->> 'contact_id' IS NULL
       AND (old_row - 'contact_id') IS NOT DISTINCT FROM (new_row - 'contact_id') THEN
        RETURN NEW;
    END IF;
    IF TG_TABLE_NAME <> 'engage_campaign_versions' AND EXISTS (
        SELECT 1
        FROM public.engage_campaign_versions
        WHERE organisation_id = (old_row ->> 'organisation_id')::uuid
          AND id = (old_row ->> 'campaign_version_id')::uuid
          AND status = 'published'
    ) THEN
        RAISE EXCEPTION 'Published campaign audience and sequence are immutable';
    END IF;
    RETURN NEW;
END;
$$
"""


LEGACY_FUNCTION = """
CREATE OR REPLACE FUNCTION public.revenueos_reject_published_campaign_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'engage_campaign_versions' AND OLD.status = 'published' THEN
        RAISE EXCEPTION 'Published campaign versions are immutable';
    END IF;
    IF TG_TABLE_NAME = 'engage_campaign_audience'
       AND OLD.contact_id IS NOT NULL
       AND NEW.contact_id IS NULL
       AND OLD.campaign_version_id IS NOT DISTINCT FROM NEW.campaign_version_id
       AND OLD.company_id IS NOT DISTINCT FROM NEW.company_id
       AND OLD.recipient_name IS NOT DISTINCT FROM NEW.recipient_name
       AND OLD.recipient_email IS NOT DISTINCT FROM NEW.recipient_email
       AND OLD.recipient_trust IS NOT DISTINCT FROM NEW.recipient_trust
       AND OLD.eligible IS NOT DISTINCT FROM NEW.eligible
       AND OLD.eligibility_code IS NOT DISTINCT FROM NEW.eligibility_code
       AND OLD.eligibility_reason IS NOT DISTINCT FROM NEW.eligibility_reason THEN
        RETURN NEW;
    END IF;
    IF TG_TABLE_NAME <> 'engage_campaign_versions' AND EXISTS (
        SELECT 1
        FROM public.engage_campaign_versions
        WHERE organisation_id = OLD.organisation_id
          AND id = OLD.campaign_version_id
          AND status = 'published'
    ) THEN
        RAISE EXCEPTION 'Published campaign audience and sequence are immutable';
    END IF;
    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(REPAIRED_FUNCTION)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(LEGACY_FUNCTION)
