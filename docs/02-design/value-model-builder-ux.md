# Value Model builder UX

The admin builder is desktop-first but responsive. It provides repeatable input/output cards, not cells or JSON. Each input exposes type, controlled unit, bounds, optional visible default, source policy, materiality, lock state and sensitivity eligibility. Changing type chooses a coherent initial unit/precision that the administrator may refine.

Each output exposes label, controlled unit, display precision, highlight/customer-facing flags and one bounded expression. The UI shows `Output label = expression` and lists the allowed function set. Server validation remains authoritative and returns product-safe errors for unknown references, cycles, unsafe division, incompatible units or hostile syntax.

Approved versions show state/version. **Create new version** copies the current definition into the form; it never mutates the approved row.
