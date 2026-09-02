# AI real-data processing gate

Status: **OWNER APPROVAL REQUIRED; TARGET PROOF NOT RUN**. No provider was activated or called for this launch-gate work.

## Exact current external AI path

The only implemented external AI vendor is OpenAI, behind server-side adapters. There is no tenant model selector, provider fallback, tool use, streaming, autonomous write authority or approved production account in repository evidence.

| RevenueOS path | Customer data sent when its OpenAI adapter is selected | Model/configuration |
| --- | --- | --- |
| Meeting Intelligence extractors: Executive Summary, Decisions, Action Items, Risks & Blockers, Open Questions, Buying Signals, Objections & Competitive Signals and Stakeholder Intelligence | Registered instructions/schema plus the bounded selected meeting transcript | `AI_PROVIDER=openai`, exact `OPENAI_MODEL`, timeout, max output tokens and `API_FEATURE_OPENAI_PROVIDER_ENABLED=true` |
| Next Best Action | Eight validated extraction artefacts; no transcript | Same main Responses API configuration |
| Follow-up Email composer | Validated Executive Summary, Decisions, Action Items and Open Questions projection plus selected tone; no transcript | Same main Responses API configuration |
| AI Debrief | Bounded normalised debrief context/answers or fragments; no raw recording | Same main provider configuration and Debrief flag |
| Voice Journal / recording transcription | Selected bounded audio file, media type, language and duration | `API_TRANSCRIPTION_PROVIDER=openai`, exact `API_TRANSCRIPTION_MODEL_IDENTIFIER` (default is `gpt-4o-mini-transcribe`), timeout, transcription flag and common OpenAI gate |
| Visual Evidence | Sanitised bounded JPEG/PNG bytes plus visual type, source ownership and optional context label | `API_VISUAL_PROVIDER_NAME=openai`, a non-mock `API_VISUAL_PROVIDER_MODEL_IDENTIFIER`, timeout and common OpenAI gate |
| Document Evidence | Extracted bounded document fragments, page/section locations, document type and source ownership | `API_EVIDENCE_EXTRACTION_PROVIDER_NAME=openai`, a non-mock evidence model identifier, timeout and common OpenAI gate |
| Pasted Email Evidence | Plain-text body plus source type, direction and sender-identity state | Same evidence-extraction adapter/configuration |

Ask RevenueOS, Revenue Brain longitudinal reasoning, Methodology, Daily, Analytics, Targets, Forecast, Manager Intelligence, Business Case and Create PPTX rendering do not call an AI provider in the current implementation. Prospect has only a deterministic mock provider and must be disabled. Live external Interaction Intelligence declares a separate flag, but no production external live adapter is currently implemented. Gmail, Apollo and mailbox/CRM external execution are absent or disabled.

## Provider behaviour implemented in code

- Responses requests use strict JSON Schema, `store=false`, no tools, no streaming and zero SDK transport retries.
- Application Pydantic validation remains authoritative; raw provider response and SDK errors are not persisted or logged.
- Provider execution occurs outside the database transaction; completion re-enters the claimed tenant and rechecks cancellation/ownership.
- Metadata may include provider/model/request ID, latency, token counts, safe finish/error and integer cost fields. Prompts, transcripts, source text, audio/images, generated content, headers and full payloads are excluded.
- Actual OpenAI account/project settings, contractual data use, abuse-monitoring retention, subprocessors, regions and deletion behaviour are **not proven by repository configuration**.

`store=false` is a request setting, not a complete retention, training, residency, DPA or cross-border decision. The stored `0 AUD` estimate means cost is not calculated, not free.

## Usage and cost controls

The repository enforces per-organisation UTC-day generation and OpenAI-attempt counters. Defaults are 100 generations and 150 OpenAI requests; each actual provider attempt, including a bounded strict-output retry, consumes the provider counter. Transcript/input, timeout, output-token, debrief, recording/transcription, visual and document/email bounds also apply. There is no approved pricing source, monetary budget enforcement, billing or accurate per-request cost estimate.

Recommended first-partner limits are 50 generations and 75 OpenAI attempts per organisation/day until observed usage and provider cost are reviewed. Record an owner-approved monthly alert/stop amount outside the product; reaching it disables external AI rather than silently increasing limits.

## Blocking approval record

The owner, privacy/legal approver and partner must approve:

1. exact OpenAI contracting entity, account/project and authorised operators;
2. exact model identifiers for every enabled path—no example or silent fallback;
3. enabled features and exact data categories above;
4. purpose, instructions, source authority and prohibited sensitive data;
5. provider DPA/terms, data-use/training settings, retention/abuse monitoring and deletion;
6. hosting/processing locations, subprocessors and cross-border disclosure;
7. TLS/egress/secret-manager controls and key rotation/revocation;
8. quality/prompt-injection evaluation appropriate to the enabled sources;
9. daily quotas, owner-approved spend alert/stop amount and incident owner;
10. partner-facing disclosure/acceptance and the disabled-provider user experience; and
11. rollback: disable every affected content feature and provider flag, stop worker claims, restart consistently and revoke/remove the key if required.

## PASS/FAIL procedure

1. Record the approved profile and exact configuration without secret values.
2. Validate `API_PRIVATE_BETA_EXTERNAL_AI_APPROVED=true`, common OpenAI flag, exact providers/models and only the selected source features.
3. Run `production-preflight` and compare flags to the approved profile.
4. With synthetic content only, process one example for every enabled adapter; verify correct trace, bounded usage counter and no content in logs. Do not use this launch package as authority to make the calls—the owner must separately authorise the synthetic provider smoke test and any cost.
5. Disable the provider and prove each affected feature fails closed with an honest unavailable state; never fall back to mock over real data.
6. Verify rate-limit, timeout, refusal, malformed output and key-revocation paths with fakes or approved synthetic tests.

The current repository path is technically bounded but **not currently approved for real customer data** because no target OpenAI account/model/terms/data-location/cost evidence or owner/partner approval has been supplied. The whole product may still launch under `NATIVE-NO-EXTERNAL-AI-V1`; `NATIVE-AI-REVIEW-V1` is `NO-GO` until this gate passes.
