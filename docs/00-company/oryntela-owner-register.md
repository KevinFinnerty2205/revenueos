# Oryntela owner register

- **Last verified:** 4 September 2026 (Australia/Sydney)
- **Scope:** brand administration, domains and business correspondence
- **Product implementation status:** no RevenueOS-to-Oryntela technical rebrand has
  been started or authorised by this record

This register records owner-approved administrative facts and completed synthetic
mail-routing checks. It is not a Privacy Notice, Terms of Use, DPA, beta agreement,
subprocessor approval or authority to process real partner/customer data. Oryntela
is the registered business name and product brand; it does not replace the legal
entity in contracts or legal notices.

## Holder and brand

| Item                            | Recorded value                          | Status         |
| ------------------------------- | --------------------------------------- | -------------- |
| Legal entity/holder             | Management Services Australia Pty. Ltd. | **CONFIRMED**  |
| ABN                             | 15 113 119 556                          | **CONFIRMED**  |
| ACN                             | 113 119 556                             | **CONFIRMED**  |
| Registered business name        | ORYNTELA                                | **REGISTERED** |
| Business-name registration term | One year                                | **CONFIRMED**  |

## Domains

| Domain            | Recorded state                                                                                                                                  |       Cost |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------: |
| `oryntela.com`    | Active through 3 September 2027; auto-renewal off; transfer lock and WHOIS ID protection enabled                                                | AUD $24.95 |
| `oryntela.com.au` | Active; one-year registration; held using Management Services Australia Pty. Ltd., ABN 15 113 119 556 and the registered business name ORYNTELA |  AUD $9.95 |

Both domains remain at VentraIP. The `.com` domain was not changed during the email
setup.

## Active business email

| Function                                                   | Active address            | Zoho configuration                             |
| ---------------------------------------------------------- | ------------------------- | ---------------------------------------------- |
| Business correspondence                                    | `kevin@oryntela.com.au`   | Primary mailbox and administrator domain login |
| General enquiries                                          | `hello@oryntela.com.au`   | Alias of the primary mailbox                   |
| Customer support and private-beta privacy/security contact | `support@oryntela.com.au` | Alias of the primary mailbox                   |

The service is Zoho Mail Lite 10 GB, billed annually. It has one paid user and one
mailbox. The two aliases add no paid users or charges. No other Oryntela domain email
identity or catch-all was configured.

- Actual email charge: AUD $26.40 including GST for one year.
- Renewal price observed at purchase: AUD $24 excluding GST per year.
- Renewal date shown by Zoho: 4 September 2027.
- Auto-renewal: enabled.
- MFA: enabled through Zoho OneAuth.
- Catch-all: disabled.
- Reply behaviour: use the same Oryntela address that received the message.

Do not store passwords, payment details, MFA secrets, recovery codes or
authentication tokens in this repository.

## Mail and authentication verification

| Check                                   | Result      | Evidence boundary                                                                   |
| --------------------------------------- | ----------- | ----------------------------------------------------------------------------------- |
| Domain ownership                        | **PASS**    | Zoho domain verification completed                                                  |
| Inbound to `kevin@oryntela.com.au`      | **PASS**    | Post-MX synthetic message received                                                  |
| Inbound to `hello@oryntela.com.au`      | **PASS**    | Post-MX synthetic message received in the primary mailbox                           |
| Inbound to `support@oryntela.com.au`    | **PASS**    | Post-MX synthetic message received in the primary mailbox                           |
| Outbound from `kevin@oryntela.com.au`   | **PASS**    | Authorised synthetic reply received externally with the correct From address        |
| Outbound from `hello@oryntela.com.au`   | **PASS**    | Authorised synthetic reply received externally with the correct From address        |
| Outbound from `support@oryntela.com.au` | **PASS**    | Authorised synthetic reply received externally with the correct From address        |
| Reply identity                          | **PASS**    | All three replies arrived with the matching From address                            |
| SPF                                     | **PASS**    | External receiving-system authentication result                                     |
| DKIM                                    | **PASS**    | External receiving-system authentication result; Zoho selector verified and enabled |
| DMARC alignment                         | **PASS**    | External receiving-system authentication result                                     |
| Secure transport defaults               | **ENABLED** | Zoho advertises SSL/TLS for the configured mail service                             |

The active email DNS posture is:

- MX: `mx.zoho.com.au` (10), `mx2.zoho.com.au` (20) and
  `mx3.zoho.com.au` (50);
- SPF: `v=spf1 include:zohomail.com.au ~all`;
- DKIM: Zoho selector `zmail._domainkey`, verified and enabled; and
- DMARC: monitoring policy `p=none`, with aggregate reports routed to the approved
  support address.

The public DKIM key is intentionally not copied into this register. Unrelated
VentraIP DNS records were preserved, and DNSSEC remains disabled.

## Recorded setup spend

| Asset                                    |    Actual spend |
| ---------------------------------------- | --------------: |
| ORYNTELA business name, one year         |      AUD $47.00 |
| `oryntela.com`                           |      AUD $24.95 |
| `oryntela.com.au`, one year              |       AUD $9.95 |
| Zoho Mail Lite 10 GB, one user, one year |      AUD $26.40 |
| **Total**                                | **AUD $108.30** |

## Remaining private-beta decisions

The addresses and synthetic routing are verified, but the private-beta launch still
requires an approved primary and backup accountable human, supervised operating
hours, an emergency escalation route, legal/privacy documents, provider disclosure
and the other controls in the first design-partner launch gate. This register does
not change those gates.
