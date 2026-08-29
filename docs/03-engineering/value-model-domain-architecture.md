# Value Model domain architecture

WO-033 adds four tenant-owned tables in migration `0042_roi_business_case`:

- `create_value_models`: organisation-owned identity/state;
- `create_value_model_versions`: immutable definition JSON, canonical AST, engine version and fingerprint;
- `create_business_cases`: Account-required/Opportunity-optional aggregate and selected model version;
- `create_business_case_versions`: immutable calculation/input/scenario/sensitivity/lineage snapshots.

All tables use UUIDs, explicit organisation predicates, composite tenant foreign keys, indexes and forced PostgreSQL RLS. PostgreSQL triggers reject updates to approved/archived model versions and approved case versions. The API uses strict Pydantic models; JSON is a validated immutable manifest, not executable metadata.

Create entitlement is required for every route. Admin authority gates model mutation; members can use approved models. Server-side calculation is synchronous, local, bounded and needs no worker/provider/network.

Quotas are structural: 50 active models, 50 versions/model, 20 active cases/Account, 100 versions/case, 30 inputs, 30 outputs, three scenarios and five sensitivity rows.
