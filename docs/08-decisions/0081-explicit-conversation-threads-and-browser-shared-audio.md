# 0081: Explicit conversation threads and user-initiated browser shared audio

- Status: Accepted
- Date: 2026-10-31

## Context

Conversation memory previously depended on an Opportunity, which forced CRM setup
and encouraged unrelated buying initiatives at one company to share evidence.
Browser capture also treated a microphone journal as the only foreground media
source even though supported browsers can return audio with an explicitly selected
tab or display. Selecting a display alone does not prove that an audio track exists,
and browser/OS combinations vary.

## Decision

Add a tenant-owned `ConversationThread` as a lightweight initiative grouping.
Company and participant overlap may rank suggestions, but only an authenticated
user confirmation creates or changes an assignment. Current-conversation framework
coverage remains separate from cumulative confirmed-thread coverage. Cumulative
reads use only validated snapshots from completed, non-deleted interactions and
retain exact source conversation dates. Private workspaces are not a thread source.
Company scope is resolved across the Interaction, Opportunity and Person links;
conflicting relationships block grouping. An unassignment keeps a versioned
thread-free assignment state so optimistic locking stays monotonic across
remove/recreate cycles.

For supported web browsers, add two explicit capture modes: microphone only, and
shared tab/display audio plus microphone. The shared mode calls `getDisplayMedia`
from a user action, verifies a live audio track, then obtains the microphone and
mixes each distinct source once into one audio-only `MediaStream` for
`MediaRecorder`. Display video is retained only to observe the share lifetime; it
is never added to the recorder stream or uploaded. Missing shared audio, permission
denial, source ending, device changes, cancellation and cleanup are explicit states.
Transcript import and authorised recording upload remain alternatives.

Private notes typed during capture are stored separately from enhanced notes in the
existing user-private optimistic-lock workspace. A media error does not clear them.

## Alternatives considered

- Company-wide aggregation was rejected because it combines separate initiatives.
- Reusing Opportunity as the mandatory grouping key was rejected because the core
  conversation workflow must work without CRM setup.
- Treating every display share as audio capture was rejected because the browser may
  return video without audio.
- Recording the display video and discarding it later was rejected because it would
  collect unnecessary media.
- Choosing or activating a realtime transcription provider in this decision was
  rejected. Provider-neutral ordered/retry orchestration is implemented first; the
  provider, privacy, region and variable-cost decision remains narrow and explicit.

## Consequences

- Users control longitudinal grouping and can correct it without rewriting source
  conversations.
- Preparation can use a confirmed thread without using a company-wide fallback.
- Browser shared audio is a supported-mode claim, not a universal system-audio or
  cross-application capture claim.
- Chrome/macOS has one controlled real-browser verification record; other release
  combinations require their own evidence.
- Native capture, call detection, overlays and installers remain deferred.
