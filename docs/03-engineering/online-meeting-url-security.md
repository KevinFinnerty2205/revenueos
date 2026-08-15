# Online Meeting URL security

**Status:** WO-018 focused security control.

Meeting references are passive navigation data, never server-fetch targets. The
normaliser requires HTTPS, rejects credentials and non-default ports, allowlists
known hosts and meeting path shapes for Teams, Zoom and Google Meet, and stores a
safe representation without query parameters or fragments. `other` uses an opaque
external meeting reference rather than presenting an unapproved link. Raw links and
tokens are not included in audit events, telemetry or logs.

The browser renders **Open Meeting** only for the stored normalised URL, using a new
tab with `noopener noreferrer`. RevenueOS never auto-joins, prefetches, follows a
redirect or navigates in the background. The API never performs DNS resolution or
HTTP requests for a supplied meeting URL, removing the SSRF route entirely.

Provider credentials and future short-lived download URLs are not meeting URLs.
They must remain inside a connector adapter, be encrypted where persisted, be
excluded from models/audits and never be returned to the general Interaction UI.
