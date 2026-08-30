# Forecast security and privacy review

All forecast tables include organisation scope, composite tenant foreign keys, forced
RLS and explicit organisation predicates. Runtime role assumptions remain those of
the existing tenant transaction context. Tests cover cross-tenant non-disclosure,
member/admin scope, owner-only writes and RLS/immutability.

Threat controls:

- request-supplied organisation IDs do not exist;
- members are forced to their own aggregate; admins may read organisation/owner scope;
- only current Opportunity owner appends seller judgment;
- expected revision prevents lost writes; past periods are locked;
- server snapshots canonical facts, ignoring client-supplied commercial context;
- audit/log metadata excludes amounts, categories, customer content and baseline
  payloads; and
- safe errors expose code/message/request ID only.

Forecast category is organisation sales-record state, not customer-direct Evidence.
No prompt/provider call, transcript, Evidence content or methodology projection is
read or mutated by the numeric model.
