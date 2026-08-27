# Event attendee import, matching and prioritisation

## Safe CSV decision

V1 accepts a deliberately selected `.csv` encoded as strict base64 JSON. The server
requires UTF-8 (optional BOM), comma-separated well-formed rows, unique bounded
headers, no null bytes, at most 5 MB/50 columns/500 rows and at most 1,000 characters
per cell. It trusts neither filename path nor MIME type. XLSX/ZIP processing is
deferred to avoid archive and formula complexity.

Approved mappings are first/last name, company, title, business email,
country/location, professional profile URL, company domain and registration category.
Sensitive/private headers cannot be mapped. Formula-looking values remain inert text;
RevenueOS never evaluates them. Invalid/free-mail addresses and unsafe/private URLs
are excluded. UI/API error payloads and logs contain issue codes/counts/row numbers,
not attendee values.

Preview persists only approved parsed fields in the tenant-scoped import row, expires
after one hour, and is cleared on confirmation/expiry. Raw bytes are never stored.
The SHA-256 file fingerprint supports same-file idempotency but is metadata-only and
excluded from privacy export.

Confirmation requires the exact version-1 authority attestation, authenticated member
and unexpired same-tenant preview. Multiple batches form a deduplicated union. Exact
person-specific business email and canonical HTTPS profile URL are strong identities.
Shared role inboxes such as `info@` are not deduplication/match keys. A row otherwise
needs name plus company. This prevents two people sharing a generic inbox from being
silently merged.

## Matching

The order is exact business email → exact professional profile/Prospect Person → exact
company domain → unmatched. Exact name similarity may set `possible_match` only and
never links a Contact. All candidates remain in the same organisation. Imported
fields do not overwrite canonical Contact data.

## Explainable priority

The engine returns a category and plain-language reasons, never a number:

1. active Opportunity relationship;
2. existing Contact/Company relationship and relevant senior/function title;
3. current Target Market priority and relevant role;
4. Event goal context; or
5. insufficient company/role context.

Attendance is only list context. It is not purchase intent, Evidence, a Buying Signal
or Methodology input. Users may plan anyone regardless of the computed category; the
plan does not mutate the category.
