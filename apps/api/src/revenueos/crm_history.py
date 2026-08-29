from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from revenueos.models import CRMRecordChange


def crm_creation_changes(
    organisation_id: UUID,
    actor_user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    source: str,
    values: dict[str, object | None],
) -> list[CRMRecordChange]:
    """Build source-labelled creation history without logging record values."""

    return [
        CRMRecordChange(
            organisation_id=organisation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_key=field_key,
            old_value_json=None,
            new_value_json=_json_value(value),
            source=source,
            changed_by_user_id=actor_user_id,
        )
        for field_key, value in values.items()
        if value is not None
    ]


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value
