from decimal import Decimal

import pytest

from revenueos.value_model_engine import (
    ENGINE_VERSION,
    FormulaError,
    InputSpec,
    OutputSpec,
    calculate,
    load_validated_model,
    parse_formula,
    validate_model,
)


def summit_model():  # type: ignore[no-untyped-def]
    inputs = [
        InputSpec("access_changes_per_month", "count", Decimal("0"), Decimal("1000000")),
        InputSpec("minutes_current", "minutes", Decimal("0"), Decimal("1440")),
        InputSpec("minutes_future", "minutes", Decimal("0"), Decimal("1440")),
        InputSpec("labour_cost_per_hour", "currency_per_hour", Decimal("0"), Decimal("10000")),
        InputSpec("annual_rekey_cost", "currency_per_year", Decimal("0"), Decimal("1000000000")),
        InputSpec("annual_subscription_cost", "currency_per_year", Decimal("0"), Decimal("1000000000")),
        InputSpec("implementation_cost", "currency", Decimal("0"), Decimal("1000000000")),
    ]
    outputs = [
        OutputSpec(
            "annual_admin_hours_saved",
            "hours_per_year",
            "access_changes_per_month * (minutes_current - minutes_future) / 60 * 12",
            2,
        ),
        OutputSpec(
            "annual_labour_savings",
            "currency_per_year",
            "annual_admin_hours_saved * labour_cost_per_hour",
            2,
        ),
        OutputSpec(
            "annual_gross_benefit",
            "currency_per_year",
            "annual_labour_savings + annual_rekey_cost",
            2,
        ),
        OutputSpec(
            "first_year_total_cost",
            "currency",
            "annual_subscription_cost + implementation_cost",
            2,
        ),
        OutputSpec(
            "first_year_net_benefit",
            "currency",
            "annual_gross_benefit - first_year_total_cost",
            2,
        ),
        OutputSpec(
            "roi_percentage",
            "percentage",
            "safe_divide(first_year_net_benefit, first_year_total_cost) * 100",
            1,
        ),
        OutputSpec(
            "payback_months",
            "months",
            "payback_months(implementation_cost, annual_gross_benefit - annual_subscription_cost)",
            1,
        ),
    ]
    return validate_model(inputs, outputs)


def test_decimal_model_is_deterministic_and_matches_hand_calculation() -> None:
    model = summit_model()
    values = {
        "access_changes_per_month": Decimal("120"),
        "minutes_current": Decimal("15"),
        "minutes_future": Decimal("5"),
        "labour_cost_per_hour": Decimal("55"),
        "annual_rekey_cost": Decimal("30000"),
        "annual_subscription_cost": Decimal("36000"),
        "implementation_cost": Decimal("25000"),
    }

    first = calculate(model, values)
    second = calculate(model, values)

    assert first == second
    assert model.canonical_ast["engineVersion"] == ENGINE_VERSION
    assert len(model.fingerprint) == 64
    outputs = {item.key: item for item in first.outputs}
    assert outputs["annual_admin_hours_saved"].display_value == "240.00"
    assert outputs["annual_labour_savings"].display_value == "13200.00"
    assert outputs["annual_gross_benefit"].display_value == "43200.00"
    assert outputs["first_year_total_cost"].display_value == "61000.00"
    assert outputs["first_year_net_benefit"].display_value == "-17800.00"
    assert outputs["roi_percentage"].display_value == "-29.2"
    assert outputs["payback_months"].display_value == "41.7"
    roi_definition = next(item for item in model.outputs if item.key == "roi_percentage")
    assert set(roi_definition.input_dependencies) == {
        "access_changes_per_month",
        "annual_rekey_cost",
        "annual_subscription_cost",
        "implementation_cost",
        "labour_cost_per_hour",
        "minutes_current",
        "minutes_future",
    }


def test_percentage_inputs_are_explicit_percent_values() -> None:
    model = validate_model(
        [InputSpec("current_cost", "currency", Decimal("0")), InputSpec("reduction", "percentage")],
        [OutputSpec("saving", "currency", "current_cost * reduction", 2)],
    )

    result = calculate(model, {"current_cost": Decimal("1000"), "reduction": Decimal("30")})

    assert result.outputs[0].exact_value == "300.0"
    assert result.outputs[0].display_value == "300.00"


def test_approved_canonical_ast_replays_without_reparsing_display_formula() -> None:
    approved = summit_model()
    loaded = load_validated_model(
        list(approved.inputs),
        [
            OutputSpec(item.key, item.unit, "display text is never executed", item.display_precision)
            for item in approved.outputs
        ],
        approved.canonical_ast,
    )
    values = {
        "access_changes_per_month": Decimal("120"),
        "minutes_current": Decimal("15"),
        "minutes_future": Decimal("5"),
        "labour_cost_per_hour": Decimal("55"),
        "annual_rekey_cost": Decimal("30000"),
        "annual_subscription_cost": Decimal("36000"),
        "implementation_cost": Decimal("25000"),
    }

    replayed = {item.key: item for item in calculate(loaded, values).outputs}
    assert replayed["roi_percentage"].display_value == "-29.2"
    assert loaded.outputs[0].formula.source == "display text is never executed"

    tampered = {**approved.canonical_ast, "unexpected": True}
    with pytest.raises(FormulaError) as error:
        load_validated_model(list(approved.inputs), [], tampered)
    assert error.value.code == "canonical_ast_invalid"


def test_payback_is_unavailable_for_non_positive_benefit() -> None:
    model = validate_model(
        [InputSpec("cost", "currency"), InputSpec("annual_benefit", "currency_per_year")],
        [OutputSpec("payback", "months", "payback_months(cost, annual_benefit)", 1)],
    )

    result = calculate(model, {"cost": Decimal("100"), "annual_benefit": Decimal("-1")})

    assert result.outputs[0].exact_value is None
    assert result.outputs[0].unavailable_reason == "non_positive_denominator"


@pytest.mark.parametrize(
    ("formula", "code"),
    [
        ("__import__('os')", "unsupported_character"),
        ("value.__class__", "unsupported_character"),
        ("lambda value: value", "unsupported_character"),
        ("value; other", "unsupported_character"),
        ("value[0]", "unsupported_character"),
        ("'string'", "unsupported_character"),
        ("value # comment", "unsupported_character"),
        ("value ** 2", "expected_value"),
        ("mіn(value, other)", "formula_ascii_only"),
        ("unknown(value)", "unsupported_function"),
        ("1e100", "unexpected_token"),
    ],
)
def test_executable_or_ambiguous_syntax_is_rejected(formula: str, code: str) -> None:
    with pytest.raises(FormulaError) as error:
        parse_formula(formula)
    assert error.value.code == code


def test_missing_reference_cycle_units_and_unsafe_division_are_rejected() -> None:
    with pytest.raises(FormulaError, match="unknown value"):
        validate_model([InputSpec("hours", "hours")], [OutputSpec("cost", "currency", "missing + 1", 2)])
    with pytest.raises(FormulaError) as cycle:
        validate_model(
            [InputSpec("seed", "count")],
            [OutputSpec("one", "count", "two + seed", 0), OutputSpec("two", "count", "one + seed", 0)],
        )
    assert cycle.value.code == "cyclic_output_reference"
    with pytest.raises(FormulaError) as units:
        validate_model(
            [InputSpec("hours", "hours"), InputSpec("cost", "currency")],
            [OutputSpec("nonsense", "currency", "hours + cost", 2)],
        )
    assert units.value.code == "incompatible_units"
    with pytest.raises(FormulaError) as division:
        validate_model(
            [InputSpec("benefit", "currency"), InputSpec("cost", "currency", Decimal("0"))],
            [OutputSpec("ratio", "percentage", "benefit / cost * 100", 1)],
        )
    assert division.value.code == "unsafe_division"


def test_required_inputs_and_bounds_are_server_authoritative() -> None:
    model = validate_model(
        [InputSpec("count", "count", Decimal("1"), Decimal("10"))],
        [OutputSpec("result", "count", "count * 2", 0)],
    )
    with pytest.raises(FormulaError) as missing:
        calculate(model, {})
    assert missing.value.code == "missing_input"
    with pytest.raises(FormulaError) as too_high:
        calculate(model, {"count": Decimal("11")})
    assert too_high.value.code == "input_above_maximum"


def test_huge_literal_and_depth_are_bounded() -> None:
    with pytest.raises(FormulaError) as huge:
        parse_formula("9" * 29)
    assert huge.value.code == "number_too_large"
    with pytest.raises(FormulaError) as deep:
        parse_formula("(" * 21 + "1" + ")" * 21)
    assert deep.value.code == "formula_too_deep"
