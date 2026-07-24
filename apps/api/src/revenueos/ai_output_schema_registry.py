from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import ValidationError

from revenueos.ai_contracts import (
    ACTION_ITEMS_SCHEMA_VERSION,
    BUYING_SIGNALS_SCHEMA_VERSION,
    DECISIONS_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    FOLLOW_UP_EMAIL_SCHEMA_VERSION,
    INFRASTRUCTURE_TEST_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    RISKS_BLOCKERS_SCHEMA_VERSION,
    STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    FollowUpEmailArtifactContent,
    InfrastructureTestArtifactContent,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.ai_output_schema_contracts import OutputSchemaDefinition
from revenueos.ai_prompt_errors import (
    DuplicateSchemaRegistrationError,
    SchemaNotFoundError,
    SchemaVersionNotFoundError,
    StructuredOutputValidationError,
)
from revenueos.domain import AIJobType

INFRASTRUCTURE_TEST_SCHEMA_KEY = "infrastructure_test"
EXECUTIVE_SUMMARY_SCHEMA_KEY = "executive_summary"
DECISIONS_SCHEMA_KEY = "decisions"
ACTION_ITEMS_SCHEMA_KEY = "action_items"
RISKS_BLOCKERS_SCHEMA_KEY = "risks_blockers"
OPEN_QUESTIONS_SCHEMA_KEY = "open_questions"
BUYING_SIGNALS_SCHEMA_KEY = "buying_signals"
OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_KEY = "objections_competitive_signals"
STAKEHOLDER_INTELLIGENCE_SCHEMA_KEY = "stakeholder_intelligence"
FOLLOW_UP_EMAIL_SCHEMA_KEY = "follow_up_email"


class OutputSchemaRegistry:
    """Instance-owned registry for immutable application output schemas."""

    def __init__(
        self,
        definitions: tuple[OutputSchemaDefinition, ...] = (),
    ) -> None:
        self._definitions: dict[tuple[str, int], OutputSchemaDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: OutputSchemaDefinition) -> None:
        identity = (definition.schema_key, definition.schema_version)
        if identity in self._definitions:
            raise DuplicateSchemaRegistrationError
        self._definitions[identity] = definition

    def resolve(
        self,
        schema_key: str,
        schema_version: int,
    ) -> OutputSchemaDefinition:
        definition = self._definitions.get((schema_key, schema_version))
        if definition is not None:
            return definition
        if any(key == schema_key for key, _ in self._definitions):
            raise SchemaVersionNotFoundError
        raise SchemaNotFoundError

    def resolve_active(self, schema_key: str) -> OutputSchemaDefinition:
        active = [
            definition for (key, _), definition in self._definitions.items() if key == schema_key and definition.active
        ]
        if not active:
            if any(key == schema_key for key, _ in self._definitions):
                raise SchemaVersionNotFoundError
            raise SchemaNotFoundError
        return max(active, key=lambda definition: definition.schema_version)

    def list_versions(self, schema_key: str) -> tuple[int, ...]:
        versions = sorted(version for key, version in self._definitions if key == schema_key)
        if not versions:
            raise SchemaNotFoundError
        return tuple(versions)

    def validate(
        self,
        definition: OutputSchemaDefinition,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            validated = definition.validation_model.model_validate(payload)
        except ValidationError as exc:
            raise StructuredOutputValidationError from exc
        return cast(dict[str, object], validated.model_dump(mode="json"))


def create_default_output_schema_registry() -> OutputSchemaRegistry:
    return OutputSchemaRegistry(
        (
            OutputSchemaDefinition(
                schema_key=INFRASTRUCTURE_TEST_SCHEMA_KEY,
                schema_version=INFRASTRUCTURE_TEST_SCHEMA_VERSION,
                job_type=AIJobType.INFRASTRUCTURE_TEST.value,
                validation_model=InfrastructureTestArtifactContent,
                description="Strict schema for deterministic infrastructure validation.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=EXECUTIVE_SUMMARY_SCHEMA_KEY,
                schema_version=EXECUTIVE_SUMMARY_SCHEMA_VERSION,
                job_type=AIJobType.EXECUTIVE_SUMMARY.value,
                validation_model=ExecutiveSummaryArtifactContent,
                description="Strict schema for transcript-grounded Executive Summaries.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=DECISIONS_SCHEMA_KEY,
                schema_version=DECISIONS_SCHEMA_VERSION,
                job_type=AIJobType.DECISIONS.value,
                validation_model=DecisionsArtifactContent,
                description="Strict schema for transcript-grounded meeting Decisions.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=ACTION_ITEMS_SCHEMA_KEY,
                schema_version=ACTION_ITEMS_SCHEMA_VERSION,
                job_type=AIJobType.ACTION_ITEMS.value,
                validation_model=ActionItemsArtifactContent,
                description="Strict schema for transcript-grounded meeting Action Items.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=RISKS_BLOCKERS_SCHEMA_KEY,
                schema_version=RISKS_BLOCKERS_SCHEMA_VERSION,
                job_type=AIJobType.RISKS_BLOCKERS.value,
                validation_model=RisksBlockersArtifactContent,
                description="Strict schema for transcript-grounded meeting Risks & Blockers.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=OPEN_QUESTIONS_SCHEMA_KEY,
                schema_version=OPEN_QUESTIONS_SCHEMA_VERSION,
                job_type=AIJobType.OPEN_QUESTIONS.value,
                validation_model=OpenQuestionsArtifactContent,
                description="Strict schema for transcript-grounded meeting Open Questions.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=BUYING_SIGNALS_SCHEMA_KEY,
                schema_version=BUYING_SIGNALS_SCHEMA_VERSION,
                job_type=AIJobType.BUYING_SIGNALS.value,
                validation_model=BuyingSignalsArtifactContent,
                description="Strict schema for transcript-grounded Buying Signals and Deal Momentum.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_KEY,
                schema_version=OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
                job_type=AIJobType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
                validation_model=ObjectionsCompetitiveSignalsArtifactContent,
                description=("Strict schema for transcript-grounded objections and competitive signals."),
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=STAKEHOLDER_INTELLIGENCE_SCHEMA_KEY,
                schema_version=STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
                job_type=AIJobType.STAKEHOLDER_INTELLIGENCE.value,
                validation_model=StakeholderIntelligenceArtifactContent,
                description="Strict schema for transcript-grounded Stakeholder Intelligence.",
                active=True,
            ),
            OutputSchemaDefinition(
                schema_key=FOLLOW_UP_EMAIL_SCHEMA_KEY,
                schema_version=FOLLOW_UP_EMAIL_SCHEMA_VERSION,
                job_type=AIJobType.FOLLOW_UP_EMAIL.value,
                validation_model=FollowUpEmailArtifactContent,
                description="Strict schema for artefact-grounded Follow-up Emails.",
                active=True,
            ),
        )
    )
