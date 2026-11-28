# Recording lifecycle guide

The deterministic states are:

`created → recording → uploading → uploaded → transcribing → completed`

Additional terminal/recovery paths are `failed`, `cancelled`, `deleting` and
`deleted`. A retryable transcription failure returns `transcribing → uploaded`;
eligible failed upload sessions may return to `uploading` or `uploaded`.

## Rules

- `created` requires persisted consent and may start capture, accept an uploaded
  source, cancel or delete.
- `recording` may stop into upload, fail, cancel or delete.
- `uploading` accepts/reconciles chunks. Finalisation moves to `uploaded` only after
  a contiguous verified manifest.
- `uploaded` is the durable worker-ready state. It may be claimed once into
  `transcribing` or fail/delete.
- `transcribing` may complete, safely retry, fail or delete.
- `completed` is immutable as a processing outcome and may only delete.
- `cancelled` may only delete; `deleted` has no outgoing transition.

Impossible transitions such as `completed → recording`, `cancelled → completed` and
`deleted → transcribing` return a product-safe conflict. Services lock the session
for finalisation/claim/result persistence. Lifecycle events are metadata only.

Interrupted browsers read the current session and verify that saved chunks belong
to that exact recording. An unexpired `uploading` session can retry finalisation
when the saved chunks are all verified and contiguous from sequence zero. If a
session is still `recording` in its original tab, stop it there. If its capture
was interrupted, the user can explicitly cancel the session.

The recording start and Interaction completion paths lock the same parent
Interaction. A browser cannot start live capture on a completed or cancelled
Interaction. Completion requires any unexpired live capture to stop first.
Previously stopped uploads and authorised recording imports can still finish
after the Interaction completes.
