# Visual Evidence security and privacy review

## Capture and content threats

- Camera access is available only through a visible user-initiated browser file input. Oryntela does not request background access, record video or keep the camera active after the browser chooser closes.
- The browser shows a local preview before upload and requires an explicit authority/consent confirmation. Users remain responsible for excluding bystanders and content they are not authorised to share.
- Whiteboards and screenshots can expose confidential, personal or unrelated material. Guidance asks users to frame or redact before upload; the system does not claim reliable automatic redaction.
- Business-card text is personal data. Extraction creates review-only contact candidates, with no automatic Contact mutation, enrichment, external lookup, buying signal or stakeholder-role inference.
- People in site or presentation photos remain visual context. Face recognition, biometric identification and sensitive-trait inference are prohibited.
- Site-photo interpretations are marked `observed` and AI-inferred. They cannot become customer-confirmed statements without a separate customer source.

## Controls implemented

- Active organisation comes only from verified auth context; every visual query and relationship uses an explicit organisation predicate and composite tenant foreign key.
- PostgreSQL RLS is enabled and forced on both new tables; runtime credentials must not bypass it.
- Objects are private and addressed by random tenant-scoped keys. Browser grants are short-lived and bound to tenant, user, visual and purpose.
- Production fails closed without private S3-compatible storage and a deployment-specific HMAC secret.
- JPEG/PNG format sniffing, structural validation, checksums, size/dimension/pixel limits, metadata stripping and trailing-content rejection run before availability.
- Bounded decompression checks reject malformed PNG streams and decompression bombs. The narrow parser rejects unknown critical PNG chunks and does not accept HEIC, SVG, PDF or executable formats.
- Image bytes, signed URLs, OCR text, candidate statements and provider payloads remain out of logs and audit metadata.
- Strict structured output and service-side source rules constrain prompt injection and false evidence.
- Complete user review is mandatory before downstream intelligence.
- Two-phase object deletion, retention cleanup, organisation deletion and reconciliation cover the object/database lifecycle.

## Access, preview and transfer

- Local previews use a revocable in-memory object URL before upload. An authenticated private preview is owned by its exact current download grant: changing or removing that grant hides and revokes the old object URL, and an obsolete request cannot replace or clear the newer preview. Private API downloads return `Cache-Control: private, no-store`, `nosniff`, a sandbox content policy and a sanitised filename.
- Before following an upload grant, the browser requires the create response to match the requested interaction, visual/capture session, MIME type, byte size, checksum, visual type and source ownership. Completion and processing responses must retain that interaction, visual/session and immutable source identity, and every candidate must name the same visual and ownership. A mismatch stops the chain before its next request, keeps the active session's selected image and consent for retry, and shows only a safe generic error. Changing interactions ends the old capture session so a late response cannot continue it or render review state.
- Local signed capabilities expire and are bound to one organisation, user, visual and upload/download purpose. S3-compatible capabilities are short-lived and name one random tenant-scoped object key. Objects are not enumerable through the product API.
- Stale or wrong-purpose grants fail closed. Authenticated metadata queries still apply tenant predicates and forced RLS; direct object capability leakage remains an incident requiring credential/key review.
- External visual-provider transfer occurs only when the server-authoritative OpenAI and visual-provider settings are both enabled and the user has confirmed authority. Requests use an allowlisted model, strict structured output, `store=false`, a timeout and no SDK retries; tests remain zero-network.

## Deletion, retention and export

- Individual deletion removes the private object first, then marks source Evidence deleted and suppresses derived current views. A storage failure leaves retryable `delete_failed` state and is not reported as complete.
- Retention and organisation deletion use the same object-first ordering. Reconciliation detects missing and orphaned tenant objects without logging content.
- Export version 8 excludes storage keys, signed URLs and provider request IDs. Image bytes are omitted unless a separately approved server setting enables them for an authorised admin export.

## Residual risks

The initial parser is deliberately narrow and is not a malware scanner or content-safety classifier. JPEG and PNG only are supported; HEIC conversion is not claimed. S3-compatible behaviour must be verified against the chosen deployment provider. Human reviewers can still accept an incorrect suggestion. Exporting image bytes is disabled by default and should be enabled only for an explicitly approved administrative export process.

## Launch requirements

Before production customer data, verify bucket access policy, TLS, encryption at rest, lifecycle/back-up policy, key rotation, provider/privacy approval, incident runbook ownership, restore/reconciliation evidence and PostgreSQL RLS tests using the non-bypass runtime role.
