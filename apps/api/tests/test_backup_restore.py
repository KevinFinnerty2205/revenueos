from __future__ import annotations

import asyncio
import base64
import subprocess
from pathlib import Path

import pytest

from revenueos.backup import BackupError, create_backup, restore_backup, verify_backup
from revenueos.config import Settings
from revenueos.visual_storage import LocalVisualStorage


def backup_settings(storage_root: Path) -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url="postgresql+asyncpg://backup_user:private-password@source.example.com:5432/revenueos?ssl=require",
        visual_storage_backend="local",
        visual_storage_directory=str(storage_root),
        private_beta_backup_encryption_key=base64.b64encode(b"k" * 32).decode(),
        log_level="WARNING",
    )


def test_encrypted_backup_verify_restore_and_source_target_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "source-objects"
    settings = backup_settings(storage_root)
    source_storage = LocalVisualStorage(str(storage_root))
    observed_commands: list[list[str]] = []
    observed_environments: list[dict[str, str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        observed_commands.append(command)
        environment = kwargs.get("env")
        assert isinstance(environment, dict)
        observed_environments.append(environment)
        if command[0] == "pg_dump":
            output = Path(command[command.index("--file") + 1])
            output.write_bytes(b"synthetic-postgresql-custom-archive")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    async def scenario() -> None:
        await source_storage.write("tenant-a/visuals/one.bin", b"first-object", "application/octet-stream")
        await source_storage.write("tenant-b/create/two.bin", b"second-object", "application/octet-stream")
        backup_path, manifest = await create_backup(settings, tmp_path / "backups")
        assert manifest.objectCount == 2
        assert manifest.encryption == "AES-256-GCM"
        assert (backup_path / "database.dump.enc").read_bytes().startswith(b"ROSBK1")
        assert b"synthetic-postgresql" not in (backup_path / "database.dump.enc").read_bytes()
        assert b"private-password" not in (backup_path / "manifest.json").read_bytes()
        verified = await verify_backup(settings, backup_path)
        assert verified == manifest

        with pytest.raises(BackupError, match="must not be the source"):
            await restore_backup(
                settings, backup_path, settings.database_url or "", LocalVisualStorage(str(tmp_path / "x"))
            )

        occupied_storage = LocalVisualStorage(str(tmp_path / "occupied-objects"))
        await occupied_storage.write("existing/object.bin", b"existing", "application/octet-stream")
        with pytest.raises(BackupError, match="must be empty"):
            await restore_backup(
                settings,
                backup_path,
                "postgresql+asyncpg://restore_user:other-password@restore.example.com/occupied?ssl=require",
                occupied_storage,
            )

        target_storage = LocalVisualStorage(str(tmp_path / "restored-objects"))
        restored = await restore_backup(
            settings,
            backup_path,
            "postgresql+asyncpg://restore_user:other-password@restore.example.com/restored?ssl=require",
            target_storage,
        )
        assert restored.backupId == manifest.backupId
        assert await target_storage.read("tenant-a/visuals/one.bin") == b"first-object"
        assert await target_storage.read("tenant-b/create/two.bin") == b"second-object"

        encrypted = backup_path / "objects.tar.enc"
        corrupted = bytearray(encrypted.read_bytes())
        corrupted[len(corrupted) // 2] ^= 1
        encrypted.write_bytes(corrupted)
        with pytest.raises(BackupError, match="failed authentication"):
            await verify_backup(settings, backup_path)

    asyncio.run(scenario())
    assert [command[0] for command in observed_commands] == ["pg_dump", "pg_restore"]
    assert all("private-password" not in " ".join(command) for command in observed_commands)
    assert observed_environments[0]["PGPASSWORD"] == "private-password"
    assert observed_environments[1]["PGPASSWORD"] == "other-password"


def test_real_data_backup_rejects_temporary_destination(tmp_path: Path) -> None:
    settings = backup_settings(tmp_path / "source-objects").model_copy(update={"private_beta_real_data_enabled": True})

    with pytest.raises(BackupError, match="durable destination"):
        asyncio.run(create_backup(settings, tmp_path / "backups"))
