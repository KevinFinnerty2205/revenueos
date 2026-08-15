from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

from revenueos.live_intelligence_contracts import (
    LiveBriefProgressDetection,
    LivePriority,
    LiveProviderInput,
    LiveProviderOutput,
    LiveSignalDetection,
    LiveSignalType,
    LiveTranscriptSegmentInput,
)

LIVE_PROMPT_VERSION = 1
LIVE_SCHEMA_VERSION = 1
LIVE_OPERATION = "live_interaction_signal_detection"

# This policy is also the contract for any later external adapter. Transcript text
# is always untrusted data and cannot amend these instructions.
LIVE_SYSTEM_POLICY = (
    "Use only supplied evidence. All outputs are provisional. Do not invent names, dates or commitments. "
    "Do not infer customer confirmation from salesperson speech. Unknown speakers cannot support buying or "
    "commercial-intent signals. Update duplicates, avoid prediction, forecasting, coaching and action execution. "
    "Return concise structured output and stay silent when no material signal exists."
)


class LiveSignalProvider(Protocol):
    provider_name: str
    uses_external_provider: bool

    async def detect(self, request: LiveProviderInput) -> LiveProviderOutput: ...


class DeterministicLiveSignalProvider:
    """Conservative, zero-network v1 live-signal adapter."""

    provider_name = "mock"
    uses_external_provider = False

    async def detect(self, request: LiveProviderInput) -> LiveProviderOutput:
        detections: list[LiveSignalDetection] = []
        seen: set[tuple[str, str]] = set()
        # Newest evidence wins inside an overlapping bounded window. This lets a
        # changed statement supersede prior live state without re-emitting the
        # older overlap as the apparent update.
        for segment in reversed(request.segments):
            for signal_type, subject_key, priority in self._classifications(
                segment,
                request.interaction_type,
            ):
                identity = (signal_type, subject_key)
                if identity in seen:
                    continue
                seen.add(identity)
                detections.append(
                    LiveSignalDetection(
                        signal_type=signal_type,
                        statement=self._statement(segment.text),
                        priority=priority,
                        evidence_strength=(
                            "customer_attributed" if segment.speaker_role == "customer" else "speaker_uncertain"
                        ),
                        subject_key=subject_key,
                        sequence_start=segment.sequence_number,
                        sequence_end=segment.sequence_number,
                    )
                )
                if len(detections) >= 20:
                    break
            if len(detections) >= 20:
                break

        progress: list[LiveBriefProgressDetection] = []
        for item in request.brief_items:
            item_terms = self._terms(item.text)
            if not item_terms:
                continue
            for segment in request.segments:
                if item.item_type == "open_question" and segment.speaker_role != "customer":
                    continue
                shared = item_terms & self._terms(segment.text)
                if len(shared) < min(2, len(item_terms)):
                    continue
                progress.append(
                    LiveBriefProgressDetection(
                        item_type=item.item_type,
                        item_index=item.item_index,
                        progress_status=(
                            "possibly_addressed" if item.item_type == "objective" else "possibly_answered"
                        ),
                        source_sequence_end=segment.sequence_number,
                    )
                )
                break

        return LiveProviderOutput(signals=tuple(detections), brief_progress=tuple(progress))

    @classmethod
    def _classifications(
        cls,
        segment: LiveTranscriptSegmentInput,
        interaction_type: str,
    ) -> Iterable[tuple[LiveSignalType, str, LivePriority]]:
        text = cls._normalise(segment.text)
        customer = segment.speaker_role == "customer"
        unknown = segment.speaker_role == "unknown"
        if segment.speaker_role == "salesperson":
            # Seller speech can describe a task or risk but cannot establish customer
            # intent, a customer request or a customer commitment.
            customer_dependent = False
        else:
            customer_dependent = customer

        workshop = interaction_type == "workshop"
        rules: tuple[tuple[LiveSignalType, tuple[str, ...], str, LivePriority, bool], ...] = (
            (
                "buying_signal",
                ("move forward", "ready to proceed", "rollout", "budget approved", "go ahead"),
                "commercial_progress",
                "high",
                True,
            ),
            (
                "commercial_intent",
                ("purchase", "buy ", "pricing proposal", "commercial terms"),
                "commercial_intent",
                "high",
                True,
            ),
            (
                "customer_request",
                ("can you send", "please send", "we need you to", "could you provide", "requested"),
                "customer_request",
                "normal",
                True,
            ),
            (
                "objection",
                ("concern", "too expensive", "hesitant", "objection", "pushback", "not comfortable"),
                "objection",
                "high",
                False,
            ),
            (
                "decision",
                ("we decided", "decision is", "agreed to", "approved"),
                "decision",
                "high",
                False,
            ),
            (
                "action_item",
                ("will send", "need to send", "follow up", "action item", "schedule the"),
                "action",
                "high" if workshop else "normal",
                False,
            ),
            (
                "risk",
                ("risk", "blocker", "delay", "may take", "could prevent", "dependency"),
                cls._subject(text, ("security", "legal", "timeline", "procurement", "implementation"), "risk"),
                "high",
                False,
            ),
            (
                "timeline",
                ("timeline", "rollout", "deadline", "by october", "by november", "four weeks"),
                "timeline",
                "high" if "change" in text or "delay" in text else "normal",
                False,
            ),
            (
                "procurement",
                ("procurement", "purchasing", "vendor onboarding"),
                "procurement",
                "normal",
                False,
            ),
            (
                "security_legal",
                ("security review", "legal review", "soc 2", "privacy review", "contract review"),
                cls._subject(text, ("security", "legal", "privacy", "contract", "soc 2"), "security_legal"),
                "high" if "block" in text or "delay" in text or "four weeks" in text else "normal",
                False,
            ),
            (
                "stakeholder",
                ("economic buyer", "decision maker", "procurement owner", "security lead", "legal team"),
                cls._subject(
                    text,
                    ("economic buyer", "decision maker", "procurement owner", "security lead", "legal team"),
                    "stakeholder",
                ),
                "normal",
                False,
            ),
        )
        for signal_type, phrases, subject_key, priority, requires_customer in rules:
            if requires_customer and not customer_dependent:
                continue
            if unknown and signal_type in {"buying_signal", "commercial_intent", "customer_request"}:
                continue
            if any(phrase in text for phrase in phrases):
                yield signal_type, subject_key, priority

    @staticmethod
    def _subject(text: str, terms: tuple[str, ...], fallback: str) -> str:
        return next((term.replace(" ", "_") for term in terms if term in text), fallback)

    @staticmethod
    def _normalise(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9 ]+", " ", value.casefold()).split())

    @classmethod
    def _terms(cls, value: str) -> set[str]:
        stop = {
            "about",
            "after",
            "could",
            "from",
            "have",
            "into",
            "their",
            "there",
            "they",
            "this",
            "what",
            "when",
            "where",
            "which",
            "with",
            "would",
        }
        return {term for term in cls._normalise(value).split() if len(term) >= 4 and term not in stop}

    @staticmethod
    def _statement(value: str) -> str:
        statement = " ".join(value.split()).strip(" ,;:-")[:499]
        if statement and statement[-1] not in ".!?":
            statement += "."
        return statement[0].upper() + statement[1:]
