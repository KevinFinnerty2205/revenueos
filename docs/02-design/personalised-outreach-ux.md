# Personalised outreach UX and simplicity review

## Current path

The user opens a canonical Contact and follows one linear path:

`Contact → Create outreach → purpose → draft → Why this message? → edit → approve → exact preview → simulation`

Create outreach is placed in Contact context rather than a campaign dashboard. The
left column presents business address trust, separate permission language,
contactability and history. The wider working column contains the one current task.
There is no campaign, sequence, audience-list, scheduling or performance UI.

## Screen states

- **Loading/error:** a semantic status or safe error with a route back to Contacts.
- **Not in plan:** a contextual Engage explanation and Settings link only for an
  authorised administrator; no dead compose control or repeated upsell.
- **No email/unknown trust/policy missing:** visible reason and disabled draft action.
- **Create:** one required Purpose field and one primary action.
- **Draft:** editable subject/body, version/state label and separate save/approve
  actions. Save always says that a new version is created; unsaved changes disable
  approval/exact preview and explain that a new version is required.
- **Why this message?:** collapsed by default; opens to source labels, trust,
  publisher/date/link, approved seller context, warning and the explicit no-hook
  explanation.
- **Approved:** **Review before send**, never an immediate send button.
- **Exact preview:** immutable From, To, subject and body plus an amber **Simulation
  only** disclosure. The final action is **Run email simulation** in this release.
- **Queued/result/history:** live-region status and a bounded refresh action. History
  describes seller outbound activity and simulation state and reopens a persisted
  message after navigation/reload.
- **Suppressed:** a clear blocking reason, disabled suppression control and no local
  override. A server rejection remains visible if a stale screen attempts creation.
- **Existing relationship:** a warning asks the seller to use appropriate re-engage
  language instead of pretending this is a first touch.

## Exact review and suppression UX

From and To include both display name and address. The provider-supplied trust label
is visible before draft creation. Trust wording never says “safe to contact” or
“consented”. Exact body copy is whitespace-preserving and read-only. Approval text
states that nothing has been sent and that contactability will be rechecked.

**Mark Do not contact** is visible in Contact context. It creates organisation-scoped
suppression immediately and clears any open preview. Recipient opt-out, complaint
and bounce restoration are intentionally not ordinary-representative actions; the
current UI exposes only manual suppression creation.

## Accessibility

- one `h1`, ordered section headings and semantic `main`, `aside`, `section`, `dl`,
  `form`, `details` and list structures;
- every input has a persistent label and bounded native validation;
- errors use `role=alert`, progress/result messages use `role=status` or polite live
  regions, and loading never relies on animation alone;
- native buttons, select, textarea and links preserve keyboard interaction and the
  repository's visible focus styling;
- state uses words in addition to colour; amber/teal surfaces retain text labels;
- no auto-advancing steps, hover-only provenance or motion-dependent disclosure.

## Mobile review

At 390 px the header actions wrap, the two-column layout becomes one column,
contactability precedes composition, and every button remains a native full-content
target. Subject/body, source disclosure and exact From/To values wrap rather than
overflow. The browser flow exercises suppression at 390×844; the flagship draft,
source and preview states use the same responsive composition.

Complex organisation policy remains in Settings, not in the member workflow. There
is no mobile campaign builder.

## Simplicity and recipient-comfort gate

| Question                                                   | Finding                                                                                                          |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Is Create outreach obvious?                                | Yes, it is the sole primary Contact task when Engage is available.                                               |
| Can a good draft be made in a few clicks?                  | Yes: choose purpose and create; review/edit remain mandatory.                                                    |
| Are sources available without clutter?                     | Yes, collapsed under **Why this message?**.                                                                      |
| Is personalisation understandable?                         | Yes, exact used sources or the no-reliable-hook state are explicit.                                              |
| Does copy avoid creepy/private context?                    | Yes, bounded professional categories plus server rejection.                                                      |
| Are trust and permission distinct?                         | Yes, both are adjacent but described separately.                                                                 |
| Is the external action unmistakable?                       | Yes; current release says simulation in the panel and button.                                                    |
| Is the exact message shown?                                | Yes, From/To/subject/body are read-only before confirmation.                                                     |
| Are blocks understandable?                                 | Yes, server-owned contactability reason is shown.                                                                |
| Is admin complexity hidden from members?                   | Yes, only administrators configure policy.                                                                       |
| Is mobile usable?                                          | Yes, no horizontal workflow or fixed-width panel.                                                                |
| Is campaign complexity absent?                             | Yes.                                                                                                             |
| Would the recipient be comfortable with the source method? | Yes for the included professional sources; unsupported/private hooks are excluded and provenance is inspectable. |

## Screenshot review checklist

The Playwright review and committed synthetic screenshots cover desktop create,
generated draft, open source disclosure, edit/re-approval, exact preview,
queued/success, history, suppression, no-personalisation, no-email,
existing-relationship and Engage policy states. Separate 390×844 shots cover draft,
source disclosure, exact preview and suppression. No mailbox connection screenshot
exists because a production mailbox connector was deliberately deferred; the UI says
so instead of presenting a mock as connected production email.
