# Business Case integration with RevenueOS Create

Only the current approved immutable Business Case version may be selected in the presentation brief. The case must match the presentation Account; an Opportunity-bound case must also match the selected Opportunity.

The presentation stores the case ID, exact case-version ID and `base` or `all` scenario selection. Generation rebuilds the customer-safe context from that pinned version and uses cautious deterministic wording: “Under the base-case assumptions, the approved model estimates…”. It never says “you will save”.

Create emits `approved_business_case` claims whose source ID is the Business Case version. Customer-facing highlighted outputs, scenario labels, at least one material assumption and the approved disclaimer are prioritised on suitable editable approved template layouts. Raw AST data is never placed on a slide.

The lineage chain is presentation claim → Business Case version → output formula → exact inputs → input sources. Approval and download-grant paths revalidate that the case version remains current/approved and its linked Evidence remains available and fresh. A superseding calculation or source change blocks export with a safe error.
