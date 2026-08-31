# Create trust experience

- **Status:** implemented for WO-039B
- **Principle:** the downloaded PowerPoint is the truth; the browser is a structured review

## Template review

The first review card names one plain-language state without a score:

- **Template ready** — safe, reviewed and compatible;
- **Template needs attention** — safe processing completed but review, placeholders or
  approval are incomplete; or
- **Template unsupported** — the file cannot pass the supported profile.

Primary copy explains the corrective action. It never exposes ZIP/XML/relationship
jargon and never offers **Allow anyway**, **Trust file** or a validation bypass.
Technical safe codes remain for operator diagnostics only.

When a slide lacks supported placeholders, editable policies are unavailable and the
administrator is directed to choose **Reuse as is**/**Locked** or author a new source
version with standard PowerPoint placeholders. A compatible customer-specific title
requires native title and subtitle/audience placeholders. Every slide remains subject
to deliberate review; compatibility never silently grants approval.

## Plan, preview and final output

The flow separates three layers:

1. **Plan** — included slide order, required/exact status and source class.
2. **Review** — customer-facing titles/body text, claim lineage, Business Case values,
   required/legal content and keep/remove decisions.
3. **PowerPoint output** — the authoritative downloaded `.pptx`.

The review heading carries visible copy:

> Review the structure and customer-facing content below. The downloaded PowerPoint
> is the final file. Fonts, spacing and layout may vary slightly by device and
> PowerPoint version.

This is ordinary product copy, not hidden legal text. RevenueOS never says “pixel
perfect”, “looks exactly like PowerPoint”, “font fidelity guaranteed” or “locked in
PowerPoint”. Conservative overflow signals say **Review recommended**; they do not
silently compress text.

## Approval and download

Lifecycle language remains customer-oriented:

```text
Draft plan → Generating → Needs review → Approved → Ready to download
```

The user never sees “bearer grant”. **Download PowerPoint** appears only for the
current approved, structurally validated version. Expiry/replay/membership changes
lead to a fresh-download recovery, not an authentication/storage explanation.

| Failure                       | Customer copy / recovery                                                                                             |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Unsupported upload            | “We couldn't use this template because it contains an unsupported PowerPoint feature.” Upload a clean standard PPTX. |
| Over-limit/complex upload     | “We couldn't use this template because the file is too large or complex.” Simplify it; no bypass.                    |
| Missing standard placeholders | Explain title/subtitle/content placeholders or use Locked/Reuse as is.                                               |
| Generation validation         | “The presentation could not be safely finalised. No downloadable file was created.” Regenerate or contact support.   |
| Expired/used download         | “This download link has expired. Request a new download.”                                                            |
| Missing/corrupt file          | “This presentation file is unavailable. Generate a new version or contact support.”                                  |
| Approval/source invalidated   | Return to review/regeneration with the source-change reason.                                                         |

## Mobile and accessibility review

At 390 px, compatibility state, disclosure, claim review, approval state and download
remain readable without horizontal page overflow. Template administration remains
desktop-first. Status is communicated by text as well as colour; headings and
landmarks are semantic; form controls retain labels, keyboard navigation and visible
focus; motion is not needed to understand state.

The structured review remains useful without thumbnails. The uploaded template owns
its authored reading order, alt text and contrast; RevenueOS does not claim to repair
those source accessibility properties.

See the [customer compatibility guide](../01-product/create-powerpoint-trust-guide.md).
