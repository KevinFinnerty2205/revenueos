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

from revenueos.models import EncryptedConnectorCredential


@dataclass(frozen=True)
class ConnectorCredential:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: tuple[str, ...]
    external_account_id: str


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
            record = EncryptedConnectorCredential(
                id=uuid.uuid4(),
                organisation_id=organisation_id,
                connection_id=connection_id,
                connector_key="hubspot",
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
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        record.nonce = nonce
        record.encrypted_payload = AESGCM(self._key).encrypt(
            nonce,
            payload,
            self._associated_data(organisation_id, connection_id, record.id),
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
        try:
            credential_id = UUID(credential_reference)
        except ValueError as exc:
            raise ValueError("Connector credential reference is invalid.") from exc
        record = await self._session.scalar(
            select(EncryptedConnectorCredential).where(
                EncryptedConnectorCredential.organisation_id == organisation_id,
                EncryptedConnectorCredential.connection_id == connection_id,
                EncryptedConnectorCredential.id == credential_id,
            )
        )
        if record is None:
            raise ValueError("Connector credential is unavailable.")
        try:
            decrypted = AESGCM(self._key).decrypt(
                record.nonce,
                record.encrypted_payload,
                self._associated_data(organisation_id, connection_id, record.id),
            )
            payload = json.loads(decrypted)
            if not isinstance(payload, dict):
                raise ValueError
            access_token = payload["accessToken"]
            refresh_token = payload["refreshToken"]
            expires_at = datetime.fromisoformat(payload["expiresAt"])
            scopes = payload["scopes"]
            external_account_id = payload["externalAccountId"]
            if not (
                isinstance(access_token, str)
                and isinstance(refresh_token, str)
                and isinstance(scopes, list)
                and all(isinstance(item, str) for item in scopes)
                and isinstance(external_account_id, str)
                and access_token
                and refresh_token
                and external_account_id
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

    @staticmethod
    def _associated_data(organisation_id: UUID, connection_id: UUID, credential_id: UUID) -> bytes:
        return f"revenueos:hubspot:{organisation_id}:{connection_id}:{credential_id}:v1".encode()


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

    async def revoke(
        self,
        organisation_id: UUID,
        connection_id: UUID,
        credential_reference: str,
    ) -> None:
        del organisation_id, connection_id, credential_reference
