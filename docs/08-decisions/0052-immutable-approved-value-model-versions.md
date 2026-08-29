# ADR 0052: Immutable approved Value Model versions

## Context

A formula edit must not silently change an approved historical customer case.

## Decision

Separate model identity from immutable versions. Approval binds definition JSON, canonical AST, engine version and fingerprint. Editing creates a new draft version; new cases use the latest approved active version while old cases keep their exact reference. PostgreSQL triggers provide database-level immutability defence.

## Alternatives

Mutable models with recalculation and copying formulas into each case were rejected because they obscure authority and lineage.

## Consequences

Definitions consume bounded version history and require explicit administration. Old versions remain readable while referenced, even when the parent model is archived.
