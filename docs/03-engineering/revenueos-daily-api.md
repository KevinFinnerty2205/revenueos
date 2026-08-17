# RevenueOS Daily read-model API

## Endpoint

```http
GET /api/v1/daily?timezone=Australia%2FSydney
```

The endpoint requires the normal authenticated user and active organisation context.
`timezone` is an optional IANA identifier; omission means the explicit `UTC`
fallback. Invalid identifiers return safe `422 invalid_timezone`. Disabled or missing
membership returns `403 forbidden`.

## Contract

The strict camelCase response contains:

- `generatedAt`, `localDate`, `timezone` and `userDisplayName`;
- one optional `topPriority` and `nextInteraction`;
- bounded `todayInteractions` plus its bounded-source count;
- current Action counts and up to five Action items;
- deal-attention count and up to three Opportunities with controlled reason codes;
- descriptive open/closing-this-month pipeline groups by currency;
- up to three existing Next Best Action recommendations;
- per-source `availability`; and
- `hasOpportunities` and `caughtUp` presentation signals.

Money serialises as decimal strings. Links are application-relative and route to the
existing Interaction, Companion, Opportunity, Action review or list workflows. The
response deliberately has no complete entity objects, evidence references, raw
customer content, provider/model metadata, forecast or target value.

## Failure contract

Optional source database failures return an otherwise valid response with that
availability flag false and an empty safe section. The frontend renders
`<Section> temporarily unavailable.` Auth/tenant failures, invalid timezone and
contract failure are not converted into partial success. A total request failure
renders Retry plus direct Interactions and Opportunities links.

No response is persisted or shared between users. The browser does not cache a local
Daily snapshot and refetches at focus/midnight so the local day cannot remain stale.
