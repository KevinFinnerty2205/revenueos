# ADR 0036: Ephemeral deterministic Ask RevenueOS v1

**Status:** Accepted

## Context

RevenueOS already holds structured Methodology, Revenue Brain, Evidence, Daily, Next
Best Action and Action state. The smallest trustworthy Ask surface must improve access
to that intelligence without introducing a generic agent, text-to-SQL, public-web
research, uncontrolled retrieval, new infrastructure or conversation-retention risk.

## Decision

Implement Ask v1 as an ephemeral deterministic composition in the existing modular
monolith. Use a fixed question taxonomy, explicit Opportunity/Account/user-owned
workspace scope, bounded structured repository reads, deterministic ranking/composer,
strict source/citation validation and four answer states. Make no AI-provider call and
retain no question, answer or conversation content. Persist only quota/audit/interaction
metadata in the existing tenant-owned beta event table.

Prefer current structured product sources. Do not add a vector database or raw-
transcript search. Preserve provenance and conflicts. Reuse Daily and existing Next
Best Action instead of creating a second prioritisation/recommendation engine.

## Alternatives considered

- **Provider-first RAG/chat:** rejected for v1 because it adds injection, privacy,
  cost and citation-fabrication surface before structured retrieval is proven.
- **Text-to-SQL/general BI:** rejected because it expands query and authorisation
  surface beyond the bounded product taxonomy.
- **Persisted conversations:** rejected because independent questions deliver the
  required value without new retention/export/deletion obligations.
- **New vector/search infrastructure:** rejected because the current structured
  source families are sufficient and better preserve policy/provenance.
- **New Ask navigation area:** rejected; Search mode and contextual links preserve
  the Core information architecture.

## Consequences

Ask is fast, inspectable, deterministic and provider-free, and fake citations cannot
enter the current path. It cannot answer outside the implemented taxonomy or retrieve
public knowledge; unknown/conflicting results are expected. Follow-ups have no memory.
A future provider-backed composer or conversation store requires a new work order and
must preserve the same scope, retrieval, status and citation invariants.
