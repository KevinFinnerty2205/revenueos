# HubSpot OAuth and credential security

## Flow

Only an active organisation admin can start or complete HubSpot OAuth. The API
generates at least 48 bytes of URL-safe random state, stores only its SHA-256 hash,
and binds it to organisation, user, connector, exact configured redirect and a
short expiry. Callback consumption is transactional and one-time. Invalid,
expired, replayed, wrong-tenant/user, changed-redirect and provider-declined
callbacks fail closed. Active membership and user status are checked on each
integration request.

The browser receives the HubSpot authorisation URL and later sends the returned
code/state to the RevenueOS API. It never receives an access token, refresh token,
client secret, encryption key or credential reference. Production requires HTTPS
for the exact redirect and official HubSpot API/authorisation hosts.

HubSpot’s standard confidential-app documentation specifies authorisation-code
exchange with `client_secret`, access-token expiry and refresh tokens. It does not
document PKCE for this standard flow, so WO-025C does not invent a verifier. State,
exact redirect binding and server-secret exchange are mandatory. Revisit PKCE if
HubSpot makes it a supported/recommended policy for this app type.

## Scopes

The fixed required set is:

- `oauth`
- company read and schema read
- Contact read/write and schema read
- deal read/write and schema read
- meeting read/write

No broad marketing, email-send, workflow, delete, import, export or private-app
token scope is requested. Missing or reduced scopes block connection. The
advertised runtime capabilities remain update Opportunity, update Contact and
create Activity only.

## Token envelope

Tokens are serialized only inside the connector boundary and encrypted with
AES-256-GCM using a new random 96-bit nonce for every write. Associated data binds
the ciphertext to organisation, connection, credential ID and envelope version,
preventing cross-tenant/connection substitution. The master key is an exact
32-byte base64url deployment secret. Production configuration fails closed when it
is missing or malformed.

Refresh rotates the encrypted envelope. Authentication failure marks the
connection `reauthorisation_required`. Test connection refreshes expired tokens,
introspects the token and verifies the HubSpot account ID. Reconnect replaces the
envelope only when introspection returns the same account ID. A different HubSpot
account is rejected and the newly granted credential is revoked where possible, so
dormant record mappings cannot silently acquire meaning in another external
account. Disconnect attempts provider refresh-token revocation, immediately
revokes local state, invalidates previews, cancels queued work and deletes local
credential ciphertext even if the provider is unavailable.

Tokens and credential references are excluded from API responses, logs, audits,
organisation export and screenshots. Client secret and master-key rotation are
deployment operations; rotation must reconnect/re-encrypt affected connections
before retiring old material.
