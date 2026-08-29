from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation, localcontext
from typing import Literal, cast

ENGINE_VERSION = "bounded_decimal_v1"
MAX_FORMULA_LENGTH = 500
MAX_AST_NODES = 100
MAX_AST_DEPTH = 20
MAX_DECIMAL_DIGITS = 28
MAX_ABSOLUTE_VALUE = Decimal("1e24")

Unit = Literal[
    "count",
    "currency",
    "currency_per_year",
    "currency_per_hour",
    "percentage",
    "hours",
    "hours_per_year",
    "minutes",
    "days",
    "months",
    "years",
    "dimensionless",
]


class FormulaError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class NumberNode:
    value: str


@dataclass(frozen=True)
class ReferenceNode:
    key: str


@dataclass(frozen=True)
class UnaryNode:
    operator: Literal["-"]
    operand: FormulaNode


@dataclass(frozen=True)
class BinaryNode:
    operator: Literal["+", "-", "*", "/"]
    left: FormulaNode
    right: FormulaNode


@dataclass(frozen=True)
class FunctionNode:
    name: Literal["min", "max", "safe_divide", "positive_divide", "payback_months"]
    arguments: tuple[FormulaNode, ...]


type FormulaNode = NumberNode | ReferenceNode | UnaryNode | BinaryNode | FunctionNode


@dataclass(frozen=True)
class ParsedFormula:
    source: str
    ast: FormulaNode
    references: frozenset[str]
    node_count: int
    depth: int

    def canonical_json(self) -> dict[str, object]:
        return _node_json(self.ast)


@dataclass(frozen=True)
class InputSpec:
    key: str
    unit: Unit
    minimum: Decimal | None = None
    maximum: Decimal | None = None


@dataclass(frozen=True)
class OutputSpec:
    key: str
    unit: Unit
    formula: str
    display_precision: int


@dataclass(frozen=True)
class ValidatedOutput:
    key: str
    unit: Unit
    formula: ParsedFormula
    display_precision: int
    input_dependencies: tuple[str, ...]
    output_dependencies: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedModel:
    inputs: tuple[InputSpec, ...]
    outputs: tuple[ValidatedOutput, ...]
    canonical_ast: dict[str, object]
    fingerprint: str


@dataclass(frozen=True)
class CalculatedOutput:
    key: str
    unit: Unit
    exact_value: str | None
    display_value: str | None
    unavailable_reason: Literal["division_by_zero", "non_positive_denominator", "dependency_unavailable"] | None
    formula: str
    canonical_ast: dict[str, object]
    input_dependencies: tuple[str, ...]
    output_dependencies: tuple[str, ...]


@dataclass(frozen=True)
class CalculationResult:
    outputs: tuple[CalculatedOutput, ...]


@dataclass(frozen=True)
class _Token:
    kind: Literal["number", "identifier", "operator", "left_paren", "right_paren", "comma", "eof"]
    value: str
    position: int


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens = _tokenise(source)
        self.index = 0
        self.nesting = 0
        self.max_nesting = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def current_kind(self) -> str:
        return self.current.kind

    def advance(self) -> _Token:
        value = self.current
        self.index += 1
        return value

    def parse(self) -> FormulaNode:
        node = self.expression()
        if self.current.kind != "eof":
            raise FormulaError("unexpected_token", f"Unexpected token at position {self.current.position + 1}.")
        return node

    def expression(self) -> FormulaNode:
        node = self.term()
        while self.current.kind == "operator" and self.current.value in {"+", "-"}:
            operator = self.advance().value
            node = BinaryNode(operator=operator, left=node, right=self.term())  # type: ignore[arg-type]
        return node

    def term(self) -> FormulaNode:
        node = self.unary()
        while self.current.kind == "operator" and self.current.value in {"*", "/"}:
            operator = self.advance().value
            node = BinaryNode(operator=operator, left=node, right=self.unary())  # type: ignore[arg-type]
        return node

    def unary(self) -> FormulaNode:
        if self.current.kind == "operator" and self.current.value == "-":
            self.advance()
            return UnaryNode(operator="-", operand=self.unary())
        if self.current.kind == "operator" and self.current.value == "+":
            raise FormulaError("unsupported_operator", "Unary plus is not supported.")
        return self.primary()

    def primary(self) -> FormulaNode:
        token = self.current
        if token.kind == "number":
            self.advance()
            _bounded_decimal(token.value)
            return NumberNode(value=token.value)
        if token.kind == "identifier":
            name = self.advance().value
            if self.current_kind() != "left_paren":
                return ReferenceNode(key=name)
            if name not in {"min", "max", "safe_divide", "positive_divide", "payback_months"}:
                raise FormulaError("unsupported_function", f"Function `{name}` is not supported.")
            self.advance()
            self._enter_nesting()
            arguments: list[FormulaNode] = []
            if self.current_kind() != "right_paren":
                arguments.append(self.expression())
                while self.current_kind() == "comma":
                    self.advance()
                    arguments.append(self.expression())
            if self.current_kind() != "right_paren":
                raise FormulaError("missing_parenthesis", "A closing parenthesis is required.")
            self.advance()
            self.nesting -= 1
            if name in {"safe_divide", "positive_divide", "payback_months"} and len(arguments) != 2:
                raise FormulaError("invalid_function_arity", f"{name} requires exactly two values.")
            if name in {"min", "max"} and not 2 <= len(arguments) <= 10:
                raise FormulaError("invalid_function_arity", f"{name} requires between two and ten values.")
            return FunctionNode(name=name, arguments=tuple(arguments))  # type: ignore[arg-type]
        if token.kind == "left_paren":
            self.advance()
            self._enter_nesting()
            node = self.expression()
            if self.current.kind != "right_paren":
                raise FormulaError("missing_parenthesis", "A closing parenthesis is required.")
            self.advance()
            self.nesting -= 1
            return node
        raise FormulaError("expected_value", f"A number or input is required at position {token.position + 1}.")

    def _enter_nesting(self) -> None:
        self.nesting += 1
        self.max_nesting = max(self.max_nesting, self.nesting)
        if self.max_nesting > MAX_AST_DEPTH:
            raise FormulaError("formula_too_deep", f"A formula may be at most {MAX_AST_DEPTH} levels deep.")


def parse_formula(source: str) -> ParsedFormula:
    if not source or len(source) > MAX_FORMULA_LENGTH:
        raise FormulaError("formula_length", f"Formulas must contain between 1 and {MAX_FORMULA_LENGTH} characters.")
    if not source.isascii():
        raise FormulaError("formula_ascii_only", "Formulas use ASCII identifiers and operators only.")
    parser = _Parser(source)
    ast = parser.parse()
    node_count, depth = _measure(ast)
    depth = max(depth, parser.max_nesting)
    if node_count > MAX_AST_NODES:
        raise FormulaError("formula_too_complex", f"A formula may contain at most {MAX_AST_NODES} nodes.")
    if depth > MAX_AST_DEPTH:
        raise FormulaError("formula_too_deep", f"A formula may be at most {MAX_AST_DEPTH} levels deep.")
    return ParsedFormula(
        source=source.strip(),
        ast=ast,
        references=frozenset(_references(ast)),
        node_count=node_count,
        depth=depth,
    )


def validate_model(inputs: list[InputSpec], outputs: list[OutputSpec]) -> ValidatedModel:
    if not 1 <= len(inputs) <= 30:
        raise FormulaError("input_count", "A value model requires between 1 and 30 inputs.")
    if not 1 <= len(outputs) <= 30:
        raise FormulaError("output_count", "A value model requires between 1 and 30 outputs.")
    input_by_key = _unique_by_key(inputs, "input")
    output_by_key = _unique_by_key(outputs, "output")
    overlap = set(input_by_key) & set(output_by_key)
    if overlap:
        raise FormulaError("duplicate_key", f"`{sorted(overlap)[0]}` cannot be both an input and an output.")

    parsed = {item.key: parse_formula(item.formula) for item in outputs}
    known = set(input_by_key) | set(output_by_key)
    for key, formula in parsed.items():
        unknown = formula.references - known
        if unknown:
            raise FormulaError("unknown_reference", f"Output `{key}` references unknown value `{sorted(unknown)[0]}`.")

    ordered_keys = _topological_order(parsed, set(input_by_key))
    dimensions: dict[str, tuple[int, int]] = {key: _unit_dimension(item.unit) for key, item in input_by_key.items()}
    transitive_inputs: dict[str, set[str]] = {}
    validated: list[ValidatedOutput] = []
    for key in ordered_keys:
        item = output_by_key[key]
        formula = parsed[key]
        dimension = _infer_dimension(formula.ast, dimensions, input_by_key)
        expected = _unit_dimension(item.unit)
        if dimension != expected:
            raise FormulaError(
                "output_unit_mismatch",
                f"Output `{key}` has unit `{item.unit}` but its formula produces an incompatible unit.",
            )
        dimensions[key] = dimension
        input_dependencies = set(formula.references & set(input_by_key))
        for dependency in formula.references & set(output_by_key):
            input_dependencies.update(transitive_inputs[dependency])
        transitive_inputs[key] = input_dependencies
        validated.append(
            ValidatedOutput(
                key=key,
                unit=item.unit,
                formula=formula,
                display_precision=item.display_precision,
                input_dependencies=tuple(sorted(input_dependencies)),
                output_dependencies=tuple(sorted(formula.references & set(output_by_key))),
            )
        )

    canonical_ast: dict[str, object] = {
        "engineVersion": ENGINE_VERSION,
        "outputs": [
            {
                "key": item.key,
                "unit": item.unit,
                "displayPrecision": item.display_precision,
                "formula": item.formula.canonical_json(),
            }
            for item in validated
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical_ast, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ValidatedModel(
        inputs=tuple(inputs),
        outputs=tuple(validated),
        canonical_ast=canonical_ast,
        fingerprint=fingerprint,
    )


def load_validated_model(
    inputs: list[InputSpec],
    outputs: list[OutputSpec],
    canonical_ast: dict[str, object],
) -> ValidatedModel:
    """Load an approved v1 AST without reparsing its display expression."""

    if set(canonical_ast) != {"engineVersion", "outputs"} or canonical_ast.get("engineVersion") != ENGINE_VERSION:
        raise FormulaError("canonical_ast_invalid", "The stored formula AST is not a supported engine document.")
    raw_outputs = canonical_ast.get("outputs")
    if not isinstance(raw_outputs, list) or not 1 <= len(raw_outputs) <= 30:
        raise FormulaError("canonical_ast_invalid", "The stored formula AST has an invalid output list.")
    input_by_key = _unique_by_key(inputs, "input")
    output_by_key = _unique_by_key(outputs, "output")
    if len(input_by_key) > 30 or set(input_by_key) & set(output_by_key):
        raise FormulaError("canonical_ast_invalid", "The stored formula AST has invalid model keys.")
    dimensions = {key: _unit_dimension(item.unit) for key, item in input_by_key.items()}
    transitive_inputs: dict[str, set[str]] = {}
    validated: list[ValidatedOutput] = []
    seen: set[str] = set()
    for raw in raw_outputs:
        if not isinstance(raw, dict) or set(raw) != {"key", "unit", "displayPrecision", "formula"}:
            raise FormulaError("canonical_ast_invalid", "A stored output AST is invalid.")
        key = raw.get("key")
        unit = raw.get("unit")
        precision = raw.get("displayPrecision")
        raw_formula = raw.get("formula")
        if not isinstance(key, str) or key in seen or key not in output_by_key:
            raise FormulaError("canonical_ast_invalid", "A stored output key is invalid.")
        output = output_by_key[key]
        if unit != output.unit or precision != output.display_precision or not isinstance(raw_formula, dict):
            raise FormulaError("canonical_ast_invalid", f"Stored output `{key}` does not match its definition.")
        ast = _node_from_json(raw_formula)
        node_count, depth = _measure(ast)
        if node_count > MAX_AST_NODES or depth > MAX_AST_DEPTH:
            raise FormulaError("canonical_ast_invalid", f"Stored output `{key}` exceeds formula limits.")
        references = frozenset(_references(ast))
        if references - set(dimensions):
            raise FormulaError("canonical_ast_invalid", f"Stored output `{key}` has an unknown or forward reference.")
        dimension = _infer_dimension(ast, dimensions, input_by_key)
        if dimension != _unit_dimension(output.unit):
            raise FormulaError("canonical_ast_invalid", f"Stored output `{key}` has an incompatible unit.")
        dimensions[key] = dimension
        seen.add(key)
        input_dependencies = set(references & set(input_by_key))
        for dependency in references & set(output_by_key):
            input_dependencies.update(transitive_inputs[dependency])
        transitive_inputs[key] = input_dependencies
        validated.append(
            ValidatedOutput(
                key=key,
                unit=output.unit,
                formula=ParsedFormula(
                    source=output.formula,
                    ast=ast,
                    references=references,
                    node_count=node_count,
                    depth=depth,
                ),
                display_precision=output.display_precision,
                input_dependencies=tuple(sorted(input_dependencies)),
                output_dependencies=tuple(sorted(references & set(output_by_key))),
            )
        )
    if seen != set(output_by_key):
        raise FormulaError("canonical_ast_invalid", "The stored formula AST is missing an output.")
    fingerprint = hashlib.sha256(
        json.dumps(canonical_ast, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ValidatedModel(
        inputs=tuple(inputs),
        outputs=tuple(validated),
        canonical_ast=canonical_ast,
        fingerprint=fingerprint,
    )


def calculate(model: ValidatedModel, values: dict[str, Decimal]) -> CalculationResult:
    expected = {item.key for item in model.inputs}
    missing = expected - set(values)
    unknown = set(values) - expected
    if missing:
        raise FormulaError("missing_input", f"Required input `{sorted(missing)[0]}` is missing.")
    if unknown:
        raise FormulaError("unknown_input", f"Input `{sorted(unknown)[0]}` is not part of this value model.")

    environment: dict[str, Decimal | None] = {}
    for input_item in model.inputs:
        value = _bounded_decimal(values[input_item.key])
        if input_item.minimum is not None and value < input_item.minimum:
            raise FormulaError("input_below_minimum", f"Input `{input_item.key}` is below its approved minimum.")
        if input_item.maximum is not None and value > input_item.maximum:
            raise FormulaError("input_above_maximum", f"Input `{input_item.key}` is above its approved maximum.")
        environment[input_item.key] = value / Decimal("100") if input_item.unit == "percentage" else value

    calculated: list[CalculatedOutput] = []
    for output_item in model.outputs:
        output_value: Decimal | None
        try:
            output_value = _evaluate(output_item.formula.ast, environment)
            unavailable_reason = None
        except _Unavailable as exc:
            output_value = None
            unavailable_reason = exc.reason
        environment[output_item.key] = output_value
        calculated.append(
            CalculatedOutput(
                key=output_item.key,
                unit=output_item.unit,
                exact_value=_decimal_string(output_value) if output_value is not None else None,
                display_value=(
                    _rounded_string(output_value, output_item.display_precision) if output_value is not None else None
                ),
                unavailable_reason=unavailable_reason,
                formula=output_item.formula.source,
                canonical_ast=output_item.formula.canonical_json(),
                input_dependencies=output_item.input_dependencies,
                output_dependencies=output_item.output_dependencies,
            )
        )
    return CalculationResult(outputs=tuple(calculated))


class _Unavailable(Exception):
    def __init__(
        self,
        reason: Literal["division_by_zero", "non_positive_denominator", "dependency_unavailable"],
    ) -> None:
        self.reason = reason


def _evaluate(node: FormulaNode, environment: dict[str, Decimal | None]) -> Decimal:
    with localcontext() as context:
        context.prec = 38
        if isinstance(node, NumberNode):
            return _bounded_decimal(node.value)
        if isinstance(node, ReferenceNode):
            value = environment[node.key]
            if value is None:
                raise _Unavailable("dependency_unavailable")
            return value
        if isinstance(node, UnaryNode):
            return _bounded_decimal(-_evaluate(node.operand, environment))
        if isinstance(node, BinaryNode):
            left = _evaluate(node.left, environment)
            right = _evaluate(node.right, environment)
            try:
                if node.operator == "+":
                    return _bounded_decimal(left + right)
                if node.operator == "-":
                    return _bounded_decimal(left - right)
                if node.operator == "*":
                    return _bounded_decimal(left * right)
                if right == 0:
                    raise _Unavailable("division_by_zero")
                return _bounded_decimal(left / right)
            except (DivisionByZero, InvalidOperation) as exc:
                raise FormulaError("calculation_invalid", "The formula produced an invalid decimal result.") from exc
        arguments = [_evaluate(argument, environment) for argument in node.arguments]
        if node.name == "min":
            return min(arguments)
        if node.name == "max":
            return max(arguments)
        numerator, denominator = arguments
        if denominator == 0:
            raise _Unavailable("division_by_zero")
        if node.name in {"positive_divide", "payback_months"} and denominator <= 0:
            raise _Unavailable("non_positive_denominator")
        if node.name == "payback_months":
            return _bounded_decimal(numerator * Decimal("12") / denominator)
        return _bounded_decimal(numerator / denominator)


def _infer_dimension(
    node: FormulaNode,
    dimensions: dict[str, tuple[int, int]],
    inputs: dict[str, InputSpec],
) -> tuple[int, int]:
    if isinstance(node, NumberNode):
        return (0, 0)
    if isinstance(node, ReferenceNode):
        return dimensions[node.key]
    if isinstance(node, UnaryNode):
        return _infer_dimension(node.operand, dimensions, inputs)
    if isinstance(node, BinaryNode):
        left = _infer_dimension(node.left, dimensions, inputs)
        right = _infer_dimension(node.right, dimensions, inputs)
        if node.operator in {"+", "-"}:
            if left != right:
                raise FormulaError("incompatible_units", "Addition and subtraction require compatible units.")
            return left
        if node.operator == "*":
            return (left[0] + right[0], left[1] + right[1])
        if not _denominator_excludes_zero(node.right, inputs):
            raise FormulaError(
                "unsafe_division",
                "Division requires a non-zero constant or input bound; use safe_divide or positive_divide otherwise.",
            )
        return (left[0] - right[0], left[1] - right[1])
    argument_dimensions = [_infer_dimension(argument, dimensions, inputs) for argument in node.arguments]
    if node.name in {"min", "max"}:
        if len(set(argument_dimensions)) != 1:
            raise FormulaError("incompatible_units", f"{node.name} requires compatible units.")
        return argument_dimensions[0]
    if node.name == "payback_months":
        if argument_dimensions[0] != (1, 0) or argument_dimensions[1] != (1, 0):
            raise FormulaError("incompatible_units", "payback_months requires two currency values.")
        return (0, 1)
    return (
        argument_dimensions[0][0] - argument_dimensions[1][0],
        argument_dimensions[0][1] - argument_dimensions[1][1],
    )


def _denominator_excludes_zero(node: FormulaNode, inputs: dict[str, InputSpec]) -> bool:
    if isinstance(node, NumberNode):
        return Decimal(node.value) != 0
    if isinstance(node, ReferenceNode) and node.key in inputs:
        item = inputs[node.key]
        return bool((item.minimum is not None and item.minimum > 0) or (item.maximum is not None and item.maximum < 0))
    return False


def _unit_dimension(unit: Unit) -> tuple[int, int]:
    if unit in {"currency", "currency_per_year"}:
        return (1, 0)
    if unit == "currency_per_hour":
        return (1, -1)
    if unit in {"hours", "hours_per_year", "minutes", "days", "months", "years"}:
        return (0, 1)
    return (0, 0)


def _topological_order(parsed: dict[str, ParsedFormula], input_keys: set[str]) -> list[str]:
    remaining = set(parsed)
    resolved = set(input_keys)
    ordered: list[str] = []
    while remaining:
        ready = sorted(key for key in remaining if parsed[key].references <= resolved)
        if not ready:
            raise FormulaError("cyclic_output_reference", "Output formulas contain a cycle.")
        for key in ready:
            ordered.append(key)
            resolved.add(key)
            remaining.remove(key)
    return ordered


def _unique_by_key[T: InputSpec | OutputSpec](items: list[T], label: str) -> dict[str, T]:
    values: dict[str, T] = {}
    for item in items:
        if item.key in values:
            raise FormulaError("duplicate_key", f"Duplicate {label} key `{item.key}`.")
        values[item.key] = item
    return values


def _tokenise(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character in " \t\r\n":
            index += 1
            continue
        if character.isdigit():
            start = index
            while index < len(source) and source[index].isdigit():
                index += 1
            if index < len(source) and source[index] == ".":
                index += 1
                if index >= len(source) or not source[index].isdigit():
                    raise FormulaError("invalid_number", f"Invalid decimal at position {start + 1}.")
                while index < len(source) and source[index].isdigit():
                    index += 1
            value = source[start:index]
            if len(value.replace(".", "")) > MAX_DECIMAL_DIGITS:
                raise FormulaError("number_too_large", "Numeric literals may contain at most 28 digits.")
            tokens.append(_Token("number", value, start))
            continue
        if "a" <= character <= "z" or character == "_":
            start = index
            index += 1
            while index < len(source) and (
                "a" <= source[index] <= "z" or source[index].isdigit() or source[index] == "_"
            ):
                index += 1
            value = source[start:index]
            if len(value) > 64:
                raise FormulaError("identifier_length", "Formula identifiers may contain at most 64 characters.")
            tokens.append(_Token("identifier", value, start))
            continue
        token_kind: dict[
            str,
            Literal["operator", "left_paren", "right_paren", "comma"],
        ] = {
            "+": "operator",
            "-": "operator",
            "*": "operator",
            "/": "operator",
            "(": "left_paren",
            ")": "right_paren",
            ",": "comma",
        }
        if character not in token_kind:
            raise FormulaError("unsupported_character", f"Unsupported character at position {index + 1}.")
        tokens.append(_Token(token_kind[character], character, index))
        index += 1
    tokens.append(_Token("eof", "", len(source)))
    return tokens


def _measure(node: FormulaNode) -> tuple[int, int]:
    if isinstance(node, (NumberNode, ReferenceNode)):
        return (1, 1)
    if isinstance(node, UnaryNode):
        children = [node.operand]
    elif isinstance(node, BinaryNode):
        children = [node.left, node.right]
    else:
        children = list(node.arguments)
    measurements = [_measure(child) for child in children]
    return (1 + sum(item[0] for item in measurements), 1 + max(item[1] for item in measurements))


def _references(node: FormulaNode) -> set[str]:
    if isinstance(node, ReferenceNode):
        return {node.key}
    if isinstance(node, NumberNode):
        return set()
    if isinstance(node, UnaryNode):
        return _references(node.operand)
    if isinstance(node, BinaryNode):
        children = [node.left, node.right]
    else:
        children = list(node.arguments)
    values: set[str] = set()
    for child in children:
        values.update(_references(child))
    return values


def _node_json(node: FormulaNode) -> dict[str, object]:
    if isinstance(node, NumberNode):
        return {"type": "constant", "value": node.value}
    if isinstance(node, ReferenceNode):
        return {"type": "reference", "key": node.key}
    if isinstance(node, UnaryNode):
        return {"type": "negate", "operand": _node_json(node.operand)}
    if isinstance(node, BinaryNode):
        return {
            "type": "binary",
            "operator": node.operator,
            "left": _node_json(node.left),
            "right": _node_json(node.right),
        }
    return {
        "type": "function",
        "name": node.name,
        "arguments": [_node_json(argument) for argument in node.arguments],
    }


def _node_from_json(value: dict[str, object]) -> FormulaNode:
    node_type = value.get("type")
    if node_type == "constant" and set(value) == {"type", "value"} and isinstance(value.get("value"), str):
        number = value["value"]
        assert isinstance(number, str)
        _bounded_decimal(number)
        if len(number.replace(".", "").lstrip("-")) > MAX_DECIMAL_DIGITS:
            raise FormulaError("canonical_ast_invalid", "A stored constant exceeds formula limits.")
        return NumberNode(value=number)
    if node_type == "reference" and set(value) == {"type", "key"} and isinstance(value.get("key"), str):
        key = value["key"]
        assert isinstance(key, str)
        if (
            not key
            or len(key) > 64
            or not key.isascii()
            or not all(character == "_" or character.isdigit() or "a" <= character <= "z" for character in key)
        ):
            raise FormulaError("canonical_ast_invalid", "A stored reference is invalid.")
        return ReferenceNode(key=key)
    if node_type == "negate" and set(value) == {"type", "operand"} and isinstance(value.get("operand"), dict):
        return UnaryNode(operator="-", operand=_node_from_json(cast(dict[str, object], value["operand"])))
    if (
        node_type == "binary"
        and set(value) == {"type", "operator", "left", "right"}
        and value.get("operator") in {"+", "-", "*", "/"}
        and isinstance(value.get("left"), dict)
        and isinstance(value.get("right"), dict)
    ):
        operator = cast(Literal["+", "-", "*", "/"], value["operator"])
        return BinaryNode(
            operator=operator,
            left=_node_from_json(cast(dict[str, object], value["left"])),
            right=_node_from_json(cast(dict[str, object], value["right"])),
        )
    if (
        node_type == "function"
        and set(value) == {"type", "name", "arguments"}
        and value.get("name") in {"min", "max", "safe_divide", "positive_divide", "payback_months"}
        and isinstance(value.get("arguments"), list)
    ):
        name = cast(
            Literal["min", "max", "safe_divide", "positive_divide", "payback_months"],
            value["name"],
        )
        raw_arguments = cast(list[object], value["arguments"])
        if not all(isinstance(argument, dict) for argument in raw_arguments):
            raise FormulaError("canonical_ast_invalid", "A stored function argument is invalid.")
        arguments = tuple(_node_from_json(cast(dict[str, object], argument)) for argument in raw_arguments)
        if name in {"safe_divide", "positive_divide", "payback_months"} and len(arguments) != 2:
            raise FormulaError("canonical_ast_invalid", "A stored function has invalid arity.")
        if name in {"min", "max"} and not 2 <= len(arguments) <= 10:
            raise FormulaError("canonical_ast_invalid", "A stored function has invalid arity.")
        return FunctionNode(name=name, arguments=arguments)
    raise FormulaError("canonical_ast_invalid", "A stored formula node is invalid.")


def _bounded_decimal(value: Decimal | str) -> Decimal:
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(value)
    except InvalidOperation as exc:
        raise FormulaError("invalid_decimal", "A value is not a valid decimal.") from exc
    if not decimal.is_finite() or abs(decimal) > MAX_ABSOLUTE_VALUE:
        raise FormulaError("decimal_out_of_range", "A decimal value is outside the supported range.")
    return decimal


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")


def _rounded_string(value: Decimal, precision: int) -> str:
    quantum = Decimal(1).scaleb(-precision)
    return format(value.quantize(quantum, rounding=ROUND_HALF_UP), f".{precision}f")
