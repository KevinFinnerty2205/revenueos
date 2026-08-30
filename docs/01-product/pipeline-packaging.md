# Pipeline packaging

The packaging decision follows the canonical Core/CRM split rather than treating the
entire Pipeline page as a CRM upsell.

## Core

- canonical Opportunity workflow assignment and history infrastructure;
- current-state Board, List and Closed views;
- descriptive currency-safe summaries;
- current stage, time tracking, closure and reopen workflow;
- links into Sales Brain, Actions, Daily and later Core analytics/forecasting.

These capabilities keep the Core Opportunity experience coherent for organisations
that do not buy the native CRM administration add-on and for external-CRM users.

## CRM add-on

- native authoritative pipeline administration;
- multiple custom pipelines, bounded stage definitions, guidance and ordering;
- default selection and safe pipeline/stage archive controls.

Configuration requires the `crm` module entitlement, the native CRM feature, the
native Pipeline feature, native CRM mode and an organisation administrator. In
external mode definitions are managed in HubSpot and RevenueOS native configuration is
read-only. The current board remains useful but direct native movement is denied so the
systems cannot silently diverge.

WO-036 analytics and WO-038 forecasting remain Core Intelligence. They are not moved
into the CRM package by WO-035.
