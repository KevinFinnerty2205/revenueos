# Manager Intelligence security and privacy review

- **Status:** Reviewed for WO-039 private beta
- **Decision:** Deal-centric and least-privilege, with no employee surveillance data

## Access and tenant isolation

The active organisation and role come only from verified tenant context. Organisation
manager endpoints and reviewer writes require `admin`; members receive 403 and a
disabled feature receives 404. Every repository query has an organisation predicate.
New reviewer tables use composite organisation relationships, forced RLS, and an
application role that cannot bypass RLS. Pipeline/owner filters and Opportunity IDs
are tenant-validated to prevent IDOR and inference.

Admin is an interim capability, not proof of a reporting line. The owner of an
Opportunity can read the manager forecast on that deal so there is no secret review
layer. Members cannot read organisation manager summaries, other sellers' manager
aggregates or a batch of personal Target attainment. Reviewer writes never modify
seller identities/revisions or bypass external CRM field authority.

## Data minimisation

Manager responses contain canonical deal metadata, typed condition labels, bounded
safe change labels and typed source references. They exclude raw transcripts,
Evidence text, full audit payloads, private debrief content and arbitrary CRM custom
fields. Discussion questions are derived in memory and are not retained. There is no
manager note, comment thread, coaching-completion event, competency profile or HR
dossier.

No provider, LLM, AI job or prompt receives manager, seller or customer data.
Manager Intelligence does not collect or infer login/session/click/screen-time,
keystroke, call/email volume, response speed, CRM hygiene, call duration, talk ratio,
sentiment, filler words, interruptions, emotion, personality or productivity. It
does not expose a people score, deal score, grade, rank, leaderboard or comparative
personal-target table.

## Integrity and lifecycle

Reviewer forecast writes accept only period, category and expected revision. The
server snapshots amount, currency, owner, close date, Pipeline/stage, state and model
context; clients cannot forge these facts. Categories are finite and contain no
probability. Past periods and closed Opportunities are locked, concurrent revisions
are rejected, and PostgreSQL rejects update/delete outside explicit maintenance.

Export v28 contains reviewer judgments/revisions; derived attention and questions do
not need export. Opportunity/organisation erasure cascades reviewer data under the
same approved maintenance control used by Forecast. Inactive-user and owner
reassignment behaviour uses retained snapshot actor/owner references and current
read permission; it does not rewrite history.

## Logs, audit and operations

Operational logs must not contain deal/account names, amounts, target values,
forecast categories, seller/manager differences, questions, Evidence, transcripts or
review context. The reviewer write audit is metadata-only: safe action code, request
ID and entity IDs. No manager-attention-opened telemetry is required. Standard tests
use deterministic local data and make no external provider calls.

## Threat checks

Covered behaviour includes cross-tenant denial, member denial, owner read-only
transparency, admin-only append, seller-history preservation, server-derived context,
optimistic concurrency, past-period/closed locks, forced RLS, immutable reviewer
revisions, safe feature-off behaviour, export and erasure. A response-token assertion
guards against score/rank/surveillance fields.

The residual limitation is broad admin access inherited from the private-beta role
model. Formal manager/team scope requires a future authorised work order; WO-039 does
not implement or imply it.
