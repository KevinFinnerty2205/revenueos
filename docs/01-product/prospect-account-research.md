# RevenueOS Prospect Account Research

**Status:** Current WO-026 implementation

RevenueOS Prospect now provides the minimum account-research journey for an
entitled sales workspace:

> Find → choose a company → Research → inspect sources → Add to Sales

Find accepts a company name or domain, returns a bounded candidate list and asks
the seller to resolve ambiguous identities. Selecting a candidate creates a
tenant-owned Research Target and an asynchronous, versioned research run. It does
not create a Company, Contact or Opportunity.

The Account Research Brief is persisted structured research, not a live web page.
It prioritises company profile, why the company may matter, recent developments
and cautious potential sales context. Every material fact carries a trust state
and linked source; unsupported values are presented as not established. A
controlled Refresh creates another immutable run and shows new, changed and no
longer supported observations without rewriting history. A failed refresh leaves
the most recent usable brief intact.

Add to Sales is an explicit confirmation. RevenueOS checks the normalised domain
inside the active organisation. It links the Research Target to the deterministic
existing match or creates one canonical Company when confirmed. It never creates
an Opportunity or Contact and never mutates Methodology, Revenue Brain or Ask
RevenueOS state.

## Availability and limits

Prospect is a separately entitled add-on. The global feature flag and the
organisation entitlement are both enforced server-side. An administrator may
change the organisation entitlement; an ordinary member may not. The private-beta
defaults allow 20 research runs per user per UTC day, 100 per organisation per
UTC day and five concurrent organisation runs. Initial results are reused for
seven days unless the seller deliberately refreshes.

The deterministic provider supplies synthetic demo data and makes no network
requests. Production configured with that mock fails closed. Enabling real-world
research therefore remains a separately reviewed deployment/provider decision.

## Scope boundary

WO-026 is company/account research only. “Lead” means an early Research Target
that may later be added as a Company; it is not a new CRM Lead object. Deep named
decision-maker research belongs to WO-027. ICP, territory and bulk lead generation
belong to WO-028. There is no LinkedIn scraping, contact enrichment, predictive
fit or intent score, trigger monitoring, outreach, campaign, sequence or autonomous
prospecting capability.

Research can be incomplete, source availability can change and provider-supplied
data can disagree with primary sources. The UI preserves those limits rather than
guessing.
