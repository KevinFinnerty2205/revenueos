# Prospect quotas and anti-abuse

WO-027 is sales research, not a data-harvesting API. Discovery requires one existing
researched company and returns at most 15 people. Defaults are 20 discovery requests
per user/day and 100 per organisation/day. Person research shares the existing
Prospect research-run limits (20 per user/day, 100 per organisation/day) and the
organisation concurrent-run cap.

Counters are tenant/date/scope keyed and atomically increment only below the limit.
Provider-controlled syntax, arbitrary domains, global people search, pagination over
a people corpus, bulk export and background monitoring do not exist. Fresh person
research is reused and page reads never call the provider.

A future paid adapter must add provider request/record caps based on documented unit
economics without weakening current tenant and concurrency controls. Rate-limit logs
contain IDs, provider key, state and counts only.
