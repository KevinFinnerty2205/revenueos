# Business Case units and currency

One case has one user-confirmed supported ISO 4217 code. Currency values carry that case currency; there is no conversion, FX API or mixed-currency formula. Current accepted codes are the bounded server allow-list including AUD, USD, GBP, EUR, NZD, CAD and SGD.

Controlled units are count, dimensionless, percentage, currency, currency/year, currency/hour, minutes, hours, hours/year, days, months and years. The dimension checker treats percentages/counts as dimensionless, normalises time dimensions and derives multiplication/division dimensions. Addition/subtraction requires identical dimensions; obvious combinations such as hours + currency fail approval.

Percentage inputs are entered as human percentages and divided by 100 for calculation. A percentage output definition must express its intended scaling explicitly. Currency does not imply tax/GST, discounting, NPV or price authority.
