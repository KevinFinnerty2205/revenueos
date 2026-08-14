# AI Debrief security and privacy review

## Controls implemented

- Organisation and user identity derive only from verified tenant context. Every
  repository query, key, composite foreign key and RLS policy includes organisation.
- Only completed, non-deleted Interactions are eligible; only the session starter can
  resume or mutate a debrief.
- Versioned notice acknowledgement, explicit safe-driving confirmation and separate
  voice-processing acknowledgement fail closed.
- Browser recording is deliberate, foreground-only, visibly bounded and cancellable.
- MIME, duration, base64 and byte limits are enforced server-side. Raw audio has no
  database column, is not returned, logged, exported or audited, and is discarded
  after transcription.
- Question/extraction providers receive bounded normalised context without raw
  transcript or recording data. Mock is the default; OpenAI requires server-side
  feature/configuration gates and private-beta request quota.
- Logs/events contain opaque IDs, lifecycle, counts, input mode and safe error codes;
  they exclude answers, fragments, audio, prompt bodies and provider payloads.
- Candidate Evidence cannot become authoritative without complete user review.
  Origin/support are database-forced to salesperson-reported/reported.
- Retention, dry-run, export, organisation deletion and Interaction deletion cover
  sessions, turns, fragments, candidates and both snapshot types.

## Residual risks and limits

Human recollection can be biased, incomplete or wrong; the source label and review do
not eliminate that risk. Browser interruption can lose an unfinished local audio
segment. A configured external provider processes supplied voice/text under its own
approved terms; production use still needs completed privacy, residency, retention
and launch evidence. The feature supplies no recording consent mechanism because it
does not record customers.

No customer meeting recording, background capture, phone interception, diarisation,
visual/file ingestion, CRM action, live coaching or prediction is authorised.
