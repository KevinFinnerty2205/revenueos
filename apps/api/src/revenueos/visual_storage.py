from __future__ import annotations

import asyncio
import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from revenueos.config import Settings

GrantPurpose = Literal["upload", "download"]


class VisualStorageError(Exception):
    code = "visual_storage_failure"


class VisualObjectMissingError(VisualStorageError):
    code = "visual_object_missing"


class VisualStorage(Protocol):
    backend_name: str
    direct_upload: bool

    def upload_url(self, storage_key: str, mime_type: str, expires_at: datetime) -> str | None: ...

    def download_url(self, storage_key: str, expires_at: datetime) -> str | None: ...

    async def write(self, storage_key: str, content: bytes, mime_type: str) -> None: ...

    async def read(self, storage_key: str) -> bytes: ...

    async def delete(self, storage_key: str) -> None: ...

    async def list_keys(self, prefix: str) -> list[str]: ...


class VisualGrantSigner:
    """Short-lived grants bound to one tenant, user, visual and operation."""

    def __init__(self, secret: str) -> None:
        self.secret = secret.encode("utf-8")

    def issue(
        self,
        organisation_id: UUID,
        user_id: UUID,
        visual_id: UUID,
        purpose: GrantPurpose,
        expires_at: datetime,
    ) -> str:
        # SQLite returns timezone-aware database columns as naive values. The
        # application contract defines them as UTC, so normalise before signing.
        normalised_expiry = expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
        expiry = int(normalised_expiry.timestamp())
        signature = self._signature(organisation_id, user_id, visual_id, purpose, expiry)
        return f"{expiry}.{signature}"

    def verify(
        self,
        token: str,
        organisation_id: UUID,
        user_id: UUID,
        visual_id: UUID,
        purpose: GrantPurpose,
    ) -> bool:
        try:
            expiry_text, supplied = token.split(".", 1)
            expiry = int(expiry_text)
        except (TypeError, ValueError):
            return False
        if expiry < int(datetime.now(UTC).timestamp()):
            return False
        expected = self._signature(organisation_id, user_id, visual_id, purpose, expiry)
        return hmac.compare_digest(supplied, expected)

    def _signature(
        self,
        organisation_id: UUID,
        user_id: UUID,
        visual_id: UUID,
        purpose: GrantPurpose,
        expiry: int,
    ) -> str:
        message = f"v1:{organisation_id}:{user_id}:{visual_id}:{purpose}:{expiry}".encode()
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()


class LocalVisualStorage:
    backend_name = "local"
    direct_upload = False

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def upload_url(self, storage_key: str, mime_type: str, expires_at: datetime) -> str | None:
        del storage_key, mime_type, expires_at
        return None

    def download_url(self, storage_key: str, expires_at: datetime) -> str | None:
        del storage_key, expires_at
        return None

    async def write(self, storage_key: str, content: bytes, mime_type: str) -> None:
        del mime_type
        path = self._path(storage_key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.uploading")

        def persist() -> None:
            try:
                temporary.write_bytes(content)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)

        await asyncio.to_thread(persist)

    async def read(self, storage_key: str) -> bytes:
        path = self._path(storage_key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise VisualObjectMissingError from exc

    async def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        await asyncio.to_thread(path.unlink, missing_ok=True)
        current = path.parent
        while current != self.root:
            try:
                await asyncio.to_thread(current.rmdir)
            except OSError:
                break
            current = current.parent

    async def list_keys(self, prefix: str) -> list[str]:
        prefix_path = self.root if not prefix else self._path(prefix.rstrip("/") + "/placeholder").parent
        if not prefix_path.exists():
            return []

        def collect() -> list[str]:
            return sorted(
                str(path.relative_to(self.root))
                for path in prefix_path.rglob("*")
                if path.is_file() and not path.name.endswith(".uploading")
            )

        return await asyncio.to_thread(collect)

    def _path(self, storage_key: str) -> Path:
        if not storage_key or storage_key.startswith(("/", ".")) or ".." in storage_key.split("/"):
            raise VisualStorageError("Invalid visual storage key.")
        path = (self.root / storage_key).resolve()
        if self.root not in path.parents:
            raise VisualStorageError("Visual storage key escaped the configured root.")
        return path


class S3CompatibleVisualStorage:
    """Narrow SigV4 adapter for a private path-style S3-compatible bucket."""

    backend_name = "s3_compatible"
    direct_upload = True

    def __init__(self, settings: Settings) -> None:
        assert settings.visual_s3_endpoint is not None
        assert settings.visual_s3_bucket is not None
        assert settings.visual_s3_region is not None
        assert settings.visual_s3_access_key_id is not None
        assert settings.visual_s3_secret_access_key is not None
        self.endpoint = settings.visual_s3_endpoint.rstrip("/")
        self.bucket = settings.visual_s3_bucket
        self.region = settings.visual_s3_region
        self.access_key = settings.visual_s3_access_key_id.get_secret_value()
        self.secret_key = settings.visual_s3_secret_access_key.get_secret_value()

    def upload_url(self, storage_key: str, mime_type: str, expires_at: datetime) -> str | None:
        return self._presign("PUT", storage_key, expires_at, {"content-type": mime_type})

    def download_url(self, storage_key: str, expires_at: datetime) -> str | None:
        return self._presign("GET", storage_key, expires_at, {})

    async def write(self, storage_key: str, content: bytes, mime_type: str) -> None:
        expires = datetime.now(UTC) + timedelta(minutes=5)
        request = urllib.request.Request(
            self._presign("PUT", storage_key, expires, {"content-type": mime_type}),
            data=content,
            method="PUT",
            headers={"Content-Type": mime_type},
        )
        await self._send(request)

    async def read(self, storage_key: str) -> bytes:
        expires = datetime.now(UTC) + timedelta(minutes=5)
        request = urllib.request.Request(self._presign("GET", storage_key, expires, {}), method="GET")
        return await self._send(request)

    async def delete(self, storage_key: str) -> None:
        expires = datetime.now(UTC) + timedelta(minutes=5)
        request = urllib.request.Request(self._presign("DELETE", storage_key, expires, {}), method="DELETE")
        await self._send(request, missing_ok=True)

    async def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        continuation: str | None = None
        while True:
            parameters = {"list-type": "2", "prefix": prefix}
            if continuation is not None:
                parameters["continuation-token"] = continuation
            expires = datetime.now(UTC) + timedelta(minutes=5)
            request = urllib.request.Request(
                self._presign("GET", "", expires, {}, parameters),
                method="GET",
            )
            try:
                root = ElementTree.fromstring(await self._send(request))
            except ElementTree.ParseError as exc:
                raise VisualStorageError from exc
            keys.extend(
                element.text
                for element in root.findall(".//{*}Key")
                if element.text is not None and element.text.startswith(prefix)
            )
            truncated = root.find(".//{*}IsTruncated")
            if truncated is None or truncated.text != "true":
                break
            next_token = root.find(".//{*}NextContinuationToken")
            if next_token is None or next_token.text is None:
                raise VisualStorageError("Object storage returned an incomplete listing.")
            continuation = next_token.text
        return sorted(keys)

    async def _send(self, request: urllib.request.Request, *, missing_ok: bool = False) -> bytes:
        def send() -> bytes:
            try:
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - configured private endpoint
                    return bytes(response.read())
            except urllib.error.HTTPError as exc:
                if missing_ok and exc.code == 404:
                    return b""
                if exc.code == 404:
                    raise VisualObjectMissingError from exc
                raise VisualStorageError from exc
            except (OSError, urllib.error.URLError) as exc:
                raise VisualStorageError from exc

        return await asyncio.to_thread(send)

    def _presign(
        self,
        method: str,
        storage_key: str,
        expires_at: datetime,
        headers: Mapping[str, str],
        query_parameters: Mapping[str, str] | None = None,
    ) -> str:
        now = datetime.now(UTC)
        normalised_expiry = expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at
        expires = max(1, min(900, int((normalised_expiry - now).total_seconds())))
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        endpoint = urllib.parse.urlsplit(self.endpoint)
        host = endpoint.netloc
        object_path = f"/{urllib.parse.quote(self.bucket, safe='')}/{urllib.parse.quote(storage_key, safe='/')}"
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        canonical_headers = {"host": host, **{key.lower(): value.strip() for key, value in headers.items()}}
        signed_headers = ";".join(sorted(canonical_headers))
        query = {
            **(query_parameters or {}),
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self.access_key}/{credential_scope}",
            "X-Amz-Date": timestamp,
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": signed_headers,
        }
        canonical_query = urllib.parse.urlencode(sorted(query.items()), quote_via=urllib.parse.quote)
        canonical_header_text = "".join(f"{key}:{canonical_headers[key]}\n" for key in sorted(canonical_headers))
        canonical_request = "\n".join(
            (
                method,
                object_path,
                canonical_query,
                canonical_header_text,
                signed_headers,
                "UNSIGNED-PAYLOAD",
            )
        )
        string_to_sign = "\n".join(
            (
                "AWS4-HMAC-SHA256",
                timestamp,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            )
        )
        signing_key = self._signing_key(date_stamp)
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return urllib.parse.urlunsplit(
            (endpoint.scheme, endpoint.netloc, object_path, f"{canonical_query}&X-Amz-Signature={signature}", "")
        )

    def _signing_key(self, date_stamp: str) -> bytes:
        date_key = hmac.new(f"AWS4{self.secret_key}".encode(), date_stamp.encode(), hashlib.sha256).digest()
        region_key = hmac.new(date_key, self.region.encode(), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def create_visual_storage(settings: Settings) -> VisualStorage:
    if settings.visual_storage_backend == "s3_compatible":
        return S3CompatibleVisualStorage(settings)
    return LocalVisualStorage(settings.visual_storage_directory)
