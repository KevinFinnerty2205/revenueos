# Google Meet online-meeting assessment

**Reviewed:** 2026-08-15 against official Google documentation. **Decision:**
recommended first technical spike if pilot ecosystems do not dictate another
provider; no Google connection is implemented.

The Meet REST API models conference records, participants, recordings and
transcripts. A production adapter would associate an authorised conference record,
list only available post-meeting artefacts and retrieve the selected artefact using
the smallest read-only OAuth scopes. Recording/transcript availability varies by
Google Workspace edition, administrator policy and meeting settings; Drive ownership
and retention must be validated for the pilot organisation.

Google is nominated for a narrow spike because its v2 API has purpose-built meeting
artefact resources and structured transcript entries, not because entitlement is
universal. The spike must test user/admin authorisation, calendar correlation,
participant minimisation, rate limits, revocation and local/upstream deletion
boundaries before any production flag is enabled.

Primary references: [Meet REST API
overview](https://developers.google.com/workspace/meet/api/guides/overview), [Meet
v2 reference](https://developers.google.com/workspace/meet/api/reference/rest/v2),
[work with artefacts](https://developers.google.com/workspace/meet/api/guides/artifacts),
and [recordings get/scopes](https://developers.google.com/workspace/meet/api/reference/rest/v2/conferenceRecords.recordings/get).
