# Business Case retention, export and deletion

Business Cases follow Create/customer-data retention. Organisation deletion removes presentation versions/presentations first, then case versions/cases, then model versions/models so restrictive lineage FKs are respected. Account deletion remains restricted while dependent customer artefacts exist, matching the existing Create presentation boundary.

Organisation export version 23 includes model metadata/definitions/canonical AST/formula engine/fingerprint/approval, cases, exact inputs/provenance, outputs, scenarios, sensitivity, lineage and approvals. Idempotency keys are excluded. Presentation exports include the selected case/version/scenario metadata. No provider payload or binary presentation is duplicated in the JSON export.

Deleting/superseding Evidence does not rewrite an immutable approved case. Current review state becomes needs review, and new Create reuse/export is denied until recalculation and approval. Historical source labels and values remain in the authorised export as the audit snapshot; deleted source content is not restored.
