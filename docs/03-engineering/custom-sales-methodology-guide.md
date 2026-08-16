# Custom sales methodology guide

**Status:** Current administrator workflow from WO-024.

An organisation administrator uses **Settings → Sales Methodology** to create and
select a custom definition. The guided builder asks for a name and purpose, then for
each field: its display name and stable key, meaning, required status, expected
Evidence, one controlled canonical fact, one controlled Evidence category, optional
stage guidance, freshness days and a suggested discovery question.

## Bounds

- five custom definitions per organisation, including archived definitions;
- one to twenty ordered fields per definition;
- up to three questions per field in the API contract (the v1 UI guides one);
- names 80 characters, descriptions/explanations 500, questions 300;
- freshness from 7 to 730 days or not applicable;
- allowlisted canonical facts, Evidence categories and Opportunity stages only; and
- unique stable keys and display orders.

There is no JSON editor, SQL, JavaScript, templates, hidden prompts, arbitrary
expressions, dependencies or rule language. Plain configuration that resembles
executable code, prompt injection or control characters is rejected server-side.
Browser validation is only convenience; the API is authoritative.

Editing creates an immutable next definition version using optimistic concurrency.
Existing projections keep the exact definition version and content needed for
explanation. Archiving prevents future selection/editing and selects `none` if the
archived definition was active; it does not remove historical projections. Selecting
a custom definition changes only the organisation default and preserves all Evidence.

Members can read and use the effective definition on authorised Opportunities.
Only active administrators can create, version, archive or select definitions.
