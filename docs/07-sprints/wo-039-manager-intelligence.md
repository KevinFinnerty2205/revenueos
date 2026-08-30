# WO-039 — Manager Intelligence & Coaching

- **Status:** Implemented; validation/Checkpoint 3 evidence recorded in the draft PR
- **Branch:** `feature/epic-16-wo-039-manager-intelligence`
- **Date:** 30 August 2026

## Outcome

WO-039 adds a deal-centric Core manager layer for organisation administrators. Home
shows a compact attention list, Pipeline provides Manager view, Opportunity provides
an evidence-backed review, Insights composes organisation references, and Forecast
adds a separate transparent manager judgment/history. There is no standalone manager
application or navigation item.

## Delivered

- migration `0048_manager_intelligence` with separate forced-RLS reviewer identity and
  immutable revision tables;
- shared Forecast context/staleness/aggregate helpers, admin-only reviewer append and
  Opportunity-owner read-only transparency;
- deterministic, de-duplicated deal attention with a nine-code bounded taxonomy;
- source-backed Methodology, Revenue Brain, Action and seller-forecast conditions;
- safe bounded recent changes and up to five derived discussion questions;
- manager summary composed from existing Actual, Target and Forecast services;
- responsive Home, Pipeline, Opportunity, Forecast and Insights integrations;
- export v28, erasure/reset, deterministic demo, API/unit/browser coverage; and
- product, design, architecture, privacy, ADR and Checkpoint 3 documentation.

## Deliberate boundaries

No rep/deal score, rank, leaderboard, productivity or behavioural monitoring,
call-behaviour analysis, sentiment, personality inference, employee profile,
persistent coaching note/dossier, AI/LLM coach, notification, automatic Action,
manager hierarchy, automatic forecast, probability, blended final forecast, Target-
to-deal pressure rule, provider or connector was added. Manager Intelligence does not
mutate Evidence, Methodology, Revenue Brain, Opportunity, Action or seller forecast.

## Validation and handoff

The complete commands and screenshot evidence are recorded in the draft pull request.
The product must now pass [Checkpoint 3](../06-roadmap/checkpoint-3-handoff.md) before
WO-040+ ecosystem work or broader beta claims. The known v1 limitations are listed in
the [product guide](../01-product/manager-intelligence.md).

Visual evidence is in `assets/wo-039/`: desktop Home, Pipeline, deal review and
Insights summary, plus 390 px Home, forecast-perspective and source-backed-question
captures. The live deterministic demo had no horizontal overflow at 390 px.
