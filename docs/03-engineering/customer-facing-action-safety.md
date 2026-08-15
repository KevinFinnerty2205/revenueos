# Customer-facing Action safety

Customer-facing proposals include follow-up emails, requested material, stakeholder
follow-up and proposed interactions. They use the `customer_facing` audience and
`external_customer_facing` risk class and receive prominent review warnings.

Recipient fields default unconfirmed. A confirmed recipient requires a tenant-owned
Contact whose stored email exactly matches the payload. Draft content is bounded and
versioned. Source currency is checked again at approval. Neither approval nor any UI
control invokes a mail, calendar or CRM adapter.

Customer-facing proposals cannot use manual completion because RevenueOS has no
independent delivery confirmation. Future execution would require a separate work
order covering credentials, scopes, preview/confirmation, idempotency, delivery
receipts, retries, revocation, audit and incident response.
