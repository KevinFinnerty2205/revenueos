# Private beta launch checklist

This checklist is intentionally unchecked in source. The accountable operator
checks each item against the actual target environment and records evidence in
the approved release record. Repository completion is not production approval.

## Identity and partner approval

- [ ] Production Clerk verification is configured and tested end to end.
- [ ] Unrestricted sign-up and organisation creation are disabled or explicitly approved.
- [ ] Initial admin user is created and can select the expected organisation.
- [ ] Test organisation is created and cross-tenant access tests pass.
- [ ] Design partners and permitted users are approved.
- [ ] Production-data prohibition is communicated and acknowledged.

## Privacy and controls

- [ ] Data notice wording/version is approved and deployed.
- [ ] Acknowledgement is enforced through API and browser.
- [ ] Retention policy is explicitly selected for every beta organisation.
- [ ] Export is generated, downloaded, expired and purged with synthetic data.
- [ ] Member disable and full organisation deletion are tested with synthetic data.
- [ ] Usage and transcript limits are tested at the boundary.
- [ ] Visual count/byte/analysis limits, private signed access and image sanitisation are tested.
- [ ] Visual export byte inclusion remains disabled unless separately approved.
- [ ] Recording consent, limits, resumability, raw retention, object-first deletion
      and tenant-scoped reconciliation are exercised with synthetic audio.
- [ ] OpenAI is disabled initially or separately approved and restricted.
- [ ] Feature flags are reviewed and unknown/disabled routes fail closed.

## Deployment and recovery

- [ ] Secret manager and least-privilege runtime identities are configured.
- [ ] TLS and explicit CORS origins are configured.
- [ ] Encrypted database backup completed.
- [ ] Non-production restore drill completed, including RLS verification.
- [ ] Migration `0025_recording_transcription` applied exactly once; recording,
      visual/debrief review and snapshot guards, tenant constraints and forced RLS
      are verified.
- [ ] API liveness/readiness are green.
- [ ] Worker starts after the compatible migration and processes mock work.
- [ ] Web sign-in, organisation selection and beta journey are green.
- [ ] Daily retention and expired-export schedules are installed and observed.
- [ ] Private visual object lifecycle and tenant-scoped reconciliation are observed.
- [ ] Private recording lifecycle, retention and report-only reconciliation are observed.
- [ ] Rollback release and decision owner are identified.

## Operations and incident readiness

- [ ] Central safe JSON logs are collected and reviewed for content leakage.
- [ ] Alerts cover API readiness, worker backlog/retries and maintenance failures.
- [ ] Twelve operational runbooks have named owners and escalation contacts.
- [ ] Secret-exposure and tenant-isolation incident contacts are reachable.
- [ ] Synthetic demo seed/reset, reviewed presentation visual and full two-meeting journey are tested.
- [ ] GitHub Actions and the complete local validation gate are green.
- [ ] Known limitations are included in design-partner onboarding.

Launch remains blocked while any item is unchecked or its evidence is stale.
