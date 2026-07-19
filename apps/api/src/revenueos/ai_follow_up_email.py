from __future__ import annotations

from collections.abc import Mapping

from revenueos.ai_contracts import (
    ActionItemsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    FollowUpEmailArtifactContent,
    FollowUpEmailSource,
    FollowUpEmailTone,
    OpenQuestionsArtifactContent,
)

FOLLOW_UP_EMAIL_SOURCE_ARTIFACT_TYPES = (
    "executive_summary",
    "decisions",
    "action_items",
    "open_questions",
)


def build_follow_up_email_source(
    *,
    executive_summary: Mapping[str, object],
    decisions: Mapping[str, object],
    action_items: Mapping[str, object],
    open_questions: Mapping[str, object],
    tone: FollowUpEmailTone,
) -> FollowUpEmailSource:
    """Validate source artefacts and expose only customer-safe composition fields."""

    summary_content = ExecutiveSummaryArtifactContent.model_validate(
        executive_summary,
    )
    decisions_content = DecisionsArtifactContent.model_validate(decisions)
    action_items_content = ActionItemsArtifactContent.model_validate(action_items)
    questions_content = OpenQuestionsArtifactContent.model_validate(open_questions)

    return FollowUpEmailSource(
        executive_summary=summary_content.executive_summary,
        decisions=tuple(_render_item(item.decision, owner=item.owner) for item in decisions_content.decisions),
        action_items=tuple(
            _render_item(
                item.task,
                owner=item.owner,
                due_date=item.due_date,
            )
            for item in action_items_content.action_items
        ),
        open_questions=tuple(
            _render_item(item.question, owner=item.owner) for item in questions_content.open_questions
        ),
        tone=tone,
    )


def output_is_grounded(
    content: FollowUpEmailArtifactContent,
    source: FollowUpEmailSource,
) -> bool:
    """Reject provider-created meeting facts after strict schema validation."""

    return (
        content.summary == source.executive_summary
        and content.decisions == source.decisions
        and content.action_items == source.action_items
        and content.open_questions == source.open_questions
        and content.tone == source.tone
    )


def _render_item(
    value: str,
    *,
    owner: str | None,
    due_date: str | None = None,
) -> str:
    metadata: list[str] = []
    if owner is not None:
        metadata.append(f"Owner: {owner}")
    if due_date is not None:
        metadata.append(f"Due: {due_date}")
    if not metadata:
        return value
    return f"{value} ({'; '.join(metadata)})"
