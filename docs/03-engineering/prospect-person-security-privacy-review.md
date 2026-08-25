# Prospect Person security and privacy review

## Outcome

Approved for deterministic mock-only private-beta operation. No live provider, scraping or paid service is enabled.

## Controls

- Tenant context comes from verified auth; repositories add explicit organisation predicates and all new tables force RLS.
- Discovery begins from a researched company target. Result caps, per-user/per-organisation daily quotas and existing concurrent-run caps reduce harvesting risk.
- Provider identities and research content pass strict schema, source, URL, trust, freshness and sensitive-content validation.
- Only public professional/business context is allowed. Personal contact, sensitive traits, personality inference, photos and private-social material are rejected.
- External links use safe HTTPS validation, no-referrer UI links and no mirrored page content.
- Logs contain tenant, target/person/run IDs, provider key, states and counts only—never contact values, profile text, prompts or payloads.
- Promotion is confirmed, duplicate-safe and limited to Contact creation/linking. It cannot mutate Opportunity, Evidence, Methodology, Stakeholder or Revenue Brain.
- Export includes contact values only where `export_allowed`; provider person IDs and raw payloads are excluded. Expiry and deletion preserve canonical Contact semantics.

## Residual risk

Public information can be stale or misattributed. The UI exposes sources, date/trust and “role may have changed”; sellers must validate hypotheses. Any live adapter requires a fresh provider, licensing and data-protection review before configuration.
