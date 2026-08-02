# Interaction domain security review

## Review result

WO-011 preserves the repository's fail-closed tenant and content-minimisation
baseline. The new surface is suitable for synthetic/private-beta metadata testing
under the existing launch restrictions. It is not approval for production customer
content, recording, transcription or later capture modes.

## Controls implemented

- Verified authentication context remains the only source of organisation and user
  identity. Active local membership is rechecked for every Interaction request.
- All repository reads include organisation predicates; PostgreSQL applies a
  transaction-local trusted tenant and forced RLS to all four new tables.
- Composite organisation foreign keys protect company, opportunity, Meeting,
  Interaction, Capture Session, Evidence and actor/member relationships.
- Meeting compatibility updates lock the relevant rows and commit both projections
  and metadata audit atomically.
- API enums, timezone/range checks and lifecycle policy reject unknown or invalid
  states. Completed/cancelled Interactions are terminal.
- Cross-tenant reads and writes return safe not-found/relationship responses without
  revealing existence.
- Interaction audit and structured logs are content-minimised. No title, transcript,
  evidence body, generated content, prompt, provider payload, secret or raw exception
  is logged.
- Evidence origin, support and validation are separate; verification does not rewrite
  provenance and no numeric confidence is invented.
- Export, retention and confirmed organisation deletion cover the new metadata.

## Database review

`interactions`, `capture_sessions`, `evidence` and
`interaction_audit_events` each have `organisation_id`, a tenant-scoped unique key,
explicit indexes and a forced tenant policy named `{table}_tenant_isolation` using
`current_setting('app.organisation_id', true)`. Runtime credentials must remain a
non-owner role without `BYPASSRLS`; migration credentials stay separate.

The Meeting link is non-null, unique per tenant and composite-tenant constrained.
The migration copies no transcript, Meeting description, participant, AI artefact or
Revenue Brain content. Downgrade data loss is explicit.

## Privacy findings

Interaction currently holds customer-event metadata such as title and relationship
links; it therefore follows the organisation's existing access, export, retention
and deletion controls. Evidence and Capture Session contain classification and
timing metadata only. There is no raw-content column or external storage reference.
The browser explicitly states that manual Interaction creation performs no
recording, transcription or AI processing.

Meeting transcript/data-notice policy is unchanged. The new Interaction API does not
grant authority to capture content and does not bypass that notice.

## Open risks and limits

- Production database-role provisioning and target-environment RLS evidence remain
  operator responsibilities.
- The current beta retention policy operates at the completed/cancelled Interaction
  or linked Meeting level; source-specific legal hold is not implemented.
- Capture Session type names are schema reservations, not working capture modes.
- Evidence has no mutation API or immutable body/version chain yet. A future body or
  processing implementation requires a new threat/privacy review.
- Existing Meeting transcript version limitations, provider approvals, backup expiry
  and production-customer-data restrictions remain unchanged.

No new blocker was introduced for the existing synthetic beta path. Production
customer data remains prohibited unless separately approved through the existing
launch process.
