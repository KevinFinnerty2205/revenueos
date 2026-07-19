from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from revenueos.ai_provider_contracts import ProviderMessage

RegistryKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_]*$",
    ),
]
PromptTemplate = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000),
]
Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
]
PromptVariableValue = str | int | UUID


class PromptDefinition(BaseModel):
    """Immutable application-owned prompt definition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt_key: RegistryKey
    prompt_version: int = Field(ge=1)
    job_type: Literal[
        "infrastructure_test",
        "executive_summary",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
        "follow_up_email",
    ]
    system_template: PromptTemplate
    user_template: PromptTemplate
    output_schema_key: RegistryKey
    output_schema_version: int = Field(ge=1)
    description: Description
    active: bool = True


class PromptVariables(BaseModel):
    """Validated prompt variables containing only safe scalar values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    values: dict[RegistryKey, PromptVariableValue]


class RenderedPrompt(BaseModel):
    """Immutable rendered messages plus safe logical trace identifiers."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt_key: RegistryKey
    prompt_version: int = Field(ge=1)
    output_schema_key: RegistryKey
    output_schema_version: int = Field(ge=1)
    messages: tuple[ProviderMessage, ...] = Field(min_length=2, max_length=2)
