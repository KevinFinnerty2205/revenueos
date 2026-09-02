# Native CRM onboarding, import and merge UX

The first-use path is Settings → CRM → Data import. It is an admin-only, desktop-first workflow with no new top-level navigation. Mobile access remains readable but explicitly recommends desktop for mapping.

## Import interaction

The user chooses Accounts, Contacts or Opportunities, downloads an optional plain CSV template and selects one UTF-8 comma-delimited file. The browser checks the 5 MB boundary and displays headers, but the API reparses and authoritatively validates the file. Every source column must map to one supported canonical/custom field or be explicitly ignored. Owners and source stage values require explicit mappings; there is no fuzzy user or stage assignment.

Preview is a true dry run. It shows total/actionable rows and row-number-only states: `new`, `matches_existing`, `possible_duplicate` or `invalid`, with safe issue codes. It states that RevenueOS has not changed records and that imported contact details do not establish permission to contact. The confirm control appears only after the admin acknowledges that only reviewed `new` rows will be created. Confirmation resends the same file and mapping; a hash/snapshot mismatch requires a new preview.

The result reports counts, not a data-quality score. The raw CSV and field values are never written to import metadata, audit logs or an error download. A refresh before confirmation simply requires another preview.

## Merge interaction

An admin opens an Account or Contact and selects **Merge duplicate**. They enter/select the survivor, preview both records, review related-record counts and choose an allowed winner for every conflicting field. A blocked preview explains the exact safe blocker, including incompatible external CRM mapping or relationship/provenance collision.

Confirmation uses the text: “The duplicate record will be archived and its supported relationships moved to the record you keep. Historical provenance will remain. This cannot be undone from RevenueOS.” There is no batch merge, fuzzy auto-merge or user undo.

After success, the source route displays a tombstone and link to the survivor; edit, restore and a second merge are unavailable. Search/current lists exclude the archived duplicate. Contact suppression is never weakened, while Evidence speaker snapshots, sent-message recipient facts and public-research provenance remain historically attributable.

## Accessibility and failure states

Fields have visible labels, summaries use headings and text rather than colour alone, buttons expose disabled/working states, and the flow remains keyboard operable with visible focus. Errors are product-safe and preserve the user's mapping where possible. Stale preview, entitlement, permission and infrastructure failures do not mutate CRM records.
