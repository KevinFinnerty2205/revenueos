# Event-platform integration boundary

WO-031 has no Eventbrite, Cvent, Bizzabo, Swapcard, badge vendor, calendar or ticketing
integration. Events are created manually and attendee input is an explicitly selected,
authorised CSV. No external Event API, webhook, browser fetch or provider credential is
used in the application or standard automated tests.

A future connector must remain behind a provider-neutral adapter and separately
approve scopes, tenant mapping, authority evidence, source provenance, incremental
deletion, webhook replay protection, rate limits and contractual permission to store
attendee data. It must produce the same approved EventAttendee fields and cannot turn
registration into contactability, customer Evidence or buying intent.

Ticket sales, registration, payments, agenda/speaker/venue operations, badge OCR,
facial recognition and attendee marketing export are outside RevenueOS's product
boundary.
