from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class HealthResponse(APIModel):
    status: Literal["healthy"]


class DependencyCheck(APIModel):
    status: Literal["ready", "unavailable", "misconfigured"]
    detail: str


class ReadyResponse(APIModel):
    status: Literal["ready", "not_ready"]
    environment: str
    dependencies: dict[str, DependencyCheck]
    request_id: str


class UserSummary(APIModel):
    id: UUID
    external_auth_id: str
    display_name: str
    email: str


class OrganisationSummary(APIModel):
    id: UUID
    name: str
    slug: str


class MeResponse(APIModel):
    user: UserSummary
    organisation: OrganisationSummary
    role: Literal["admin", "manager", "member"]
    auth_mode: Literal["mock", "clerk"]
    request_id: str


class ErrorResponse(APIModel):
    code: str
    message: str
    request_id: str
    details: dict[str, str] | None = Field(default=None)
