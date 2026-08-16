from __future__ import annotations

from typing import Protocol


class CredentialStore(Protocol):
    """Boundary for future encrypted or secret-manager backed credentials."""

    async def revoke(self, credential_reference: str) -> None: ...


class MockCredentialStore:
    """WO-022 mock connectors have no credential material to persist or revoke."""

    async def revoke(self, credential_reference: str) -> None:
        del credential_reference
