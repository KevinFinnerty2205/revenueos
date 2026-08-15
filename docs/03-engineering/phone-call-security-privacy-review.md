# Phone-call security and privacy review

**Review date:** 2026-08-15
**Scope:** WO-017 browser phone workflow, associations, imported recording and
metadata-only observability.

## Findings and controls

| Area                       | Implemented control                                                                                               | Residual requirement                                                        |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Ordinary calls             | No dialler, call-log read, cellular interception, same-device recording control or background microphone use     | Users must use their existing authorised phone system                       |
| Phone numbers              | Reuse Contact data; no copied Interaction number and no number in telemetry, audit metadata or provider payloads | Contact correctness remains the organisation's responsibility               |
| Associations               | Trusted-tenant repository predicates, composite Contact FK and same-company/opportunity validation               | No automatic phone-number matching or enrichment                            |
| Imported audio             | Explicit authority attestation, allowlist, limits, private tenant-derived keys and resumable checksums           | Customer/legal owners must approve jurisdiction and participant policy      |
| Recording source           | Required controlled provenance for every non-live recording                                                       | A label is not proof that the source was lawfully obtained                   |
| Processing                 | Existing server-side transcription port, strict lifecycle, safe errors and content-redacted events              | Production provider, region and retention gates remain off by default       |
| Personal calls             | No automatic history ingestion; user must deliberately create/link/import one business Interaction              | Admin policy and training must prohibit accidental personal-call processing |
| Admin/support access       | Existing membership roles and narrowly approved maintenance paths; no public object URL                          | Production access review and support audit remain launch gates              |
| Export/deletion/retention  | Export v8 adds call metadata/source; existing object-first deletion and source-lineage rules apply               | Backup/provider expiry is reported honestly, not as instant erasure         |

## Observability review

Allowed events include `phone_call_created`, `call_started`, `call_completed` and
`recording_imported` with opaque Interaction/organisation IDs, controlled direction,
outcome, source, status, duration bucket or counts. Prohibited content includes
phone number, Contact/customer name, filename, transcript, debrief response, audio,
object key, signed URL and raw provider payload.

## Threat conclusions

- Cross-tenant Contact, company, opportunity, recording and transcript attachment
  fails closed through service validation, composite constraints and existing RLS.
- Association changes are blocked after final Interaction Intelligence so evidence
  cannot be silently moved to another relationship.
- Missed calls do not produce customer intelligence or opportunity deterioration.
- Recording/debrief disagreement is surfaced as `conflicting` or `unresolved`; the
  application does not select a winner or assign a confidence percentage.
- No production customer call should be processed until the existing private-beta
  legal, privacy, provider, storage, residency and incident-response gates pass.

This review is an engineering control assessment, not legal advice.
