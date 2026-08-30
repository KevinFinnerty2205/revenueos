# Actual vs Target vs Forecast

| Concept            | Meaning                                                            | Authority                                          |
| ------------------ | ------------------------------------------------------------------ | -------------------------------------------------- |
| Actual             | Won value already realised in the selected calendar period         | `SalesMetricService` metric `won_value` v1         |
| Target             | The chosen matching Won-value goal                                 | `SalesTargetService` and immutable Target revision |
| Seller forecast    | Inclusive Commit/Likely/Possible cases over current eligible deals | Current Opportunity owner                          |
| RevenueOS baseline | Historical expected contribution over covered current deals        | Forecast model v1                                  |

These values are displayed together for comparison but are never merged. Actual does
not remain in open forecast. Targets do not change forecast. Seller categories do not
alter the historical baseline. The baseline does not overwrite seller judgment.

Every request selects one ISO currency. Other currencies are viewed separately; no
FX conversion or cross-currency total exists. Target matching requires the same
period, currency, Pipeline binding and personal/organisation scope.
