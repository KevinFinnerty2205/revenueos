from __future__ import annotations

from uuid import UUID

EXPORT_OBJECT_REFERENCE_PREFIX = "object-storage:"


def export_storage_key(organisation_id: UUID, request_id: UUID) -> str:
    return f"{organisation_id}/exports/revenueos-export-{request_id}.json"


def export_object_reference(organisation_id: UUID, request_id: UUID) -> str:
    return f"{EXPORT_OBJECT_REFERENCE_PREFIX}{export_storage_key(organisation_id, request_id)}"


def parse_export_object_reference(value: str, organisation_id: UUID, request_id: UUID) -> str | None:
    if not value.startswith(EXPORT_OBJECT_REFERENCE_PREFIX):
        return None
    key = value.removeprefix(EXPORT_OBJECT_REFERENCE_PREFIX)
    if key != export_storage_key(organisation_id, request_id):
        raise ValueError("The export object reference is outside the tenant-scoped export prefix.")
    return key
