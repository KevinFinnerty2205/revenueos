# Prospect quotas and anti-abuse

WO-028 Target Market discovery returns at most 50 companies and defaults to five
runs per user/day, 25 per organisation/day and ten active Target Markets per
organisation. A fresh result is reused unless a user explicitly refreshes. Discovery
has no global pagination, CSV export or background monitor.

WO-027 is sales research, not a data-harvesting API. Discovery requires one existing
researched company and returns at most 15 people. Defaults are 10 discovery requests
per user/day and 50 per organisation/day. Person research shares the existing
Prospect research-run limits (20 per user/day, 100 per organisation/day) and the
organisation concurrent-run cap.

Counters are tenant/date/scope keyed and atomically increment only below the limit.
Provider-controlled syntax, arbitrary domains, global people search, pagination over
a people corpus, bulk export and background monitoring do not exist. Fresh person
research is reused and page reads never call the provider.

A future paid company or person adapter must add provider request/record caps based on documented unit
economics without weakening current tenant and concurrency controls. Rate-limit logs
contain IDs, provider key, state and counts only.

## Engage Campaign controls

WO-030 adds independent server-side Campaign caps: 50 explicit Contacts, one to four
steps, five active Campaigns per owner, ten per organisation, 100 Campaign drafts per
organisation/day and five-minute recipient launch spacing. The existing Outreach
per-user/per-organisation daily send limits and global Contact cooldown apply across
one-to-one and Campaign sends. Quota/cooldown defers rather than releases a backlog.
See [Campaign quotas and cost controls](campaign-quotas-cost-controls.md).
