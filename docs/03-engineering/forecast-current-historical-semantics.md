# Current versus historical forecast semantics

Current forecast is a live read: canonical eligibility, amount and scope are evaluated
now; the latest seller category is applied and stale differences are disclosed. A
correction therefore updates the operating total without rewriting its old review.

History is locked context: prior categories, amounts and baseline samples stay as
recorded. Completed periods accept no new revisions. Closing removes an Opportunity
from current remaining forecast; Won Actual comes from the current canonical close
state/date through Sales Analytics. Reopening may make a deal eligible again, but the
old revision will show `status_changed` and must be reviewed by its current owner.
