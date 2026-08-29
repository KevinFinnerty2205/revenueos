# Business Case provenance and lineage

The immutable case version stores input snapshots and a lineage document containing model/version/fingerprint, engine version, output formula/AST/dependency metadata and scenario membership. Output API responses expose the readable formula and input/output dependency keys; the UI joins these to actual input values and source labels.

Linked Evidence is accepted only as support for a seller-entered exact number and remains `salesperson_reported`. Current Evidence prose is not parsed into a number. Canonical Account employee count is the only current approved-company exact-number path. Public bands and vague prose are never midpointed or inferred.

On case load, approval, Create selection and export, source availability/freshness and per-input age/review rules are checked. A source change never replaces the saved value or recalculates silently.
