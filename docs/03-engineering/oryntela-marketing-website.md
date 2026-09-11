# Oryntela marketing website

- **Work order:** WO-053
- **Status:** Complete; engineering review passed
- **Surface:** Public routes in the existing Next.js application
- **Deployment:** Not performed
- **Database/API:** Unchanged

## Commercial purpose

The website positions Oryntela as an **end-to-end sales platform** and, secondarily,
a **sales operating system** for Australian B2B leaders, managers and sellers. It
uses the actual completed product to tell one connected story from Prospect through
reviewed Closed-Won Handover. It is not a technical manual or an inventory of every
internal capability.

The selected hero is:

> **One sales system from prospect to handover.**
>
> Oryntela gives Australian B2B teams one clear way to find accounts, prepare
> reviewed outreach, run deals, forecast the number and hand over wins cleanly.

The primary CTA is **Request trial access**. It deliberately routes to direct email
contact instead of implying that public self-service trial activation is live. The
secondary CTA is **Explore the platform**.

## Information architecture

| Route           | Purpose                                                                    | Search state                     |
| --------------- | -------------------------------------------------------------------------- | -------------------------------- |
| `/`             | Commercial narrative, connected process, product proof, plan/trial entry   | Index                            |
| `/platform`     | Grouped Sell, Run, Manage and Close/Transition product story               | Index                            |
| `/pricing`      | Canonical Core, Growth, Complete and Enterprise pricing and trial terms    | Index                            |
| `/integrations` | Native CRM option and honest Microsoft/Google/HubSpot/Salesforce status    | Index                            |
| `/security`     | Implemented trust controls, explicit assurance limits and legal dependency | Index                            |
| `/contact`      | Trial, demo and support mail routes plus concise company identity          | Index                            |
| `/privacy`      | Honest shell recording the missing approved public Privacy Notice          | Noindex; absent from sitemap     |
| `/terms`        | Honest shell recording the missing approved public Terms                   | Noindex; absent from sitemap     |
| `/sign-in`      | Existing product authentication entry                                      | Noindex; disallowed in robots    |
| `/deal-room`    | Existing bearer-link buyer route                                           | Noindex/noarchive; not marketing |

The root 404 returns users to the website or Contact rather than assuming they are
inside the product.

## Application architecture

Marketing pages live under the App Router `(marketing)` route group and share one
server-rendered shell. The root layout remains common so the approved Geist Sans
variable font, Oryntela metadata and security headers are reused. No second
framework, application or runtime was introduced.

`apps/web/lib/public-routes.ts` records the narrow public marketing surface and the
current identity-aware application prefixes. Clerk middleware and the browser Clerk
provider run only for those known application and authentication paths. Marketing,
Deal Room and unknown paths therefore do not depend on identity initialisation; an
unknown path can reach the branded 404 even when Clerk is not configured. Every
authenticated route still sits beneath the fail-closed protected layout and retains
noindex metadata. The Deal Room keeps its independent fragment-token, Clerk-free and
noindex treatment. A new authenticated top-level route must be added to the
identity-aware prefix list in the same change.

`apps/web/lib/marketing.ts` owns the small website copy/data surface that needs
deterministic drift protection:

- hero positioning and CTAs;
- trial terms;
- public plan names, values and user limits;
- approved public integration families; and
- canonical-origin/metadata helpers.

The FastAPI commercial catalogue remains the pricing authority. A bounded Vitest
check compares the public tuples with `commercial_services.py` and separately
checks the shared browser trial literals. This avoids importing Python internals
into the website while detecting drift.

## Brand and visual system

The implementation reuses the exact WO-051/052 assets and tokens:

- Midnight `#0E1B32`;
- warm off-white `#F6F4EF`;
- copper `#C96B45` as an accent;
- mineral blue `#204E5A`; and
- local Geist Sans supplied through the existing `geist` package.

Product proof uses real Oryntela UI captures selected from the WO-052 synthetic
evidence set. Crops remove the development banner, development-workspace card and
capture duplication. Product media scales inside its frame at narrow widths, with no
page-level clipping or hidden CTA content. Full provenance and regeneration
instructions are in
[the screenshot record](oryntela-marketing-screenshot-provenance.md).

Motion is limited to short hover/focus transitions and one mobile menu marker. The
existing reduced-motion rule removes non-essential motion. The mobile menu uses an
explicit disclosure button, moves focus into the open navigation, contains Tab focus,
closes on Escape, returns focus to its trigger and prevents background scrolling while
open. There is no hero video, remote font, illustration package, third-party logo or
third-party script.

## Pricing and trial truth

The website publishes the owner-authorised V1 values in AUD:

| Plan       | Monthly  | Annual prepayment | Included users |
| ---------- | -------- | ----------------- | -------------- |
| Core       | AUD $200 | AUD $2,000        | 5              |
| Growth     | AUD $350 | AUD $3,500        | 10             |
| Complete   | AUD $500 | AUD $5,000        | 15             |
| Enterprise | Custom   | Custom            | Custom         |

Annual pricing is called an annual prepayment. The site makes no “two months free”
claim and publishes no Credit-pack or connector add-on price. The trial states 14
days, Complete-level modules, no card, no automatic charge and no automatic
conversion.

## Contact and conversion boundary

No public form, database table, API route or mail relay was added. Trial and demo
buttons use subject-prefilled `mailto:` links to `hello@oryntela.com.au`; product,
privacy and security support use `support@oryntela.com.au`. This is reliable with
the existing zero-additional-spend mailbox and avoids fake submission success,
public relay risk, unbounded persistence and spam infrastructure.

Public signup and payment are not activated by WO-053. Existing `/sign-up` and test
billing code remain unchanged and are not used as public conversion claims.

## Integration wording and activation

The site names Microsoft 365, Google Workspace, HubSpot and Salesforce as **built;
activation pending**. Each card says it is not yet production-active and that
availability depends on customer account authority, provider approval and WO-054
launch activation. Apollo is not named publicly. Native Oryntela CRM is presented
as the available system-of-record path that does not depend on a connector.

After WO-054, update status text only after each provider has its approved production
configuration and synthetic smoke evidence. A successful code build, OAuth app
registration or configured secret is not enough to change public wording to “live”.

## Security and legal boundaries

The trust page uses only implemented controls: tenant predicates and forced RLS,
role-aware checks, reviewed consequential actions, AES-256-GCM connector credential
envelopes, positive allow-listed Deal Room snapshots and organisation export/deletion
workflows. It explicitly avoids certification, penetration-test and residency claims.

Repository legal evidence gives the following exact status after the 11 September
2026 owner-drafting update:

- **Privacy: OWNER REVIEW DRAFT** — complete copy exists but is not approved or effective;
- **Terms: OWNER REVIEW DRAFT** — complete copy exists but is not approved or effective; and
- **Contact: READY** — general and support addresses are approved and routing-tested.

The Privacy and Terms pages render the canonical drafts with visible status and
noindex metadata. The website must not be treated as public-launch ready until the
owner approves the text, supplies the effective date, records versions and
fingerprints, and the required Terms-acceptance evidence exists.

## SEO and social metadata

The canonical origin is read from `NEXT_PUBLIC_SITE_URL` when it is a valid HTTPS
origin. HTTP is accepted only for `localhost`, `127.0.0.1` or `[::1]` local work;
other protocols and insecure non-local origins safely fall back to
`https://oryntela.com.au`. It never trusts forwarded request headers. Preview builds
must either omit the variable to retain the likely launch-domain canonical or set a
deliberate HTTPS canonical; WO-054 must confirm the final domain before deployment.

Every indexable page has a unique title, description, canonical URL, OpenGraph title,
OpenGraph description and X/Twitter summary-card metadata. The site-wide OpenGraph
image is generated locally at build time with the approved Oryntela wordmark,
symbol geometry and palette. No remote asset is needed.

`robots.ts` allows only the selected public marketing surface and disallows product,
auth, Deal Room and incomplete legal paths. `sitemap.ts` includes only Home,
Platform, Pricing, Integrations, Security and Contact. Structured data is limited to
truthful `Organization` and `SoftwareApplication` facts; there are no ratings,
reviews, customer counts or offer-availability claims.

## Privacy, analytics and performance

WO-053 adds no analytics, tracking pixel, non-essential cookie, consent banner, chat
widget or external script. The pages are server components except for the existing
root identity boundary. Product images use `next/image`, fixed intrinsic dimensions,
responsive sizing and below-fold lazy loading. The hero image alone is prioritised.

The global CSP and Deal Room headers are unchanged. The existing conservative
`no-store` response policy remains in place; cache/header tuning, if desired for the
deployed marketing surface, belongs to WO-054 and must preserve private-route safety.

## Launch activation checklist

WO-054 may deploy only after it separately confirms:

1. final canonical domain, hosting, DNS and TLS;
2. owner-approved Privacy Policy and Terms replacing draft/noindex status;
3. exact publisher/contracting treatment and public legal details;
4. Clerk production verification and public trial eligibility/abuse controls;
5. live Stripe, tax and purchase behaviour if payment is enabled;
6. per-provider approval, production configuration and synthetic smoke proof before
   integration status changes;
7. production Credit packs/prices before any Credit table is published;
8. support owners, hours and escalation process; and
9. final production security, performance and accessibility evidence.

WO-053 performs none of those activation steps.

## Engineering review

The 10 September 2026 engineering review found and fixed three bounded website defects:

1. the initial native mobile disclosure did not implement the required Escape,
   focus-containment, focus-return and background-scroll behaviour; and
2. the canonical-origin guard accepted a non-HTTP scheme when the hostname was
   `localhost`; and
3. robots directives covered private-path descendants but not their exact root URLs.

Regression coverage now enumerates every current protected route root against the
Clerk boundary, samples nested and lookalike paths, verifies canonical protocol rules,
and exercises the complete mobile-menu keyboard lifecycle. Privacy and Terms remain
documented WO-054 launch blockers, not unresolved WO-053 engineering defects.
