# Browser voice capture

The WO-013 browser implementation uses `MediaRecorder` only after a user gesture and
browser permission. It selects the first supported allowlisted type from WebM/Opus,
Ogg/Opus and MP4 variants. Unsupported browsers immediately retain a typed Voice
Journal path.

The component owns the media stream, recorder and in-memory chunks. It exposes
recording, paused, processing and idle states; tracks elapsed seconds; stops at 120
seconds; and disables conflicting primary actions. Cancel and unmount mark the
recording cancelled before stopping tracks so the callbacks cannot upload discarded
audio.

On stop, the bounded Blob is converted to base64 for the single JSON request because
this private-beta path accepts short segments only. The API validates base64, MIME,
duration and the 8 MB byte ceiling, commits consent/quota state, transcribes through
the narrow provider boundary, then discards the bytes. Only answer text and safe
transcription metadata are persisted.

This design intentionally does not add object storage, resumable upload, streaming,
background capture, service-worker recording, long-form media retention or a media
deletion subsystem. Those require a separate recording/consent work order.
