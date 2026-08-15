# Recording consent guide

Customer-interaction recording uses a separate path from salesperson-only Voice
Journal. Recording cannot start until the authenticated user explicitly confirms
that participants received required notice and that the user has authority to
record. The UI also states that customer participants may be captured, configured
external transcription may receive audio and rules vary by jurisdiction. This is a
product notice, not legal advice.

The server stores organisation, Interaction, Recording Session, user, notice
version, acknowledgement time, controlled consent method and authority attestation.
It does not store free-form legal declarations. Consent is tenant-scoped, versioned,
immutable evidence for that session and included as metadata in authorised export.
It is never inferred from Meeting attendance, calendar acceptance, prior recordings
or browser microphone permission.

Administrators remain responsible for selecting permitted jurisdictions/workflows.
Recording can be globally disabled with the server flag. Disabled users, missing
membership, stale notice, absent attestation or cross-tenant resources fail closed.
Voice Journal, AI Debrief and manual capture remain available where policy permits.
