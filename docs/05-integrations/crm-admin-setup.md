# CRM administrator setup

An organisation admin can complete the useful minimum HubSpot setup in one guided
flow:

1. Open **Settings → Integrations**.
2. Select **Connect HubSpot**, review the named permissions in HubSpot and return.
3. Confirm the safe account name, **Connected** status and three capabilities.
4. Select **Test connection**.
5. Open **Advanced mapping settings** only when ready.
6. Map the small field set the team will use—normally amount, close date and next
   step. Leave unused fields as **Not mapped**.
7. Keep **Review before update** unless HubSpot must be the source of truth; that
   alternative blocks RevenueOS writes.
8. Map only the RevenueOS stages used by the team to exact HubSpot pipeline stages.

No arbitrary scripts, global import or automatic matching is required. A salesperson
then opens an Opportunity, selects **Connect to CRM record**, searches on demand and
explicitly links one result. Contact updates likewise require an exact existing
Contact link; RevenueOS will not guess, merge or silently create one.

For a prepared CRM Action, the salesperson approves the reviewed Action, selects
**Review CRM update**, verifies CRM current/new values, and selects **Update CRM**.
Approval alone changes nothing. Cancel remains available until confirmation.

If HubSpot changed after preview, RevenueOS asks for a fresh review. If an outcome
is uncertain, use the read-only reconciliation control. Disconnect immediately
blocks new work but does not undo prior CRM updates.

The setup is keyboard-operable, uses labelled selects/search, keeps advanced fields
collapsed, introduces no top-level CRM navigation and does not fetch HubSpot on
ordinary Opportunity render.
