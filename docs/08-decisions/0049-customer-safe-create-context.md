# ADR 0049: Typed customer-safe Create context and exact provenance

## Context

RevenueOS contains useful customer Evidence and public research alongside internal
forecasting, coaching, risks, notes, suppression and contactability state. Passing raw
records or a broad Revenue Brain dump into customer-facing generation could disclose
internal data or relabel public inference as customer truth.

## Decision

Build `customer_safe_presentation_context_v1` from an explicit allow-list of typed
fields. Keep approved company content, customer-direct Evidence, seller-reported
Evidence and public Prospect observations as distinct origins. Deny raw transcripts,
notes, recordings, financials, probability/forecast, methodology scores, internal
risks/coaching, contactability and suppression. Persist an exact per-claim provenance
manifest and revalidate its sources before human approval.

## Alternatives

- **Pass ORM/domain rows to a composer:** rejected because schema growth could silently
  widen disclosure.
- **Treat all Revenue Brain content as customer-safe:** rejected because its internal
  decision-support purpose differs.
- **Flatten public research into Evidence:** rejected because it invents authority.

## Consequences

Some decks use approved generic copy or show missing support instead of richer prose.
That constraint is intentional: claims remain inspectable, removable and defensible,
and a later AI provider cannot broaden the data boundary without another decision.

## WO-033 amendment

`approved_business_case` is now an additional typed source class, governed by
[ADR 0053](0053-approved-business-case-create-source.md). It carries only an exact
approved case/version/scenario selection, customer-facing deterministic outputs,
material assumptions and the approved disclaimer. The claim manifest records the
case-version identifier and revalidation blocks generation, presentation approval and
download when the selected version is no longer current/approved or a linked source
needs review. This does not broaden customer-safe context to raw formulas, hidden
defaults, arbitrary financials, Revenue Brain or Methodology state.
