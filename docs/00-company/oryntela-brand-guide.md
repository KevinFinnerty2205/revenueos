# Oryntela practical brand guide — final identity candidate

> **FINAL CANDIDATE — OWNER SIGN-OFF REQUIRED**
> Status: WO-051 design and documentation only. Do not use these assets in
> production until Kevin gives explicit final owner sign-off and separately
> authorises WO-052.

## 1. Identity summary

### Selected direction

The final candidate is **Meridian / Direction**: M1 supplies the brand idea and
logo architecture; M3 contributes only small-size discipline and shape economy.
The result is a refinement of M1, not a mechanical composite.

The identity communicates, abstractly:

- direction and orientation;
- clarity emerging from evidence;
- deliberate commercial movement; and
- one connected sales system.

It intentionally avoids a literal compass, arrow, navigation pin, target, chart,
AI sparkle, connected-dot network or agent character.

### Personality

**Premium/minimal first; intelligent/commercial second.** The system is calm,
precise and useful. Copper provides a human signal, not visual noise. Gradients,
glow and decorative “AI” effects are not part of the core identity.

### Architecture

The primary architecture is **symbol + wordmark**. Use the full horizontal lockup
whenever space permits. The symbol can stand alone only where the brand is already
clear, including favicon, app icon, compact navigation and profile contexts.

No tagline is part of the identity. “The end-to-end sales platform.” may appear in
the non-production review mockups only; WO-053 owns any final tagline decision.

## 2. The mark

The mark has two essential forms:

1. an open, asymmetric course; and
2. one rising meridian crossing the internal negative space.

The open course keeps the device from becoming a literal compass or a closed
letterform. The rising meridian creates directional tension without an arrowhead.
The copper terminal is a restrained accent. It can disappear in monochrome without
changing the silhouette or meaning.

The final geometry uses two economical strokes with equal weight, round terminals
and no dependent detail. This is the M3-influenced simplification: the concept's
motion is preserved while junctions and decorative complexity are removed.

## 3. Wordmark

### Selected case

Use **`Oryntela`** in the logo, while ordinary prose continues to spell the name
the same way. Title case was selected over `ORYNTELA` after lockup and navigation
testing because it:

- reads faster at product-header sizes;
- creates a more distinctive word shape;
- avoids the generic tracked-capitals pattern common in enterprise software; and
- balances the mark's geometric tension with a credible, human rhythm.

### Construction

The wordmark is an outlined vector asset, not live text. It starts from Geist's
neo-grotesk proportions, then uses pair-specific optical placement rather than one
global tracking value. The opening `O` is given room against the symbol, the
`ry`/`nt` joins are tightened selectively, and the single-storey alternate `a`
gives the terminal a quiet proprietary character without futuristic illegibility.

Never recreate the wordmark by typing the name in Geist or another font. Use the
supplied SVG master.

## 4. Logo variants

| Use                          | Asset                                                                          | Rule                                                                                           |
| ---------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| Primary / horizontal / light | [`oryntela-logo-primary.svg`](assets/oryntela-brand/oryntela-logo-primary.svg) | Midnight mark and wordmark with copper terminal on white or warm light surfaces.               |
| Dark surface                 | [`oryntela-logo-dark.svg`](assets/oryntela-brand/oryntela-logo-dark.svg)       | Warm-white mark and wordmark with copper terminal on deep canvas or midnight.                  |
| Black monochrome             | [`oryntela-logo-black.svg`](assets/oryntela-brand/oryntela-logo-black.svg)     | One-colour black for print, engraving, fax-like or constrained output.                         |
| White monochrome             | [`oryntela-logo-white.svg`](assets/oryntela-brand/oryntela-logo-white.svg)     | One-colour white on sufficiently dark imagery or colour.                                       |
| Compact                      | [`oryntela-logo-compact.svg`](assets/oryntela-brand/oryntela-logo-compact.svg) | Optional centred stack for square or narrow compositions; never use in the application header. |
| Wordmark only                | [`oryntela-wordmark.svg`](assets/oryntela-brand/oryntela-wordmark.svg)         | Use only where the symbol appears nearby or the context is unmistakably Oryntela.              |
| Symbol                       | [`oryntela-symbol.svg`](assets/oryntela-brand/oryntela-symbol.svg)             | Favicon, app, compact navigation or established-profile contexts.                              |

The primary SVG is intentionally also the horizontal and light-background master;
duplicating the same geometry under extra filenames would create avoidable drift.

## 5. Clear space and minimum size

Let **x** equal the width of the symbol's meridian stroke. Maintain at least
**1.5x** clear space on every side of the full lockup, wordmark, compact lockup and
standalone symbol. No text, container edge, photograph detail or other mark may
enter that area.

Minimum sizes:

| Asset                  |     Digital |      Print |
| ---------------------- | ----------: | ---------: |
| Full horizontal lockup |  144px wide |  38mm wide |
| Wordmark only          |   96px wide |  25mm wide |
| Standalone symbol      | 16px square | 5mm square |

At 16px, use the favicon/symbol asset only. The copper terminal may be rendered in
colour, but recognition must never depend on it. Below 16px, use a platform-provided
fallback rather than inventing another micro-mark.

## 6. Colour system

### Core palette

| Role         | Name           | Value     | Intended use                                                         |
| ------------ | -------------- | --------- | -------------------------------------------------------------------- |
| Primary      | Midnight       | `#0E1B32` | Core mark, wordmark, text, primary controls and deep surfaces.       |
| Background   | Warm off-white | `#F6F4EF` | Calm brand canvas and future marketing/document background.          |
| Accent       | Copper         | `#C96B45` | Small distinguishing signals, focus treatment and the mark terminal. |
| Secondary    | Mineral blue   | `#204E5A` | Supporting digital/product emphasis, never a second dominant brand.  |
| Dark canvas  | Deep canvas    | `#07101F` | Dark presentation and hero surface.                                  |
| Surface      | White          | `#FFFFFF` | Product cards, forms and document interior surfaces.                 |
| Muted text   | Muted slate    | `#59687A` | Secondary copy on light surfaces.                                    |
| Light border | Border slate   | `#7C8999` | Essential boundaries on light surfaces.                              |
| Dark muted   | Dark muted     | `#B9C2CC` | Secondary copy on dark surfaces.                                     |
| Dark border  | Dark border    | `#5A6880` | Essential boundaries on dark and midnight surfaces.                  |

Copper is an accent, not the dominant colour. Do not use white normal-sized text
on copper: the contrast is only 3.70:1 on `#FFFFFF`. If a copper control is later
approved, use midnight text, which is 4.64:1, and test every interaction state.

### Candidate semantic tokens

The reusable light and dark token maps are in
[`brand-tokens.json`](assets/oryntela-brand/brand-tokens.json). The minimum brand
surface is:

- `brand-primary`
- `brand-primary-foreground`
- `brand-secondary`
- `brand-accent`
- `brand-surface`
- `brand-background`
- `brand-text`
- `brand-muted`
- `brand-border`
- `brand-focus`

Success, warning, error and information colours remain separate product-semantic
tokens. Never substitute brand copper or mineral blue for those meanings.

### Contrast evidence

Ratios below use WCAG relative luminance. Text combinations meet WCAG AA for their
stated size; essential non-text boundaries and focus indicators meet 3:1.

| Combination                    |   Ratio | Candidate use               | Result                |
| ------------------------------ | ------: | --------------------------- | --------------------- |
| Midnight on warm off-white     | 15.64:1 | Body/display text and logo  | Pass AAA              |
| Midnight on white              | 17.19:1 | Product text and controls   | Pass AAA              |
| Warm off-white on midnight     | 15.64:1 | Dark-surface text and logo  | Pass AAA              |
| Warm off-white on deep canvas  | 17.32:1 | Dark hero text and logo     | Pass AAA              |
| Mineral blue on warm off-white |  8.31:1 | Supporting text/link        | Pass AAA              |
| Muted slate on warm off-white  |  5.18:1 | Secondary normal text       | Pass AA               |
| Dark muted on deep canvas      | 10.56:1 | Secondary dark-surface text | Pass AAA              |
| Copper against warm off-white  |  3.37:1 | Focus/non-text accent       | Pass non-text         |
| Copper against deep canvas     |  5.14:1 | Focus/non-text accent       | Pass                  |
| Border slate against white     |  3.56:1 | Essential light boundary    | Pass non-text         |
| Dark border against midnight   |  3.05:1 | Essential dark boundary     | Pass non-text         |
| White on copper                |  3.70:1 | Normal text                 | **Fail — prohibited** |

WO-052 must still validate component states in context; these ratios do not approve
future CSS implementation by themselves.

## 7. Typography

Use one primary family: **Geist Sans**.

| Role           |          Weight | Guidance                                                                             |
| -------------- | --------------: | ------------------------------------------------------------------------------------ |
| Brand/display  |      600 or 700 | `-0.02em` to `-0.01em`; 1.05–1.15 line height; use sentence/title case.              |
| UI heading     |             600 | `-0.01em`; 1.15–1.25 line height.                                                    |
| UI/body        |             400 | Normal tracking; 1.45–1.60 line height; target 55–75 characters per line.            |
| Labels/actions |      500 or 600 | Normal tracking in sentence case; `0.06em` only for short uppercase metadata labels. |
| Dense figures  | 400, 500 or 600 | Use `font-variant-numeric: tabular-nums lining-nums`.                                |

Fallback stack:

```css
font-family: "Geist", "Helvetica Neue", Arial, sans-serif;
```

Do not add a second brand family. Geist Mono is not required for ordinary numeric
alignment; use tabular numerals in Geist Sans. A later production implementation
should self-host only the necessary WOFF2 subsets/weights, never call a remote font
service, and must retain the OFL notice.

The official Geist repository and licence were rechecked on 9 September 2026 at
revision `10dc7658f13c38a474cde201bb09a4617267545b`. It identifies Geist as licensed
under SIL OFL 1.1. The candidate package contains the upstream licence text but no
font binary. See
[`THIRD-PARTY-LICENCES.md`](assets/oryntela-brand/THIRD-PARTY-LICENCES.md).

## 8. Favicon, app and profile use

- Favicon source: [`oryntela-favicon.svg`](assets/oryntela-brand/oryntela-favicon.svg).
- ICO: [`oryntela-favicon.ico`](assets/oryntela-brand/oryntela-favicon.ico), with
  16, 32 and 48px frames.
- App source: [`oryntela-app-icon.svg`](assets/oryntela-brand/oryntela-app-icon.svg),
  with transparent 64, 128, 256 and 512px checks.
- Social/profile:
  [`oryntela-social-profile.svg`](assets/oryntela-brand/oryntela-social-profile.svg)
  and one 512px derivative.

The standalone symbol does not rely on a rounded-square container. Platform masks
may crop the optional social treatment; keep the supplied safe zone and do not
enlarge the mark inside it.

## 9. Basic UI application

The non-production owner board shows five application tests:

- **Product header:** primary lockup at real navigation scale; copper appears only
  in the terminal and focus/active signal.
- **Login:** primary lockup on warm light with a white form surface and restrained
  mineral support.
- **Deal Room:** dark logo and calm buyer-facing hierarchy on deep canvas; the
  experience is not made to look like an internal CRM screen.
- **Business Case cover:** generous warm space, midnight type, one copper rule and
  tabular commercial figures.
- **Website header:** minimal future hero using real product-language context; it
  is not a tagline decision or website implementation.

These tests validate fit only. They do not replace any current production surface.

## 10. Incorrect use

Do not:

- stretch, condense, skew or rotate any logo asset;
- alter the symbol-to-wordmark proportions or spacing;
- close the outer course or turn the meridian into an arrow;
- recolour the mark arbitrarily or make copper dominant;
- add gradients, shadows, bevels, glow, textures or animation to the core mark;
- place the logo on a low-contrast or visually busy background;
- recreate the wordmark with typed Geist, another font or manual tracking;
- put the symbol in an arbitrary rounded-square container;
- use the compact lockup when the horizontal version fits; or
- attach a tagline to the master logo.

## 11. Small-size and reproduction results

| Test                      | Result | Observation                                                                          |
| ------------------------- | ------ | ------------------------------------------------------------------------------------ |
| 16px                      | Pass   | Open silhouette and rising meridian remain distinguishable; colour is non-essential. |
| 32px                      | Pass   | Round terminals and internal negative space are clean.                               |
| 48px                      | Pass   | Copper terminal is controlled and the mark does not need a container.                |
| 64/128/256/512px app icon | Pass   | Transparent safe-zone treatment scales without clipping.                             |
| Black on white            | Pass   | One-colour silhouette retains the identity.                                          |
| White on black            | Pass   | No counter or stroke closes up.                                                      |
| Warm light background     | Pass   | Primary logo has 15.64:1 logo/text contrast through midnight.                        |
| Midnight/deep background  | Pass   | Dark logo has 15.64–17.32:1 logo/text contrast through warm white.                   |

## 12. Similarity sanity check

On 9 September 2026, the final symbol and lockup were compared again with the
current public visual identities previously audited for Salesforce, HubSpot, Gong,
Clari, Outreach, Salesloft, Apollo and Pipedrive, and with ORYNTECH public material.

- The final candidate does not use the reviewed category's cloud, connector node,
  sparkle/starburst, agent character, infinity loop, purple-gradient orb or closed
  circular-gradient device.
- The symbol stays asymmetric and open, while ORYNTECH public material reviewed in
  this work presents a closed multicolour circular device with a lowercase
  wordmark. The Oryntela wordmark is title case and the core mark has no gradient.
- The remaining generic-form risk is that an open course plus diagonal may be read
  broadly as direction or an abstract `O`. The unequal opening, blunt meridian and
  detached copper terminal reduce literal compass, arrow and monogram readings.
- No competitor artwork is copied into the repository. No close unexpected device
  match was identified in this bounded design review.

This is a visual design sanity check only. It is not a device search, freedom-to-use
opinion, registrability assessment or trade-mark clearance. The existing ORYNTECH
and ORYNTE name/class questions remain priorities for qualified professional advice
before irreversible public investment.

## 13. Status and approval boundary

The candidate package contains no customer data, migration or production code
change. New spend is AUD $0. The current module names remain unchanged. PR #81 must
remain **open, draft and unmerged**.

After Kevin inspects the final review board, the permitted responses are:

- explicit final owner sign-off; or
- a bounded refinement request within WO-051.

Do not begin WO-052, apply the candidate assets to production, change RevenueOS
references or lock a tagline before that explicit sign-off.
