# Live signal schema guide

## Persisted signal

`provisional_signals` stores one bounded statement and metadata; it never stores a
copy of a transcript window, prompt or raw provider response.

| Field group      | Meaning                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| Ownership        | UUID, organisation, Interaction, live session and transcript version    |
| Classification   | controlled signal type, high/normal priority and evidence strength      |
| Content          | a statement limited to 500 characters                                   |
| Lifecycle        | detected, updated, superseded, dismissed, promoted candidate or expired |
| Final comparison | pending, confirmed, revised, unsupported or unresolved                  |
| Dedupe           | signal fingerprint, subject fingerprint and optional superseding signal |
| Source           | inclusive segment sequence start/end, detection/update timestamps       |

`is_provisional` is database-constrained to true. A final result is always stored in
the existing final-intelligence aggregate, never by changing this flag.

## Signal types

The v1 controlled set is buying signal, objection, stakeholder, decision, action
item, risk, timeline, procurement, security/legal, customer request, commercial
intent, objective progress, open-question progress and other. Objective/question
progress is normally represented in `live_brief_progress` so the UI can preserve
brief order and labels without making it a commercial signal.

## Provenance and public contract

The API exposes the transcript-version ID and exact segment sequence range, evidence
strength (`customer_attributed`, `speaker_uncertain` or `context_only`), lifecycle
and resolution. It excludes signal/subject fingerprints, processing-window hashes,
provider/model names, request IDs, prompt text and raw transcript content.

The UI uses “Possible …” language and explicitly labels every item provisional. It
does not expose a confidence number or convert priority into predictive deal score.

## Database guarantees

Migration `0030_live_interaction_intel` adds constrained values, length/range checks,
composite tenant foreign keys, per-session uniqueness, indexes and forced RLS. The
upgrade widens immutable transcript versions to accept `progressive`/`provisional`
and adds a constrained optional `speaker_role` to segments. Downgrade deletes live
state and progressive versions before restoring the WO-019 transcript contract.
