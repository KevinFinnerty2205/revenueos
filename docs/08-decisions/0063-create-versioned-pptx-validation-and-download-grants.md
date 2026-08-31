# ADR 0063: Versioned PPTX validation and authenticated one-time downloads

- **Status:** accepted
- **Date:** 31 August 2026
- **Decision owners:** Product and Engineering
- **Work order:** WO-039B

## Context

Create previously approved a deterministic structured review after `python-pptx`
saved a file, but did not prove the claim manifest, placeholder values and downloaded
bytes agreed. Template versions could describe edits without a usable mapped shape.
Downloads used either a reusable HMAC secret in a query string or a direct storage
presigned URL, so application membership, approval and source state could not be
rechecked at consume time and the credential could enter history/proxy logs.

PPTX compatibility rules will also evolve. Treating today's approval as permanently
valid under a future parser/security contract would silently broaden trust.

## Decision

1. Define one code-deployed, non-configurable
   `CREATE_PPTX_PROFILE_VERSION = 1`. Store the profile and validation time on
   template and generated versions. A template must be `compatible`, deliberately
   approved and current-profile validated before planning, generation, final approval
   or download.
2. Require supported native title/audience and content mappings for editable slides.
   Locked/reuse-as-is remains a generation policy; a template without a writable
   customer-specific title cannot be approved for Create.
3. Before exposing generated output, prove claim/structured-slide equality, save the
   actual PPTX, reparse it through the hostile-package preflight and validate slide
   count/order, all replacements, required/exact content, prohibited metadata and
   internal identifier absence. Persist validation only with the immutable bytes and
   SHA-256 checksum.
4. Replace Create query/presigned downloads with a persistent, forced-RLS one-time
   grant. Return the high-entropy secret separately from a credential-free path;
   store only SHA-256. Bind organisation, user, current presentation version, expiry
   and approval fingerprint. POST the secret in the authenticated request body.
5. Recheck membership, entitlement, template/source/approval/profile state and stored
   checksum at download. Fetch private storage server-side and atomically consume at
   most once. Do not log, audit or export the secret.

## Alternatives considered

- **Keep reusable signed query tokens and redact proxy logs:** rejected because
  browser history/Referer and every intermediary remain a credential surface, replay
  persists until expiry and direct storage cannot recheck application state.
- **Use only very short-lived S3 presigned URLs:** rejected for Create because it adds
  provider-specific behaviour and still bypasses one-time consume and state recheck.
- **Trust `python-pptx.save()`:** rejected because a successful save does not establish
  manifest/output equivalence, exact-content presence or metadata safety.
- **Pixel-render every deck in production:** rejected because PowerPoint fidelity is
  environment-dependent and an Office/rendering service broadens execution, cost and
  security. Browser review remains explicitly structural.
- **Administrator “allow anyway”:** rejected; security/profile incompatibility is not
  overrideable.

## Consequences

Migration `0049_create_trust` adds template/presentation validation fields and
`create_download_grants`. Existing approved template versions default to **Needs
attention** and require current-profile revalidation for new generation. Expired
grants are removed by bounded retention maintenance and all grants cascade with
membership/version/organisation deletion.

Downloads now require two application requests and private storage bytes pass through
the API, trading some bandwidth for current authorisation and integrity enforcement.
A successful consume precedes response delivery; connection failure therefore needs
a fresh grant. Missing/corrupt storage does not consume the grant.

Structural output guarantees become testable and versioned. Visual fidelity remains
best effort and must be disclosed; test-only LibreOffice renders are evidence, not a
production dependency or a universal PowerPoint guarantee.
