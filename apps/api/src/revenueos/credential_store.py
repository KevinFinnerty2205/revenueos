from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import EncryptedConnectorCredential, IntegrationConnection


@dataclass(frozen=True)
class ConnectorCredential:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: tuple[str, ...]
    external_account_id: str
    api_base_url: str | None = None
    schema_version: str | None = None
    schema_capabilities: tuple[str, ...] = ()


class CredentialStore(Protocol):
    """Opaque, tenant-bound storage used only inside a connector boundary."""

    async def put(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential: ConnectorCredential,
    ) -> str: ...

    async def get(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> ConnectorCredential: ...

    async def get_for_update(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> ConnectorCredential: ...

    async def revoke(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> None: ...


class EncryptedDatabaseCredentialStore:
    """AES-256-GCM token envelope using a deployment-managed master key."""

    def __init__(self, session: AsyncSession, encoded_master_key: str) -> None:
        self._session = session
        self._key = self.decode_master_key(encoded_master_key)

    @staticmethod
    def decode_master_key(value: str) -> bytes:
        try:
            padded = value + "=" * (-len(value) % 4)
            key = base64.urlsafe_b64decode(padded.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("Connector credential master key is malformed.") from exc
        if len(key) != 32:
            raise ValueError("Connector credential master key must decode to exactly 32 bytes.")
        return key

    async def put(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential: ConnectorCredential,
    ) -> str:
        record = await self._session.scalar(
            select(EncryptedConnectorCredential).where(
                EncryptedConnectorCredential.organisation_id == organisation_id,
                EncryptedConnectorCredential.connection_id == connection_id,
            )
        )
        now = datetime.now(UTC)
        if record is None:
            connection = await self._session.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.organisation_id == organisation_id,
                    IntegrationConnection.id == connection_id,
                )
            )
            if connection is None or connection.connector_key not in {
                "hubspot",
                "salesforce",
                "microsoft_365",
                "google_workspace",
            }:
                raise ValueError("Connector credential owner is unavailable.")
            record = EncryptedConnectorCredential(
                id=uuid.uuid4(),
                organisation_id=organisation_id,
                connection_id=connection_id,
                connector_key=connection.connector_key,
                encrypted_payload=b"pending",
                nonce=b"0" * 12,
                key_version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(record)
        nonce = os.urandom(12)
        payload = json.dumps(
            {
                "accessToken": credential.access_token,
                "refreshToken": credential.refresh_token,
                "expiresAt": credential.expires_at.astimezone(UTC).isoformat(),
                "scopes": list(credential.scopes),
                "externalAccountId": credential.external_account_id,
                "apiBaseUrl": credential.api_base_url,
                "schemaVersion": credential.schema_version,
                "schemaCapabilities": list(credential.schema_capabilities),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        record.nonce = nonce
        record.encrypted_payload = AESGCM(self._key).encrypt(
            nonce,
            payload,
            self._associated_data(record.connector_key, organisation_id, connection_id, record.id),
        )
        record.updated_at = now
        await self._session.flush()
        return str(record.id)

    async def get(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> ConnectorCredential:
        return await self._get(organisation_id, connection_id, credential_reference, for_update=False)

    async def get_for_update(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> ConnectorCredential:
        return await self._get(organisation_id, connection_id, credential_reference, for_update=True)

    async def _get(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
        *,
        for_update: bool,
    ) -> ConnectorCredential:
        try:
            credential_id = UUID(credential_reference)
        except ValueError as exc:
            raise ValueError("Connector credential reference is invalid.") from exc
        statement = select(EncryptedConnectorCredential).where(
            EncryptedConnectorCredential.organisation_id == organisation_id,
            EncryptedConnectorCredential.connection_id == connection_id,
            EncryptedConnectorCredential.id == credential_id,
        )
        if for_update:
            statement = statement.with_for_update()
        record = await self._session.scalar(statement)
        if record is None:
            raise ValueError("Connector credential is unavailable.")
        try:
            decrypted = AESGCM(self._key).decrypt(
                record.nonce,
                record.encrypted_payload,
                self._associated_data(record.connector_key, organisation_id, connection_id, record.id),
            )
            payload = json.loads(decrypted)
            if not isinstance(payload, dict):
                raise ValueError
            access_token = payload["accessToken"]
            refresh_token = payload["refreshToken"]
            expires_at = datetime.fromisoformat(payload["expiresAt"])
            scopes = payload["scopes"]
            external_account_id = payload["externalAccountId"]
            api_base_url = payload.get("apiBaseUrl")
            schema_version = payload.get("schemaVersion")
            schema_capabilities = payload.get("schemaCapabilities", [])
            if not (
                isinstance(access_token, str)
                and isinstance(refresh_token, str)
                and isinstance(scopes, list)
                and all(isinstance(item, str) for item in scopes)
                and isinstance(external_account_id, str)
                and access_token
                and refresh_token
                and external_account_id
                and (api_base_url is None or isinstance(api_base_url, str))
                and (schema_version is None or isinstance(schema_version, str))
                and isinstance(schema_capabilities, list)
                and all(isinstance(item, str) for item in schema_capabilities)
            ):
                raise ValueError
        except (InvalidTag, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Connector credential is unavailable.") from exc
        return ConnectorCredential(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=tuple(scopes),
            external_account_id=external_account_id,
            api_base_url=api_base_url,
            schema_version=schema_version,
            schema_capabilities=tuple(schema_capabilities),
        )

    async def revoke(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> None:
        try:
            credential_id = UUID(credential_reference)
        except ValueError:
            return
        record = await self._session.scalar(
            select(EncryptedConnectorCredential).where(
                EncryptedConnectorCredential.organisation_id == organisation_id,
                EncryptedConnectorCredential.connection_id == connection_id,
                EncryptedConnectorCredential.id == credential_id,
            )
        )
        if record is not None:
            await self._session.delete(record)

    def encrypt_oauth_state_secret(
        self,
        organisation_id: UUID,
        state_id: UUID,
        value: str,
    ) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        encrypted = AESGCM(self._key).encrypt(
            nonce,
            value.encode("utf-8"),
            f"revenueos:oauth-state:{organisation_id}:{state_id}:v1".encode(),
        )
        return nonce, encrypted

    def decrypt_oauth_state_secret(
        self,
        organisation_id: UUID,
        state_id: UUID,
        nonce: bytes | None,
        encrypted: bytes | None,
    ) -> str:
        if nonce is None or encrypted is None or len(nonce) != 12:
            raise ValueError("OAuth state secret is unavailable.")
        try:
            return (
                AESGCM(self._key)
                .decrypt(
                    nonce,
                    encrypted,
                    f"revenueos:oauth-state:{organisation_id}:{state_id}:v1".encode(),
                )
                .decode("utf-8")
            )
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise ValueError("OAuth state secret is unavailable.") from exc

    @staticmethod
    def _associated_data(
        connector_key: str,
        organisation_id: UUID,
        connection_id: UUID,
        credential_id: UUID,
    ) -> bytes:
        return f"revenueos:{connector_key}:{organisation_id}:{connection_id}:{credential_id}:v1".encode()


class MockCredentialStore:
    """WO-022 mock connectors have no credential material."""

    async def put(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential: ConnectorCredential,
    ) -> str:
        del organisation_id, connection_id, credential
        raise ValueError("Mock connectors do not store credentials.")

    async def get(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> ConnectorCredential:
        del organisation_id, connection_id, credential_reference
        raise ValueError("Mock connectors do not store credentials.")

    async def get_for_update(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> ConnectorCredential:
        return await self.get(organisation_id, connection_id, credential_reference)

    async def revoke(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> None:
        del organisation_id, connection_id, credential_reference
