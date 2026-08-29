# Business Case security and privacy review

Business Case values may reveal costs, salaries, volumes and budgets, so they are customer business content. Values, formulas with substituted data, case titles, Account names and source text are excluded from telemetry and metadata audit logs. Logs record only organisation/actor IDs, model/case IDs, version and bounded counts/status.

Controls include forced RLS, composite tenant FKs, verified tenant context, admin-only model mutation, strict source-origin authority, server-only outputs, Decimal bounds, canonical-AST integrity, parser allow-lists, immutable approvals and revalidation before Create export.

Threats explicitly covered: formula/code injection, client output spoofing, cross-tenant attachment, source-ID spoofing, price-assumption override, stale/deleted evidence, scenario range bypass, giant decimals/AST denial of service, mixed currency and customer-facing guaranteed-language generation.

No financial content is sent to OpenAI or another provider. Standard tests require no external credentials or provider calls.
