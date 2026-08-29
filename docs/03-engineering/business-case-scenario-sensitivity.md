# Business Case scenario and sensitivity architecture

A case-version request contains one base input set, zero or one conservative override set, zero or one upside override set and optional one-variable sensitivity. Scenario names are a closed enum. The server validates override keys against `sensitivity_eligible`, applies the approved input validator and calls the same canonical-AST evaluator independently for every result.

The calculation fingerprint covers model-version ID/fingerprint, currency, ordered input provenance/value records, explicit scenario overrides and sensitivity request. An identical calculation reuses the current version; a changed request creates a new immutable version. Sensitivity rows do not enter the base or scenario approval values.

No loop or combinatorial formula is user-controlled. At most three scenarios and five sensitivity values keep evaluation linear and bounded.
