# Meeting-bot assessment

**Decision:** Defer. A bot is not required for the WO-018 baseline.

A visible meeting bot can provide consistent media access in some deployments, but
it creates a larger trust and operational surface than platform artefact import. It
must be admitted through waiting rooms, remains vulnerable to organiser policy and
manual removal, can fail to join or reconnect, and may produce incomplete recording
or speaker attribution. Its visibility does not itself prove authority or consent.

Provider terms, bot identities, regional media processing, customer recording
policy, data residency, notices, participant objections and enterprise acceptance
vary. Running join/media infrastructure across three providers also introduces
continuous compatibility, scaling, monitoring and incident burden before the import
workflow has been validated.

The current priority remains: platform-provided artefact, deliberate user import,
one selected native adapter, then AI Debrief/Voice Journal. Reconsider a narrow bot
only after design-partner evidence shows a high-value gap that those paths cannot
fill, and only with provider-TOS review, visible participant identity, explicit
consent, regional processing controls, reliable admission/removal handling and a
separate security decision. The `meeting_bot` provenance value is future-ready
metadata and must not be interpreted as implemented capability.
