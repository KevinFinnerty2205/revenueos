# Prospect-to-Contact promotion guide

Promotion is the only boundary crossing from Prospect Person research into Core.

The service first requires the parent researched company to be explicitly promoted to a canonical Company and requires a usable person research run. It then searches within the same tenant and company for exact business-email matches and same-name/company possibilities.

If a possible Contact exists, the API returns a conflict until the seller chooses **Attach research** or **Create separate Contact**. Attach preserves every canonical Contact field. Create adds first/last name, public current title and a permitted current business email; unknown email is stored as null. A profile value populates the canonical `linkedin_url` field only when it is actually a permitted LinkedIn URL—generic company or conference profiles remain Prospect research. Field-level provenance is created in the same transaction.

Promotion updates the Prospect Person with Contact, actor and timestamp. It creates no Opportunity, stakeholder, Evidence, Methodology answer, Revenue Brain fact, task, action or outreach. Refresh remains one-way research: it cannot silently update the Contact.

Deleting the Prospect Person removes research and promotion linkage but preserves the Contact. The UI warns about that distinction. Canonical Contact deletion remains a separate Core operation.

WO-034 additionally appends field-level CRM creation history with source
`prospect_promotion` in the same transaction. This makes the origin readable without
changing the existing field-source trust model, and native CRM mode does not push
the promoted Contact to HubSpot.
