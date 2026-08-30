# Sales Forecast domain architecture

WO-038 stays inside the FastAPI/PostgreSQL modular monolith. Routes under
`/api/v1/forecast` call `SalesForecastService`; tenant-scoped repositories load
canonical Opportunities, Pipeline stages/events and append-only forecast records.
The service calls `SalesMetricService` for Actual and `SalesTargetService` for matching
Target records. It does not copy their formulas or stored values.

The primary read is synchronous, bounded to one period/currency/scope and paginated
to 100 Opportunities. Historical outcome counts are one grouped set query keyed by
Pipeline/stage. Seller revisions and names are set-loaded. Target matching reads
bounded canonical Target/revision records without calculating unrelated target
actuals. Migration `0047_transparent_forecast` adds only forecast identity/revision
indexes; existing WO-035 stage-event indexes serve the cohort query.

There is no provider, worker, queue, warehouse, cache, microservice, generic formula
engine or persisted aggregate. Safe audits contain IDs, period type, revision number
and model version only—not amounts, categories, customer text or forecasts.
