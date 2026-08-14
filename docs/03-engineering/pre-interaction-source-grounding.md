# Pre-Interaction Brief source context and grounding

## Deterministic selection

Every query carries the trusted organisation ID. The service resolves the requested
Interaction, its linked opportunity, and the company directly or through that
opportunity. It then selects:

1. participant metadata from the Meeting linked to the target Interaction;
2. the latest prior, completed and non-deleted Meeting for the exact opportunity;
3. company scope only when the Interaction has no opportunity;
4. only completed current-version artefacts for that one selected Meeting;
5. the latest valid opportunity Revenue Brain insight, with account fallback only
   when no opportunity is linked; and
6. Interaction, company and opportunity metadata needed for factual context.

Meeting order is meeting date then UUID, descending, and is bounded before the
target scheduled time when one exists. Exact opportunity scope prevents mixing
unrelated opportunities at the same company.

## Explicit exclusions

The source repository never queries the transcript table or calls a transcript
repository/service. Artefact currency relies on the content-minimised Meeting audit
version, the existing append-only artefact trace, completed-job requirement and
`superseded_at` state. The brief path also never reads recordings, documents,
emails, rendered prompts, raw provider responses, superseded artefacts,
incomplete-job artefacts or cross-tenant rows.

Each known artefact body is revalidated against its strict capability contract.
Invalid bodies are skipped with a metadata-only event and do not enter the
fingerprint, composition or provenance list.

## Composition mapping

- company/opportunity metadata and Executive Summary support account context;
- Revenue Brain changes alone support recent changes;
- Next Best Action, unresolved Buying Signals and Open Questions support objectives;
- Open Questions, risks, objections and unresolved Buying Signals support questions;
- Stakeholder Intelligence, then target participant metadata, supports stakeholder focus;
- open Action Items and tentative/deferred Decisions support commitments;
- Risks & Blockers and unresolved objections/competitors support risks; and
- interaction type plus grounded context supports observable success criteria and guidance.

Names and roles are never invented. Completion, ownership, probability and forecast
are never inferred. Empty arrays are valid for changes, stakeholders, commitments
and risks.

## Trace and fingerprint

The canonical fingerprint includes source IDs, versions, scopes and strictly
validated structured content. Stored section references retain capability, source
ID, scope, source classification and validation state. Product responses derive
cautious source labels without returning raw IDs.
