# Account Research trust and sources

**Status:** Current WO-026 product contract

Account Research uses exactly four visible trust states:

| UI label            | Stored value        | Meaning                                                                                      |
| ------------------- | ------------------- | -------------------------------------------------------------------------------------------- |
| Verified            | `verified`          | Supported by a primary, official-public or regulatory source in the same research run.       |
| From data provider  | `provider_supplied` | Supplied by a structured business-data provider and not independently verified by RevenueOS. |
| RevenueOS inference | `inferred`          | A cautious hypothesis derived from cited public observations.                                |
| Not established     | `unknown`           | The available sources do not establish the value.                                            |

Verified is deterministic, not a confidence threshold. It requires at least one
citation whose authority is primary, official-public or regulatory. A provider
profile alone can never produce Verified. Provider-supplied observations require a
structured-provider citation. Inferences require cited support and cautious wording
such as “may”, “could”, “might”, “possible” or “worth exploring”. Unknown claims do
not carry a citation that could misleadingly appear to prove the unknown value.

Each displayed source is metadata only: title, publisher, canonical HTTPS URL,
source type, authority, optional publication date, provider reference and content
fingerprint. RevenueOS does not persist full pages, active HTML or raw provider
payloads. Duplicate URLs and fingerprints are rejected within a run. Every
observation citation must resolve to a source in that same organisation, target and
run; a provider cannot invent or borrow a citation.

Potential sales context is always hypothetical. It is never labelled Verified and
does not become a predictive score. Recent developments are dated when the
provider supplies a reliable publication date. Source links open through normal
browser navigation using a new browsing context, `noopener noreferrer` and a
no-referrer policy.
