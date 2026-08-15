# WO-015 recording security review

**Finding:** No unresolved critical/high implementation finding in the reviewed
WO-015 boundary. Enabling production recording still requires deployment-specific
storage, provider/privacy and jurisdiction approval.

| Threat | Control and residual risk |
| --- | --- |
| Unexpected microphone use | Permission requested after explicit consent; no implicit start. Browser permission persistence remains visible browser state. |
| Unauthorised/covert recording | Versioned authority attestation, server flag and membership checks. Product cannot determine local law; organisation policy is required. |
| Tenant leakage/enumeration | Trusted tenant context, tenant predicates/composite FKs, forced RLS, opaque not-found behaviour and tenant-prefixed object scope. |
| Object/key enumeration | Random opaque keys and exact short-lived signed grants; public buckets and browser credentials prohibited. |
| Replay/stale grants | Exact key/method/expiry signature plus chunk idempotency/checksum. A captured grant remains usable until its short expiry. |
| Chunk tampering/gaps | SHA-256 at declaration, completion and worker assembly; contiguous manifest and total-size checks. SHA-256 supplies integrity, not malware scanning. |
| MIME spoofing/polyglots/file bombs | Narrow MIME/header allowlist, per-chunk/count/total/duration bounds and streamed assembly. No transcoding or decompression platform is introduced. |
| Oversized/resource exhaustion | Per-session/day limits, simultaneous jobs, bounded retries/timeouts and temporary-file cleanup. Operators must monitor disk headroom. |
| Transcript/provider leakage | Server-only provider, safe adapter output, no browser trace/credentials, no content/raw payload logs. Provider processing remains an approved external disclosure. |
| Browser cache/interruption | Audio is held in browser MediaRecorder blobs only as needed; no persistent browser audio cache is implemented. Device/browser memory behaviour is residual. |
| Storage lifecycle/orphans | Object-first deletion, retention command and tenant-scoped reconciliation. Storage outage leaves explicit retry state. |
| Disabled user/org deletion | Each API action resolves active auth; organisation deletion covers binary and relational lineage. Already issued short grants expire within minutes. |
| Export | Content-free manifest and transcript history; raw audio and provider/internal storage trace excluded from synchronous export. |

Logs and audits were reviewed for raw audio, transcript, signed URL, storage key,
filename, customer-name and raw provider-output fields; the Recording path emits
only IDs, state, safe errors and counts. Automated tests assert transcript content
does not appear in worker logs.

## Release gates

Before production enablement: use private S3-compatible storage and a unique signing
secret; confirm bucket public access is blocked/encryption/region/lifecycle; approve
the transcription provider’s retention/training terms; document jurisdictional
consent policy; run RLS/migration/deletion/reconciliation drills; complete physical
browser tests; and keep all three recording flags off until evidence is approved.
