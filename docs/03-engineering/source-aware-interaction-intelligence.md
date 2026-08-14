# Source-aware Interaction Intelligence

WO-013 adds an immutable, source-aware composition for accepted post-interaction
Evidence. The content explicitly carries `origin=salesperson_reported`,
`sourceLabel=Reported by you`, category, statement, validation state and accepted
Evidence identifiers.

The Opportunity Workspace exposes this as a separate “Reported by you” section. It
does not merge the statements into customer-direct Meeting Intelligence, and it does
not produce win probability, deal score or forecast.

When an account can be resolved, the same accepted sources append a
`RevenueBrainInteractionSnapshot`. This is an additive subtype in the existing
Revenue Brain, not a second Brain and not a rewrite of Meeting snapshots. Existing
Meeting Intelligence and longitudinal history remain unchanged. Future comparison
logic can explicitly compare source-aware states while retaining the Evidence IDs.

Snapshots are immutable in normal application use. Retention, organisation deletion
and Interaction deletion remove them in documented dependency order. Removing source
Evidence therefore removes the owned derived post-interaction composition; it never
rewrites an earlier Meeting Intelligence snapshot.
