# Prospect SSRF and public-content security

**Status:** Current WO-026 control and future-fetch gate

WO-026 has no runtime public-page fetcher, browser automation, HTML parser, download
path or model synthesis. A malicious page therefore cannot reach a browser session,
execute script, supply prompt instructions or consume an unbounded response body.
The provider delivers structured values, and strict schemas treat every string as
data.

Every candidate and source URL is still accepted only through the public URL
policy:

- HTTPS only, with no username/password and only the default HTTPS port;
- maximum 2,048 characters and ASCII-only host input;
- canonical lower-case domain and normalised path;
- no IP-literal host;
- blocked localhost, metadata, `.local`, `.internal`, `.home` and `.lan` names;
- syntactically valid multi-label DNS host;
- every supplied DNS result must be a globally routable IP;
- maximum five redirects, with every hop revalidated and loops rejected; and
- browser links use `noopener noreferrer` and no-referrer behaviour.

The DNS and redirect functions are policy primitives, not evidence that the
application currently resolves or follows external URLs. A future network adapter
must resolve immediately before each connection, connect only to the validated
address, re-resolve each redirect and prevent transport-layer redirection to a
different address. It must also enforce timeouts, byte caps, MIME allowlists and no
cookies/authentication/JavaScript/downloads. Until those controls and provider terms
are approved, production research fails closed.

Prompt injection is structurally excluded because no page text is sent to a model.
If synthesis is later authorised, source text must be bounded and marked untrusted;
the prompt must ignore embedded instructions, use only supplied source IDs, produce
strict structured output and pass the same citation/trust validator before storage.
