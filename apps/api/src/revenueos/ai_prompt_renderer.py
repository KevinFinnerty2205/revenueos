from __future__ import annotations

import re
import string

from revenueos.ai_prompt_contracts import (
    PromptDefinition,
    PromptVariables,
    RenderedPrompt,
)
from revenueos.ai_prompt_errors import (
    MissingPromptVariableError,
    PromptRenderingError,
    UnknownPromptVariableError,
)
from revenueos.ai_provider_contracts import ProviderMessage

SAFE_VARIABLE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def _required_variables(template: str) -> set[str]:
    required: set[str] = set()
    try:
        parts = string.Formatter().parse(template)
        for _, field_name, format_spec, conversion in parts:
            if field_name is None:
                continue
            if not SAFE_VARIABLE_NAME.fullmatch(field_name) or format_spec or conversion:
                raise PromptRenderingError
            required.add(field_name)
    except ValueError as exc:
        raise PromptRenderingError from exc
    return required


def render_prompt(
    definition: PromptDefinition,
    variables: PromptVariables,
) -> RenderedPrompt:
    required = _required_variables(definition.system_template) | _required_variables(definition.user_template)
    supplied = set(variables.values)
    if required - supplied:
        raise MissingPromptVariableError
    if supplied - required:
        raise UnknownPromptVariableError

    safe_values = {key: str(value) for key, value in variables.values.items()}
    try:
        system_content = definition.system_template.format_map(safe_values).strip()
        user_content = definition.user_template.format_map(safe_values).strip()
    except (KeyError, ValueError) as exc:
        raise PromptRenderingError from exc
    if not system_content or not user_content:
        raise PromptRenderingError

    return RenderedPrompt(
        prompt_key=definition.prompt_key,
        prompt_version=definition.prompt_version,
        output_schema_key=definition.output_schema_key,
        output_schema_version=definition.output_schema_version,
        messages=(
            ProviderMessage(role="system", content=system_content),
            ProviderMessage(role="user", content=user_content),
        ),
    )
