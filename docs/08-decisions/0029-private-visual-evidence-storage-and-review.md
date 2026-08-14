# ADR 0029: Private visual evidence storage and mandatory review

## Context

WO-014 requires photos and images to participate in Interaction Intelligence without turning RevenueOS into a general media repository or treating AI interpretation as fact. Database-only blobs would increase backup, API and deletion risk; public URLs would break the privacy model.

## Decision

Store sanitised bytes in a private storage adapter and keep tenant-scoped metadata/provenance in the modular monolith database. Local/test use deterministic private filesystem storage. Production requires a private S3-compatible backend. Access uses short-lived tenant/user/purpose-bound grants.

Visual analysis is provider-neutral and strict. All output remains unreviewed candidate evidence until a user accepts, edits or rejects every item. Source ownership remains distinct from AI origin. Seller presentation material, business cards and site photos have explicit conservative downstream policies.

## Alternatives considered

- Database blobs: rejected because they couple large media to migrations, backups and API transactions.
- Public or long-lived object URLs: rejected because revocation and tenant isolation are weaker.
- Automatic intelligence/contact updates: rejected because source meaning and extraction accuracy require review.
- A separate media service or queue: rejected because current scale does not justify another deployable or datastore.

## Consequences

Operations must manage private object credentials, deletion ordering and reconciliation. The API supports only JPEG/PNG and foreground processing. Future document/video/native capture work must extend this boundary through a separately approved work order.
