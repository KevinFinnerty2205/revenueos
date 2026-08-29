# Business Case scenarios and sensitivity

The base case is always the explicitly supplied input set. Conservative and upside are optional named sets of explicit input overrides. Only inputs marked sensitivity-eligible by the approved model can be overridden, and all values must satisfy the same type and bounds.

RevenueOS does not infer, randomise or optimise scenario values. Model presets, when configured, are visible suggestions rather than hidden coefficients. Approval covers every included scenario.

One-variable sensitivity accepts two to five explicit values for one approved input. It calculates a separate deterministic row without mutating the base case. There is no confidence interval, probability, Monte Carlo simulation, tornado score or predictive benchmark.

Create defaults to base plus material assumptions. A user may deliberately choose all scenarios; conservative, base and upside are then labelled in the generated claims. Upside-only presentation reuse is not supported in v1.
