# Interaction security, privacy and consent

- **Status:** Target controls and review questions; WO-010 is not legal advice and
  implements no capture or processing capability
- **Baseline:** Preserve current verified tenant context, forced RLS, safe errors,
  content-redacted logs, retention/export/deletion controls and provider boundaries

## Governance posture

RevenueOS must support organisation policy and jurisdiction-specific configuration,
but it must not decide legal authority by itself. Before any production capture
release, the customer and RevenueOS need appropriate legal/privacy review for the
launch jurisdictions, participants, employment context, source types, providers,
retention and intended use.

Consent is not one universal checkbox. The product records the applicable policy,
notice/consent method and outcome for a capture attempt. It does not claim that the
metadata proves legal validity in every circumstance.

## Threat and privacy boundaries

Interaction evidence can contain confidential business information, personal
information, voices, images, contact details, whiteboard content, contract terms and
internal sales observations. Major boundaries are:

- signed-in user and trusted active organisation;
- device and browser permissions;
- local/offline storage;
- API and database;
- private object storage;
- AI/transcription providers;
- future calendar, meeting, email, document and CRM connectors;
- notification services; and
- exports, backups and approved maintenance operations.

Each transition requires purpose, minimum payload, tenant scope, encryption,
retention and deletion behaviour.

## Recording consent and participant notice

Before microphone capture, evaluate:

- organisation recording policy and allowed interaction types;
- jurisdiction(s) and customer-specific contractual rules;
- whether every relevant participant received the required notice/consent;
- platform-native recording indicators and policies;
- purpose, processor/provider, retention and sharing;
- late joiners, phone participants and changing rooms/groups; and
- refusal or withdrawal.

The UX must provide **Continue without recording** with equal legitimacy. Refusal
must stop/not start capture and should not trigger repeated pressure. Withdrawal
pauses/stops acquisition; treatment of already captured material follows reviewed
policy and applicable requirements.

Recording indicators remain visible and accessible. Background recording must use
OS-required modes/indicators. RevenueOS never records implicitly or always-on.

## Consent/policy evidence

A content-minimised policy record can include:

- tenant and Interaction/Capture Session;
- policy/version and capture purpose;
- notice/consent mechanism category;
- actor who initiated capture;
- time and result: allowed, declined, withdrawn, unknown or blocked;
- participant coverage category without unnecessary names/content; and
- customer/jurisdiction policy reference.

Do not store a fabricated legal conclusion or raw conversation in an audit field.
Where explicit evidence such as a platform receipt exists, store a protected
reference under retention/access policy.

## Non-recording evidence

Debrief, Voice Journal and user observations may still contain personal/confidential
information. Tell users they are creating internal reported evidence and apply
retention/access from the first byte. Do not imply recording refusal authorises a
detailed internal reconstruction that violates customer policy.

## Visual evidence

Photos may capture faces, badges, business cards, screens, visitor logs, whiteboards,
facility layouts and confidential documents. The product should:

- show photo-specific permission/policy guidance;
- allow immediate review, crop/exclude/delete before upload where feasible;
- remove unnecessary metadata such as precise location unless authorised and useful;
- classify and restrict evidence at receipt;
- treat OCR/captions as derived and fallible;
- avoid face recognition and protected-attribute inference;
- support sensitive-region redaction before broad processing where practical; and
- propagate deletion to thumbnails, OCR, derived claims and provider copies.

Business cards and badges are personal information; contact creation remains a
reviewable action, not an automatic consequence of OCR.

## Email and document permissions

Future connectors use least-privilege scopes and explicit tenant-admin/user
authorisation. Prefer selected items/folders/events over full-mailbox or drive-wide
collection where platform capability permits. Record provider, external object ID,
version, access actor, source authority and deletion/sync state.

Respect source permissions at retrieval time. A user must not gain access to a
document/email merely because an AI artefact references it. Revocation, shared-link
changes and source deletion make dependent evidence ineligible and trigger
reconciliation. Connected systems remain authoritative for their records.

## Tenant isolation

- derive organisation only from verified auth/session context;
- require `organisation_id` in every owned row, composite key, object path,
  idempotency key and cache/index partition;
- use explicit repository predicates and forced PostgreSQL RLS;
- keep the runtime role unable to bypass RLS;
- separate migration/admin credentials and narrowly gate approved deletion context;
- validate every participant, account, opportunity, evidence, artefact and action
  reference in the same tenant;
- never accept a client-supplied storage key or tenant path; and
- test cross-tenant reads, writes, links, signed URLs, worker claims and deletion.

## Device and offline security

Responsive web should minimise local persistence and not promise secure long media
buffering. A native client uses encrypted files, OS key protection, short-lived
tokens, least local context, per-session quotas and deletion after verified upload.

For lost devices:

- revoke sessions/tokens server-side;
- prevent new signed grants and data retrieval;
- request app data/key deletion on next contact;
- document offline residual-data risk; and
- integrate with customer MDM controls only as a later, explicit enterprise
  capability.

Do not claim guaranteed remote wipe for an offline device outside platform/MDM
control. Lock-screen notifications contain no customer details by default.

## External AI and transcription processing

Provider calls remain server-side behind typed adapters and policy gates. Before a
source type/provider is enabled, document:

- exact minimum payload and purpose;
- provider/model and region;
- retention/training settings and subprocessor terms;
- encryption and access controls;
- residency/transfer requirements;
- retry/deletion behaviour;
- content categories prohibited from transfer; and
- evaluation and fallback.

No recording, transcript, image, document, email, prompt, output, token or signed URL
appears in logs. Model output remains untrusted until strict validation and
provenance checks. Customer content is not used to train provider or RevenueOS models
without separate explicit, lawful agreement.

## Data residency

Residency is an end-to-end property: device upload region, object storage, database,
AI/transcription provider processing, backups, notification metadata and support
access. A regional database alone does not justify a residency claim. Organisation
policy chooses only from deployed, verified paths; unsupported combinations fail
closed or use non-processing capture.

## Retention, deletion and export

Define retention by source and purpose:

- raw audio/video typically shortest and independently configurable;
- transcript/visual/document content while needed and authorised;
- reported observations and validated intelligence under customer policy;
- local device buffer only until verified upload/expiry;
- derived thumbnails/OCR/embeddings, if any, no longer than their source allows;
- content-minimised job/audit/security metadata according to operational policy; and
- backups until documented expiry.

Deletion immediately prevents normal access and new processing, then walks the
source-to-derived graph across database, object storage, providers, indexes, exports
and local clients. Immutable history retains only the approved minimum and shows
when support was removed. Export uses access-controlled, versioned, time-limited
packages and avoids internal secrets/provider payloads.

Legal hold, contractual retention and backup expiry need customer/legal decisions.
The UI must distinguish active-store deletion, provider deletion, offline-device
risk and backup expiry.

## Sensitive and restricted content

Organisation policy can block capture, provider processing, visual evidence or broad
workspace exposure by interaction/source classification. Users need pause, exclude,
redact and delete controls. Restricted content must not flow into generic summaries,
follow-up drafts, notifications or manager alerts.

Do not infer health, protected characteristics, legal advice, emotion/personality or
other sensitive traits. Do not use Interaction Intelligence for employment decisions
or covert seller monitoring.

## Employee monitoring and analytics

Use aggregate product-effectiveness measures, not surveillance. Prohibit:

- continuous location or ambient microphone monitoring;
- individual activity rankings;
- talk-time, debrief completion or recording adoption as performance scores;
- emotion, personality or deception inference;
- hidden manager alerts based on private recollection; and
- reuse of evidence beyond the disclosed customer-interaction purpose.

Admin policy and analytics should be visible to users. Manager alerts need a defined
business purpose, supported evidence, permission and review boundary.

## Enterprise security review package

Before Interaction Platform Beta, provide:

- data-flow and trust-boundary diagrams;
- source/provider/subprocessor inventory and regions;
- tenant isolation/RLS and signed-upload test evidence;
- mobile threat model and secure storage/permission design;
- retention, deletion, export and incident runbooks;
- access/role matrix and support-access controls;
- encryption/key management and backup posture;
- dependency, vulnerability and penetration-test evidence as appropriate;
- model/transcription evaluation and prompt-injection controls;
- recording/visual consent configuration guidance; and
- limitations and shared-responsibility documentation.

These artefacts support but do not replace customer legal, privacy and security
approval.

## Launch gates

No production customer capture until:

- WO-009 launch gates are satisfied for the target environment;
- customer legal/privacy/security owners approve intended capture modes;
- jurisdiction-specific guidance and customer policy are configured;
- consent/refusal/withdrawal and non-recording fallbacks pass testing;
- provider and residency paths are approved;
- device loss/offline and deletion behaviour are documented and exercised;
- logs, analytics and notifications are verified content-free; and
- incident response and feature-disable rollback are ready.

## Related documents

- [Privacy, security and trust model](privacy-security-and-trust-model.md)
- [Evidence and provenance model](evidence-and-provenance-model.md)
- [Recording and transcription architecture](recording-and-transcription-architecture.md)
- [Interaction platform risk register](interaction-platform-risk-register.md)
