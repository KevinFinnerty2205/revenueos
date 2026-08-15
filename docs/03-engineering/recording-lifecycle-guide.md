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

Interrupted browsers read current sessions and verified chunk manifests. An
`uploading` session can retry finalisation; a still-`recording` session cannot claim
background survival and should be cancelled/restarted if capture was lost.
