# RevenueOS Prospect

- **Status:** WO-026 company Account Research and WO-027 company-scoped Prospect Person Intelligence implemented; ICP/territory and outreach remain future
- **Purpose:** Find the right customers and the right people

## Product outcome

Prospect connects territory and pipeline needs to responsible, verifiable account
and person research. It helps a seller decide whom to approach and why, then saves
the selected relationship into the Core sales workflow.

## Capability boundary

The current WO-026/027 slice includes bounded company name/domain search, explicit
candidate selection, versioned sourced Account Research and duplicate-safe promotion
to a canonical Company, followed by bounded relevant-person discovery, versioned
professional research, buying-role hypotheses and explicit duplicate-safe Contact
promotion. See the
[implementation guide](prospect-account-research.md),
[person implementation guide](prospect-person-intelligence.md),
[buying-committee guide](buying-committee-hypotheses.md),
[business-contact trust guide](business-contact-trust.md),
[professional safety guide](professional-research-safety.md),
[trust/source guide](account-research-trust-and-sources.md) and
[customer Evidence boundary](prospect-research-vs-customer-evidence.md).

The following is the broader target capability boundary; ICP/territory and outreach
are not implemented by WO-027:

- account discovery and prioritisation;
- ICP and territory definitions;
- whitespace and pipeline-gap exploration;
- company trigger events with source dates;
- buying-committee hypotheses;
- relevant public professional person research;
- permitted business contact intelligence; and
- save/promote to a Core Account, Contact or future CRM Lead workflow.

Prospect is not a consumer social profile, a private-person dossier, a prohibited
scraper or a source of unsourced personal claims.

## Research trust model

Every finding carries a source, observed date, subject, claim, permitted-use class
and one of:

- `verified`: independently verified under the defined policy;
- `provider_supplied`: returned by a named provider but not independently verified;
- `inferred`: a bounded interpretation or format hypothesis; or
- `unknown`: no supported value.

Source links are shown where the source may be opened lawfully. RevenueOS does not
infer sensitive traits, fabricate rapport, guess an email address and label it
verified, or turn private information into outreach context.

## Domain language

- **Prospect:** an unsaved or staged organisation/person considered for targeting.
- **Account:** a saved Company relationship owned by the organisation and reused by
  Sales Brain.
- **Contact:** a known person record linked to an Account; it may exist without being
  a lead.
- **Lead:** a CRM qualification/work record for a person or organisation that may
  become an opportunity. It is introduced only with a concrete CRM workflow.

Saving a Prospect should resolve duplicates and preserve research provenance rather
than create a second Account or Contact model.

## ICP and territory

An organisation can define bounded industries, size, geography, revenue, employee
count, permitted technology characteristics, business problems and exclusions.
A territory combines geography, segment and ownership policy. Results explain which
criteria matched and which data is missing. Initial prioritisation is deterministic;
predictive lead scoring is deferred.

Example: for NSW universities with more than 5,000 students, Prospect can show known,
active, untouched and target accounts, current opportunities, public triggers and a
recommended review order. It must disclose source coverage and avoid claiming a
complete market census.

## Person and contact intelligence

Appropriate context includes role, public career history, professional articles,
public interviews, relevant initiatives, public speaking and professional
affiliations. It excludes protected characteristics, intimate/personal life,
irrelevant family information and deceptive familiarity.

Business contact data separately shows verified, provider supplied, inferred format
or unknown. An inferred corporate email pattern cannot be used as a verified
recipient without the required validation and outreach policy.

## First-time and power-user experience

Current first-time experience: type a company name or domain, choose an unambiguous
candidate, inspect a sourced brief and deliberately Add to Sales. From that company,
find a small set of relevant people, research one and explicitly add/link a Contact.
Current mobile keeps that concise flow. ICP and power-user territory behaviours remain future.

- First-time: choose an ICP or describe a bounded territory, review sourced results,
  save one target.
- Power user: reusable filters, territory coverage, bulk review and deduplication,
  with no unbounded bulk contact export.
- Mobile: search, review a target and save; complex ICP/territory administration is
  desktop-first.
- Not purchased: contextual learn-more only when a pipeline gap or Find link is
  relevant; Core continues without interruption.

## Simplicity test

- **Where/first action:** Find; search an account/person or choose a guided ICP.
- **Navigation:** Find is the only permanent destination; research, ICP and territory
  are nested views.
- **Hidden until needed:** Provider detail, advanced filters, bulk review and territory
  administration follow the result/source view.
- **Mobile:** Search, inspect provenance and save one target; configuration is desktop-first.
- **When not purchased:** A restrained contextual explanation appears only where Find
  or a pipeline-gap action is relevant; Core navigation/workflows remain complete.
- **First-time/power user:** First-time users save one sourced target; power users gain
  reusable filters, coverage and bounded bulk review.
- **AI/manual work:** AI proposes supported filters, hypotheses and duplicate links;
  users verify sources, correct findings and explicitly promote canonical records.

## Success and safeguards

Measure sourced targets reviewed, saved-account quality, duplicate prevention,
research corrections and progression to legitimate conversations—not raw contacts
collected. See [research architecture](../03-engineering/prospect-research-evidence-architecture.md)
and [Find experience](../02-design/find-and-prospect-experience.md).
