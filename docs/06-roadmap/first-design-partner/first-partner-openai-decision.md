# First-partner OpenAI real-data decision

- **Assessment date:** 2 September 2026 (Australia/Sydney)
- **Status:** **OWNER INPUT REQUIRED — OPENAI IS NOT APPROVED OR CONFIGURED**
- **Recommended model if approved:** `gpt-5.6-terra`
- **Applicable profile:** `NATIVE-AI-REVIEW-V1` only

OpenAI is the only implemented real AI provider. It is central to the preferred
first-partner Sales Brain value test, but RevenueOS can launch a narrower Core
workflow without it. No API key, billing, provider request or customer-data transfer
is authorised by this document.

## 1. Which features require OpenAI?

The preferred first-partner profile uses the main OpenAI Responses adapter for:

- eight Meeting Intelligence extractors: Executive Summary, Decisions, Action
  Items, Risks & Blockers, Open Questions, Buying Signals, Objections & Competitive
  Signals and Stakeholder Intelligence;
- Next Best Action, composed from the eight validated extraction artefacts;
- Follow-up Email draft composition from four validated artefact projections; and
- bounded AI Debrief question/evidence processing from typed debrief answers or
  fragments.

The implementation also has separate OpenAI-capable audio transcription, visual and
document/email evidence paths, but **all are disabled in the first-partner profile**.
There is no live external-AI adapter, tool execution, mailbox send or Prospect
provider in this scope.

## 2. What customer information is sent?

Only after a user deliberately supplies an authorised transcript or debrief input:

| Path | Sent to OpenAI | Not sent by this path |
| --- | --- | --- |
| Eight extractors | Registered instructions and strict output schema plus the selected transcript, bounded to 50,000 characters per extractor | Passwords/keys, browser auth headers, unrelated tenant records, files/audio/images |
| Next Best Action | The eight validated current-transcript artefacts | Original transcript |
| Follow-up Email | Validated Executive Summary, Decisions, Action Items and Open Questions projection plus selected tone | Original transcript; mailbox credentials; no email is sent |
| AI Debrief | Bounded normalised context, answers or text fragments needed for the next question/evidence | Raw recording/audio in this profile |

Names, employers, roles, contact details, meeting statements, commercial needs,
objections, decisions and actions may appear inside those inputs. The first partner
must be told this and must not supply special-category/highly sensitive material.

## 3. Why is it sent?

The provider converts deliberately supplied sales-conversation evidence into strict,
reviewable JSON. RevenueOS validates and stores only schema-conforming output, then
shows it for human review. OpenAI receives no authority to update CRM records, send
email, call tools or act for the customer.

## 4–5. What happens if OpenAI is disabled, and what still works?

Use `NATIVE-NO-EXTERNAL-AI-V1`. The OpenAI-dependent features above are off and show
an honest unavailable/not-enabled state. They do not silently use mock intelligence
or another provider.

Core records and workflows still work: Accounts, Contacts, Opportunities, Tasks,
ordinary Interaction records and deliberately entered notes/transcripts, Daily,
Opportunity Workspace, Methodology, internal Actions/manual completion, Native CRM,
Pipeline, Analytics, Targets, Forecast, Manager views, export and supervised
organisation deletion. Prospect, Engage, Gmail, Apollo, HubSpot, recording,
transcription, live intelligence and external execution remain off in both profiles.

## 6. Required configuration if approved

The exact production configuration must include:

- `API_PRIVATE_BETA_REAL_DATA_ENABLED=true` only after the full launch gate passes;
- `API_PRIVATE_BETA_EXTERNAL_AI_APPROVED=true` with an owner/legal approval reference;
- `AI_PROVIDER=openai`, `OPENAI_MODEL=gpt-5.6-terra` and
  `API_FEATURE_OPENAI_PROVIDER_ENABLED=true`;
- one restricted server-side `OPENAI_API_KEY` in the target secret manager, never in
  the browser, source control, image or logs;
- `OPENAI_TIMEOUT_SECONDS=30` and `OPENAI_MAX_OUTPUT_TOKENS=4096` initially;
- `API_PRIVATE_BETA_MAX_GENERATIONS_PER_DAY=50` and
  `API_PRIVATE_BETA_MAX_OPENAI_REQUESTS_PER_DAY=75` per organisation;
- transcription, visual, document/email evidence, live, recording, Prospect and
  Engage/provider flags off; and
- target egress/TLS, rotation/revocation owner, provider project budget alert and
  tested kill switch.

Current code sends foreground Responses API requests with strict JSON Schema,
`store=false`, no tools, no streaming and zero SDK transport retries. Application
validation, job leases, tenant checks and bounded retries remain authoritative. Logs
contain metadata such as model, job type, latency and token counts—not prompts,
transcripts, outputs, credentials or full provider payloads. The stored `0 AUD` cost
means “not calculated”, not “free”.

`gpt-5.6-terra` is recommended because OpenAI describes it as balancing intelligence
and cost, and it supports Responses and Structured Outputs. Model quality must still
pass synthetic evaluation for every enabled schema before real data.

## 7. Usage limits

Repository defaults are 100 new generations and 150 OpenAI attempts per
organisation/UTC day. The first-partner profile lowers them to 50 and 75. Every
actual provider attempt—including a bounded structured-output retry—uses the provider
counter. A worker job can have up to three execution attempts and strict output can
also retry within its configured bound, so the counters limit volume but do **not**
guarantee a monetary maximum.

The OpenAI project/account also has its own tier rate limits and billing controls.
The lower effective limit wins. Reaching the owner monthly stop amount must disable
the provider/affected features; it must not increase limits automatically.

## 8. Tiny-beta cost estimate

As at the assessment date, OpenAI lists standard short-context
`gpt-5.6-terra` pricing at **USD 2 per million input tokens** and **USD 12 per million
output tokens**. A conservative full interaction analysis with eight transcript
extractors plus two composers is roughly 110,000 input and 10,000 output tokens, or
about **USD 0.34** before retries. Actual transcripts and outputs should usually be
smaller.

| Illustrative monthly use | Approximate provider cost | Planning interpretation |
| --- | ---: | --- |
| 10 full interaction analyses | about USD 3–5 | Small supervised start |
| 50 full interaction analyses | about USD 17–25 | Includes modest debrief/retry allowance |
| Recommended owner alert-and-stop | **AUD 50/month** | Disable external AI and review; not an automatic recharge authority |

At the maximum 75 attempts every day, a worst-case input/output assumption could
exceed AUD 250/month. That is why the daily quota is not the budget. Record actual
token spend weekly and keep the project limit below the owner's maximum.

## 9. Privacy/data-processing decision Kevin must approve

OpenAI states that API data is not used to train or improve its models by default
unless the customer opts in. Standard `/v1/responses` abuse-monitoring retention is
up to 30 days. RevenueOS uses `store=false`, which avoids ordinary Responses
application-state storage, but it is **not** a Zero Data Retention guarantee and does
not remove standard abuse-monitoring processing.

OpenAI currently lists an Australian endpoint for regional **storage**, not regional
**processing**. Access to non-US data residency requires OpenAI approval for Modified
Abuse Monitoring or Zero Data Retention and a retention amendment. OpenAI says that
when a region lacks regional processing it may process and temporarily store customer
content outside that region. Therefore the first-partner disclosure must say that
OpenAI processing can leave Australia. Do not claim Australian AI data residency.

Kevin, the legal/privacy approver and the named partner must accept:

1. the exact features, content categories and sales-intelligence purpose above;
2. the OpenAI terms/DPA, standard retention or separately approved controls,
   subprocessors and cross-border disclosure;
3. no training/data-sharing opt-in;
4. the model, quotas, monthly stop amount, quality limitations and human-review duty;
5. the partner's authority to provide the transcript/debrief content; and
6. immediate rollback by stopping claims, disabling the affected features/provider
   and revoking the key where required.

## 10. Account/project/settings eventually required

After—not before—approval, create or identify a production OpenAI API organisation
and a dedicated RevenueOS private-beta project. Limit authorised human operators,
use a project service account/restricted key, disable all voluntary data sharing,
record the contracting entity and DPA, configure spend alerts/limits, and monitor
project usage. Choose one of these explicit locations:

- **Global processing (simplest):** accept and disclose cross-border processing and
  standard retention; or
- **Australian regional storage:** only if OpenAI approves the required retention
  controls/amendment and the exact endpoint/model smoke test passes; still disclose
  that inference processing is not in Australia. Eligible regional endpoints add a
  10% pricing uplift for models released after 5 March 2026.

Do not enable background mode, tools, audio/visual/evidence providers, file uploads or
another model. Capture configuration evidence without recording the key.

## Owner decision

Select exactly one in the [owner approval block](owner-approval-block.md):

> **APPROVE OPENAI FOR SUPERVISED REAL-DATA BETA**
>
> **DO NOT APPROVE YET**

Until a dated approval and the AI gate both pass, the answer is **DO NOT APPROVE
YET** operationally and the required profile is `NATIVE-NO-EXTERNAL-AI-V1`.

## Official OpenAI sources

- [Data controls, retention and regional processing](https://developers.openai.com/api/docs/guides/your-data)
- [GPT-5.6 Terra model capabilities and price](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

These are time-sensitive. Recheck model availability, pricing and data controls
immediately before approval/setup.
