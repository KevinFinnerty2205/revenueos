# ADR 0031: Use provider-neutral online-meeting ingestion before native connectors

- **Status:** Accepted
- **Date:** 2026-08-15

## Context

Online meetings span Teams, Zoom and Meet, but browser system-audio capture is not a
reliable or honest cross-platform foundation. Building three OAuth/webhook adapters
or a meeting bot before the design-partner ecosystem is known would add credentials,
permissions and operational surface without proving value.

## Decision

Make online meetings first-class Interactions with normalised platform metadata,
safe meeting references and server-negotiated capture capabilities. Ship deliberate
recording/transcript import through the existing evidence pipelines plus AI
Debrief/Voice Journal fallback. Define and fake-test one provider-neutral adapter;
leave native and auto-ingest flags off. No connector or bot is implemented.

If pilot demand is otherwise equal, use Google Meet v2 as the first technical spike
because it exposes purpose-built conference-record and artefact resources with
narrow read-only scopes. Final production priority remains conditional on the first
design partners' ecosystem and entitlement testing.

## Alternatives considered

- **Browser system-audio capture:** rejected as incomplete/unreliable and easy to
  misrepresent.
- **Three production connectors:** rejected as premature breadth.
- **Meeting bot baseline:** deferred due consent, visibility, admission, provider
  terms, reliability and maintenance burden.
- **Debrief only:** rejected because authorised platform/user artefacts provide
  higher-fidelity evidence when available.

## Consequences

The baseline works without external credentials, native software or provider calls
and preserves one intelligence pipeline. Users must obtain an authorised artefact
themselves until a connector is selected. Platform licensing and policy remain
visible constraints. Any native adapter, webhook or auto-ingestion rollout needs a
new focused security and operations review.
