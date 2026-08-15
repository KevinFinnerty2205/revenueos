# Email sanitisation and security guide

## Plain-text-only contract

WO-019 accepts manually selected plain text. HTML, MIME attachments, remote images,
tracking pixels, mailbox links and provider message payloads are outside the
current contract. RevenueOS neither renders HTML nor follows links found in email
text.

## Conservative normalisation

The server removes a trailing signature only when it follows a conventional
signature delimiter. It removes a quoted reply only when the boundary is
unambiguous, such as a standard `On … wrote:` line or conventional header block.
When a separator may be meaningful content, the text is retained and
`quote_handling=ambiguous` is recorded. Original body text remains the auditable
source until deletion; normalised text is a processing aid, not a replacement.

No address or sender name is inferred from text. Customer identity is verified
only through a Contact identifier already present in the same organisation and
account. Unknown senders stay unknown.

## Untrusted-content controls

Email instructions aimed at the model are treated as quoted evidence, never as
system instructions. The AI provider receives a bounded plain-text value with
explicit source type/direction supplied by server policy. Strict response schemas
and source-location validation fail closed. Outbound/internal email cannot create
customer-direct findings regardless of its wording.

Subjects, addresses, bodies, quoted material, prompts and provider payloads are
excluded from request, event and exception logs. Safe telemetry includes source ID,
direction, processing state, duration/counter data and safe error code only.

## Deletion and export

An authorised tenant export contains the source email body and metadata because it
is a user-requested data export. Routine API metadata responses and logs do not.
Deletion clears subject, original body and normalised body, then deletes candidate,
accepted-evidence and source-snapshot lineage. Upstream mailbox data is unaffected
because no mailbox connection exists.
