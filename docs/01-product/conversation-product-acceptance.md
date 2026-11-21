# Oryntela conversation product acceptance contract

## Product shorthand

The owner direction is **Backdrop + Granola in one**: Oryntela should combine
source-aware relationship context and sales guidance with quiet preparation,
personal notes, deliberate capture, enhanced notes and follow-through. This is
product shorthand, not a claim that Oryntela reproduces either reference product
or every feature they offer.

The daily product is conversation-first. A GTM professional or startup founder
must be able to prepare, take notes or deliberately capture an authorised
conversation, understand what happened and continue the relationship without
performing CRM administration. CRM records remain useful supporting context and
an optional system-of-record integration; they do not control the primary journey.

## Daily acceptance journey

The coherent product loop is:

1. open an account's restrained relationship history or create a general
   conversation without an account;
2. prepare from approved organisation knowledge and explicitly confirmed
   conversation history;
3. keep private notes, or deliberately start a supported capture path;
4. review transcript-grounded enhanced notes, evidence and follow-up;
5. correct or approve the result without silently changing an external system; and
6. return later to source-visible relationship history before the next conversation.

The default web experience must satisfy these behaviours:

- Home, account-directory and Search account links open the account's conversation
  history rather than CRM detail, pipeline or opportunity administration.
- Account history fails closed when any returned conversation is not explicitly
  linked to the requested account. A rejected later page keeps only the already
  confirmed history visible and remains retryable.
- One conversation route presents Preparation, Notes & capture, Review & follow-up
  and Relationship history. Visited sections stay mounted so switching sections
  does not stop capture or discard local text.
- A simple note opens directly in the notes editor. Title and conversation type are
  required; account, company, opportunity and scheduled time are optional context.
- Private notes and core start/end controls remain available when optional Companion
  capabilities are disabled or temporarily unavailable. Preparation, capture and
  marker failures degrade only those controls; they do not remove the private note
  editor, discard its local text or strand the conversation lifecycle.
- Preparation works without a company or opportunity. Confirmed initiative history
  is used deliberately; unrelated work at the same company is not silently merged.
- Preparation and relationship-memory responses are adopted only when their
  authoritative conversation and organisation identities match the active view.
  Mixed private payloads fail closed atomically, and a mismatched later response
  does not replace already verified on-screen state.
- Relationship history lists a bounded set of earlier conversations only from the
  explicitly confirmed initiative, even when no sales framework or intelligence
  output exists. Each metadata-only item links back to its source conversation;
  there is no company-wide fallback and no private note or transcript excerpt.
- Framework questions come from supported, missing or stale evidence. Event and
  general notes do not automatically receive sales-qualification prompts.
- Live question suggestions are conservative and inspectable. Only supported,
  customer-attributed provisional signals and relevant unanswered preparation
  questions may drive them; uncertain-speaker, dismissed, superseded or unsupported
  signals do not.
- Transcript imports and completed capture stay in the conversation review journey;
  users are not diverted into legacy meeting or opportunity administration.
- Local note text is not replaced while the authenticated workspace is loading.
  Changed notes are saved before explicitly ending a conversation. A failed save
  leaves the text visible and blocks completion until the user resolves it. On a
  stale-session conflict, Oryntela presents the local and latest saved private note
  separately. The user must explicitly use the latest note or save a reviewed merge;
  neither version is replaced automatically.
- Search can locate a conversation from its title, relationship, transcript or the
  authenticated user's own live notes, enhanced notes and follow-up draft. A private
  note match returns conversation metadata only: it never exposes note text or lets
  one member's private note influence another member's results. This deterministic
  lookup is separate from Ask and shared conversation intelligence.
- Home brings the authenticated user's own nonblank, unreviewed follow-up drafts
  back as a bounded metadata-only review queue. It links to the private Review &
  follow-up section without exposing draft text, requiring CRM data or including
  another member's workspace. Editing a nonblank draft reopens `Needs review`,
  while saving an unchanged draft preserves `Reviewed`. `Reviewed` becomes visible
  and removes the Home item only after the private save succeeds.

Legacy CRM, pipeline, campaign, forecast and content-production records remain
available through their existing compatibility routes. They are not collected into
the default conversation workflow, and this contract does not authorise deleting
their data.

## Private-note and intelligence boundary

Live notes are authenticated organisation-and-user private data. They remain
separate from shared intelligence, the transcript and generated enhanced notes.
Optimistic locking prevents another session from silently replacing the user's
workspace. A reviewed conflict save uses the latest lock and carries forward newer
unrelated private enhanced-note and follow-up fields.

For automatic post-conversation generation, Oryntela may pin one nonblank snapshot
of at most 20,000 characters from the source owner's private live notes. The
snapshot is bound to the exact private generation and transcript lineage. It can
guide emphasis only in that owner's enhanced notes; it cannot establish a buyer
commitment or other customer fact. Shared artefacts, follow-up composition and
conversation memory remain transcript-only and cannot read the private snapshot.
A longer saved note remains intact and causes that generation to proceed without a
note snapshot rather than truncating it.

The automatic origin is immutable and is checked against its non-public creation
audit. The worker re-establishes the owner's private tenant context and rechecks the
feature gate, membership, data notice and recording/evidence authority before work
and before a provider request. Revoking that lineage cancels only the affected
automatic private generation. The currently verified path is deterministic and
local; this contract does not activate a live AI provider.

## Completion standard

| Capability                    | Current truthful boundary                                                                                      | Still required before claiming complete parity                                                                                                                   |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Quiet desktop capture         | Deliberately armed web microphone and supported shared-tab/display audio, with import and typed-note fallbacks | Signed macOS and Windows applications, supported-call detection, system-audio coverage, sleep/reconnect/device-change evidence and visible consent/stop controls |
| Granola-style enhanced notes  | Private notes can guide owner-private, transcript-grounded enhanced notes through the deterministic path       | Approved live-model evaluation using consented synthetic audio, long conversations, corrections, speaker attribution, retries and user edits                     |
| Backdrop-style sales guidance | Approved-knowledge preparation, framework coverage, provisional signals and bounded next-question suggestions  | Approved generative product answers and objection guidance grounded in reviewed business knowledge, with useful latency and low-interruption evidence            |
| Meeting feedback and scoring  | Evidence coverage distinguishes confirmed, partial, missing, stale and conflicting information                 | An explained per-conversation assessment rubric, selectable goals and evidence-calibrated validation; coverage is not a win probability or quality score         |
| Business learning             | Reviewed website/file knowledge ingestion and source-aware preparation exist behind controlled boundaries      | Approved real-source ingestion, correction/reapproval and evidence that organisation language improves useful guidance                                           |
| Before-conversation delivery  | Timezone-aware deterministic brief preparation and a disabled-by-default private outbox exist                  | Target-environment calendar/email activation, deduplication, cancellation, delivery and owner acceptance evidence                                                |
| Long relationships            | Explicit initiatives separate unrelated work and expose bounded, source-linked earlier-conversation history    | Owner review across many conversations, changing stakeholders, dormant relationships and parallel initiatives                                                    |
| Search and knowledge          | Account/conversation navigation, owner-private notes-content search and existing tenant-scoped Ask paths       | Broader cross-conversation retrieval and sharing verified end to end                                                                                             |
| Simple daily use              | One conversation-first journey with legacy administration outside the default path                             | Desktop/mobile visual review, real-browser acceptance and owner usability evidence                                                                               |

Native applications, live providers and target-environment integrations are separate
delivery milestones. A green source build or deterministic demo does not establish
them. Oryntela must not be marketed as the complete combination of the reference
products until the relevant acceptance evidence above exists.

## Rollout boundary

This contract introduces no provider activation, outbound communication, billing or
Credits authority, customer-data approval, production deployment authority or schema
migration. Consequential external actions remain proposals until separately reviewed
and authorised. Existing privacy, tenant-isolation, consent, retention and launch
gates continue to apply.
