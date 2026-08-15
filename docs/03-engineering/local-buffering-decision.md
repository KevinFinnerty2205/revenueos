# Local audio buffering decision

## Decision

WO-016 retains not-yet-verified audio chunks in bounded JavaScript memory in the
current tab. It does not persist audio in IndexedDB, Cache Storage, localStorage,
the filesystem or a service worker.

## Rationale

Memory buffering enables short network interruptions to recover without adding
a second persistent media store, new erasure surface or misleading background
behaviour. Stable per-chunk idempotency keys allow retry without duplicating
server records. Three immediate/bounded attempts are made before the user must
retry deliberately.

## Data-loss boundary

Verified server chunks remain recoverable under the WO-015 recording lifecycle.
Unsent browser-memory chunks are lost if the tab reloads, crashes, is discarded
or the browser process ends. The page-leave warning reduces accidental loss but
cannot prevent it. Product copy and support guidance must state this boundary.

## Revisit trigger

Persistent offline audio requires a separate privacy, encryption, quota,
retention, deletion, browser-compatibility and threat-model decision. It is not
authorised by WO-016.
