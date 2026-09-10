# Oryntela marketing screenshot provenance

- **Work order:** WO-053
- **Status:** Curated from real WO-052 product captures
- **Customer data:** None
- **Published location:** `apps/web/public/marketing/product/`

## Source authority

WO-052 captured twenty-seven customer-facing Oryntela surfaces from the actual Next.js
product using deterministic synthetic fixtures. The
[WO-052 record](../07-sprints/wo-052-oryntela-customer-facing-rebrand.md) confirms that
the set contains synthetic data and no customer data. WO-053 selects and crops those
captures; it does not generate glossy replacement dashboards or modify product UI.

The source files carry a `.png` filename from the earlier evidence workflow but are
JPEG-encoded. WO-053 writes correctly named `.jpg` outputs. `sips` adds no remote
content and performs only an explicit crop.

## Published files and crops

Crop arguments are `height width`, followed by `offsetY offsetX`.

| Published file                  | WO-052 source                                 | Crop                  | Marketing use                         |
| ------------------------------- | --------------------------------------------- | --------------------- | ------------------------------------- |
| `sales-brain.jpg`               | `wo-052-sales-brain-desktop.png`              | `780 560`, `24 125`   | Home hero and Sales Brain proof       |
| `prospect.jpg`                  | `wo-052-prospect-desktop.png`                 | `700 590`, `20 125`   | Prospect/target-market proof          |
| `engage.jpg`                    | `wo-052-engage-desktop.png`                   | `360 590`, `20 125`   | Engage pre-launch boundary            |
| `create.jpg`                    | `wo-052-create-desktop.png`                   | `720 600`, `20 125`   | Create and Business Case proof        |
| `opportunity-workspace.jpg`     | `wo-052-opportunity-desktop.png`              | `720 600`, `20 125`   | Opportunity/Native CRM proof          |
| `pipeline.jpg`                  | `wo-052-pipeline-desktop.png`                 | `900 610`, `20 125`   | Pipeline proof                        |
| `deal-room.jpg`                 | `wo-052-deal-room-admin-desktop.png`          | `900 610`, `4550 125` | Seller Deal Room publication proof    |
| `handover.jpg`                  | `wo-052-handover-desktop.png`                 | `620 610`, `1370 125` | Closed-Won transition boundary        |
| `analytics.jpg`                 | `wo-052-analytics-desktop.png`                | `920 430`, `80 0`     | Targets/Forecast/Analytics proof      |

## Regeneration

Run from the repository root. Replace `<source>` and `<output>` with one row from the
table, preserving the recorded values:

```sh
mkdir -p apps/web/public/marketing/product
sips -c <height> <width> --cropOffset <offsetY> <offsetX> \
  docs/07-sprints/assets/wo-052/<source> \
  --out apps/web/public/marketing/product/<output>
```

After regeneration:

1. inspect every output at native resolution;
2. confirm the Oryntela UI and approved palette are visible;
3. confirm only `[DEMO]`, `[CHECKPOINT 3]`, `.example` or explicitly labelled
   synthetic records appear;
4. confirm the development-mode banner, development-workspace card, debug bubbles,
   secrets, tokens, internal UUIDs and broken states are absent;
5. confirm no standalone legacy `RevenueOS` display name appears;
6. confirm the Engage caption still explains its deliberately visible inactive
   production-mailbox boundary; and
7. rerun web unit, Playwright and production-build checks.

## Content review

All nine WO-053 outputs were visually inspected after cropping. They contain actual
rebranded product components and synthetic names/values. The Engage capture is the
only published image with an inactive-provider notice; the adjacent page content and
caption explicitly explain that pre-launch state. No image contains a customer name,
real email, phone, contract, secret, token or live provider result.

These are marketing assets, not new product fixtures. A future product UI change
should regenerate the affected crop from a fresh deterministic synthetic run rather
than retouching the old screenshot.

## Website review evidence

Production-build screenshots from the WO-053 local review are stored in
`docs/07-sprints/assets/wo-053/`. The set covers Home at desktop, 768 px tablet and
390 px mobile widths; the expanded 390 px mobile menu; desktop and mobile Platform
and Pricing; the dark Platform management section; desktop Integrations, Security,
Contact, Privacy, Terms and branded 404; and a 390 px Contact view.

The screenshots were taken from a local `next start` production build, except that
the same route set was first inspected in development while iterating. No deployment,
external request, customer data or live provider was involved. Automated DOM checks
also inspected every public route and the 404 at 1,440 px, 768 px and 390 px for
viewport overflow and primary-content bounds.
