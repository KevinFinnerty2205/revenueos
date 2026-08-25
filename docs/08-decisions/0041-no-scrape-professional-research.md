# ADR 0041: No-scrape, mock-only professional research boundary

## Context

Professional network content can be commercially useful but scraping creates contractual, privacy, security and operational risk. No evaluated no-cost provider met the WO-027 licensing and lifecycle gate.

## Decision

Keep a provider-neutral typed interface and ship only deterministic synthetic mock data. Do not add LinkedIn/private-social scraping, browser automation, profile-photo processing or a search-engine scraping workaround. Production configuration fails closed.

Future provider access must be through a permitted API/source, with approved licensing, field trust, expiry/export controls, cost quotas and no real CI calls.

## Alternatives

- **Scrape public pages:** rejected because public visibility does not grant automated collection or redistribution rights.
- **Activate a trial provider:** rejected because a trial does not resolve production storage, deletion, export and unit economics.
- **Remove provider interfaces:** rejected because a stable boundary and deterministic contract tests reduce later integration risk.

## Consequences

Production contact coverage remains unavailable until approval. The product remains useful for architecture and UX verification without misrepresenting an integration or incurring cost.
