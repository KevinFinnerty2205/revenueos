from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from revenueos.backup import (
    BackupError,
    BackupManifest,
    RemoteBackupConfiguration,
    _download_remote_backup,
    _restore_target_database_url,
    create_backup,
    create_remote_backup,
    restore_backup,
    verify_backup,
)
from revenueos.config import Settings
from revenueos.visual_storage import LocalVisualStorage


def remote_configuration() -> RemoteBackupConfiguration:
    return RemoteBackupConfiguration(
        source_database_url="postgresql+asyncpg://backup:secret@source.example.test/revenueos",
        release_sha="a" * 40,
        source_database_tls_mode="verify_full_system",
        encryption_key=base64.b64encode(b"k" * 32).decode(),
        source_s3_endpoint="https://syd1.digitaloceanspaces.com",
        source_s3_bucket="source-private",
        source_s3_region="syd1",
        source_s3_access_key_id="source-access",
        source_s3_secret_access_key="source-secret",
        destination_s3_endpoint="https://s3.ap-southeast-2.amazonaws.com",
        destination_s3_bucket="destination-private",
        destination_s3_region="ap-southeast-2",
        destination_s3_access_key_id="destination-access",
        destination_s3_secret_access_key="destination-secret",
    )


def backup_settings(storage_root: Path) -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url="postgresql+asyncpg://backup_user:private-password@source.example.com:5432/revenueos?ssl=require",
        database_tls_mode="verify_full_system",
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

        manifest_path = backup_path / "manifest.json"
        original_manifest = manifest_path.read_bytes()
        tampered_manifest = json.loads(original_manifest)
        tampered_manifest["databaseFingerprint"] = "attacker-controlled-source"
        manifest_path.write_text(json.dumps(tampered_manifest), encoding="utf-8")
        with pytest.raises(BackupError, match="manifest failed authentication"):
            await verify_backup(settings, backup_path)
        manifest_path.write_bytes(original_manifest)

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
    assert observed_environments[0]["PGSSLMODE"] == "verify-full"
    assert observed_environments[1]["PGSSLMODE"] == "verify-full"


def test_real_data_backup_rejects_temporary_destination(tmp_path: Path) -> None:
    settings = backup_settings(tmp_path / "source-objects").model_copy(update={"private_beta_real_data_enabled": True})

    with pytest.raises(BackupError, match="durable destination"):
        asyncio.run(create_backup(settings, tmp_path / "backups"))


def test_restore_target_url_can_stay_out_of_command_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "postgresql+asyncpg://restore-user:synthetic-secret@restore.example.com/target"
    monkeypatch.setenv("API_RESTORE_TARGET_DATABASE_URL", target)

    assert _restore_target_database_url(None) == target
    assert _restore_target_database_url(" postgresql://local/explicit ") == "postgresql://local/explicit"

    monkeypatch.delenv("API_RESTORE_TARGET_DATABASE_URL")
    with pytest.raises(BackupError, match="not configured"):
        _restore_target_database_url(None)


def test_remote_backup_uploads_verified_payloads_before_commit_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_id = "20260910T010203Z-abcdef123456"
    manifest = BackupManifest(
        formatVersion=2,
        backupId=backup_id,
        createdAt=datetime.now(UTC).isoformat(),
        databaseFingerprint="database-fingerprint",
        databaseArchiveSha256="database-plaintext-sha",
        storageArchiveSha256="storage-plaintext-sha",
        objectCount=2,
        encryption="AES-256-GCM",
        releaseSha="a" * 40,
        authentication="synthetic-test-manifest-authentication",
    )

    async def fake_create_backup(
        settings: Settings,
        destination: Path,
        *,
        allow_encrypted_temporary_destination: bool = False,
    ) -> tuple[Path, BackupManifest]:
        del settings
        assert allow_encrypted_temporary_destination is True
        path = destination / backup_id
        path.mkdir()
        (path / "database.dump.enc").write_bytes(b"encrypted-database")
        (path / "objects.tar.enc").write_bytes(b"encrypted-objects")
        (path / "manifest.json").write_text(
            json.dumps(manifest.__dict__, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return path, manifest

    class FakeRemoteStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.digests: dict[str, str] = {}
            self.upload_order: list[str] = []

        async def write_file(
            self,
            key: str,
            source: Path,
            mime_type: str,
            *,
            sha256: str,
        ) -> None:
            del mime_type
            self.upload_order.append(key)
            self.objects[key] = source.read_bytes()
            self.digests[key] = sha256

        async def file_metadata(self, key: str) -> tuple[int, str | None]:
            return len(self.objects[key]), self.digests[key]

        async def read_file(self, key: str, destination: Path) -> None:
            destination.write_bytes(self.objects[key])

        async def delete(self, key: str) -> None:
            self.objects.pop(key, None)
            self.digests.pop(key, None)

    storage = FakeRemoteStorage()
    monkeypatch.setattr("revenueos.backup.create_backup", fake_create_backup)
    monkeypatch.setattr("revenueos.backup._remote_destination_storage", lambda _configuration: storage)

    async def fake_verify_remote_backup(
        configuration: RemoteBackupConfiguration,
        requested_backup_id: str,
    ) -> BackupManifest:
        del configuration
        assert requested_backup_id == backup_id
        assert storage.upload_order[-1].endswith("/manifest.json")
        return manifest

    monkeypatch.setattr("revenueos.backup.verify_remote_backup", fake_verify_remote_backup)

    result = asyncio.run(create_remote_backup(remote_configuration()))
    assert result == manifest
    assert [key.rsplit("/", 1)[-1] for key in storage.upload_order] == [
        "database.dump.enc",
        "objects.tar.enc",
        "manifest.json",
    ]
    assert all(storage.digests[key] == hashlib.sha256(storage.objects[key]).hexdigest() for key in storage.upload_order)

    downloaded = asyncio.run(_download_remote_backup(remote_configuration(), backup_id, tmp_path))
    assert (downloaded / "database.dump.enc").read_bytes() == b"encrypted-database"
    assert (downloaded / "objects.tar.enc").read_bytes() == b"encrypted-objects"


def test_remote_backup_configuration_requires_independent_https_aws_destination() -> None:
    with pytest.raises(ValueError, match="independent"):
        remote_configuration().model_copy(
            update={"destination_s3_endpoint": "https://syd1.digitaloceanspaces.com"}
        ).validate_remote_boundaries()
    with pytest.raises(ValueError, match="HTTPS"):
        remote_configuration().model_copy(
            update={"destination_s3_endpoint": "http://s3.example.test"}
        ).validate_remote_boundaries()
    with pytest.raises(ValueError, match="independent providers"):
        remote_configuration().model_copy(
            update={"source_s3_endpoint": "https://s3.us-east-1.amazonaws.com"}
        ).validate_remote_boundaries()
