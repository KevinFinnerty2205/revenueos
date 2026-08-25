# Prospect source and citation architecture

**Status:** Current WO-026 implementation

Each provider result contains at most eight sources and thirty observations. Models
reject additional fields and bound every identifier, title, statement and URL.
Sources carry a run-local key, canonical HTTPS URL, type, publisher, optional date,
authority class, optional provider reference and SHA-256 content fingerprint.

Validation happens before persistence:

1. Canonicalise and safety-check every URL.
2. Reject duplicate source keys, URLs or fingerprints in the run.
3. Reject duplicate observation keys or repeated citations.
4. Resolve every citation against the same provider result.
5. Enforce trust-specific authority rules.
6. Persist sources, observations and tenant/run-bound citation rows atomically.

Database uniqueness and composite foreign keys repeat these constraints. An
observation/source link includes organisation and run, so a citation from another
tenant or run cannot attach even if an identifier is guessed.

Verified requires at least one primary, official-public or regulatory source.
Provider-supplied requires a structured-provider source. Inferred requires at least
one source and cautious language. Unknown cannot cite a source as proof. Validation
rejects the result rather than downgrading a provider’s unsupported assertion
silently.

Refresh never edits earlier sources or observations. Stable observation keys drive
the new/changed/no-longer-supported comparison. Source metadata and concise
observations are exportable; raw responses, fetched pages and provider credentials
do not exist in the stored model.
