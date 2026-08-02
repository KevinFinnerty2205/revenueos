# Evidence foundation implementation

## Purpose and current boundary

WO-011 creates only the minimum source-neutral metadata needed for future capture
work. It does not accept or store an evidence body, recording, image, document,
transcript copy, URL, blob, provider payload or AI output, and it exposes no public
Evidence or Capture Session API.

## Evidence envelope

Every Evidence row belongs to an organisation and Interaction and may reference one
same-tenant Capture Session. The controlled metadata is:

- type: `transcript`, `user_observation`, `recording`, `visual`, `document`,
  `email` or `system_metadata`;
- origin: `customer_direct`, `salesperson_reported`, `system_metadata`,
  `imported_external`, `seller_prepared` or `ai_inferred`;
- support: `direct`, `reported`, `inferred`, `corroborated`, `verified`,
  `disputed`, `stale` or `superseded`;
- validation: `unreviewed`, `verified`, `disputed`, `rejected` or
  `not_applicable`;
- optional capturing member and capture/effective times;
- lifecycle: `received`, `available`, `excluded`, `superseded` or `deleted`; and
- retention class: `inherited`, `short_lived` or `standard`.

Origin, support and validation are deliberately independent. A salesperson-reported
observation remains salesperson-reported after verification. Validation cannot
upgrade it to customer-direct, and WO-011 adds no confidence percentage.

## Capture Session decision

Capture Session is justified because ADR 0026 models AI Debrief and Voice Journal as
supporting activity beneath a customer Interaction rather than as customer events.
The foundation stores only organisation, Interaction, controlled capture type,
status, starter and timestamps. Types are `ai_debrief`, `voice_journal`,
`live_recording`, `visual_capture`, `uploaded_transcript`, `uploaded_recording` and
`manual_notes`; status is `created`, `capturing`, `completed`, `abandoned` or
`failed`.

These names reserve a coherent taxonomy only. No session execution, lifecycle
service, microphone/camera permission, upload, audio, question, processing pipeline
or AI capability exists.

## Tenant, retention and deletion behaviour

Composite tenant foreign keys prevent an Evidence or Capture Session from referring
to another organisation's Interaction, membership or session. Both tables enable
and force RLS. Export version 2 includes their structured metadata. Retention and
Meeting/organisation deletion remove Evidence before Capture Sessions and
Interactions. Interaction soft deletion hides the parent through normal APIs;
approved hard-deletion maintenance cascades/removes metadata in deterministic order.

Future work that adds a body or storage object requires its own approved schema,
consent, encryption, access, retention, deletion, malware/content handling and
provenance review. It must not overload these metadata columns.
