# DigitalOcean deployment template

`app.production.template.yaml` is an inert, reviewed target specification. It does not create infrastructure, alter DNS or spend money. The legal gate intentionally prevents the web image from building as production while the committed Privacy and Terms routes remain GAP copy.

Before applying it, follow the canonical [production launch runbook](../../docs/03-engineering/production-launch-runbook.md). Download the provider-normalised spec after initial creation and commit only non-secret, non-account-specific changes. Put every `SECRET` value in the DigitalOcean control plane; never replace the comments below with credentials in Git.

The template uses one instance each for web, API and the non-routable worker. The database-backed leases and idempotency rules tolerate restart overlap and an accidental second worker, but the baseline keeps `instance_count: 1` to control cost. The worker's private liveness probe restarts an event loop that stops ticking.
