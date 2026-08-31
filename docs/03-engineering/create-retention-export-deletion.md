# Create retention, export, deletion and storage reconciliation

## Current policy

WO-032 does not add an automatic age-based expiry window. Approved templates,
presentation metadata and generated binaries remain organisation records until an
authorised organisation deletion workflow removes them or a later retention policy is
approved. This is deliberate: an unimplemented expiry must not be described as active.

Raw template PPTX and generated PPTX are private objects. Metadata and structured
manifests live in PostgreSQL. Storage keys are tenant-prefixed opaque values and are
never browser-authored or logged.

## Export

Private-beta organisation export schema v22 contains:

- Create template, version and slide-review metadata;
- approved content-item metadata and approved text;
- presentation brief/plan metadata and immutable version/claim manifests; and
- base64 template and generated PPTX bytes when the referenced object is available.

The export reads objects server-side through the storage adapter. Download-grant
secrets, grant hashes and storage credentials are never exported.

WO-039B adds tenant-owned one-time download-grant metadata. Grants contain only a
SHA-256 digest, user/version binding, approval fingerprint, lifecycle timestamps and
safe identifiers. Expired grants are removed in bounded batches by the existing
tenant-scoped retention command even when customer-content retention is manual.

## Organisation deletion

Deletion is object-first. The maintenance service resolves exact tenant-scoped
template and presentation keys, deletes those objects, and stops the database erase
if storage deletion fails. Once objects are confirmed deleted, normal tenant cascade
and explicit cleanup remove download grants before Create presentations/versions,
then content items, slides, template versions and templates. Membership,
presentation-version and organisation cascades also invalidate/remove associated
grants. Canonical Account, Opportunity, Contact, Evidence or Prospect records are not
owned by Create and follow their own lifecycle.

## Reconciliation

The existing private-storage reconciliation includes Create template and generated
presentation keys in the reserved-object set. A known database key without an object
is reported as missing; an unknown object below an organisation prefix is reported as
orphaned. Reconciliation reports metadata only and does not emit content or signed
URLs. Operators investigate before deleting an orphan.

The worker deletes a newly written generated object when its database commit fails,
so a failed publication cannot leave an intentionally reachable deck. A missing or
checksum-mismatched generated object fails closed at download; it is never replaced
with another version. WO-039C still owns target-environment scheduling, restore,
offboarding and operational reconciliation evidence.

## Legal hold and per-asset deletion

No Create-specific legal-hold or individual presentation/template delete endpoint is
implemented in WO-032. Do not promise either control. A future retention work order
must define approval-history consequences, object/version tombstones, export effects
and organisation-policy precedence before adding them.

## WO-033 Business Case extension

Organisation export schema v23 includes Value Models, their versions, Business Cases,
calculation versions and presentation-to-case lineage. Organisation erasure deletes
presentations before Business Cases, then model versions/models, preserving foreign-key
order. Case/model archive is a soft lifecycle operation, not erasure. Deleting linked
Evidence does not mutate an immutable snapshot; it makes the case ineligible for new
approval or Create reuse until a new calculation is reviewed. The same customer-data
retention policy applies; no standalone legal hold or per-version delete was added.
