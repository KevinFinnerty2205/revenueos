# Formula parser security

The lexer accepts ASCII lowercase identifiers, decimal literals, whitespace, `+ - * /`, commas and parentheses. The parser recognises only the five allow-listed function names. It never calls `eval`, `exec`, a shell, SQL, JavaScript, Python AST execution or spreadsheet software.

Rejected syntax includes attributes, brackets, strings, comments, semicolons, imports, lambdas, exponent notation/operators, Unicode confusables, unknown functions, unary plus, huge literals, deep nesting and extra tokens. Canonical AST loading independently validates exact object keys, node types, operators, function arity, references, dimensions and limits.

Resource exhaustion is bounded by input/output, character, node, depth, dependency and decimal limits. Division failures produce controlled unavailable/error states. Safe API errors expose codes without formulas, values, stack traces or customer financial content in logs.
