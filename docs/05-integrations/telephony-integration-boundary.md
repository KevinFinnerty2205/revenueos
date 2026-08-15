# Telephony integration boundary

**Status:** Documented future boundary; no telephony integration is implemented.

WO-017 does not add a speculative `CallProviderAdapter`. The current domain needs
only a phone Interaction, controlled direction/outcome, explicit associations and
recording provenance. A provider interface becomes justified when an approved
business-phone integration has concrete authentication, webhook, retention and
licensing requirements.

A future narrow adapter may return:

- an opaque provider and call identifier;
- direction and start/end timestamps;
- tenant-authorised participant references for explicit review;
- recording availability and protected recording metadata; and
- an authorised retrieval stream or reference for the existing Recording Session
  ingestion boundary.

The adapter must never make provider identity a customer-facing intelligence silo.
It must map into the existing Interaction, Evidence, Recording Session, transcript
and review domains. Provider call IDs stay nullable, scoped by organisation and
provider, and absent from ordinary UI/telemetry. No phone-number-only Contact merge
or silent association is allowed.

Before implementation, separately approve least-privilege scopes, webhook
verification and replay protection, data residency, recording ownership/consent,
personal-call exclusion, deletion/provider expiry, rate limits, provider outage
behaviour and tenant-safe idempotency. Twilio, Aircall, RingCentral, Dialpad, Zoom
Phone and Teams Phone are not installed or called by WO-017.
