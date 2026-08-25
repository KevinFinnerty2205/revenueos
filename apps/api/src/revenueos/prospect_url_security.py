from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

MAX_URL_LENGTH = 2_048
MAX_REDIRECTS = 5
HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
BLOCKED_HOSTS = frozenset({"localhost", "localhost.localdomain", "metadata.google.internal"})
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".home", ".lan")


class PublicUrlSafetyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CanonicalPublicUrl:
    url: str
    domain: str


def canonicalize_public_https_url(value: str, *, company_origin_only: bool = False) -> CanonicalPublicUrl:
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_URL_LENGTH:
        raise PublicUrlSafetyError("invalid_public_url", "The public URL is missing or too long.")
    if any(ord(character) > 127 for character in candidate):
        raise PublicUrlSafetyError("unsafe_domain", "Unicode domains are not accepted in this version.")
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise PublicUrlSafetyError("invalid_public_url", "The public URL is malformed.") from exc
    if parsed.scheme.lower() != "https":
        raise PublicUrlSafetyError("unsafe_scheme", "Only HTTPS public URLs are accepted.")
    if parsed.username is not None or parsed.password is not None:
        raise PublicUrlSafetyError("credential_url", "Credential-bearing URLs are not accepted.")
    if port not in (None, 443):
        raise PublicUrlSafetyError("unsafe_port", "The public URL uses an unsupported port.")
    domain = _validated_domain(parsed)
    path = parsed.path or "/"
    if company_origin_only and (path not in ("", "/") or parsed.query or parsed.fragment):
        raise PublicUrlSafetyError("invalid_company_website", "Enter the company's website origin only.")
    canonical_path = "/" if company_origin_only else _canonical_path(path)
    canonical = urlunsplit(("https", domain, canonical_path, "" if company_origin_only else parsed.query, ""))
    if len(canonical) > MAX_URL_LENGTH:
        raise PublicUrlSafetyError("invalid_public_url", "The canonical public URL is too long.")
    return CanonicalPublicUrl(url=canonical, domain=domain)


def normalise_company_website(value: str) -> CanonicalPublicUrl:
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    return canonicalize_public_https_url(candidate, company_origin_only=True)


def validate_resolved_public_addresses(addresses: list[str] | tuple[str, ...]) -> None:
    if not addresses:
        raise PublicUrlSafetyError("dns_unavailable", "The public host did not resolve.")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise PublicUrlSafetyError("invalid_dns_result", "The public host returned an invalid address.") from exc
        if not address.is_global:
            raise PublicUrlSafetyError("private_network", "The public host resolved to a blocked network.")


def validate_redirect_chain(urls: list[str] | tuple[str, ...]) -> tuple[CanonicalPublicUrl, ...]:
    if len(urls) > MAX_REDIRECTS + 1:
        raise PublicUrlSafetyError("redirect_limit", "The public URL exceeded the redirect limit.")
    canonical = tuple(canonicalize_public_https_url(value) for value in urls)
    keys = [item.url for item in canonical]
    if len(set(keys)) != len(keys):
        raise PublicUrlSafetyError("redirect_loop", "The public URL contains a redirect loop.")
    return canonical


def _validated_domain(parsed: SplitResult) -> str:
    host = parsed.hostname
    if host is None:
        raise PublicUrlSafetyError("invalid_public_url", "The public URL has no host.")
    domain = host.lower().rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain or len(domain) > 253:
        raise PublicUrlSafetyError("unsafe_domain", "The public URL has an invalid host.")
    if domain in BLOCKED_HOSTS or domain.endswith(BLOCKED_SUFFIXES):
        raise PublicUrlSafetyError("private_network", "Local and internal hosts are not accepted.")
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        pass
    else:
        raise PublicUrlSafetyError("ip_literal", "IP-address company websites are not accepted.")
    labels = domain.split(".")
    if len(labels) < 2 or any(not HOST_LABEL.fullmatch(label) for label in labels):
        raise PublicUrlSafetyError("unsafe_domain", "The public URL has an invalid host.")
    return domain


def _canonical_path(path: str) -> str:
    collapsed = re.sub(r"/{2,}", "/", path)
    return collapsed if collapsed.startswith("/") else f"/{collapsed}"
