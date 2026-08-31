# Create file-processing dependency remediation

- **Reviewed:** 31 August 2026
- **Scope:** production dependencies materially related to Create and customer file handling

## `pypdf` decision

`pypdf` is a direct production dependency. It is not called by Create/PPTX code, but
it is reachable through the existing deliberately uploaded PDF Evidence document
parser in `document_parsing.py`; it is therefore not valid to dismiss it as test-only
or unreachable. WO-039B does not add or expand PDF features.

The baseline lock was 5.9.0. Checkpoint 3 identified a family of malformed-PDF
resource-exhaustion/infinite-loop advisories fixed across the 6.x line, with the
assigned acceptance floor at 6.15.0. The manifest now requires
`pypdf>=6.15.0,<7.0.0`; the deterministic lock resolves 6.16.2. The authoritative
[pypdf advisory list](https://github.com/py-pdf/pypdf/security/advisories) and
[PyPI release record](https://pypi.org/project/pypdf/) were checked on the review
date.

| Dependency | Baseline → resolved | Runtime reachability                           | Create relevance                                           | Severity                                                                | Resolution                                  | Regression evidence                                                                                                                                                    |
| ---------- | ------------------- | ---------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pypdf`    | 5.9.0 → 6.16.2      | Production PDF Evidence upload/text extraction | Shared customer-file attack surface; no Create PDF feature | Multiple moderate malformed-input availability findings in Checkpoint 3 | Upgrade beyond 6.15.0 floor; no suppression | strict/malformed/password/page/text/activity bounds plus adversarial inline-image/resource-dimension fixtures fail in under 2 seconds; full API/package build required |

`BoundedDocumentParser` still checks exact PDF signature/EOF, byte/page/character and
active-content constraints, uses strict parsing, rejects password protection and
does no external fetch. The new elapsed-time regression tests protect the specific
fixed malformed-resource cases. Parsing remains in process; process-level CPU/memory
isolation is a residual general document-platform improvement, not a new PDF feature
in WO-039B.

## Production Python audit

The frozen production lock was exported without development dependencies and audited
with `pip-audit`. `pypdf 6.16.2` produced no advisory. The audit reported four
advisories for `cryptography 46.0.7`:

| Advisory                                  | Severity/fix                          | Repository reachability                                                                                                                                                   | Create/file relevance                                        | WO-039B decision                                                                              |
| ----------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| `PYSEC-2026-3552` / `GHSA-g6cj-pr64-35w5` | Moderate; 50.0.0                      | Requires PKCS#7 EnvelopedData decrypt APIs; repository has no PKCS#7/S/MIME decrypt path                                                                                  | None                                                         | Not applicable to this work order; no suppression was added.                                  |
| `PYSEC-2026-3553` / `GHSA-jwv3-5hgf-82ww` | Low; 49.0.0                           | Requires attacker-controlled X.509 chain verification through `cryptography.x509.verification`; repository does not call it                                               | None                                                         | Not applicable to this work order; record for platform dependency maintenance.                |
| `PYSEC-2026-3554` / `GHSA-m2h6-j472-rp4c` | Low; 49.0.0                           | Requires the same unused X.509 verification API/name-constraint topology                                                                                                  | None                                                         | Not applicable to this work order; record for platform dependency maintenance.                |
| `GHSA-537c-gmf6-5ccf` / `CVE-2026-34180`  | Low vendor severity; wheel fix 48.0.1 | Requires parsing an attacker-supplied ASN.1 primitive over 2 GB through OpenSSL `d2i_*`; repository imports only AES-GCM credential encryption and accepts no such object | None; Create uses standard-library SHA-256 and random tokens | Not applicable to WO-039B. Major-range platform upgrade is not bundled into Create hardening. |

The classifications use the upstream
[PKCS#7 advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5),
[duplicate-chain advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-jwv3-5hgf-82ww),
[wildcard/name-constraint advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-m2h6-j472-rp4c),
[wheel advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-537c-gmf6-5ccf)
and [OpenSSL vulnerability record](https://openssl-library.org/news/vulnerabilities-3.6/index.html).
The last issue requires an ASN.1 content length beyond 2 GB, while this application
does not expose an ASN.1 upload/decoder and Create rejects at 50 MB before parsing.

These findings are not represented as fixed. They are explicitly classified as
production-installed but unreachable through the reported primitives in the current
repository and outside the assigned Create/file path. Static source inspection on
31 August 2026 found production use only of `AESGCM`/`InvalidTag` in the credential
store; RSA appears only in private-beta tests. There is no PKCS#7, X.509 verification
API or OpenSSL ASN.1 decoder call. The platform dependency owner must move the
`cryptography` major range after credential/JWT regression review as part of the
WO-039C production-package gate. WO-039B does not weaken or waive that audit gate.

## JavaScript audit

The frozen production JavaScript audit reported no known vulnerabilities. The full
dependency audit likewise reported no JavaScript advisories. No JavaScript dependency
or lockfile changed in WO-039B.
