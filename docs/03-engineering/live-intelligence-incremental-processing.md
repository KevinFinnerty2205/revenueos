# Live Intelligence incremental processing guide

## Server-authoritative cursor

The browser may ask for an update, but it never supplies the transcript cursor.
`LiveInteractionSession.last_processed_sequence` is the authority. The repository
reads the next contiguous progressive segments plus a bounded overlap from the same
tenant and immutable transcript version.

Processing waits until at least two new segments or 160 new characters are present.
The default window is at most 12 segments and 8,000 characters with two prior
segments of overlap. The API polls at a default 15-second cadence; a poll can return
`processed=false` without advancing the cursor.

## Idempotency and overlap

- a client trigger key is unique within a live session;
- the server hashes transcript-version identity and exact window boundaries/content;
- duplicate trigger and window fingerprints reuse the stored result;
- new segments must be contiguous with the persisted cursor;
- the cursor advances only after provider output and derived state commit together;
- stable signal fingerprints suppress duplicate provider output; and
- subject fingerprints supersede a changed signal while retaining history.

Newest evidence is considered first within an overlap window so corrected or changed
wording can supersede an earlier subject rather than being masked by the older
segment. The source reference still points to exact sequence bounds.

## Concurrency and failure

The session row is locked before processing. `processing` is a durable state and the
database has unique trigger/window keys. A concurrent or retrying poll cannot create
a second equivalent signal. A provider failure records only a safe code, moves the
session to `failed` and leaves final intelligence untouched.

This implementation uses bounded synchronous work from the polling request. It does
not introduce WebSockets, a broker, Redis, Celery or another worker. A future
external provider would need separately approved timeout, unknown-outcome and claim
semantics before replacing this private-beta path.

## Limits

Defaults per organisation are four live requests/minute, 120 requests/Interaction,
200,000 processed characters/Interaction, three concurrent live Interactions and
200 external-provider calls/day. The provider-call counter is reserved through the
existing beta usage service only when an external provider declares itself active.
