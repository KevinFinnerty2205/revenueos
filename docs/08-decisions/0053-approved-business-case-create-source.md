# ADR 0053: Approved Business Case as a Create source

## Context

Presentation claims need a stable source that preserves the full calculation chain without treating a seller model as customer truth.

## Decision

Add `approved_business_case` to the customer-safe Create source classes. Pin the exact approved case version and scenario selection on the presentation. Generate cautious deterministic statements, material assumptions and disclaimer; manifest claims source the case version. Revalidate before approval/export.

## Alternatives

Copying values as approved company content, using draft calculations or ingesting ROI into Revenue Brain/Methodology were rejected because each loses provenance or changes truth semantics.

## Consequences

Create can explain every displayed number. A superseded/stale case blocks export, and templates without a suitable editable approved layout fall back to existing approved content rather than inventing a slide design.
