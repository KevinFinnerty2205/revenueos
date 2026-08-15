# ADR 0030: Orchestrate field capture in a foreground browser Companion

- **Status:** Accepted
- **Date:** 2026-08-15

## Context

WO-012 through WO-015 provide preparation, post-interaction debrief, visual
evidence and consented browser recording as separate capabilities. A field user
needs one mobile surface without weakening their different consent, provenance,
review and retention rules. Browsers cannot guarantee background execution,
same-device phone audio, online-meeting system audio or durable unsent memory.

## Decision

Add a thin Companion route that derives phase from the existing Interaction
lifecycle and reuses the established capture components. Persist only a new
tenant-owned, controlled, metadata-only marker entity. Keep unsent audio in
current-tab memory with stable idempotent bounded retry. Use screen wake lock as
best effort. Force phone calls and online meetings into passive mode.

The Companion may summarise capture status and pass bounded semantic coverage
targets into deterministic debrief reasoning. It may not create intelligence
from a marker or bypass existing user review.

## Alternatives considered

- **Native app or background service:** rejected for this work order; it adds a
  different platform, permission and privacy surface.
- **Persistent IndexedDB audio queue:** rejected until encryption, retention,
  quota and erasure controls are designed.
- **Free-text markers:** rejected because they increase distraction and create
  an uncontrolled customer-content store.
- **Microphone recording for phone/online interactions:** rejected because it
  would overstate what the browser reliably captures.

## Consequences

The field workflow is useful with or without recording and remains inside the
modular monolith. Capture can still be interrupted by browser suspension, and
unsent audio cannot survive tab loss. These limits are deliberate and visible.
