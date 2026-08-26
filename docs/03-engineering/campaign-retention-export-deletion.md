# Campaign retention, export and deletion

Campaign data inherits the organisation's private-beta retention setting. Bounded
retention selects completed/stopped Campaigns older than the cutoff, deletes their
enrolment/step/audience/version graph, then deletes linked Outreach/Action records.
Outreach linked to a non-terminal Campaign is excluded from ordinary standalone
Outreach expiry so history cannot be orphaned.

Export schema version 20 includes Campaign lifecycle, public version/approval fields,
ordered sequence, exact audience/eligibility snapshot, enrolment state/outcome and
schedule/Outreach references. It deliberately excludes worker IDs, leases, internal
launch/policy fingerprints, credentials and provider payloads. Message subject/body
remain covered by the existing authorised Outreach export.

Deleting a canonical Contact immediately cancels queued retryable Campaign execution,
cancels unsent steps, stops the enrolment and nulls live Contact references in
audience/enrolment. Recipient snapshots remain until retention so history is
understandable. The database immutability guard permits only this reference scrub on
a published audience.

Organisation deletion removes Campaign step/enrolment/audience/sequence/version rows
before Outreach/Action and membership data. Published-row deletion remains available
only through approved retention/organisation-deletion paths; normal product APIs do
not expose Campaign deletion.
