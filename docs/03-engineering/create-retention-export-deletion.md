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

The export reads objects server-side through the storage adapter. Signed download
tokens and storage credentials are never exported.

## Organisation deletion

Deletion is object-first. The maintenance service resolves exact tenant-scoped
template and presentation keys, deletes those objects, and stops the database erase
if storage deletion fails. Once objects are confirmed deleted, normal tenant cascade
and explicit cleanup remove Create presentations/versions, content items, slides,
template versions and templates. Canonical Account, Opportunity, Contact, Evidence or
Prospect records are not owned by Create and follow their own lifecycle.

## Reconciliation

The existing private-storage reconciliation includes Create template and generated
presentation keys in the reserved-object set. A known database key without an object
is reported as missing; an unknown object below an organisation prefix is reported as
orphaned. Reconciliation reports metadata only and does not emit content or signed
URLs. Operators investigate before deleting an orphan.

## Legal hold and per-asset deletion

No Create-specific legal-hold or individual presentation/template delete endpoint is
implemented in WO-032. Do not promise either control. A future retention work order
must define approval-history consequences, object/version tombstones, export effects
and organisation-policy precedence before adding them.
