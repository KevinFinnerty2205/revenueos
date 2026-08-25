# Prospect provider and fetch strategy

**Status:** Deterministic provider implemented; production provider deferred

WO-026 deliberately implements one `ProspectResearchProvider` boundary with a
deterministic synthetic provider. Search, candidate resolution and structured
research use strict bounded models. Standard tests, demos and local development
perform no network request and require no credentials or paid account.

No real search, company-data, page-fetch or synthesis provider was selected. The
available work-order evidence did not establish a suitable no-cost production path
whose commercial terms, attribution, retention, regional/privacy posture and rate
limits were approved for RevenueOS. No paid plan, credits or credentials were
created. Because no external API was selected, there was no provider-specific
official documentation to rely on in this implementation.

Production configured with `PROSPECT_RESEARCH_PROVIDER_NAME=mock` returns
unavailable and the worker rejects execution. A future production adapter must be
explicitly configured and separately approved; adding a name to configuration
without a real adapter is not a working integration.

## No public-page fetcher

RevenueOS does not fetch arbitrary pages in WO-026. This is the smallest safe
choice: it avoids turning the product into a crawler, avoids executing untrusted
HTML/JavaScript and eliminates cookies, authentication, downloads, MIME handling,
page mirroring and arbitrary redirects from the runtime path. Unsupported MIME and
oversized-response handling are therefore not dormant claims; there is no response
body fetch surface to test.

The provider contract returns bounded structured source metadata and observations.
URLs are revalidated before persistence. The standalone public-URL policy validates
HTTPS scheme, credentials, port, ASCII domain syntax, IP literals, blocked local
suffixes, public DNS results and redirect chains so it can be reused only if a
future approved adapter needs it.

Any future fetcher requires its own interface and review. At minimum it must use
server-side DNS resolution, revalidate every resolved address and redirect, cap
redirects/time/body size, allowlist static text MIME types, execute no JavaScript,
send no cookies or credentials, reject downloads and discard extracted content
after validated synthesis. Provider-supplied snippets are preferred when their
terms make that safer than direct fetching.

The existing OpenAI provider is not used. There is no prompt, model call or public
content synthesis in WO-026.
