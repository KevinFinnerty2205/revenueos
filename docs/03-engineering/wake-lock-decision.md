# Screen wake lock decision

## Decision

Request the browser Screen Wake Lock API only after recording starts, release it
after finalisation/cancellation/unmount, and request it again when a still-active
recording returns to a visible tab. Treat rejection, release or absence as a
normal degraded state.

## Rationale

A wake request can reduce accidental screen sleep during a foreground field
conversation, but browser and operating-system policy remains authoritative.
Battery state, permissions, visibility changes and platform support can release
or reject the request at any time. RevenueOS therefore shows `Requested` or
`Not guaranteed`, never `Device will stay awake`.

## Consequences

- No wake request occurs before explicit consented recording.
- Passive Companion does not request wake lock.
- Wake lock failure does not fail recording.
- The user must still keep the page visible and the device awake.
- There is no background service, native integration or operating-system bypass.
