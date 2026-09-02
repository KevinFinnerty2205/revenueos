# First-partner subprocessor/service register

- **Architecture basis:** recommended `AWS-SYD-PRIVATE-BETA-V1`
- **Status:** **OWNER/LEGAL AND PARTNER APPROVAL REQUIRED**
- **Purpose:** operational inventory and disclosure input; **not legal certification**

Only services in the proposed first-partner boundary appear here. The owner-approved
legal schedule must use the providers' exact contracting entities, current DPAs and
subprocessor lists. Regions describe configured customer-data infrastructure where
known; they are not blanket residency guarantees.

## Required for the base platform

| Service | Purpose | Customer data involved | Region/location where known | Approval required | Current status |
| --- | --- | --- | --- | --- | --- |
| Amazon Web Services (Lightsail, S3, CloudWatch/Route 53/SNS or approved equivalents) | Run web/API/worker; managed PostgreSQL; private active files; encrypted backups; logs, health and alerts | All tenant application records; deliberately supplied transcripts; derived artefacts; private Create files only if separately enabled; encrypted backups; content-minimised operational metadata | RevenueOS data-plane resources configured in AWS Asia Pacific (Sydney), `ap-southeast-2`; AWS control-plane, billing, support and service metadata may have other locations under AWS terms | Owner/legal approval of AWS terms/DPA, exact services, Sydney configuration, access model, subprocessor/cross-border disclosure and spend | **NOT APPROVED; NO ACCOUNT OR RESOURCE CREATED BY THIS WORK** |
| Clerk | Authentication, user/organisation identity, invitation, session verification and role/permission claims | User name/email/identifier, organisation identity/membership, session/security metadata; no RevenueOS transcript/CRM body is intentionally sent | Clerk DPA permits processing where Clerk and its subprocessors maintain facilities; no Australian-residency claim was found | Owner/legal approval of plan, DPA/subprocessors/cross-border handling; production instance/domain/session/MFA policy; partner disclosure | **NOT APPROVED; PRODUCTION INSTANCE NOT PROVEN** |

An owner-selected support mailbox provider becomes required before launch, but the
provider has not been selected. Add it to this section only after OD-02 identifies
the actual service and its locations. Ordinary tickets must remain content-minimised.

## Conditional

| Service | Purpose | Customer data involved | Region/location where known | Approval required | Current status |
| --- | --- | --- | --- | --- | --- |
| OpenAI | Bounded Meeting Intelligence, Next Best Action, Follow-up Email draft and AI Debrief under `NATIVE-AI-REVIEW-V1` | Selected transcript or typed debrief content; validated artefact projections; instructions/schema; request/usage metadata | Global by default. Eligible Australian project endpoint can provide regional storage after approval controls, but not Australian inference processing; content may be processed/temporarily stored outside Australia | Separate OD-04 owner/legal and partner approval of model, DPA/terms, retention/training settings, cross-border flow, quotas and spend; synthetic smoke-test authority | **NOT APPROVED; NO PROJECT/KEY/BILLING/REQUEST** |
| Fly.io | App hosting only if the owner selects alternative `FLY-SUPABASE-SYD-V1` | Customer requests/responses and content-minimised logs handled by web/API/worker | App Machines pinned to `syd`; global edge/control-plane/support considerations remain | Alternative-architecture and legal/subprocessor approval plus spend | **NOT SELECTED** |
| Supabase | PostgreSQL and private object storage only if the owner selects the alternative | Tenant records, transcripts/artefacts, files and seven-day managed backups/logs | Exact primary project region `ap-southeast-2` (Sydney); support/control-plane/subprocessor considerations remain | Alternative-architecture and legal/subprocessor approval plus target RLS/S3/restore proof | **NOT SELECTED** |
| Owner-selected support-mail provider | Receive support, privacy and incident correspondence | Contact identity, request/incident metadata and only the minimum content supplied by the sender | **OWNER INPUT REQUIRED** | OD-02 selection; security/MFA/retention/access and privacy disclosure | **NOT SELECTED** |

If AWS primary is selected, Fly.io and Supabase are removed from the approved launch
schedule. If the alternative is selected, AWS remains only for the separate Sydney
portable backup unless the owner approves a different already-evaluated backup.

## Not yet used

| Service | Potential purpose | Customer data involved now | Region/location | Approval required | Current status |
| --- | --- | --- | --- | --- | --- |
| HubSpot | Future CRM connection | None in the first Native CRM profile | Not assessed for this launch | Separate partner evidence, provider/legal/security proof and work authority | **NOT USED; FLAG OFF** |
| Gmail / Google Workspace API | Future reviewed email delivery/reconciliation | None | Not assessed for this launch | Separate work order and provider/legal/operational approval | **NOT USED; NO GMAIL WORK STARTED** |
| Apollo | Future Prospect provider qualification | None | Not assessed for this launch | Separate work order and provider/legal/source-licence approval | **NOT USED; NO APOLLO WORK STARTED** |

No live meeting, recording, transcription, visual AI, document/email evidence,
payment/billing or external monitoring provider is part of the recommended
first-partner architecture. Do not add a company to the legal schedule merely because
RevenueOS may use it in a future roadmap.

## Approval procedure

1. Owner selects the architecture, support provider and OpenAI decision.
2. Remove non-selected conditional infrastructure providers.
3. Record exact contracting entities, current DPA/terms/subprocessor-list URLs,
   service purpose, data categories, configured region and cross-border limitation.
4. Legal/privacy approver signs the schedule; the named partner acknowledges it
   before data entry.
5. Reopen the gate on a material provider, purpose, data-category or location change.

Reference sources:
[AWS Lightsail](https://aws.amazon.com/lightsail/),
[Clerk DPA](https://clerk.com/legal/dpa),
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data),
[Fly.io regions](https://fly.io/docs/reference/regions/) and
[Supabase regions](https://supabase.com/docs/guides/platform/regions).
