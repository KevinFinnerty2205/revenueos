# Visual Evidence engineering guide

## Current boundary

WO-014 adds tenant-isolated visual evidence to the existing Interaction Domain. The web app can use the browser’s file chooser, rear-camera hint or drag-and-drop surface for JPEG and PNG images. It does not add a native app, live recording, background capture, video, general document ingestion or contact auto-creation.

The API remains the source of truth. Image bytes live in private object storage; PostgreSQL-compatible tables hold metadata, review state and provenance. Local and CI use the clearly labelled deterministic mock provider. Production configuration fails closed unless private S3-compatible storage and a deployment-specific signing secret are present.

## Workflow

1. The user selects a local image and sees a browser-only preview.
2. The user assigns a visual type, source ownership and optional context, then confirms authority to upload and process it.
3. `POST /api/v1/interactions/{interaction_id}/visual-evidence/uploads` creates a tenant-bound upload record and short-lived grant.
4. The browser uploads directly to the private backend. Local mode uses the authenticated API content route; S3-compatible mode uses a signed object URL without browser-held storage credentials.
5. Completion validates the declared size and checksum, sniffs the real format, checks dimensions and PNG CRCs, rejects trailing/polyglot content, removes JPEG EXIF/XMP/comment segments and unsafe PNG ancillary metadata, then replaces the raw upload with the sanitised image.
6. Processing uses a strict provider-neutral result schema. A completed result creates unreviewed `VisualCandidateEvidence` only.
7. The user must accept, edit or reject every candidate. Accepted candidates create verified AI-inferred Evidence and immutable Interaction Intelligence/Revenue Brain snapshots where policy permits.

No candidate updates downstream intelligence before review. Business cards remain contact candidates only. Seller-created presentation material remains context only. Site photos remain observed rather than customer-confirmed.

## Persistence

Migration `0024_visual_evidence` adds `visual_assets` and `visual_candidate_evidence`, widens Evidence support to `observed`, and allows Interaction Intelligence snapshots to reference any Capture Session. Every relationship is tenant-composite. PostgreSQL RLS is enabled and forced. Reviewed candidate provenance is immutable.

`VisualAsset.storage_key` is a random tenant/interaction-scoped internal key, never a supplied filename. `display_filename` is sanitised for presentation only. Object bytes, OCR text, signed URLs and provider payloads never enter audit events.

## Read models

Reviewed eligible visual evidence can update:

- the latest schema-version-2 Interaction Intelligence snapshot;
- the Opportunity Workspace visual-intelligence section; and
- the Revenue Brain reviewed-visual timeline.

Every current read verifies that all source Evidence remains available and verified. Deleting a visual therefore suppresses stale derived current views without rewriting immutable historical snapshots.

## Failure behaviour

Upload validation failures exclude the source and attempt object deletion. Provider timeout, refusal, malformed output and transient failure return a safe retryable error bounded by the configured attempt limit. Object deletion is two-phase: a failed object delete remains `delete_failed` and is never reported as complete. Retention and organisation deletion stop database deletion when object deletion fails.

## Validation

Backend coverage includes tenant isolation, idempotency, MIME spoofing, polyglot rejection, EXIF/metadata stripping, review gates, source rules, stale-source suppression, migration guards, export and storage reconciliation. Web coverage includes preview-before-upload, explicit authority confirmation, progress, review/edit/reject controls, conservative labels and mobile layout. The flagship Playwright path covers presentation upload through accepted reviewed evidence.

## Related documents

- [Browser camera and upload](browser-camera-upload.md)
- [Visual provenance rules](visual-provenance-rules.md)
- [Visual provider guide](visual-provider-guide.md)
- [Visual storage lifecycle](visual-storage-lifecycle.md)
- [Visual evidence security review](visual-evidence-security-review.md)
