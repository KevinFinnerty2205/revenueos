# Campaigns & Sequences UX

- **Status:** current WO-030 implementation
- **Design goal:** controlled sales outreach that a seller can understand without
  marketing-automation knowledge

## Desktop flow

Campaigns sits under **Sell** beside Accounts, People and Interactions when Engage is
available. The list provides a restrained first-use explanation and operational
state. **Create campaign** proceeds through four ordinary form sections:

1. name, purpose and the organisation's approved offering;
2. up to 50 explicit canonical Contacts—never pasted addresses or CSV;
3. one to four ordered step rows with objective and wait days; and
4. an unmistakable choice between review every send and bounded campaign auto-send.

There is deliberately no draggable canvas, arrow, branch, script editor or hidden
advanced automation tier. The review page shows the exact audience snapshot,
recipient trust, eligible/blocked decision and plain-language reason before launch.

## Launch and monitoring

Launch freezes the audience, sequence, approval mode and policy version. Review mode
requires one launch confirmation. Auto-send adds a prominent warning and second
checkbox explaining that future steps may execute only after current safety checks.

The active view shows ordered steps, local send window, active-Opportunity stop,
operational counts and recipients. Pause, resume and stop remain visible without a
settings detour. Reporting excludes opens/clicks and labels reply/meeting outcomes as
seller-reported.

## Recipient view

Each recipient has a compact timeline, current status, safe block/stop reason and
next scheduled work. A prepared review-mode message shows exact sender, recipient,
subject/body and **Why this message?** sources, followed by approval and the existing
exact Execution Preview. Recipient stop and seller-reported replied, meeting booked
and not interested controls are adjacent and unambiguous.

## Mobile

The four-item mobile navigation is unchanged. Campaigns is discoverable contextually
from People and direct Campaign links. Mobile supports campaign summary, recipient
timeline, exact message review/approval, seller-reported outcomes and pause/stop.
Campaign authoring remains responsive but desktop-oriented.

## State and accessibility review

All Campaign surfaces include loading, first-use/empty, safe error and needs-attention
states. Forms use fieldsets, legends and labels; tables have headers; controls have
visible focus and 44-pixel-class targets; state is communicated in text as well as
colour. The existing reduced-motion rule applies. Blocked reasons, mailbox
unavailable, policy change, quota/cooldown deferral, suppression and active
Opportunity stops use plain language without exposing internal/provider payloads.
