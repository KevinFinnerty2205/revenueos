from __future__ import annotations

import logging
import uuid

import pytest
from pydantic import ValidationError

from revenueos.ai_contracts import InfrastructureTestArtifactContent
from revenueos.ai_output_schema_contracts import OutputSchemaDefinition
from revenueos.ai_output_schema_registry import (
    OutputSchemaRegistry,
    create_default_output_schema_registry,
)
from revenueos.ai_prompt_contracts import PromptDefinition, PromptVariables
from revenueos.ai_prompt_errors import (
    DuplicatePromptRegistrationError,
    DuplicateSchemaRegistrationError,
    MissingPromptVariableError,
    PromptNotFoundError,
    PromptRenderingError,
    PromptVersionNotFoundError,
    SchemaNotFoundError,
    SchemaVersionNotFoundError,
    UnknownPromptVariableError,
)
from revenueos.ai_prompt_registry import (
    PromptRegistry,
    create_default_prompt_registry,
)
from revenueos.ai_prompt_renderer import render_prompt
from revenueos.ai_provider_contracts import (
    InfrastructureTestProviderInput,
    ProviderMessage,
)


def _prompt_definition(**overrides: object) -> PromptDefinition:
    values: dict[str, object] = {
        "prompt_key": "infrastructure_test",
        "prompt_version": 1,
        "job_type": "infrastructure_test",
        "system_template": "Return JSON for {request_id}.",
        "user_template": "Run job {job_id}.",
        "output_schema_key": "infrastructure_test",
        "output_schema_version": 1,
        "description": "Infrastructure prompt.",
        "active": True,
    }
    values.update(overrides)
    return PromptDefinition(**values)  # type: ignore[arg-type]


def _schema_definition(**overrides: object) -> OutputSchemaDefinition:
    values: dict[str, object] = {
        "schema_key": "infrastructure_test",
        "schema_version": 1,
        "job_type": "infrastructure_test",
        "validation_model": InfrastructureTestArtifactContent,
        "description": "Infrastructure schema.",
        "active": True,
    }
    values.update(overrides)
    return OutputSchemaDefinition(**values)  # type: ignore[arg-type]


def test_prompt_definition_is_strict_validated_and_immutable() -> None:
    definition = _prompt_definition()

    assert definition.prompt_key == "infrastructure_test"
    with pytest.raises(ValidationError):
        definition.prompt_version = 2  # type: ignore[misc]
    for overrides in (
        {"prompt_key": ""},
        {"prompt_key": "Not Normalized"},
        {"prompt_version": 0},
        {"prompt_version": "1"},
        {"job_type": "summary"},
        {"system_template": ""},
        {"user_template": ""},
        {"output_schema_key": ""},
        {"output_schema_version": 0},
    ):
        with pytest.raises(ValidationError):
            _prompt_definition(**overrides)
    with pytest.raises(ValidationError):
        PromptDefinition.model_validate({**definition.model_dump(), "unknown": True})


def test_schema_definition_is_strict_validated_and_immutable() -> None:
    definition = _schema_definition()

    assert definition.validation_model is InfrastructureTestArtifactContent
    with pytest.raises(ValidationError):
        definition.schema_version = 2  # type: ignore[misc]
    for overrides in (
        {"schema_key": ""},
        {"schema_key": "Not Normalized"},
        {"schema_version": 0},
        {"schema_version": "1"},
        {"job_type": "summary"},
        {"description": ""},
    ):
        with pytest.raises(ValidationError):
            _schema_definition(**overrides)
    with pytest.raises(ValidationError):
        OutputSchemaDefinition.model_validate({**definition.model_dump(), "unexpected": True})


def test_provider_messages_are_strict_bounded_and_immutable() -> None:
    message = ProviderMessage(role="system", content="Safe instructions.")

    assert message.content == "Safe instructions."
    with pytest.raises(ValidationError):
        message.content = "Changed."  # type: ignore[misc]
    for values in (
        {"role": "assistant", "content": "Not supported."},
        {"role": "system", "content": ""},
        {"role": "system", "content": "x" * 60_001},
        {"role": "system", "content": "Safe.", "unexpected": True},
    ):
        with pytest.raises(ValidationError):
            ProviderMessage.model_validate(values)


def test_infrastructure_provider_input_requires_system_then_user_messages() -> None:
    system = ProviderMessage(role="system", content="Safe instructions.")
    user = ProviderMessage(role="user", content="Safe request.")

    payload = InfrastructureTestProviderInput(messages=(system, user))

    assert payload.messages == (system, user)
    for messages in ((user, system), (system,), (system, user, user)):
        with pytest.raises(ValidationError):
            InfrastructureTestProviderInput(messages=messages)


def test_schema_registry_resolves_versions_and_rejects_duplicates() -> None:
    registry = OutputSchemaRegistry()
    first = _schema_definition()
    second = _schema_definition(schema_version=2)
    registry.register(first)
    registry.register(second)

    assert registry.resolve("infrastructure_test", 1) is first
    assert registry.resolve_active("infrastructure_test") is second
    assert registry.list_versions("infrastructure_test") == (1, 2)
    with pytest.raises(DuplicateSchemaRegistrationError):
        registry.register(first)
    with pytest.raises(SchemaNotFoundError):
        registry.resolve("unknown", 1)
    with pytest.raises(SchemaVersionNotFoundError):
        registry.resolve("infrastructure_test", 99)


def test_prompt_registry_resolves_versions_and_requires_registered_schema() -> None:
    schemas = create_default_output_schema_registry()
    registry = PromptRegistry(schemas)
    first = _prompt_definition()
    second = _prompt_definition(prompt_version=2)
    registry.register(first)
    registry.register(second)

    assert registry.resolve("infrastructure_test", 1) is first
    assert registry.resolve_active("infrastructure_test") is second
    assert registry.list_versions("infrastructure_test") == (1, 2)
    with pytest.raises(DuplicatePromptRegistrationError):
        registry.register(first)
    with pytest.raises(PromptNotFoundError):
        registry.resolve("unknown", 1)
    with pytest.raises(PromptVersionNotFoundError):
        registry.resolve("infrastructure_test", 99)
    with pytest.raises(SchemaNotFoundError):
        registry.register(
            _prompt_definition(
                prompt_key="unknown_schema_prompt",
                output_schema_key="unknown_schema",
            )
        )


def test_default_registries_are_deterministic_and_instance_isolated() -> None:
    schemas_one = create_default_output_schema_registry()
    schemas_two = create_default_output_schema_registry()
    prompts_one = create_default_prompt_registry(schemas_one)
    prompts_two = create_default_prompt_registry(schemas_two)

    prompts_one.register(_prompt_definition(prompt_version=2))

    default_prompt = prompts_two.resolve("infrastructure_test", 1)
    default_schema = schemas_two.resolve("infrastructure_test", 1)
    assert prompts_one.list_versions("infrastructure_test") == (1, 2)
    assert prompts_two.list_versions("infrastructure_test") == (1,)
    assert default_prompt.output_schema_key == "infrastructure_test"
    assert default_prompt.output_schema_version == 1
    assert default_schema.validation_model is InfrastructureTestArtifactContent
    assert schemas_one.resolve_active("infrastructure_test").schema_version == 1
    assert schemas_two.resolve_active("infrastructure_test").schema_version == 1


def test_prompt_rendering_is_deterministic_and_rejects_bad_variables() -> None:
    definition = _prompt_definition()
    variables = PromptVariables(
        values={
            "request_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
            "job_id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
        }
    )

    first = render_prompt(definition, variables)
    second = render_prompt(definition, variables)

    assert first == second
    assert tuple(message.role for message in first.messages) == ("system", "user")
    assert all(message.content.strip() for message in first.messages)
    with pytest.raises(MissingPromptVariableError):
        render_prompt(
            definition,
            PromptVariables(values={"job_id": uuid.uuid4()}),
        )
    with pytest.raises(UnknownPromptVariableError):
        render_prompt(
            definition,
            PromptVariables(
                values={
                    **variables.values,
                    "unexpected": "not allowed",
                }
            ),
        )
    with pytest.raises(ValidationError):
        PromptVariables(values={"unsupported_boolean": True})


def test_prompt_renderer_rejects_unsafe_templates_and_empty_results() -> None:
    unsafe = _prompt_definition(
        system_template="{value.__class__}",
        user_template="constant",
    )
    with pytest.raises(PromptRenderingError):
        render_prompt(unsafe, PromptVariables(values={"value": "safe"}))

    empty = _prompt_definition(
        system_template="{value}",
        user_template="constant",
    )
    with pytest.raises(PromptRenderingError):
        render_prompt(empty, PromptVariables(values={"value": " "}))


def test_rendered_prompt_content_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    definition = _prompt_definition(
        system_template="System {value}",
        user_template="User {value}",
    )

    render_prompt(
        definition,
        PromptVariables(values={"value": "sensitive-rendered-value"}),
    )

    assert "sensitive-rendered-value" not in caplog.text
