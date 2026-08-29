# Value Model administration

Organisation administrators manage Value Models under **Create → Manage Value Models**. Members can list and use approved versions but cannot create, edit, approve or archive formula definitions.

An administrator defines a bounded name/description, 1–30 typed required inputs, 1–30 deterministic outputs and an optional exact customer disclaimer. The form exposes keys, controlled types/units, bounds, source policy, visible defaults, assumption locks, materiality, scenario eligibility, formula and display precision. It is not a JSON editor or spreadsheet.

Saving validates references, cycles, division policy, unit dimensions, limits and supported syntax. Approval repeats validation and binds an immutable `bounded_decimal_v1` canonical AST and fingerprint. Editing creates a new draft version. Historical cases retain the exact old version; a new case selects the highest approved active version.

Current source policies are:

- `reviewed_manual`: salesperson-reported, user-entered, visible organisation assumption or unknown;
- `customer_or_manual`: typed validated Evidence when available, salesperson-reported or user-entered;
- `approved_org_only`: the exact approved organisation assumption/company value only;
- `public_or_manual`: exact reviewed public values when available, or a manual seller value.

WO-033 deliberately rejects current free-text Evidence and public bands as exact automated inputs because the existing Evidence model has no reviewed typed numeric fact.
