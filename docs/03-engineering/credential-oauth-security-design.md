# Credential and OAuth security design

WO-022 defined the abstraction. WO-025C implements it for HubSpot with server-side
OAuth and AES-256-GCM database envelopes. Mock connections still use no credential.

## Boundary

`CredentialStore` exposes the opaque-reference revocation port needed by the
current connection lifecycle. A future live implementation must extend that
boundary with reference-oriented storage and retrieval.
`integration_connections.credential_reference` is reserved for an opaque secret
manager reference; token material must never be stored in the application table.
API responses, shared browser contracts, exports, audits and logs omit the field.
Revocation clears the reference after asking the credential store to revoke it.

## Live HubSpot implementation

High-entropy state is stored hashed and bound to tenant, admin user, exact redirect,
expiry and one-time consumption. Short-lived access and refresh tokens are available
only inside the adapter. A 32-byte environment master key is required; associated
data binds every ciphertext to tenant, connection and credential ID. Refresh rotates
the envelope and disconnect attempts provider revocation before local deletion.
See [HubSpot OAuth security](crm-oauth-credential-security.md).

## Requirements for any additional live connector

- Administrator-only, deliberate connection and reauthorisation.
- PKCE and state/nonce validation where applicable.
- Exact redirect URI allowlist and provider/tenant binding.
- Minimum scopes per capability; offline access only where justified.
- Encrypted secret-manager storage, rotation and access audit.
- Tokens loaded only inside the adapter for the active organisation.
- No tokens, authorisation headers, signed URLs or provider bodies in logs/errors.
- Revocation before organisation erasure and a documented provider-side fallback.
- Clear re-consent when scopes expand.

Provider installation, OAuth consent and a stored reference do not establish a
working integration. A live adapter must additionally satisfy idempotency,
reconciliation, deletion, retention, residency, incident and launch gates.
