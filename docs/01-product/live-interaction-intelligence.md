# Live Interaction Intelligence product guide

## Current product boundary

WO-020 adds an optional, quiet Live Companion panel for an in-progress supported
Interaction when Oryntela already has an authorised progressive transcript source.
It helps a salesperson notice material conversation changes without pretending that
an incomplete transcript is final evidence.

Every live result is labelled **Provisional · needs review**. Final Interaction
Intelligence remains authoritative. A live result never updates opportunity fields,
the final Opportunity Workspace intelligence projection or Revenue Brain.

## User journey

1. Prepare and review the Pre-Interaction Brief.
2. Start the Interaction and its separately authorised source capture.
3. Explicitly choose **Enable Live Intelligence**.
4. Review the next unresolved preparation question, bounded
   objective/question progress and material emerging signals.
5. Collapse the panel, dismiss an individual signal or disable it for the Interaction.
6. End the Interaction. Oryntela freezes live processing.
7. Finalise the normal evidence path and run final Interaction Intelligence.
8. Compare the frozen live state with final intelligence.
9. Use AI Debrief for material ambiguity that final evidence did not resolve.

The panel uses no audio, toast, modal, vibration or autonomous prompt. When a reviewed
preparation question remains unresolved, the panel may quietly surface that exact
question as **Suggested next question**. It does not generate a new coaching script,
interrupt, auto-speak or claim that the question is appropriate for the current
moment. Silence is a valid result. There is no score, forecast or confidence
percentage.

## Supported and fallback behaviour

- Face-to-face meetings, presentations, workshops, site visits and online meetings
  can use live processing only when an authorised progressive source exists.
- The browser can deliberately tap an authorised recording stream as 24 kHz mono
  PCM16 and send it through authenticated server routes to the disabled-by-default
  OpenAI Realtime transcription adapter. Final provider turns are persisted as a
  provisional `progressive` transcript for this feature; partial and final text are
  also reconciled in the recording UI. Ordering, bounded buffering, cancellation,
  reconnect/retry and final drain are fixture- and synthetic-browser-tested only.
  WO-015 batch processing remains the authoritative final transcript path.
- Ordinary cellular calls have no same-device capture. Phone Live Intelligence is
  unavailable unless a separately authorised progressive source exists.
- Executive lunches and other sensitive unsupported modes fall back to passive
  Companion and post-interaction Debrief.

## What the panel may show

- possible buying signal;
- possible objection, decision, action, risk or customer request;
- possible timeline, procurement, security/legal or stakeholder change;
- an objective as **Possibly addressed**; and
- an open question as **Possibly answered**; and
- the first still-unresolved preparation question as a quiet
  **Suggested next question**.

Buying, commercial-intent and customer-request signals require customer attribution.
Unknown speakers can support only conservative, visibly uncertain operational
signals. Seller speech and seller-prepared material are context, never proof of
customer intent.

## Known limitations

- Live output can be incomplete or wrong and may change as segments arrive.
- There is no biometric speaker identification.
- Unknown speaker identity reduces what can be inferred.
- There is no guaranteed sub-second latency; the default cadence is 15 seconds and
  processing also waits for enough new material.
- Online live capability depends on an authorised progressive source.
- There is no ordinary cellular-call interception, native app or meeting bot.
- A server-only OpenAI Responses live-signal adapter is implemented with strict
  schema/source validation, no tools, `store=false`, bounded timeouts and safe
  retry/error mapping. Each live session durably records its provider mode and,
  when external processing is selected, the user's acknowledgement time; processing
  fails closed if runtime configuration no longer matches that binding. Live
  activation and verification remain disabled; the local deterministic detector
  remains the default.
- Progressive audio-to-text transport is implemented behind closed gates, but live
  provider behaviour, regional processing, retention, cost, reliability and
  production rollout/drain remain unverified activation boundaries. Fixture-tested
  protocol compatibility is not live-provider verification.
- Private-beta flags, quotas, consent, retention and production-data restrictions
  remain in force.

See the [provisional/final architecture](../03-engineering/live-intelligence-provisional-final-architecture.md),
[speaker and provenance rules](../03-engineering/live-intelligence-speaker-provenance-safety.md)
and [security review](../03-engineering/live-intelligence-security-review.md).
