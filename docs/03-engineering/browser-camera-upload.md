# Browser camera and upload

## Supported capture

The web app uses `<input type="file" accept="image/jpeg,image/png">`, with `capture="environment"` as a mobile-browser hint. Desktop users can choose or drag and drop a file. Camera behaviour is controlled by the browser and device; RevenueOS does not claim a custom camera, native capture or background operation.

The browser rejects unsupported MIME declarations and files over 10 MB for fast feedback. The API repeats every check and is authoritative. The preview uses a short-lived local object URL and appears before upload confirmation.

## Upload sequence

The client calculates SHA-256, requests an idempotent upload, sends the exact MIME type to the supplied signed destination, completes verification and then requests analysis. Relative local URLs receive API authentication. Absolute object-storage URLs never receive RevenueOS bearer tokens.

Progress reflects checksum, upload, verification and processing stages. If a page is refreshed, the interaction’s tenant-scoped visual list restores uploaded, failed, review and completed states. Failed analysis exposes a bounded retry action.

## Validation and privacy

The server accepts only verified JPEG and PNG byte streams. It rejects executable or unknown content, size/checksum mismatch, malformed chunks/markers, excessive dimensions, excessive pixels, path traversal names and content after the image end marker. JPEG APP1/APP13/comment segments and unsafe PNG ancillary chunks are stripped before the object becomes available.
