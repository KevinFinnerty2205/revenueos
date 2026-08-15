# Mobile browser recording UX guide

## Promise to users

Browser capture works only while the page remains open and the browser continues
running it. Device lock, backgrounding, operating-system suspension, permission
changes, memory pressure or lost connectivity can interrupt capture. The UI must
always repeat that boundary before recording.

## Start sequence

1. The user chooses recording in the Companion.
2. The consent and authority notice is displayed.
3. The user confirms the notice.
4. Only an explicit `Start recording` action requests microphone permission.
5. The API creates one consented recording session and starts its lifecycle.
6. The browser starts `MediaRecorder` using the first supported allowlisted
   audio MIME type.

Permission denial and unsupported MIME types return the user to passive capture
and post-interaction debrief options. They do not block the Interaction.

## Active controls and status

The recording panel exposes elapsed time, recording lifecycle, verified chunk
count, queued chunk count, online/offline state, microphone state and whether a
best-effort screen wake request is active. Pause and resume are shown only when
the recorder instance provides both operations.

A page-leave warning applies during recording, pause, upload or while an audio
chunk remains in memory. This is a warning, not a background guarantee.

## Stop and recovery

Stopping flushes the recorder, waits for control events and chunk uploads,
stops the server session and finalises only after no in-tab chunk remains. Each
chunk create/complete pair retains stable idempotency keys across bounded retry.
Failed audio remains in memory in the same tab and can be retried after the
connection recovers. Already verified server chunks survive page reload and can
support finalisation recovery; unsent in-memory bytes do not.

Cancellation stops local tracks, releases wake lock, clears the in-memory queue
and cancels the server session. The UI never claims that recovery is possible
after the tab or browser discards unsent bytes.

## Interaction-type exclusions

Phone calls never show browser recording controls. Online meetings never
represent microphone recording as system-audio capture. Authorised imports and
provider-native recordings remain future/integration paths.
