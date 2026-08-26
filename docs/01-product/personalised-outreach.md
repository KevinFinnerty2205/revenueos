# Personalised one-to-one outreach

- **Status:** implemented by WO-029 behind the `engage` organisation entitlement
- **Channel:** email simulation outside production; no production mailbox provider
- **Boundary:** one canonical Contact, one sender and one reviewed message at a time

## Product promise

RevenueOS Engage helps a relationship-driven seller turn permitted business-contact
data, bounded Prospect research and an administrator-approved offering into a short,
professional email. It does not decide that a person may be contacted merely because
an address exists or has a trust label. The user chooses a purpose, inspects why the
copy was personalised, edits it, approves one immutable version and separately
reviews the exact execution payload.

The current purposes are introduction, request a meeting, share relevant information
and re-engage. Approval never sends. Production sending fails closed; development and
test may use the visibly labelled deterministic Mock Email simulation.

## Source-backed personalisation

The composer may use only:

- the Contact's current professional role and canonical Company;
- current, eligible Prospect company/person observations with an attached source;
- `verified` or `provider_supplied` professional facts within the freshness policy;
- the organisation's approved offering, value proposition and call to action; and
- the user-selected purpose.

Every used research hook is persisted against the exact outreach version and shown
under **Why this message?** with its trust state, publisher, date and public link when
available. An approved seller-context reference is always included. A provider or
composer cannot submit arbitrary source IDs through the public contract.

The automatic boundary rejects sensitive or private-person categories, manipulative
personality framing, fake familiarity, fake mutual connections, fabricated urgency,
deceptive `Re:`/`Fwd:` subjects and invented percentage/ROI claims. Research is not
customer Evidence and an outbound seller message cannot confirm Methodology or
Revenue Brain facts.

If no reliable professional hook exists, RevenueOS says so and creates a transparent
role/company/value-based introduction. It never invents an anecdote, post, event,
relationship or inferred email address to make the message seem personalised.

## Address trust, permission and contactability

Address trust answers only how the business email was established: `verified`,
`provider_supplied` or `unknown`. Permission is assessed separately by the
organisation's outreach policy. Verification does not establish consent, lawful
basis or permission.

The server evaluates contactability at draft context, approval, exact preview,
confirmation and worker execution. Sending is blocked for an unknown/inferred or
missing address, missing Engage entitlement, disabled sender/membership, missing or
disabled policy, disallowed provider-supplied data, active suppression, cooldown,
quota, changed recipient/version, unavailable sender connection or an opt-out
requirement the current provider cannot satisfy. A change to the approved offering,
value proposition or CTA also invalidates the existing review/send boundary.

Organisation administrators configure outbound enablement, whether provider-supplied
business addresses are permitted, cooldown, per-user/per-organisation daily limits,
offering, value proposition and CTA. The UI reminds administrators that their
organisation remains responsible for applicable outreach and privacy law; RevenueOS
does not present configuration as legal advice.

## Suppression and opt-out

WO-029 implements server-side manual do-not-contact, recipient opt-out, complaint and
permanent-bounce reasons. Active suppression wins over approval and preview state.
The lookup key is an organisation-scoped HMAC of the normalised email, not raw email,
so suppression can survive Contact deletion and later re-discovery without exposing a
plain address in the suppression identity. Contact deletion unlinks the Contact while
retaining the minimum outreach history and active suppression. Organisation deletion
removes the policy, history and suppressions; it cannot recall email already sent by
an external provider.

There is no public unsubscribe endpoint because no production provider or delivered
email exists. If a production provider is later selected, scanner-safe POST-based
unsubscribe and provider event handling are required before any policy that requires
an opt-out mechanism can be enabled.

## Review and execution

Each edit creates an immutable `OutreachVersion` and matching immutable Action
revision. Editing invalidates approval. The exact preview is generated only from the
currently approved version and shows sender name/address, canonical Contact
name/address, subject, body, connection, simulation state and expiry. The sender is
the authenticated user's active user-bound connection; neither sender nor recipient
can be injected in the request.

Unsaved browser edits cannot be approved or previewed. The user must persist a new
immutable revision first, which visibly clears approval. Persisted Contact outreach
history can be reopened after navigation or reload.

Final confirmation reuses the WO-022 execution foundation. Its preview fingerprint,
exact Action version and connection form the confirmation boundary. The idempotency
key prevents duplicate confirmed executions. Worker execution performs the same
authorisation, suppression, policy, mailbox, membership, recipient and version checks
again. Current deterministic simulation records seller activity but performs no
network email call.

The execution domain reserves a safe unknown-delivery state for a future provider.
No production adapter may blindly retry an ambiguous accepted request; it must use a
provider receipt or safe reconciliation. Scheduling, automatic retry and
reconciliation are deferred with production sending.

## Safe outreach principles

- communicate as the real salesperson from their authorised mailbox;
- be concise, truthful and specific only where sources support specificity;
- use professional business context, never private or sensitive traits;
- show address trust and source provenance without claiming permission;
- honour suppression immediately and provide no send-screen override;
- keep all copy user-reviewable and every external step explicit;
- measure legitimate conversations, corrections and suppression health—not volume;
- do not add tracking pixels, click tracking, covert monitoring or fabricated social
  proof.

## Current limitations and handoff

WO-029 has no Gmail/Microsoft OAuth, live sending, delivered/read semantics, inbound
reply sync, unsubscribe route, campaign, sequence, bulk recipient import, automatic
follow-up, scheduling, LinkedIn/call automation, tracking, predictive send time or
arbitrary recipient address. HubSpot logging is not performed: seller outreach stays
inside RevenueOS until a separately reviewed CRM-activity contract exists.

WO-030 may add campaign/sequence orchestration only by preserving canonical Contacts,
per-person immutable rendering, suppression, quotas, exact review, idempotency and
provider reconciliation. It is not implemented by WO-029. WO-031 Event Intelligence
is also outside this slice.
