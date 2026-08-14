# Pre-Interaction Brief security and privacy review

## Reviewed controls

- Trusted authentication and active membership derive organisation scope; clients
  cannot supply it.
- Every source and persistence query has an explicit organisation predicate.
- `pre_interaction_briefs` has composite tenant foreign keys and forced PostgreSQL RLS.
- Completed content is immutable; review metadata can be appended once.
- Transcript tables, recordings, raw documents/emails, prompts and provider output
  are outside the source path. A SQL-capture regression rejects any transcript query.
- Strict contracts reject unknown, predictive and automation fields and bound every
  collection and string.
- Logs contain identifiers, interaction type, safe codes and counts only.
- The server feature flag, active membership, current notice acknowledgement and
  private-beta quota fail closed.
- Product responses exclude internal source IDs and infrastructure metadata.
- Retention dry runs/counts, approved deletion, organisation export and demo reset
  include brief rows without logging their content.

## Residual limitations

Source completeness is a bounded heuristic, not calibrated confidence, win
probability or forecast. Deterministic wording can be generic when little validated
intelligence exists. Source references are database IDs rather than cryptographic
proof. Production customer data remains prohibited until the repository's wider
launch, provider/privacy and operational gates are approved.

No recording, live processing or new external processor was introduced, so there is
no new microphone, media, telephony or OpenAI data flow in WO-012.
