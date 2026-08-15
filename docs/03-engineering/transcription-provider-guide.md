# Transcription provider guide

**Status:** Current batch-transcription port with deterministic mock and one optional
server-side OpenAI adapter.

## Contract

`TranscriptionProvider.transcribe_file` receives a bounded local file reference,
normalised MIME type, optional language, duration and the configured timeout. It
returns full text, ordered timestamp segments, optional neutral speaker labels,
provider name/request trace and duration. The provider never receives tenant data
through browser credentials and is never called from an API request.

The deterministic `mock` provider performs no network request. It recognises a
synthetic `MOCK_TRANSCRIPT:` marker for tests, produces deterministic segments and
never logs supplied bytes or text. `openai` is constructed only when server-side
configuration validates. SDK retries are disabled because the Recording Worker owns
durable retry classification.

## Configuration

- `API_TRANSCRIPTION_PROVIDER=mock|openai`
- `API_TRANSCRIPTION_MODEL_IDENTIFIER`
- `API_TRANSCRIPTION_TIMEOUT_SECONDS`
- `API_FEATURE_TRANSCRIPTION_ENABLED`
- `API_FEATURE_OPENAI_PROVIDER_ENABLED` and `OPENAI_API_KEY` for OpenAI only

Missing or malformed production configuration fails during Settings validation.
Provider keys and request traces never enter public recording responses.

The optional OpenAI file-transcription path enforces the provider's 25 MB request
limit before making an external request. The default `gpt-4o-mini-transcribe`
configuration requests JSON and therefore produces one safe full-duration,
unlabelled segment. `whisper-1` requests `verbose_json` segment timestamps;
`gpt-4o-transcribe-diarize` requests `diarized_json` with automatic server
chunking and preserves neutral speaker labels. These request shapes follow the
[OpenAI audio transcription reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
and [file-transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text).
The 25 MB limit is an optional-adapter constraint, not a lower private-storage
limit; an oversized session fails with a safe code and remains available for
deletion or retry after provider configuration changes.

## Normalisation and errors

Responses must contain non-empty text no longer than one million characters.
Segments require non-empty bounded text and valid `start <= end` times. Provider
speaker strings are normalised to neutral labels; no participant identity is
inferred. Empty segment arrays fall back to one full-duration segment. Timeouts and
connection/rate/server errors are retryable; rejected media, malformed output and
policy failures are permanent. A retry returns the session to `uploaded`; exhausted
or permanent failures move it to `failed` with a safe code.

Raw SDK errors, response bodies, audio and transcript text are never logged.

## Diarisation posture

WO-015 is diarisation-ready, not diarisation-dependent. Provider labels may be
preserved as `Speaker …`; absent labels do not fail transcription. Biometric voice
identification and automatic mapping to Contacts are prohibited.
