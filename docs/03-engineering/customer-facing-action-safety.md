# Customer-facing Action safety

Customer-facing proposals include follow-up emails, requested material, stakeholder
follow-up and proposed interactions. They use the `customer_facing` audience and
`external_customer_facing` risk class and receive prominent review warnings.

Recipient fields default unconfirmed. A confirmed recipient requires a tenant-owned
Contact whose stored email exactly matches the payload. Draft content is bounded and
versioned. Source currency is checked again at approval. Approval invokes no
adapter. WO-022 rechecks currency, recipient/attendees, connection, risk class and
the complete preview fingerprint before a separate simulation confirmation.

Customer-facing proposals cannot use manual completion because RevenueOS has no
independent delivery confirmation. A successful WO-022 mock result is explicitly
`simulated_success`, not delivery. Future live execution still requires a separate
work order covering credentials, scopes, provider receipts, reconciliation,
deletion and incident response.
