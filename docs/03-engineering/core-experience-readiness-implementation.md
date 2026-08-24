# Core experience readiness implementation guide

- **Work order:** WO-025A
- **Implemented:** 24 August 2026
- **Migration:** none; `0033_sales_methodology` remains the single Alembic head
- **Boundary:** experience hardening over existing Core contracts

## What changed

The protected shell now presents the implemented product as one workflow rather than
eleven equally weighted entities. Desktop exposes Home, Sell (Accounts, People and
Interactions), Pipeline, Search and Settings. Mobile exposes exactly Today,
Interactions, Actions and Search in a fixed bottom navigation. Historical URLs remain
compatible and contextual links still reach Meetings, Tasks, onboarding and feedback.

`/assistant` is now a bounded workspace search for Companies, Opportunities and
Interactions. It does not use a provider, inspect transcript bodies, answer natural-
language questions or mutate data. Ask RevenueOS remains WO-025B.

Opportunity now leads with deal identity, one next-action focus, methodology,
evidence and reviewable Actions. Meeting association, account history, complete
meeting intelligence and meeting history use progressive disclosure. Interaction
uses Prepare → Capture → Review → Follow through; planned face-to-face capture stays
inside Companion and completed source options are disclosed only when needed.

Action copy distinguishes prepared, approved, simulated and manually completed work.
Approval never implies an external send/update. Settings loads `/api/v1/me` and hides
organisation administration from members while preserving API enforcement.

## Contract and security impact

There is no route, schema, RLS, tenant, provider, prompt, worker or application
persistence-contract change.
All searches reuse tenant-scoped API repositories. Feature gates, consent choices,
recording warnings, review controls, Action confirmation, export/deletion controls and
server-side role checks remain authoritative. Client-side role composition improves
clarity but does not replace API authorisation.

The synthetic demo seed now flushes an Action proposal and immutable version before
its foreign-keyed audit event, and its `create_task` payload validates against the
current strict Action contract. This fixes fresh-database demonstrations without
changing production data.

## Performance findings

The shell and navigation add no data request. Search runs only after an explicit
submit, caps each result group at six and requests the three existing tenant-scoped
lists concurrently. Settings adds one `/me` identity request so administrator-only
sections are not mounted for members. Opportunity progressive disclosure reuses its
existing workspace response and does not add a new polling or background-refresh
path. The web and API production builds remain successful; no performance benchmark
or production traffic claim is inferred from the local gate.

## Operational boundary

This implementation improves the product path and deterministic demo. It does not by
itself authorise production customer data or close target-environment identity,
retention, backup/restore, incident-response, browser/jurisdiction or design-partner
approval gates. Those remain governed by the private-beta launch material and an
environment-specific launch review.

## Known limitations

- Ask RevenueOS is now implemented by WO-025B as a second Search mode and contextual
  Opportunity/Account utility; normal Search remains deterministic.
- Production CRM matching and approved writes remain WO-025C.
- Forecasting, Manager Intelligence and Prospect remain later work.
- There is no native mobile app or background recording promise.
- Current connector outcomes are simulation-only.
- Private-beta restrictions and feature flags remain in force.
