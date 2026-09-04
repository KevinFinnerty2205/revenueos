# Legal and owner approval checklist

Status: **OWNER APPROVAL REQUIRED** for every applicable launch row. Approved contact
addresses are recorded below, but they do not complete the remaining owner, process
or legal approvals. This is a blocking evidence template, not legal advice,
compliance certification or a substitute for qualified counsel.

The repository contains technical privacy/security guidance and a product data notice mechanism. It does **not** contain an approved Privacy Policy/Notice, Terms of Use, DPA, beta agreement or subprocessor schedule. Do not invent or infer approval from code, a preflight flag or a document draft.

## Owner-supplied decisions

| Item                               | Owner must provide                                                                                                                                                                        | Current status                                   |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Publisher/legal entity             | Exact contracting/publishing entity name, registered address and governing jurisdiction                                                                                                   | **OWNER APPROVAL REQUIRED**                      |
| ABN                                | ABN, or signed reason it is not applicable                                                                                                                                                | **OWNER APPROVAL REQUIRED**                      |
| Privacy notice                     | Approved customer/user-facing notice, version/effective date, public location and counsel/owner approval reference                                                                        | **OWNER APPROVAL REQUIRED**                      |
| Terms                              | Approved beta Terms of Use/service terms, version/effective date and acceptance method                                                                                                    | **OWNER APPROVAL REQUIRED**                      |
| DPA/data-processing terms          | Approved controller/processor roles, instructions, security measures, deletion/return and audit/incident terms                                                                            | **OWNER APPROVAL REQUIRED**                      |
| Support contact                    | `support@oryntela.com.au` is the approved and routing-verified address; hours, response expectations and accountable humans remain required                                               | **ADDRESS APPROVED; OPERATING DETAILS REQUIRED** |
| Privacy contact                    | `support@oryntela.com.au` is the approved and routing-verified private-beta address; accountable person and response process remain required                                              | **ADDRESS APPROVED; PROCESS/OWNER REQUIRED**     |
| Incident/security contact          | `support@oryntela.com.au` is the approved and routing-verified private-beta address; primary/backup humans, escalation path and communication authority remain required                   | **ADDRESS APPROVED; ESCALATION/OWNERS REQUIRED** |
| Hosting/data location              | Exact regions for web, API, workers, PostgreSQL, object storage, backups and logs                                                                                                         | **OWNER APPROVAL REQUIRED**                      |
| Subprocessor list                  | Legal name, purpose, data categories and locations for Clerk, hosting, database, storage, OpenAI if enabled and any monitoring/support provider                                           | **OWNER APPROVAL REQUIRED**                      |
| Backup retention                   | Backup frequency, maximum retention, access, encryption, expiry and restore objectives; explain immutable-copy deletion timing                                                            | **OWNER APPROVAL REQUIRED**                      |
| Production-data retention          | Default/allowed active retention, logs/audits/export expiry, deletion/export process and any lawful-hold limitation                                                                       | **OWNER APPROVAL REQUIRED**                      |
| AI processing/data flow            | Approve disabled AI or the exact OpenAI account/project, models, data categories, `store=false`, provider terms/settings, data use, retention, locations, quotas and disablement fallback | **OWNER APPROVAL REQUIRED**                      |
| Cross-border processing/disclosure | Approved disclosure/transfer position for each provider/region and required contractual safeguards                                                                                        | **OWNER APPROVAL REQUIRED**                      |
| Beta agreement                     | Named partner agreement covering purpose, supported use, supervision, no warranties/SLA beyond approved terms, data boundary, feedback, pause/offboarding and deletion                    | **OWNER APPROVAL REQUIRED**                      |
| Exact partner feature profile      | Signed profile revision, Native CRM mode, enabled sources, Create status, providers, limits and kill-switch owner                                                                         | **OWNER APPROVAL REQUIRED**                      |

## Approval record

For each row record `decision`, `approved value/document`, `version`, `evidence link`, `approver`, `approval date`, `review/expiry date` and `partner-specific restrictions`. Evidence links must be access-controlled; never copy signatures, identity documents, secrets or customer content into repository files.

Before final approval, reconcile customer-facing claims against actual target evidence:

- invite-only supervised beta, not public/commercial availability;
- no Gmail, Apollo, live Prospect research, live sending or autonomous external execution;
- Native CRM is the selected system of record for this partner;
- imported business email is not permission to contact;
- no immediate-erasure claim for immutable backups;
- no data-residency claim that ignores logs, backups, identity or AI subprocessors;
- no regulated-industry, legal-compliance, availability or security certification claim; and
- AI customer-content transfer only when the exact profile is approved and disclosed.

The owner must place the final approval reference in `API_PRIVATE_BETA_LEGAL_APPROVAL_REFERENCE` and the approved support address in `API_PRIVATE_BETA_SUPPORT_EMAIL`. Those values allow preflight to recognise recorded approval; they do not create it.

## Final signatures

```text
Named partner:
Target environment:
Feature/AI profile revision:
Product owner — name/date/decision:
Security/operations owner — name/date/decision:
Legal/privacy approver — name/date/decision:
Partner authorised representative — name/date/decision:
Restrictions/expiry:
```

Until all applicable rows and signatures are complete, the legal/owner gate is `FAIL` for data entry even if the deployment is technically ready.
