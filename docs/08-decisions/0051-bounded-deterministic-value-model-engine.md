# ADR 0051: Bounded deterministic Value Model engine

## Context

Customer-facing ROI must be reproducible and resistant to formula injection. Arbitrary spreadsheet/Python/JavaScript execution would violate that boundary.

## Decision

Use `bounded_decimal_v1`: a strict ASCII expression parser, small allow-listed operator/function set, dimension validation, Decimal evaluation, conservative resource limits and canonical AST execution. Store the human expression for review, but execute only the approved AST after fingerprint verification.

## Alternatives

Excel import, `eval`, a generic rules engine and AI-created formulas were rejected for security, ambiguity and hidden-number risk. A structured-only JSON AST was rejected as the sole authoring interface because administrators need a readable expression.

## Consequences

The engine is intentionally less expressive than a spreadsheet. Advanced finance and conditionals require a future versioned engine/ADR; they cannot be smuggled into v1.
