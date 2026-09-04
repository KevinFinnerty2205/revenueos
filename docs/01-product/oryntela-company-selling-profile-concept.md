# Oryntela Company & Selling Profile concept

- **Status:** **IMPLEMENTED IN WO-046 — AWAITING MERGE**
- **Priority:** Phase 1 of the owner-approved pre-launch roadmap
- **Authority:** Organisation-supplied/company-approved context; never customer Evidence

## Problem

Sales Brain understands the buyer and deal from authorised Evidence, but its reuse of
approved context about **what the Oryntela customer sells** is fragmented. Prospect,
Engage, Create, Business Case, Methodology and Ask already carry pieces of offering,
target-market, proof-point and approved-content context. WO-046 provides the smallest
approved profile and revision-pinned server projection without collapsing those
existing authority domains.

## Existing overlap to reuse

- organisation identity and settings;
- Target Markets and ICP criteria;
- Engage offering, value and call-to-action context;
- approved Create templates, slides, claims and content;
- approved Value Models and Business Case assumptions;
- Prospect research objectives and exclusions; and
- bounded custom Methodology definitions.

The profile must compose or reference these primitives. It must not copy them into a
second source of truth.

## Implemented bounded model

The organisation-owned, administrator-controlled and versioned profile can explain:

- company description and approved market language;
- products/services and multiple distinct offerings;
- ideal customer profiles, industries, company sizes, personas and territories;
- problems solved, customer outcomes and differentiators;
- approved proof points, case studies, objections and competitor context;
- value propositions and customer-safe claims; and
- pricing/packaging context only where separately authorised.

One stable profile has immutable revision snapshots. A draft can be edited with
optimistic concurrency, approved as current, superseded by a later approval or
retired. The single approved-context projection identifies the exact revision.

## Context and authority layers

| Layer                                 | Authority                                     | Permitted use                                                   |
| ------------------------------------- | --------------------------------------------- | --------------------------------------------------------------- |
| Organisation-approved selling context | Approved internal context, not buyer truth    | Constrain and improve drafts/research/questions                 |
| Public professional research          | Sourced external observation or inference     | Suggest relevance; never establish customer intent              |
| Seller-reported context               | Explicit salesperson statement                | Context with visible attribution                                |
| Customer-direct Evidence              | Highest customer-claim support where verified | Deal understanding and methodology according to Evidence policy |
| System facts                          | Canonical product/record state                | Workflow control, not market truth                              |

Approved profile text remains untrusted input to AI execution. It must be bounded,
escaped/structured, content-minimised, tenant-isolated and protected against prompt
injection. It never becomes customer Evidence automatically.

## Reuse across Oryntela

| Consumer                  | Potential improvement                                                          |
| ------------------------- | ------------------------------------------------------------------------------ |
| Sales Brain / preparation | Explain why a buyer issue matters to the relevant offering                     |
| Prospect                  | Reuse approved ICP and offering constraints without broadening data collection |
| Engage                    | Produce more specific drafts within approved claims and seller voice           |
| Create                    | Reuse approved positioning, proof and brand content                            |
| Business Case             | Select approved value models; never invent numbers                             |
| Ask                       | Answer organisation-context questions separately from customer Evidence        |
| Methodology / Actions     | Suggest relevant questions and work without marking fields complete            |

## First-partner validation

Collect a short, approved onboarding brief outside customer Evidence:

1. What do you sell?
2. Who normally buys it?
3. Which problems and outcomes may be stated?
4. Which proof, material and claims are approved?
5. Which offering is relevant to the initial opportunities?

Aim for a useful first version in under ten minutes, review it with the partner, and
reuse existing fields/documents manually where possible. Record repeated missing
context and correction—not sensitive customer content—in the feedback process.

Implementation does not prove product value. Partner validation must establish setup
time, correction frequency and whether reuse improves at least two workflows before
the profile is expanded or connected more broadly.

## Non-goals

- knowledge-base or document-management platform;
- public website crawler that silently defines company truth;
- automatic approval of claims, proof points or prices;
- prompt repository exposed to administrators;
- customer Evidence or CRM replacement;
- per-seller private company profiles; or
- a requirement before the first design partner.
