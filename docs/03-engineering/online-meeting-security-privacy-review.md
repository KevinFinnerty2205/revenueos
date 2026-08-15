# Online Meeting security and privacy review

**Review outcome:** Acceptable for the WO-018 private-beta boundary. Native provider
connections and automatic ingestion remain disabled and require a new review.

## Controls

- Trusted authentication determines the organisation; all metadata/import rows use
  tenant predicates, composite tenant foreign keys and forced PostgreSQL RLS.
- Meeting URLs are reduced to safe navigation references and never fetched or logged.
- Transcript and recording import require explicit business-authority attestation
  and an external-processing notice. Artefact presence is not treated as legal
  permission.
- Transcript content, recording content, attendee email addresses, external meeting
  IDs, OAuth tokens and raw provider payloads are prohibited from telemetry/logs.
- The import API validates format, encoding and size before persistence; recording
  import reuses WO-015 MIME, bytes, duration, chunk, quota and private-storage rules.
- Participant mapping is exact authorised email only; display names do not create or
  merge Contacts, assign stakeholder roles or trigger enrichment.
- Speaker labels remain unverified. No biometric voice recognition is used.
- Export v9 and organisation deletion include local online-meeting data. Existing raw
  recording expiry remains seven days by default. Local deletion does not delete an
  upstream Teams, Zoom or Meet artefact.

## Deferred risks

Native OAuth tokens, administrator scopes, provider download references, webhooks,
regional processing and provider-side erasure are not present. A connector review
must prove encryption/revocation, per-organisation connection ownership, least
privilege, webhook authenticity/replay protection, bounded payloads, reconciliation,
edition constraints and support/incident procedures. Auto-ingestion stays off until
an organisation-visible eligibility rule prevents unrelated-meeting ingestion.

## Explicit non-capabilities

There is no meeting bot, browser/OS system-audio interception, hidden/background
capture, live transcription, live coaching, native app, extension or real meeting
provider call. Local microphone capture is not offered as complete online-meeting
capture.
