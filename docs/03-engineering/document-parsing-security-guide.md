# Document parsing and security guide

## Boundary

Document parsing is deliberately narrow: PDF and UTF-8 TXT only. Parsing is local
and bounded before private storage and before any AI provider call. RevenueOS does
not run document macros, scripts, URLs, attachments, OCR, shell commands or remote
fetches.

## Rejection rules

The parser rejects:

- files over the configured byte, page or extracted-character limits;
- extension/media-type mismatches, invalid UTF-8, NUL and unsafe control bytes;
- malformed, truncated or password-protected PDFs;
- PDFs containing JavaScript, automatic actions, launch actions, embedded files,
  rich media or XFA forms;
- blank/image-only PDFs because OCR is not an approved path; and
- the EICAR test signature used to verify malware rejection behaviour.

PDF parsing enforces a PDF header and end marker and extracts text page by page.
Each non-empty paragraph becomes a separately bounded fragment. Failure produces a
safe code; raw bytes and parser internals do not enter logs.

This is format hardening, not a replacement for a production malware-scanning
service. A production scanner remains an explicit deployment dependency if the
private beta accepts broader or higher-risk files.

## Prompt-injection boundary

Document text is untrusted evidence. Provider instructions state that embedded
requests are content, not commands. The provider receives a bounded structured
payload and must return a strict schema. Unknown fields, unsupported categories,
oversized statements and invalid page/paragraph citations fail processing rather
than being coerced. Customer- and seller-origin rules are assigned by server policy
after parsing and cannot be supplied by model output.

## Storage and download

Objects use tenant-prefixed opaque keys in the configured private storage adapter.
Production cannot use the local filesystem adapter. Downloads require normal
authentication, tenant lookup and a short-lived signed grant and return no-store
headers. The browser never receives provider credentials or storage keys.

Deletion is object-first. If object removal fails, database lineage is retained in
`deletion_pending`/`delete_failed` so an operator can retry without falsely
reporting deletion.
