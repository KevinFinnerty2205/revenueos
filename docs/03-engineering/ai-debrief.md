# AI Debrief engineering guide

## Current boundary

WO-013 implements a tenant-isolated post-interaction capture workflow for completed
Interactions. It works without customer recording or a supplied transcript. The
salesperson can use guided text/voice answers or a short Voice Journal, review every
candidate item, and accept, edit or reject it before RevenueOS composes validated
Interaction Intelligence.

This is not a CRM, call interceptor, long-form recorder, meeting bot, live assistant
or autonomous action system.

## Flow

1. The user confirms they are safely stopped and starts `ai_debrief` or
   `voice_journal` with an idempotency key.
2. RevenueOS creates one Capture Session and one Debrief Session. The standard
   opening is “How did it go?”; a short phone call uses “What changed?”.
3. Each answer becomes an unreviewed `Evidence` row, a `DebriefTurn` and a source
   `EvidenceFragment` before structured reasoning runs.
4. The versioned `ai_debrief_question` prompt/schema selects one useful next
   question or completes. The configurable cap defaults to six follow-ups; Voice
   Journal is capped at two.
5. Finish runs the separate `ai_debrief_evidence` extraction and creates reviewable
   Candidate Evidence. No candidate mutates validated intelligence.
6. The user must decide every candidate. Accepted or edited items create verified,
   `salesperson_reported` Evidence; rejected items remain rejected.
7. Accepted evidence composes immutable Interaction Intelligence and, when an
   account is available, an additive Revenue Brain Interaction snapshot.

## Context and provider execution

Question selection receives only normalised Interaction metadata, Opportunity
metadata, the latest Pre-Interaction Brief, latest Revenue Brain snapshot identity,
latest longitudinal insight, previous validated reported intelligence, the current
debrief answers and prior question targets. WO-016 also supplies metadata-only
marker types and the names of semantic targets covered by completed direct recording
evidence so already-covered gaps can be suppressed. It does not pass recording or
raw transcript content into the debrief provider input.

WO-020 adds only controlled gap targets for non-dismissed live signals that final
reconciliation leaves pending, unsupported or unresolved. Confirmed/revised targets
are suppressed. The debrief question context receives a generic category target,
never the provisional statement, speaker/customer name or transcript excerpt.

`ai_debrief_question` and `ai_debrief_evidence` are explicit structured-output
allowlist entries with prompt/schema version 1. The default mock follows the same
strict contract with no network. OpenAI is available only through the existing
server-side flag/configuration gate. User input is committed before a bounded
foreground provider call; the transaction is reopened with trusted tenant context
to store the validated result. Provider payloads are never logged or persisted.

Voice transcription uses the separate narrow `TranscriptionProvider` contract; no
binary audio enters the text structured-output contract.

## Lifecycle and API

Lifecycle is `collecting -> processing -> collecting|review -> completed`; cancel
produces `cancelled` and a safe provider failure produces `failed`. Only the starting
user can read or mutate a session. Routes are documented in [API](api.md).

Session start, answer/voice upload, finish and review are idempotent at their durable
boundaries. Row locks and unique tenant-scoped keys prevent duplicate turns,
candidates, accepted Evidence and intelligence composition.

## Configuration

- `API_FEATURE_AI_DEBRIEF_ENABLED=true`
- `API_FEATURE_VOICE_JOURNAL_ENABLED=true`
- `API_PRIVATE_BETA_MAX_DEBRIEF_SESSIONS_PER_DAY=25`
- `API_PRIVATE_BETA_DEBRIEF_QUESTION_CAP=6` (allowed 1–10)
- `API_PRIVATE_BETA_MAX_DEBRIEF_AUDIO_SECONDS=120`
- `API_PRIVATE_BETA_MAX_DEBRIEF_AUDIO_BYTES=8000000`

Phone calls reuse these flags and quotas. Their server-owned caps are one question
for no-answer/voicemail/cancelled, two for a call up to three minutes or Voice
Journal, four for a normal connected call and five for a linked opportunity call of
at least 15 minutes, always bounded by the configured global cap.

OpenAI question/extraction requests additionally consume the organisation’s existing
external-provider request guardrail. Finish consumes the existing generation quota.

## Known limitations

Salesperson memory can be incomplete or biased. Accepted content remains labelled
“Reported by you” and is never silently upgraded to customer-direct evidence. There
is no background recording, phone interception, live diarisation, email/document
ingestion, CRM automation or native mobile application. WO-016
may route the user into this flow after optional foreground recording or visual
capture, but accepted debrief content remains separately labelled
salesperson-reported evidence. Production data remains subject to private-beta
gates.
