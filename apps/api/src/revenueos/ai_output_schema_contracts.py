from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SchemaKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_]*$",
    ),
]
SchemaDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
]


class OutputSchemaDefinition(BaseModel):
    """Immutable application-owned structured-output schema definition."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
        strict=True,
    )

    schema_key: SchemaKey
    schema_version: int = Field(ge=1)
    job_type: Literal[
        "infrastructure_test",
        "executive_summary",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
        "buying_signals",
        "objections_competitive_signals",
        "stakeholder_intelligence",
        "follow_up_email",
    ]
    validation_model: type[BaseModel]
    description: SchemaDescription
    active: bool = True
