# Journey reliability architecture

## Cross-module navigation and state contract

RevenueOS remains a Next.js/FastAPI/PostgreSQL modular monolith. Routes carry
canonical UUIDs and optional explicit return paths. Prospect records remain separate
from canonical Account/Contact records until deliberate promotion. Promotion is
Company-first, duplicate-safe and provenance preserving.

Opportunity mutations dispatch an in-browser `revenueos:opportunity-changed` event
only after the API confirms stage, close or reopen. Mounted Opportunity, CRM and
manager consumers refetch from their existing tenant-scoped endpoints. Navigation to
Pipeline, Insights, Target or Forecast also performs fresh `no-store` reads. This is
targeted invalidation, not a client cache or new state platform.

## Frontend data revalidation guidance

1. Treat the API response as authoritative; do not infer a successful transition.
2. Update the component that owns the mutation from the returned representation.
3. Notify other mounted consumers by the narrow domain event when required.
4. Re-read on a later route load; do not carry stale record snapshots in query
   strings or browser storage.
5. Abort obsolete reads on unmount. Ignore only the resulting `AbortError`.

The shared API client gives bodyless reads no JSON `Content-Type`, assigns one safe
request ID and makes up to three attempts only for network-failed GETs with 50 ms and
100 ms delays. It never retries a write or HTTP error. A final network failure is an
`ApiClientError` with a safe message and request ID.

## Reliability error-handling guide

- 404: say the record is unavailable and link to the collection or previous canonical
  context.
- 409/stale revision: tell the user the record changed, then require refresh/review.
- 401/403: show authentication/permission language without revealing another tenant.
- feature disabled/unentitled: preserve the shell and a permitted destination; never
  turn availability uncertainty into a false entitlement claim.
- network/5xx: keep entered form data where safe, show request ID and local Try again.

Errors never include authorisation headers, transcript text, prompts, provider bodies
or stack traces. Duplicate submission remains prevented by existing in-flight
disabling, idempotency keys and server constraints.

## Browser test architecture

`apps/web/e2e/journey-reliability.spec.ts` is the single synthetic flagship journey.
Its stateful fixture starts with one unseen Northstar Account candidate and retains
the same Account, Contact, Interaction, Evidence, Opportunity, Business Case,
presentation, Target and Forecast identities through close Won. Test steps map
one-for-one to the 40-step product contract and assert the final Pipeline/Actual/
Target/Analytics/Forecast/history convergence. The suite also performs direct-route,
recovery and 390 px containment checks. Existing module suites remain the detailed
contract tests; the flagship proves their hand-offs are one coherent loop.

Screenshots are captured from the running deterministic application and indexed in
the [WO-039A record](../07-sprints/wo-039a-end-to-end-journey-reliability.md).

## Performance envelope

The reviewed 1,000-Opportunity response was 209.3 KiB and produced a long browser
DOM. The API contract remains unchanged, but the list now renders 100 records per
batch with an explicit next-batch control. This avoids speculative server pagination
while bounding initial React work. Server pagination/query redesign belongs to
WO-039C only if production evidence requires it.
