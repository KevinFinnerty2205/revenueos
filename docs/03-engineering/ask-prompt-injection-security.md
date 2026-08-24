# Ask RevenueOS prompt-injection security

## Threat model

Question text and customer/seller Evidence are untrusted content. They may attempt to
change instructions, reveal another tenant, fabricate a citation, alter the response
schema, invoke a tool or trigger an Action.

## WO-025B controls

- The classifier recognises common instruction-exfiltration/action/fabrication
  patterns and returns a bounded `unknown` response.
- Classification maps to a fixed enum; it cannot emit SQL, a tool name or a retrieval
  plan.
- Evidence text is treated only as bounded source content. No prompt interprets it,
  and no external model/provider receives it in Ask v1.
- Repositories—not question content—choose tenant scope, source families and limits.
- Strict request/response models reject extra fields and unrecognised statuses/types.
- Citation IDs are created from retrieved records and revalidated against that set.
- Ask exposes no execution tool and cannot call the Action executor, connector,
  email, CRM or calendar boundary.
- Logs and normal telemetry contain classifications/counts/IDs, never question,
  answer, excerpt, transcript, document or email content.

Regression coverage includes instruction override/data extraction, public-web
requests, extra/query-like request fields, fake citations, cross-tenant IDs and source
content with distinct provenance/conflict metadata. Because the composer is
deterministic, malicious transcript/email/document text can at most remain visibly
labelled evidence; it cannot alter schema or control flow.

## Future provider gate

Provider-backed composition is not implemented. Before enabling it, require a
versioned prompt that treats all retrieved content as quoted data, a provider/tool
allowlist with no tools enabled, strict structured output, citation-set validation,
injection evaluation across every source family, tenant-safe redaction, bounded one-
call context, metadata-only failure telemetry and an updated privacy/security review.
