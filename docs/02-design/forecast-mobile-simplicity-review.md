# Forecast mobile and simplicity review

WO-038 uses the existing responsive Insights shell. Filters form a single column at
390 px; tab navigation wraps; summary, range and calibration cards stack; deal review
uses cards rather than a wide table; touch controls meet the existing 44 px minimum.
Native details/summary controls support keyboard operation and reduced-motion users
without new animation.

The mandatory simplicity questions pass in the implemented flow:

- Actual, Target, seller range and baseline have separate labels and explanations.
- Commit/Likely/Possible definitions appear beside the values.
- One category and one save action complete a deal review in seconds.
- Samples, lookback, missing inputs and insufficient history are visible.
- No probability, stage-weight editor, score, rank or combined forecast number exists.
- Closing a deal naturally transfers it from remaining forecast to canonical Actual.

Desktop and mobile Playwright fixtures also check that the page has no horizontal
document overflow. Screenshots live under `docs/07-sprints/assets/wo-038-*`.
