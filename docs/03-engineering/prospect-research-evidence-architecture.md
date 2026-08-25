# Prospect research and evidence architecture

## Current WO-027 person research boundary

Professional role, activity, public statements, conversation context and buying-role
hypotheses remain Prospect observations/projections. They carry public source links
and Prospect trust; they are not `Evidence`, `CandidateEvidence` or customer-direct
statements. Contact promotion copies only canonical identity/contact fields with
provenance and does not promote research claims.

No WO-027 service calls Evidence, Methodology, Stakeholder Intelligence, Revenue Brain
or Ask RevenueOS writers. Later use of saved public research must preserve a distinct
public-research origin and require an explicitly approved consumer contract.

- **Status:** WO-026/027 separation is implemented; broader ICP/territory architecture remains proposed
- **Purpose:** Find relevant business accounts and people using attributable,
  permitted professional information

## Boundary with the canonical domain

| Term             | Meaning                                                                     |
| ---------------- | --------------------------------------------------------------------------- |
| Prospect Account | A research candidate not yet accepted as a canonical Company                |
| Prospect Person  | A professional candidate associated with a Prospect Account                 |
| Lead             | A deliberately saved or assigned person/account pursuit requiring follow-up |
| Contact          | A canonical person in RevenueOS, normally associated with a Company         |
| Account          | User-facing language for a canonical Company and its relationship workspace |

Research objects remain staged until a user or explicit policy promotes them. Saving
a Prospect Account creates or links a tenant-scoped Company after duplicate review;
saving a person creates or links a Contact. A Lead represents pursuit state, not a
second copy of the person. Promotion preserves source lineage and does not silently
overwrite canonical fields.

## Conceptual model

| Concept                   | Responsibility                                                                |
| ------------------------- | ----------------------------------------------------------------------------- |
| `ResearchSubject`         | Organisation-scoped account/person candidate and provider identifiers         |
| `ResearchSource`          | Source URL/provider, publisher, observed/fetched time and access basis        |
| `ResearchFinding`         | Atomic claim, category, trust state, source references and expiry             |
| `ResearchRun`             | Query, authorised scope, provider/policy versions and safe lifecycle metadata |
| `ContactPointObservation` | Business email/phone candidate and verification lifecycle                     |
| `ICPDefinition`           | Versioned target criteria, exclusions, rationale and owner                    |
| `TerritoryDefinition`     | Versioned geographic/segment/account assignment constraints                   |
| `ProspectPriority`        | Explainable fit/relevance factors; never an unsupported personality score     |
| `PromotionReview`         | Link/create/ignore decision, duplicates and retained lineage                  |

These are future design concepts, not authorised database tables. Every row, key,
query, cache key and future storage path is explicitly organisation-scoped.

## Provenance and trust

Each finding is atomic enough to verify and shows source links where permitted. Its
trust state is one of:

- `verified` — corroborated by an approved verification method or authoritative
  source;
- `provider_supplied` — returned by a named provider under an approved contract but
  not independently verified;
- `inferred` — derived from cited public professional information, with the inference
  clearly labelled;
- `unknown` — origin, freshness or support is insufficient.

Record source type, URL/provider reference, publisher, observation time, retrieval
time, policy/provider version and expiry. Conflicting findings coexist until review;
supersession preserves history. A provider confidence score never replaces RevenueOS
trust state or visible provenance.

## Business contact verification

Contact points use separate states such as `source_claimed`, `format_valid`,
`provider_verified`, `delivery_observed`, `invalid`, `opted_out` and `unknown`.
RevenueOS must never guess an address and present it as verified. Verification method,
provider, time and expiry are visible. Opt-out, suppression and do-not-contact state
override any positive verification.

## Research flow

1. The user supplies an ICP, territory or specific professional research question.
2. Policy validates purpose, geography, source/provider and prohibited attributes.
3. Provider adapters retrieve only permitted public or licensed business data.
4. Normalisation proposes subjects and atomic findings with provenance.
5. Deterministic validation checks schema, source presence, age and duplicates.
6. The user sees fit reasons, uncertainty, sources and contact verification.
7. Save-to-Sell performs duplicate resolution and an explicit promotion review.
8. Corrections/suppressions invalidate affected priorities and downstream drafts.

Search-based research must respect source terms and robots/access policy; it is not a
licence to scrape prohibited sources. Provider raw payloads and credentials stay out
of logs and long-term storage unless explicitly required and approved.

## ICP and territory

An ICP combines typed supported criteria such as geography, industry, organisation
size, business model, approved technology or public trigger events. It includes
exclusions and explains why a result matched. Territory constrains which accounts a
user/team may pursue and can include named-account ownership, regions and supported
segments. Effective criteria and assignment versions are captured on a research run
so results remain reproducible.

Protected or sensitive personal characteristics, private life, health, political or
religious beliefs, deceptive affinity and vulnerability must not be criteria.
Professional interests are included only when relevant, sourced and presented as
context—not instructions to manipulate a person.

## Safety and privacy controls

- Establish lawful basis, contractual source rights and jurisdiction review before
  enabling a provider or geography.
- Minimise collection, set category-specific retention and support access, correction,
  suppression, export and deletion workflows.
- Never infer sensitive traits, scrape prohibited sources, expose private knowledge,
  fabricate rapport or treat event attendance as blanket marketing consent.
- Restrict exports and bulk access; rate-limit and audit high-volume research.
- Tenant, role, territory and module entitlement checks happen server-side.
- No production customer research is permitted before the required identity,
  governance, retention and erasure controls are complete.

Research informs outreach but never authorises it. Engage must independently apply
consent, suppression, frequency, sender and jurisdiction policy.

## Architecture and evaluation

Provider-specific clients sit behind explicit adapters. A research service owns
policy, run lifecycle, normalisation, provenance and promotion; canonical Company and
Contact repositories continue to own accepted records. Durable external work extends
the existing job and execution foundations with idempotency and safe receipts.

Evaluate source-link validity, claim support, freshness, duplicate precision,
promotion correctness, contact verification accuracy, prohibited-attribute rejection
and cross-organisation isolation with synthetic fixtures. Observability records safe
counts, provider/version, latency and errors—not queries, findings, contact details or
source payloads.

## Explicitly out of scope

WO-023 adds no provider, crawler, enrichment, Lead schema or contact-verification
implementation. Consumer profiling, covert surveillance, sensitive-trait inference,
unbounded data resale and uncontrolled list building are not RevenueOS capabilities.
