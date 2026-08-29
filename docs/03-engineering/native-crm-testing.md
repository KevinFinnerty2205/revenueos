# Native CRM testing strategy

Backend tests cover configuration/entitlement, roles, owner isolation, exact duplicate prevention, native/external authority, optimistic concurrency, six custom-field types and limits, archive/restore, source-labelled history, bounded activity, promotion hooks, export/deletion and forced-RLS isolation. Migration tests cover single head, schema/checks/indexes, downgrade/re-upgrade and duplicate preflight failure.

Frontend component tests cover settings state/mode confirmation/schema administration, record overview/custom values/history/activity/archive and external-authoritative read-only fields, as well as short CRUD forms, ownership lists and duplicate links. Playwright captures deterministic desktop and mobile screenshots and checks visible headings/overflow without real providers.

The complete gate is the repository `AGENTS.md` command list. Standard tests use mock auth/providers and local seeded mapping rows; external credentials must never be required or cause skips.
