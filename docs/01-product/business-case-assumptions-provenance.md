# Business Case assumptions and provenance

Every input snapshot retains value, calculation value, unit, controlled origin, optional source ID, product-safe source label, assumption/material/customer-facing flags, observed time and freshness. Outputs retain exact and display-rounded values, formula, unit and dependency keys.

Visible labels distinguish:

- **Reported by you**: a seller-entered statement, optionally linked to available Evidence;
- **Entered by you**: manual input without a stronger claim;
- **Approved organisation assumption**: exact approved default, always visible;
- **Approved company data**: an exact supported canonical field, currently Account employee count;
- **Source unknown — review required**: calculation may be reviewed internally but cannot be approved.

`validated_customer_evidence` and `prospect_public` are controlled contract origins, but automatic numeric use is rejected until a reviewed typed exact-number representation exists. A range such as 1,000–5,000 never becomes 3,000. Conflicting text sources therefore cannot be silently resolved into a numeric input; the seller must choose and enter a value with the resulting manual provenance.

Source deletion, expiry or configured maximum age marks an approved case as needing review. The old immutable snapshot remains available for audit, but Create rejects it for new external reuse.
