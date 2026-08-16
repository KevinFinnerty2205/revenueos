# Future webhook boundary

WO-022 implements no webhook endpoint. This page records the minimum boundary
for later provider work so inbound events cannot bypass tenancy or execution
reconciliation.

A future webhook adapter must:

- use a provider-specific route and signature/version validator;
- identify an installed connection from a non-secret provider installation ID,
  then derive organisation context server-side;
- reject unbound, revoked, stale-timestamp and replayed deliveries;
- store only an idempotency hash and minimum metadata before bounded processing;
- keep raw customer/provider payloads out of logs and general audit tables;
- apply provider ordering/version semantics and never downgrade newer state;
- route events through explicit connector services rather than browser database access;
- participate in retention, erasure, export and incident runbooks; and
- treat delivery as a reconciliation signal, not proof that a requested action
  did or did not occur.

Generic user-configured webhook URLs, unauthenticated callbacks and webhook-driven
autonomous execution are out of scope. Provider selection and implementation
require a separate decision record and work order.
