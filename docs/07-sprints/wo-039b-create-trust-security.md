# WO-039B — Create Trust, Security & Output Integrity

- **Branch:** `feature/pre-beta-wo-039b-create-trust-security`
- **Baseline:** `558795c82103bc9310e1bf89f07f3322f21860ac`
- **Status:** implemented and locally validated; draft pull request remains unmerged
- **Migration:** `0049_create_trust`
- **Data:** synthetic only

## Outcome

WO-039B closes the eight Create findings assigned by Checkpoint 3. An authorised PPTX
now passes a versioned hostile-package and compatibility profile; editable policy
requires writable mapped placeholders; deterministic composition proves its claim
manifest before rendering; the actual saved PPTX is reparsed against slide, text,
required/exact and internal-data expectations; approval is available only for the
validated immutable version; and download uses a short-lived authenticated one-time
grant with current membership/approval/checksum checks.

The downloadable PowerPoint is explicitly the authoritative file. The browser is an
accessible structured review and makes no pixel-equivalence or font-fidelity claim.
No DOCX, Google Slides, AI layout, rendering service, paid scanner, mailbox, Apollo,
external provider or WO-039C/WO-040 capability was added.

## Schema and lifecycle

Migration `0049_create_trust` adds compatibility state/details/profile/time to
template versions, validation profile/time to generated presentation versions and
the tenant-owned `create_download_grants` table. The new table has composite tenant
foreign keys, forced PostgreSQL RLS, expiry/consumption/revocation constraints and
indexes for user/expiry and version lookup. Existing templates default to **Needs
attention** and cannot generate under profile v1 until revalidated and approved.

The worker persists a generated object only with its SHA-256 and successful output
validation metadata, and deletes the new object if the database commit fails. Missing
or checksum-drifted output fails closed. Expired grants are bounded maintenance data;
membership/version/organisation deletion cascades remove grants and organisation
deletion remains object-first.

## Trust architecture

Profile v1 supports standard transitional `.pptx`, native title/subtitle/content
placeholders, common safe shapes, Unicode and embedded PNG/JPEG/GIF. Selected source
masters/layouts/themes remain, while complex self-contained content is supported only
as locked/reuse-as-is. Macros, ActiveX, OLE/embedded packages/workbooks, embedded
fonts, custom XML, SVG, mismatched media and all external relationships—including
hyperlinks—are rejected. Hidden slides cannot be approved; notes/comments, custom
properties and thumbnails do not survive generated output.

The exact matrix and administrator path are in the
[Create PowerPoint trust guide](../01-product/create-powerpoint-trust-guide.md). Bounds,
target resolution, XML parsing, output expectations and the grant protocol are in the
[trust architecture](../03-engineering/create-pptx-trust-architecture.md).

## Deterministic file and visual evidence

`scripts/generate_wo039b_pptx_evidence.py` builds synthetic fixtures through the
production processor and writes the checked-in evidence below. LibreOffice and
Poppler are test-only inspection tools; production never invokes either.

| Fixture          | Structural result           | Visual inspection                         | Important proof                                      |
| ---------------- | --------------------------- | ----------------------------------------- | ---------------------------------------------------- |
| Simple corporate | PASS, 2 slides, no warnings | PASS; no observed clipping                | customer title/audience and two content replacements |
| Brand-heavy      | PASS, 2 slides, no warnings | PASS; authored white title/style retained | placeholder editability with brand styling           |
| Multi-layout     | PASS, 3 slides, no warnings | PASS; no observed clipping                | preserved layouts and ordered replacements           |
| Exact legal      | PASS, 2 slides, no warnings | PASS; exact legal text visible            | source notes/internal marker absent from output      |
| External content | UNSUPPORTED / `unsafe_pptx` | deliberately not rendered                 | external relationship rejected before `python-pptx`  |

Hashes, parsed text, editability counts and leakage flags are recorded in
[`inspection-manifest.json`](assets/wo-039b/inspection-manifest.json). Source/generated
PPTX, rendered PDFs and 18 page PNGs live under `assets/wo-039b/`. These renders are
representative smoke evidence, not a promise that every PowerPoint environment has
identical pixels.

Synthetic desktop template-readiness and 390-pixel presentation-review captures are
also checked in as `ui-template-ready-desktop.png` and
`ui-presentation-review-mobile.png`. They prove the customer-facing compatibility and
download-review disclosures without including customer content.

## Dependency decision

`pypdf` moved from 5.9.0 to locked 6.16.2 within the explicit `>=6.15,<7` range. The
checkpoint malformed-PDF family is no longer present in the installed version and
resource fixtures are bounded by regression tests. The production Python audit also
reports four `cryptography` advisories; the repository does not expose their PKCS#7,
X.509 verifier or over-2-GB ASN.1 primitives, so they are recorded—not claimed fixed—
for the platform dependency owner. The complete decision and upstream evidence are in
[Create dependency remediation](../03-engineering/create-dependency-remediation.md).

## Verification

The frozen local gate passed with these results:

- Prettier, ESLint, TypeScript, Ruff lint/format and strict mypy passed; mypy checked
  233 source files.
- Vitest passed 228 tests across 60 files. Playwright passed all 64 tests, including
  Ready / Needs attention / Unsupported template states and the 390-pixel review.
- Full pytest passed 1,037 tests with four intentional skips and one existing
  Starlette/httpx deprecation warning. This includes hostile-package bounds,
  relationship/media/XML policy, exact-shape output validation, grant replay and
  concurrency, forced RLS and migration assertions.
- Migration 0049 upgraded, downgraded to 0048 and re-upgraded; `alembic heads` reported
  one head and `alembic check` reported no new upgrade operations. The web production
  build and API source/wheel builds passed.
- `pnpm audit` and `pnpm audit --prod` reported no known vulnerabilities. The frozen
  production Python audit reported no `pypdf` finding and the four explicitly
  classified `cryptography` findings above.
- The repository secret/scope audit passed 1,322 tracked or pending files; 815 local
  links in changed Markdown resolved; prohibited implementation scope, new debug/TODO
  markers and `git diff --check` were clean.

CI links and final check status are recorded in the draft pull request.

## Remaining limitations and WO-039C handoff

- PowerPoint/font rendering varies; every customer-facing file still needs human
  review. Conservative overflow detection is not PowerPoint font measurement.
- Local object storage is development/test only; an approved private production
  adapter and target-environment evidence remain mandatory.
- The structural parser is not a general antivirus claim and profile v1 deliberately
  rejects unsupported/ambiguous content rather than sanitising it.
- WO-039C owns production identity proof, live runtime-role/RLS evidence, backup and
  restore, retention/deletion/offboarding job proof, support/incident operations, real
  tenant provisioning, native CRM import/dedupe/merge, broader secret/monitoring proof
  and the real-data beta runbook.

The final disposition of each checkpoint item is in the
[remediation checklist](wo-039b-remediation-checklist.md). WO-040 remains blocked and
the draft pull request must not be merged by this work order.
