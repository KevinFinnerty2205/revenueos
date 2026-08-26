# Campaign personalisation reuse

WO-030 does not introduce a second composer or an AI call. It invokes the WO-029
deterministic Outreach service, which selects only current, supported, non-sensitive
Prospect observations and approved seller context and stores exact
`OutreachVersion`/`OutreachPersonalizationSource` records.

Campaign context adds step instance, objective, order, total steps, prior confirmed
send timestamp and enrolment source-memory exclusions. Step 1 uses source-backed
value. A later follow-up may say “my note from …” only when a successful prior send
timestamp exists. A different-angle step excludes source IDs already used by the
enrolment. A final step uses a respectful close and cannot appear before the end.
`Re:` prefixes, invented prior conversations and unsupported familiarity remain
prohibited.

Before auto-send, every stored source is re-resolved against its current research
run, trust, allowed professional category, sensitivity exclusion and freshness.
Missing, stale, unsupported or sensitive source state halts the recipient. Successful
send is the only event that appends source IDs to enrolment memory.

Outbound copy and its sources remain seller-prepared context. They do not create
customer Evidence, change Methodology/Stakeholder/Revenue Brain or count as a reply.
