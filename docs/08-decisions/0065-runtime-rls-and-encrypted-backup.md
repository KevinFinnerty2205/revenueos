# ADR 0065 — Non-bypass runtime RLS and encrypted database/object backup

## Context

Forced RLS is ineffective for a superuser/`BYPASSRLS` runtime role, and database-only backups cannot recover private Create/evidence objects.

## Decision

Production preflight proves a non-superuser, non-`BYPASSRLS` runtime role and transaction-local tenant reset. A separate migration role owns schema change. The supported portable backup combines a custom PostgreSQL dump and private-object tar, authenticates both with AES-256-GCM, records content-free hashes/counts and restores only to isolated database/storage targets.

## Alternatives

Session-persistent tenant variables and runtime-owner credentials were rejected as cross-request hazards. Unencrypted local dumps and database-only snapshots were rejected as incomplete. Managed snapshots remain a complementary deployment control.

## Consequences

Operators must manage a backup key separately from application/provider credentials, exercise quarterly restores and reconcile database/object state. The tool does not claim multi-region availability or zero data loss.
