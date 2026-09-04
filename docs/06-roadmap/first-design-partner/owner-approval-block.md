# RevenueOS first design-partner owner approval

**Instructions:** Kevin completes this block. Do not pre-fill facts, infer approval or
use a recommendation as a selection. Attach/link the dated signed approval in the
restricted launch record. This block authorises only the choices explicitly marked;
it never authorises real customer data by itself.

```text
REVENUEOS FIRST DESIGN PARTNER OWNER APPROVAL

Approval date (Australia/Sydney):
Owner name and role:

1. BUSINESS / LEGAL IDENTITY (OD-01)

Legal/publisher name:
Registered address and jurisdiction:
ABN: [11 digits / NONE]
RevenueOS status: [REGISTERED BUSINESS NAME / PRODUCT BRAND ONLY / UNSURE]

Privacy Notice / Terms / DPA / beta agreement / subprocessor schedule
owner or legal approval reference:
Approver name/role:
Effective/version date:

2. CONTACTS AND HUMAN OWNERS (OD-02)

Support email:
Privacy email:
Security/incident email:
Primary support/incident human and role:
Backup support/incident human and role:
Supervised operating hours and timezone:
Emergency escalation route reference (do not put a secret here):
Support-mail provider:

3. TARGET ENVIRONMENT AND SPEND (OD-03)

Target hosting option:
[AWS-SYD-PRIVATE-BETA-V1 / FLY-SUPABASE-SYD-V1 / NOT APPROVED]

Target application region:
Target database and region:
Target private storage and region:
Target backup storage and region:

Maximum approved monthly platform spend, including hosting, database,
storage, backup, monitoring, Clerk and expected tax: AUD $_____ per month

Clerk plan: [PRO / HOBBY / NOT APPROVED]
Annual Clerk billing approved: [YES / NO / NOT APPLICABLE]

Selected required/conditional subprocessor schedule approved:
[YES / NO]
Subprocessor approval reference:

4. OPENAI REAL-DATA USE (OD-04)

OpenAI decision:
[APPROVE OPENAI FOR SUPERVISED REAL-DATA BETA / DO NOT APPROVE YET]

Approved model: [gpt-5.6-terra / NONE]
Approved OpenAI data location/processing disclosure:
[GLOBAL CROSS-BORDER PROCESSING / AUSTRALIAN REGIONAL STORAGE SUBJECT TO
 OPENAI APPROVAL, WITH CROSS-BORDER PROCESSING / NONE]

No voluntary provider data-sharing/training opt-in: [CONFIRMED / NOT CONFIRMED]
Maximum approved OpenAI beta alert-and-stop amount: AUD $_____ per month
Owner/legal OpenAI approval reference:

5. RETENTION (OD-05)

Private-beta application retention:
[30 DAYS / 90 DAYS / 180 DAYS / MANUAL / NOT APPROVED]

Encrypted backup retention: _____ days
Operational log retention: _____ days

6. FEATURE PROFILE (OD-06)

First partner feature profile:
[NATIVE-AI-REVIEW-V1 / NATIVE-NO-EXTERNAL-AI-V1 / NOT APPROVED]

Create for the partner: [DISABLED / SEPARATELY APPROVED AFTER FILE PROOF]

7. PARTNER / COMMERCIAL BOUNDARY (OD-07)

First-partner selection profile approved: [YES / NO]
First-partner commercial model:
[FREE DESIGN PARTNER / DISCOUNTED PILOT / PAID PILOT / NOT APPROVED]

Approved design-partnership term:
Approved active-user limit:
Additional partner/commercial restrictions:

8. EXECUTION AUTHORITY (OD-08)

APPROVE TARGET ENVIRONMENT SETUP AND SYNTHETIC PROOF:
[YES / NO]

Approved setup operator:
Approved one-off/setup spend, if any: AUD $_____
Approved synthetic OpenAI smoke test if OpenAI above is approved:
[YES / NO / NOT APPLICABLE]

Additional restrictions:

REAL CUSTOMER DATA AUTHORISED BY THIS BLOCK: NO

Real customer data remains prohibited until the exact target proof, owner/legal
pack, named-partner agreement/data authority and final launch go/no-go all pass.

Owner signature/record reference:
```

## Consistency checks before accepting the block

- `NATIVE-AI-REVIEW-V1` is invalid unless OpenAI is approved, an OpenAI stop amount
  is present and the AI gate later passes.
- A target option is invalid without exact Sydney locations and a non-zero platform
  cap. `NOT APPROVED` or `APPROVE TARGET ENVIRONMENT SETUP: NO` means no setup.
- Target setup approval allows synthetic proof only. It does not create authority to
  upload, preview or process partner data.
- Annual billing, a provider account, a paid smoke test or any spend outside the
  explicit amounts requires separate approval.
- Binding legal documents and identity facts require owner/legal approval; Codex may
  record them but cannot originate approval.
