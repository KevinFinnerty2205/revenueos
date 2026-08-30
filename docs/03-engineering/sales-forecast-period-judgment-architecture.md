# Forecast period and judgment architecture

`sales_forecast_periods` identifies a tenant calendar month/quarter and freezes the
organisation timezone used at creation. One `sales_forecast_judgments` identity links
a period and Opportunity. `sales_forecast_judgment_revisions` appends the seller's
category and context; `(judgment_id, revision_number)` is unique.

The service derives tenant identity from verified context. Expected close date owns
eligibility. Current owner alone may append; an admin gains read scope, not overwrite
authority. Optimistic `expectedRevisionNumber` prevents lost updates. Concurrent
identity creation is contained by unique keys and savepoints. Database triggers block
updates/deletes outside the explicit maintenance transaction setting.

Calendar periods only are supported. Fiscal calendars, arbitrary ranges, manager
review types and external CRM category sync are not represented in v1.
