# Deterministic formula engine

`revenueos/value_model_engine.py` implements `bounded_decimal_v1`. It uses Python `Decimal` with precision 38, no binary float, no network, time, randomness or provider. Intermediate values are not display-rounded. Exact decimal text and per-output half-up display rounding are stored.

Approval parses the expression into a canonical AST, validates the dependency DAG and dimensions, and stores both the original display expression and AST. Calculation verifies the definition+AST+engine fingerprint and loads the canonical AST directly. It does not reparse the display expression, so historical v1 semantics cannot change silently with a future parser.

Limits are 500 formula characters, 100 AST nodes, depth 20, 28 literal digits and absolute values no larger than `1e24`. Models have at most 30 inputs/outputs. Missing/unknown/out-of-bound inputs fail closed.

Supported functions are `min`, `max`, `safe_divide`, `positive_divide` and `payback_months`. Plain `/` is accepted only when approved bounds prove a non-zero denominator. `payback_months` returns unavailable for a non-positive benefit rather than Infinity or a misleading negative duration.
