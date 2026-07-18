from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Never, cast

from pydantic import JsonValue

from revenueos.ai_output_schema_contracts import OutputSchemaDefinition
from revenueos.ai_output_schema_registry import OutputSchemaRegistry
from revenueos.ai_prompt_errors import (
    MalformedJSONOutputError,
    NonObjectStructuredOutputError,
)


def _reject_non_standard_constant(_: str) -> Never:
    raise ValueError("Non-standard JSON constants are not accepted.")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object keys are not accepted.")
        result[key] = value
    return result


def parse_structured_output(
    output: Mapping[str, JsonValue] | str,
) -> dict[str, object]:
    if isinstance(output, str):
        try:
            parsed = json.loads(
                output.strip(),
                parse_constant=_reject_non_standard_constant,
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (TypeError, ValueError) as exc:
            raise MalformedJSONOutputError from exc
    else:
        parsed = dict(output)
    if not isinstance(parsed, dict):
        raise NonObjectStructuredOutputError
    return cast(dict[str, object], parsed)


def parse_and_validate_structured_output(
    output: Mapping[str, JsonValue] | str,
    *,
    definition: OutputSchemaDefinition,
    schemas: OutputSchemaRegistry,
) -> dict[str, object]:
    parsed = parse_structured_output(output)
    return schemas.validate(definition, parsed)
