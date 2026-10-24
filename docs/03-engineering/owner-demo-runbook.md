# Private owner demo runbook

## Purpose and boundary

This runbook presents the implemented Oryntela platform as one coherent owner
walkthrough. It is a private, loopback-only development environment using
synthetic records and deterministic/test adapters. It is not a production
deployment, customer onboarding flow or authority to activate a live provider.

The owner seed refuses to run unless all of these conditions hold:

- environment is `development` or `test`;
- mock authentication is enabled;
- object storage is local;
- AI and Prospect research use the deterministic mock providers;
- OpenAI and the external Prospect provider are disabled;
- Microsoft 365, Google Workspace, HubSpot and Salesforce are disabled;
- real-customer data release is disabled; and
- billing uses the deterministic test adapter in test mode; and
- billing and Credits feature flags remain disabled.

The configured database URL and the session factory's actual engine must also
identify the same local target: a local SQLite file or PostgreSQL on
`localhost`, `127.0.0.1` or `::1`. Remote hosts, Unix-socket overrides and URL
encoding tricks fail before any database access. The fixed local owner must
already have an active administrator membership.

It makes zero external provider calls. Never add production secrets or real
customer data to this environment.

## Start and seed

Complete the repository setup in the [development guide](development-guide.md)
and run migrations:

```text
pnpm api:migrate
pnpm api:migration:check
```

On a clean database, start the API first. Its development lifespan provisions
the fixed mock organisation, user and active administrator membership that the
owner command must verify:

```text
pnpm dev:api
```

Wait until [http://localhost:8000/ready](http://localhost:8000/ready) returns
ready. In a second terminal, seed the owner dataset:

```text
pnpm demo:owner
```

Only after the seed reports success, start the worker and web app in separate
terminals:

```text
pnpm dev:worker
```

```text
pnpm dev:web
```

The command is tenant-scoped and idempotent while the fixture remains in its
exact seeded state. Success returns `"status": "ready"`,
`"dataset_version": 20` and `"provider_calls": 0`. It creates only clearly
labelled synthetic records for the fixed local development organisation and
user. Version 20 includes a real Northstar-linked Task; it is not merely an
Action proposal. It also generates deterministic BANT then MEDDPICC projections
for the Northstar Opportunity. A clean owner environment finishes with MEDDPICC
selected; if a methodology setting already existed, the seed restores that
setting unchanged after building the two synthetic projections.

The seed owns its PowerPoint template by a tenant-scoped deterministic UUID and
an exact checksum. It refuses a name, identity or checksum collision instead of
adopting an existing template. It also processes only the exact template or
presentation work item that it just queued; unrelated tenant or organisation
work remains untouched.

If an older pre-v20 dataset already has a published campaign snapshot or Find
result tied to the legacy Northstar Account, the seed fails closed. Use the
reset/reseed sequence below; it never rewrites a published campaign audience.

After an empty-or-exact base preflight, the owner command records a durable
tenant-scoped pre-seed reservation before the multi-commit base seed. The
reservation records whether the organisation methodology setting genuinely
pre-existed and, when it did, its exact original state until the base finishes.
When it did not, the reservation and exact synthetic MEDDPICC setting are
committed atomically. An interrupted BANT-to-MEDDPICC seed can therefore restore
a genuine pre-existing setting or remove only its own recoverable intermediate,
while a pre-existing setting never grants deletion authority. The reservation
becomes the full ownership manifest after the base seed completes. Reserved
Company, Contact, Opportunity, Task, Target
Market, Target and Forecast collisions fail before base mutation. Owner
extensions are then built in committed, retryable stages. Each extension is
validated before that stage mutates it, so a later collision is preserved and
fails closed, although earlier exact synthetic stages may already exist. Reset
removes only stages proven by the manifest and their strict content checks. The
manifest is not a licence to adopt same-named or same-key user content:
seller-authored content and local blobs are still checked against the canonical
synthetic fixture.

The web and PostgreSQL host ports bind to loopback. Do not change them to a
LAN-facing address for an owner walkthrough.

## URL and access

- Start: [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
- Seeded Opportunity: [http://localhost:3000/opportunities/9030752b-8d62-5471-a891-ac303d279f0a](http://localhost:3000/opportunities/9030752b-8d62-5471-a891-ac303d279f0a)
- API health: [http://localhost:8000/health](http://localhost:8000/health)
- API readiness: [http://localhost:8000/ready](http://localhost:8000/ready)

No username or password is required. The development-only mock session signs in
as **Alex Morgan**, administrator of **Example Revenue Team**. The application
visibly identifies mock authentication. Do not enter a real Clerk, Microsoft,
Google, HubSpot, Salesforce, Stripe or provider credential.

## Walkthrough

1. Open **Settings**. Review the approved synthetic Company & Selling Profile,
   readable server capability states and the disabled billing/Credits boundary.
   Review the current Terms/Privacy acceptance and onboarding state, **Members**,
   the export control and the deletion controls. Do not queue deletion.
2. Open **Accounts**, select **[DEMO] Northstar Facilities Group**, then review
   its linked People, the real linked **[DEMO] Prepare the Northstar security
   workshop** Task and **[DEMO] Northstar multi-site workflow pilot**. **Add
   person** should carry the Account into the form; do not enter real details.
3. Use **Find** to review deterministic target-market/account research, then
   **Campaigns** to inspect the paused synthetic campaign and reviewed outreach.
   No discovery, mailbox or send provider is contacted.
4. Open the seeded Opportunity. Review its interactions, evidence, Sales Brain,
   methodology, Ask Oryntela citations and proposed/approved actions.
5. Open **Create → Studio**. Review the approved Northstar Business Case, reviewed
   presentation and approved synthetic PowerPoint template.
6. Return to the Opportunity. Review the published Deal Room, its Business Case,
   presentation resource, stakeholders, milestones and customer-safe boundary.
   The original one-time buyer token is deliberately irrecoverable, so the
   seeded state supports internal published-configuration review only. To review
   the buyer experience, use **Rotate link**, open the returned URL with its
   fragment token in a private local tab, then reset/reseed after the walkthrough.
7. Review the prepared Closed-Won Handover on the same Opportunity. The draft
   pins the available Opportunity, evidence, Business Case, Deal Room and Task
   sources. It remains unapproved while the Opportunity is open. To demonstrate
   the full reviewed lifecycle, explicitly mark the synthetic Opportunity Closed
   Won, refresh sources, submit and approve the Handover. Reset recognises these
   server-generated owner-fixture lifecycle descendants without accepting a
   foreign creator or untracked content edit.
8. Open **Pipeline** and **Insights**. During Q4 2026, in Insights
   select **Last quarter** to review the fixed July/August 2026 analytics
   fixture. For a later walkthrough, select **Custom** and use
   **1 July to 30 September 2026** instead;
   the preset is relative to the current date. Review Pipeline, Targets, Forecast,
   Analytics and administrator-only Manager Intelligence using the wider
   deterministic dataset. Forecast judgments are the fixed Q3 2026 fixture: set
   the quarter anchor to **24 August 2026** to review them. The default current
   quarter is time-dependent and may correctly contain no seeded judgments.
9. Return to **Settings** for the commercial boundary. In this owner environment,
   billing, checkout and Credits remain disabled; do not try to start a trial,
   create a checkout or record a manual paid-Credit grant. The deterministic
   catalogue, trial transition, Credit reservation/settlement and fail-closed
   cleared-funds rules are automated isolated-database proofs, not an interactive
   owner-dataset lifecycle.

Closing the synthetic Opportunity is optional and deliberate. It makes the Deal
Room read-only and is required before Handover approval; it does not activate a
customer, provider, checkout or charge.

## Commercial proof without a purchase

Use the repository tests as the evidence boundary. They create and remove only
isolated synthetic test records:

```text
uv run --project apps/api pytest \
  apps/api/tests/test_commercial.py::test_trial_boundaries_are_deterministic_and_never_charge_or_delete \
  apps/api/tests/test_credits.py::test_expiry_trial_grant_validation_and_negative_balance_protection \
  apps/api/tests/test_credits.py::test_exact_balance_full_and_zero_settlement_release_and_refund_guards \
  apps/api/tests/test_credits.py::test_manual_paid_purchase_requires_cleared_funds_review_and_fresh_safe_values
```

These tests prove deterministic trial and Credit state transitions, bounded
reservation/settlement and that the manual paid-Credit operation rejects missing
cleared-funds authority. They do not authorise entering a fictional payment in
the owner dataset. Checkout stays disabled and no provider charge is made.

## What is simulated

- identity is the visibly labelled development mock;
- AI, Ask, research and generated content are deterministic synthetic fixtures;
- Prospect discovery, outreach, campaign delivery and connector execution do not
  call external systems;
- commercial trial and Credit lifecycles are proven by isolated deterministic
  tests while the owner UI keeps billing, checkout and Credits disabled;
- the generated presentation uses the deterministic local renderer; and
- all companies, people, interactions, evidence and commercial assumptions are
  synthetic and labelled `[DEMO]` where presented as business records.

Live-capable adapters for Clerk, OpenAI, Apollo, Microsoft 365, Google Workspace,
HubSpot, Salesforce and Stripe remain separately gated by feature flags,
credentials, provider approvals and the real-data release gate.

## Reset

Reset deletes only the fixed tenant's manifest-owned synthetic demo records and
captured local demo objects:

```text
pnpm demo:reset
```

The reset applies the same environment, database binding, active-administrator,
mock-provider, connector, real-data and billing guards as the seed. It refuses
non-local object storage and any identity/content collision. Exact tenant-scoped
database deletions commit before captured local demo blobs are removed, so a
failed transaction cannot leave live rows pointing at deleted files. A durable
exact-key cleanup marker preserves any failed post-commit blob deletion; rerun
`pnpm demo:reset` to retry only those captured keys. No broad storage-prefix
deletion is used.

Reset restores a pre-existing organisation-wide methodology setting unchanged;
on a clean owner environment it removes only the exact MEDDPICC setting that
the owner seed created. It preserves unrelated local records and does not delete
production data, backups, DNS, provider accounts, infrastructure or commercial
transaction history.
