# Create PowerPoint trust and compatibility guide

- **Current scope:** authorised `.pptx` templates and editable PowerPoint output only
- **Validation profile:** `CREATE_PPTX_PROFILE_VERSION = 1`
- **Audience:** organisation administrators who prepare templates and sellers who review output

## What RevenueOS promises

The downloaded PowerPoint is the authoritative customer-facing file. The browser
review shows slide structure, customer-facing text, required content, claim sources
and Business Case values; it is not a pixel-identical PowerPoint renderer. PowerPoint
may render fonts, wrapping, spacing and layout differently by operating system,
installed fonts and PowerPoint version. RevenueOS therefore requires a final human
review before customer use.

For a supported template, RevenueOS guarantees the generated package can be safely
reopened, contains the expected slides and placeholder replacements, retains exact
required text, matches its non-removed claim manifest, contains the selected approved
Business Case values, and has no notes, comments, hidden slides, external links or
unnecessary internal metadata. It does not guarantee identical pixels or font
availability.

## Template compatibility states

| State                        | Meaning                                                                                                                                                                 | Administrator action                                                                                                                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Template ready**           | Secure parsing completed, every slide was reviewed, the title/audience and content placeholders needed for generation exist, and the version was deliberately approved. | Use the immutable approved version.                                                                                                                       |
| **Template needs attention** | The file is structurally safe but slide review, supported placeholders or approval is incomplete. It cannot be used for new generation.                                 | Use standard PowerPoint title, subtitle and content placeholders; mark non-editable slides **Reuse as is** or **Locked**; review every slide and approve. |
| **Template unsupported**     | The file contains a prohibited or unsupported package feature, invalid structure or exceeds a safety bound. There is no bypass.                                         | Export a clean standard `.pptx` without embedded, linked, active or unsupported content and upload a new version.                                         |

A source-file change always creates a new immutable template version. File hash,
compatibility/profile changes and slide-policy edits never silently inherit approval.
Existing versions validated under an older profile must be revalidated before new
generation.

## Supported PowerPoint profile

### Supported

- Standard transitional Open XML `.pptx` packages with no encryption or password.
- Up to 50 MB, 100 slides and the documented bounded package/media/XML limits.
- Native PowerPoint title, subtitle and body/content text placeholders.
- Every non-empty text shape on an editable slide must have a supported role; a slide
  with unmapped source text must be Locked/Reuse as is so stale customer copy cannot
  remain beside generated content.
- Common shapes and safe PNG, JPEG and GIF images already inside the package.
- Source masters, layouts, theme references, shape bounds and font-family references
  needed by selected approved slides.
- Approved locked/reuse-as-is slides and exact required legal content.
- Normal Unicode text, including accented names, smart punctuation, emoji and CJK
  characters, subject to font availability on the viewer's machine.

### Supported with limitations

- Ordinary text boxes, tables, shapes, headers/footers and slide numbers may remain on
  an approved locked/reuse-as-is slide, but RevenueOS does not edit or preview their
  internal layout.
- Font family names are retained where present. Proprietary font files are never
  extracted, embedded or redistributed; PowerPoint may substitute a missing font.
- Bounds and conservative text-density checks can recommend review, but RevenueOS
  does not reproduce PowerPoint's exact font metrics and never silently shrinks text
  to an unreadable size.
- “Locked” means RevenueOS generation does not modify the slide. It is not PowerPoint
  DRM and a recipient can still edit the downloaded file.

### Rejected

- `.ppt`, `.pptm`, PDF, DOCX, Google Slides and Keynote.
- Macros, ActiveX, OLE/embedded packages or workbooks, embedded fonts, custom XML,
  external templates/data/media and executable/action relationships.
- Every external relationship, including clickable web/email hyperlinks, in profile
  v1. RevenueOS never fetches a link while parsing or rendering.
- SVG, EMF/WMF, audio, video, 3D models and images whose bytes do not match their PNG,
  JPEG or GIF extension.
- Hidden slides for customer reuse. Speaker notes and comments may be detected for
  administrator attention, but are always removed from generated output.
- Encrypted/password-protected, malformed, ambiguous, path-traversing, duplicate-entry,
  excessively compressed or otherwise over-limit packages.

RevenueOS performs structural safety validation. This is not a general antivirus or
“virus-free” guarantee.

## Compatibility matrix

| Source feature              | Parsed?                    | Preserved?                                  | Editable?                          | Browser reviewed?     | Generated?            | Potential fidelity difference                     | Fails safe?                 |
| --------------------------- | -------------------------- | ------------------------------------------- | ---------------------------------- | --------------------- | --------------------- | ------------------------------------------------- | --------------------------- |
| Slide order                 | Yes                        | Selected approved order                     | Plan only                          | Yes                   | Yes                   | None structurally                                 | Yes                         |
| Slide title                 | Yes                        | Yes                                         | Supported placeholder only         | Yes                   | Yes                   | Font wrapping may vary                            | Yes                         |
| Body text                   | Yes                        | Yes                                         | Supported content placeholder only | Yes                   | Yes                   | Line wrapping may vary                            | Yes                         |
| Required/exact text         | Yes                        | Exact text checked after save               | No when exact                      | Yes                   | Yes                   | Visual wrapping only                              | Yes                         |
| Locked/reuse content        | Yes                        | Reused without RevenueOS edits              | No                                 | Structure/text        | Yes                   | Viewer may edit later                             | Yes                         |
| Placeholder replacement     | Yes                        | Source bounds/style retained where present  | Yes                                | Yes                   | Yes                   | Font metrics may vary                             | Yes                         |
| Approved reusable content   | Yes                        | Version-pinned                              | Policy-dependent                   | Yes                   | Yes                   | Layout best effort                                | Yes                         |
| Customer-specific claims    | Yes                        | Claim/slide/output equality checked         | Supported placeholder              | Yes with lineage      | Yes                   | Layout best effort                                | Yes                         |
| Business Case numbers       | Yes                        | Approved version/scenario/currency text     | No formula editing                 | Yes with lineage      | Yes                   | Layout best effort                                | Yes                         |
| Legal wording               | Yes                        | Exact visible shape text                    | No when exact                      | Yes                   | Yes                   | Wrapping may vary                                 | Yes                         |
| PNG/JPEG/GIF images         | Signature checked          | On selected slides                          | No                                 | Not pixel-previewed   | Yes                   | Viewer scaling/rendering may vary                 | Yes                         |
| Tables                      | Package structure only     | Locked/reuse slide only                     | No                                 | Text structure only   | Yes when package-safe | Not layout-guaranteed                             | Yes                         |
| Charts                      | Package structure only     | Locked/reuse slide only when self-contained | No                                 | No                    | Yes when package-safe | Not layout-guaranteed; embedded workbook rejected | Yes                         |
| Font names                  | Yes where authored         | Referenced, not redistributed               | No                                 | Name not visual proof | Yes                   | Substitution if unavailable                       | Review warning/limitation   |
| Text-box bounds             | Yes                        | Yes                                         | Text only                          | Structure only        | Yes                   | Exact wrapping not known                          | Conservative review warning |
| Hidden slides               | Yes                        | No                                          | No                                 | Warning/excluded      | No                    | Not applicable                                    | Yes                         |
| Notes/comments              | Detected                   | No                                          | No                                 | Warning only          | No                    | Not applicable                                    | Yes                         |
| Master/layout/theme         | Relationship-validated     | For selected slides                         | No                                 | No                    | Yes                   | Renderer/version differences possible             | Yes if unresolved/unsafe    |
| Hyperlinks                  | External relation detected | No in v1                                    | No                                 | No                    | No                    | Not applicable                                    | Yes—template rejected       |
| Header/footer/slide number  | Package structure only     | Best effort on selected slides              | No                                 | No                    | Yes when package-safe | Position/field rendering may vary                 | Yes if relationship unsafe  |
| Custom properties/thumbnail | Detected                   | No                                          | No                                 | No                    | No                    | Not applicable                                    | Yes                         |

## Authoring a compatible template

1. Start with a standard `.pptx`; do not rename another format.
2. Use the built-in **Title Slide** layout for the customer title and audience. Keep a
   native title placeholder and subtitle placeholder.
3. Use native title and body/content placeholders on slides RevenueOS may edit.
4. Remove or convert every other text box on an editable slide; otherwise choose
   **Reuse as is** or **Locked** so old customer-specific text cannot survive.
5. Use **Reuse as is** or **Locked** for approved brand, legal, image-heavy, table or
   otherwise non-editable slides. Mark legal wording exact where required.
6. Remove hidden/internal slides, comments, speaker notes, hyperlinks, embedded
   objects/workbooks/fonts and linked media before upload.
7. Use only embedded PNG/JPEG/GIF images with truthful extensions.
8. Upload as an administrator, confirm the organisation has authority to use it,
   review every slide, resolve the compatibility state and deliberately approve the
   exact version.

## Review, approval and secure download

A generated version remains **Needs review** until every pending claim is kept or
removed and the seller approves the exact structurally validated file. The button is
then **Download PowerPoint**. Each download request creates a short-lived, one-time
credential delivered in the request body, never in the URL. The server rechecks the
signed-in user's active membership, Create entitlement, tenant, exact current version,
template/source validity, approval and file checksum. A used, expired, wrong-user,
wrong-tenant, stale or revoked grant is denied; request a fresh download.

If the file is missing or its checksum differs, RevenueOS shows that the presentation
is unavailable and serves no bytes. A successful download consumes the grant before
the response is returned; if the connection then fails, request a new download.

See the [Create trust experience](../02-design/create-trust-experience.md) and
[engineering trust architecture](../03-engineering/create-pptx-trust-architecture.md).
