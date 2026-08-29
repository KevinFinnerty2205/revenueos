# Native CRM UX

- **Status:** Implemented foundation; screenshot review recorded in WO-034
- **Design test:** A five-person sales team can understand and maintain records without an implementation consultant.

## Information architecture

No CRM destination is added. Desktop continues to use Accounts, People and Pipeline; mobile continues to use Today, Interactions, Actions and Search. Settings gains a CRM section. Existing Account, Contact and Opportunity pages are enriched rather than mirrored under new routes.

## Settings

Settings → CRM first shows the current availability and a plain-language choice: use RevenueOS as the CRM or use connected HubSpot. Only admins see mutation controls. Selecting a mode requires explicit confirmation. Connection/mapping conflicts produce a safe explanation and do not silently rewrite authority. Custom-field administration groups fields by record type and exposes only label, key, supported type, options/order and archive.

## Records

The record header shows identity, owner, mode and archive state. A compact overview shows five to seven core fields. Externally managed fields display “CRM controlled · read-only”; review-before-sync fields display their review state. Edit is a focused page, not permanently live inline controls. Entitled administrators can archive after confirmation and restore; archived records cannot be edited.

Custom fields sit behind a labelled **CRM details** disclosure after the core overview, in a responsive two-column grid and as one column on narrow screens. Their type controls use native labels/input semantics. When entitlement is removed, values remain visible and controls become read-only. Activity remains visible customer-work context from existing sources; Record history uses a separate disclosure with a human-readable field diff, actor, source and time.

## Duplicate and failure UX

An exact domain/email conflict returns a stable link to **Open existing record**. There is no name-only block, merge UI or override that weakens the database uniqueness boundary. Loading, empty, unavailable, stale-write and safe error states remain inline. Keyboard focus, visible labels, semantic sections/lists, native controls and reduced-motion-compatible styling follow the existing web conventions.

## Mobile simplicity review

Record overview, owner, edit action and core fields stack without horizontal tables. Custom fields and history remain available under disclosures while relationship Activity stays visible. Administration remains responsive but is intentionally secondary; no new mobile navigation item is added. The mobile test validates access through existing Search and confirms no overflow.

## Deliberate exclusions

Import/export wizards, tags, arbitrary filters, bulk actions, configurable layouts, Pipeline configuration and native reviewed-Action preview are absent. These are not hidden incomplete controls; their safe architecture must be approved separately.
