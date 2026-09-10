from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import subprocess
import tarfile
import tempfile
import urllib.parse
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO, Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

from revenueos.config import Settings, get_settings
from revenueos.visual_storage import (
    LocalVisualStorage,
    S3CompatibleVisualStorage,
    VisualStorage,
    VisualStorageError,
    create_visual_storage,
)

BACKUP_FORMAT_VERSION = 2
ENCRYPTED_FILE_MAGIC = b"ROSBK1"
CHUNK_BYTES = 1024 * 1024
REMOTE_BACKUP_PREFIX = "revenueos-private-beta/v1"
BACKUP_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")


class RemoteBackupConfiguration(BaseSettings):
    """Dedicated scheduled-backup configuration with no application/provider secrets."""

    model_config = SettingsConfigDict(env_prefix="API_BACKUP_", extra="ignore", case_sensitive=False)

    source_database_url: SecretStr
    release_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_database_tls_mode: Literal["verify_full_system", "verify_full_custom_ca"]
    source_database_ca_certificate_base64: SecretStr | None = None
    encryption_key: SecretStr
    source_s3_endpoint: str
    source_s3_bucket: str
    source_s3_region: str
    source_s3_access_key_id: SecretStr
    source_s3_secret_access_key: SecretStr
    destination_s3_endpoint: str = "https://s3.ap-southeast-2.amazonaws.com"
    destination_s3_bucket: str
    destination_s3_region: Literal["ap-southeast-2"] = "ap-southeast-2"
    destination_s3_access_key_id: SecretStr
    destination_s3_secret_access_key: SecretStr
    restore_target_database_url: SecretStr | None = None
    restore_target_database_ca_certificate_base64: SecretStr | None = None
    restore_target_s3_endpoint: str | None = None
    restore_target_s3_bucket: str | None = None
    restore_target_s3_region: str | None = None
    restore_target_s3_access_key_id: SecretStr | None = None
    restore_target_s3_secret_access_key: SecretStr | None = None

    @model_validator(mode="after")
    def validate_remote_boundaries(self) -> RemoteBackupConfiguration:
        source = urllib.parse.urlsplit(self.source_s3_endpoint)
        destination = urllib.parse.urlsplit(self.destination_s3_endpoint)
        if source.scheme != "https" or destination.scheme != "https":
            raise ValueError("Backup object-storage endpoints must use HTTPS.")
        if not source.hostname or not destination.hostname or source.hostname == destination.hostname:
            raise ValueError("Backup destination must use a provider endpoint independent from source storage.")
        if source.hostname.endswith(".amazonaws.com"):
            raise ValueError("Backup source and destination must use independent providers.")
        if not destination.hostname.endswith(".amazonaws.com"):
            raise ValueError("The reviewed independent backup destination must be Amazon S3.")
        if self.source_s3_bucket == self.destination_s3_bucket and source.hostname == destination.hostname:
            raise ValueError("Backup source and destination must be different buckets.")
        if (
            self.source_database_tls_mode == "verify_full_custom_ca"
            and self.source_database_ca_certificate_base64 is None
        ):
            raise ValueError("Custom-CA source database TLS requires a CA certificate.")
        restore_values = (
            self.restore_target_database_url,
            self.restore_target_database_ca_certificate_base64,
            self.restore_target_s3_endpoint,
            self.restore_target_s3_bucket,
            self.restore_target_s3_region,
            self.restore_target_s3_access_key_id,
            self.restore_target_s3_secret_access_key,
        )
        if any(value is not None for value in restore_values) and not all(
            value is not None for value in restore_values
        ):
            raise ValueError("Named restore configuration must be complete when any restore value is supplied.")
        return self


@dataclass(frozen=True)
class BackupManifest:
    formatVersion: int
    backupId: str
    createdAt: str
    databaseFingerprint: str
    databaseArchiveSha256: str
    storageArchiveSha256: str
    objectCount: int
    encryption: str
    releaseSha: str | None = None
    authentication: str = ""


class BackupError(RuntimeError):
    pass


def _encryption_key(settings: Settings) -> bytes:
    if settings.private_beta_backup_encryption_key is None:
        raise BackupError("Backup encryption is not configured.")
    try:
        key = base64.b64decode(settings.private_beta_backup_encryption_key.get_secret_value(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BackupError("Backup encryption is not configured correctly.") from exc
    if len(key) != 32:
        raise BackupError("Backup encryption is not configured correctly.")
    return key


def _database_url(value: str | None) -> URL:
    if value is None:
        raise BackupError("PostgreSQL is not configured.")
    url = make_url(value)
    if not url.drivername.startswith("postgresql") or not url.host or not url.database:
        raise BackupError("Backup and restore require a named PostgreSQL database.")
    return url


def _restore_target_database_url(argument: str | None) -> str:
    value = argument or os.environ.get("API_RESTORE_TARGET_DATABASE_URL")
    if value is None or not value.strip():
        raise BackupError("Restore target PostgreSQL is not configured.")
    return value.strip()


def database_fingerprint(value: str | None) -> str:
    url = _database_url(value)
    assert url.host is not None
    canonical = f"{url.host.casefold()}:{url.port or 5432}/{url.database}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_ca_certificate(encoded: str | None, directory: Path, filename: str) -> Path | None:
    if encoded is None:
        return None
    try:
        certificate = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BackupError("Database CA certificate is invalid.") from exc
    path = directory / filename
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(certificate)
    return path


def _postgres_environment(
    url: URL,
    tls_mode: Literal["disable", "verify_full_system", "verify_full_custom_ca"],
    ca_certificate: Path | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    if url.password is not None:
        environment["PGPASSWORD"] = url.password
    if tls_mode != "disable":
        environment["PGSSLMODE"] = "verify-full"
        if ca_certificate is not None:
            environment["PGSSLROOTCERT"] = str(ca_certificate)
    else:
        ssl_mode = url.query.get("sslmode") or url.query.get("ssl")
        if ssl_mode:
            environment["PGSSLMODE"] = str(ssl_mode)
    return environment


def _postgres_connection_arguments(url: URL) -> list[str]:
    arguments = ["--host", url.host or "", "--port", str(url.port or 5432), "--dbname", url.database or ""]
    if url.username:
        arguments.extend(("--username", url.username))
    return arguments


def _encrypt_file(source: Path, destination: Path, key: bytes) -> None:
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.writing")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as target, source.open("rb") as incoming:
            target.write(ENCRYPTED_FILE_MAGIC)
            target.write(nonce)
            while chunk := incoming.read(CHUNK_BYTES):
                target.write(encryptor.update(chunk))
            target.write(encryptor.finalize())
            target.write(encryptor.tag)
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _decrypt_file(source: Path, destination: Path, key: bytes) -> None:
    source_size = source.stat().st_size
    header_size = len(ENCRYPTED_FILE_MAGIC) + 12
    if source_size <= header_size + 16:
        raise BackupError("Encrypted backup archive is incomplete.")
    with source.open("rb") as incoming:
        if incoming.read(len(ENCRYPTED_FILE_MAGIC)) != ENCRYPTED_FILE_MAGIC:
            raise BackupError("Encrypted backup archive has an unsupported format.")
        nonce = incoming.read(12)
        incoming.seek(-16, os.SEEK_END)
        tag = incoming.read(16)
        ciphertext_bytes = source_size - header_size - 16
        incoming.seek(header_size)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as target:
                remaining = ciphertext_bytes
                while remaining:
                    chunk = incoming.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise BackupError("Encrypted backup archive ended unexpectedly.")
                    target.write(decryptor.update(chunk))
                    remaining -= len(chunk)
                target.write(decryptor.finalize())
        except InvalidTag as exc:
            destination.unlink(missing_ok=True)
            raise BackupError("Encrypted backup archive failed authentication.") from exc
        except BaseException:
            destination.unlink(missing_ok=True)
            raise


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_authentication(manifest: BackupManifest, key: bytes) -> str:
    payload = {name: value for name, value in manifest.__dict__.items() if name != "authentication"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    authentication_key = hmac.new(key, b"RevenueOS backup manifest authentication v2", hashlib.sha256).digest()
    return f"hmac-sha256:{hmac.new(authentication_key, canonical, hashlib.sha256).hexdigest()}"


def _safe_storage_key(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or any(not part for part in path.parts):
        raise BackupError("Object storage returned an unsafe key.")
    return str(path)


async def _write_storage_archive(storage: VisualStorage, archive_path: Path) -> int:
    keys = await storage.list_keys("")
    with tempfile.TemporaryDirectory(prefix="revenueos-object-backup-") as temporary_name:
        temporary = Path(temporary_name)
        with tarfile.open(archive_path, "w") as archive:
            for index, key in enumerate(keys):
                safe_key = _safe_storage_key(key)
                object_path = temporary / f"object-{index}"
                await storage.read_file(key, object_path)
                info = tarfile.TarInfo(safe_key)
                info.size = object_path.stat().st_size
                info.mode = 0o600
                info.mtime = 0
                with object_path.open("rb") as content:
                    archive.addfile(info, content)
                object_path.unlink()
    return len(keys)


async def create_backup(
    settings: Settings,
    destination_root: Path,
    *,
    allow_encrypted_temporary_destination: bool = False,
) -> tuple[Path, BackupManifest]:
    database_url = _database_url(settings.database_url)
    key = _encryption_key(settings)
    backup_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    resolved_root = destination_root.expanduser().resolve()
    temporary_roots = {
        Path("/tmp").resolve(),
        Path("/private/tmp").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    }
    if (
        settings.private_beta_real_data_enabled
        and not allow_encrypted_temporary_destination
        and any(
            resolved_root == temporary_root or temporary_root in resolved_root.parents
            for temporary_root in temporary_roots
        )
    ):
        raise BackupError("Real-data backups require a durable destination outside temporary storage.")
    resolved_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved_root.chmod(0o700)
    destination = resolved_root / backup_id
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    destination.chmod(0o700)
    try:
        with tempfile.TemporaryDirectory(prefix="revenueos-backup-") as temporary_name:
            temporary = Path(temporary_name)
            source_ca = _write_ca_certificate(
                settings.database_ca_certificate_base64.get_secret_value()
                if settings.database_ca_certificate_base64 is not None
                else None,
                temporary,
                "source-database-ca.pem",
            )
            database_archive = temporary / "database.dump"
            storage_archive = temporary / "objects.tar"
            command = [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(database_archive),
                *_postgres_connection_arguments(database_url),
            ]
            await asyncio.to_thread(
                subprocess.run,
                command,
                env=_postgres_environment(database_url, settings.database_tls_mode, source_ca),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            object_count = await _write_storage_archive(create_visual_storage(settings), storage_archive)
            database_hash = _sha256_file(database_archive)
            storage_hash = _sha256_file(storage_archive)
            _encrypt_file(database_archive, destination / "database.dump.enc", key)
            _encrypt_file(storage_archive, destination / "objects.tar.enc", key)
        manifest = BackupManifest(
            formatVersion=BACKUP_FORMAT_VERSION,
            backupId=backup_id,
            createdAt=datetime.now(UTC).isoformat(),
            databaseFingerprint=database_fingerprint(settings.database_url),
            databaseArchiveSha256=database_hash,
            storageArchiveSha256=storage_hash,
            objectCount=object_count,
            encryption="AES-256-GCM",
            releaseSha=settings.release_sha,
        )
        manifest = replace(manifest, authentication=_manifest_authentication(manifest, key))
        manifest_path = destination / "manifest.json"
        descriptor = os.open(manifest_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(manifest.__dict__, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        return destination, manifest
    except BaseException:
        for child in destination.iterdir():
            child.unlink(missing_ok=True)
        destination.rmdir()
        raise


def _load_manifest(source: Path) -> BackupManifest:
    try:
        payload = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        manifest = BackupManifest(**payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BackupError("Backup manifest is invalid.") from exc
    if manifest.formatVersion != BACKUP_FORMAT_VERSION or manifest.encryption != "AES-256-GCM":
        raise BackupError("Backup manifest version is unsupported.")
    return manifest


async def verify_backup(settings: Settings, source: Path) -> BackupManifest:
    key = _encryption_key(settings)
    manifest = _load_manifest(source)
    if not hmac.compare_digest(manifest.authentication, _manifest_authentication(manifest, key)):
        raise BackupError("Backup manifest failed authentication.")
    with tempfile.TemporaryDirectory(prefix="revenueos-backup-verify-") as temporary_name:
        temporary = Path(temporary_name)
        database_archive = temporary / "database.dump"
        storage_archive = temporary / "objects.tar"
        _decrypt_file(source / "database.dump.enc", database_archive, key)
        _decrypt_file(source / "objects.tar.enc", storage_archive, key)
        if _sha256_file(database_archive) != manifest.databaseArchiveSha256:
            raise BackupError("Database backup integrity check failed.")
        if _sha256_file(storage_archive) != manifest.storageArchiveSha256:
            raise BackupError("Object backup integrity check failed.")
        try:
            with tarfile.open(storage_archive, "r") as archive:
                members = archive.getmembers()
                if len(members) != manifest.objectCount:
                    raise BackupError("Object backup count does not match its manifest.")
                for member in members:
                    _safe_storage_key(member.name)
                    if not member.isfile():
                        raise BackupError("Object backup contains an unsupported entry.")
        except tarfile.TarError as exc:
            raise BackupError("Object backup archive is invalid.") from exc
    return manifest


async def _restore_storage(storage: VisualStorage, archive: Path) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="revenueos-object-restore-") as temporary_name:
            temporary = Path(temporary_name)
            with tarfile.open(archive, "r") as source:
                for index, member in enumerate(source.getmembers()):
                    key = _safe_storage_key(member.name)
                    if not member.isfile():
                        raise BackupError("Object backup contains an unsupported entry.")
                    extracted: IO[bytes] | None = source.extractfile(member)
                    if extracted is None:
                        raise BackupError("Object backup entry could not be read.")
                    object_path = temporary / f"object-{index}"
                    digest = hashlib.sha256()
                    descriptor = os.open(object_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(descriptor, "wb") as output:
                        while chunk := extracted.read(CHUNK_BYTES):
                            digest.update(chunk)
                            output.write(chunk)
                    await storage.write_file(
                        key,
                        object_path,
                        "application/octet-stream",
                        sha256=digest.hexdigest(),
                    )
                    object_path.unlink()
    except tarfile.TarError as exc:
        raise BackupError("Object backup archive is invalid.") from exc


async def restore_backup(
    settings: Settings,
    source: Path,
    target_database_url: str,
    target_storage: VisualStorage,
) -> BackupManifest:
    manifest = await verify_backup(settings, source)
    if database_fingerprint(target_database_url) == manifest.databaseFingerprint:
        raise BackupError("Restore target must not be the source database.")
    if await target_storage.list_keys(""):
        raise BackupError("Restore target storage must be empty.")
    target_url = _database_url(target_database_url)
    key = _encryption_key(settings)
    with tempfile.TemporaryDirectory(prefix="revenueos-restore-") as temporary_name:
        temporary = Path(temporary_name)
        target_ca_value = (
            settings.restore_target_database_ca_certificate_base64.get_secret_value()
            if settings.restore_target_database_ca_certificate_base64 is not None
            else (
                settings.database_ca_certificate_base64.get_secret_value()
                if settings.database_ca_certificate_base64 is not None
                and _database_url(settings.database_url).host == target_url.host
                else None
            )
        )
        if settings.environment == "production" and target_ca_value is None:
            raise BackupError("Production restore requires a certificate-verifying target database CA.")
        target_ca = _write_ca_certificate(target_ca_value, temporary, "target-database-ca.pem")
        database_archive = temporary / "database.dump"
        storage_archive = temporary / "objects.tar"
        _decrypt_file(source / "database.dump.enc", database_archive, key)
        _decrypt_file(source / "objects.tar.enc", storage_archive, key)
        command = [
            "pg_restore",
            "--exit-on-error",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            *_postgres_connection_arguments(target_url),
            str(database_archive),
        ]
        await asyncio.to_thread(
            subprocess.run,
            command,
            env=_postgres_environment(
                target_url,
                "verify_full_custom_ca" if target_ca else settings.database_tls_mode,
                target_ca,
            ),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        await _restore_storage(target_storage, storage_archive)
    return manifest


def _remote_source_settings(configuration: RemoteBackupConfiguration) -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=configuration.source_database_url.get_secret_value(),
        release_sha=configuration.release_sha,
        database_tls_mode=configuration.source_database_tls_mode,
        database_ca_certificate_base64=configuration.source_database_ca_certificate_base64,
        restore_target_database_ca_certificate_base64=(configuration.restore_target_database_ca_certificate_base64),
        visual_storage_backend="s3_compatible",
        visual_s3_endpoint=configuration.source_s3_endpoint,
        visual_s3_bucket=configuration.source_s3_bucket,
        visual_s3_region=configuration.source_s3_region,
        visual_s3_access_key_id=configuration.source_s3_access_key_id,
        visual_s3_secret_access_key=configuration.source_s3_secret_access_key,
        private_beta_backup_encryption_key=configuration.encryption_key,
    )


def _remote_storage(
    *,
    endpoint: str,
    bucket: str,
    region: str,
    access_key_id: SecretStr,
    secret_access_key: SecretStr,
) -> S3CompatibleVisualStorage:
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        visual_storage_backend="s3_compatible",
        visual_s3_endpoint=endpoint,
        visual_s3_bucket=bucket,
        visual_s3_region=region,
        visual_s3_access_key_id=access_key_id,
        visual_s3_secret_access_key=secret_access_key,
    )
    return S3CompatibleVisualStorage(settings)


def _remote_destination_storage(configuration: RemoteBackupConfiguration) -> S3CompatibleVisualStorage:
    return _remote_storage(
        endpoint=configuration.destination_s3_endpoint,
        bucket=configuration.destination_s3_bucket,
        region=configuration.destination_s3_region,
        access_key_id=configuration.destination_s3_access_key_id,
        secret_access_key=configuration.destination_s3_secret_access_key,
    )


def _remote_object_key(backup_id: str, filename: str) -> str:
    if BACKUP_ID_PATTERN.fullmatch(backup_id) is None:
        raise BackupError("Remote backup ID is invalid.")
    if filename not in {"database.dump.enc", "objects.tar.enc", "manifest.json"}:
        raise BackupError("Remote backup filename is invalid.")
    return f"{REMOTE_BACKUP_PREFIX}/{backup_id}/{filename}"


async def _upload_remote_file(
    storage: S3CompatibleVisualStorage,
    backup_id: str,
    source: Path,
    mime_type: str,
) -> None:
    digest = _sha256_file(source)
    key = _remote_object_key(backup_id, source.name)
    await storage.write_file(key, source, mime_type, sha256=digest)
    size, remote_digest = await storage.file_metadata(key)
    if size != source.stat().st_size or remote_digest != digest:
        raise BackupError("Remote backup upload verification failed.")


async def create_remote_backup(configuration: RemoteBackupConfiguration) -> BackupManifest:
    settings = _remote_source_settings(configuration)
    storage = _remote_destination_storage(configuration)
    with tempfile.TemporaryDirectory(prefix="revenueos-remote-backup-") as temporary_name:
        backup_path, manifest = await create_backup(
            settings,
            Path(temporary_name),
            allow_encrypted_temporary_destination=True,
        )
        try:
            # The manifest is the commit marker and is always uploaded last, after
            # both encrypted payloads pass remote size and digest verification.
            for filename, mime_type in (
                ("database.dump.enc", "application/octet-stream"),
                ("objects.tar.enc", "application/octet-stream"),
                ("manifest.json", "application/json"),
            ):
                await _upload_remote_file(storage, manifest.backupId, backup_path / filename, mime_type)
            manifest = await verify_remote_backup(configuration, manifest.backupId)
        except BaseException:
            for filename in ("manifest.json", "objects.tar.enc", "database.dump.enc"):
                try:
                    await storage.delete(_remote_object_key(manifest.backupId, filename))
                except VisualStorageError:
                    pass
            raise
    return manifest


async def _download_remote_backup(
    configuration: RemoteBackupConfiguration,
    backup_id: str,
    destination_root: Path,
) -> Path:
    if BACKUP_ID_PATTERN.fullmatch(backup_id) is None:
        raise BackupError("Remote backup ID is invalid.")
    storage = _remote_destination_storage(configuration)
    destination = destination_root / backup_id
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for filename in ("manifest.json", "database.dump.enc", "objects.tar.enc"):
        await storage.read_file(_remote_object_key(backup_id, filename), destination / filename)
    manifest = _load_manifest(destination)
    if manifest.backupId != backup_id:
        raise BackupError("Remote backup manifest does not match the requested backup.")
    return destination


async def verify_remote_backup(
    configuration: RemoteBackupConfiguration,
    backup_id: str,
) -> BackupManifest:
    settings = _remote_source_settings(configuration)
    with tempfile.TemporaryDirectory(prefix="revenueos-remote-verify-") as temporary_name:
        source = await _download_remote_backup(configuration, backup_id, Path(temporary_name))
        return await verify_backup(settings, source)


async def restore_remote_backup(
    configuration: RemoteBackupConfiguration,
    backup_id: str,
) -> BackupManifest:
    restore_values = (
        configuration.restore_target_database_url,
        configuration.restore_target_database_ca_certificate_base64,
        configuration.restore_target_s3_endpoint,
        configuration.restore_target_s3_bucket,
        configuration.restore_target_s3_region,
        configuration.restore_target_s3_access_key_id,
        configuration.restore_target_s3_secret_access_key,
    )
    if not all(value is not None for value in restore_values):
        raise BackupError("Named restore configuration is incomplete.")
    assert configuration.restore_target_database_url is not None
    assert configuration.restore_target_s3_endpoint is not None
    assert configuration.restore_target_s3_bucket is not None
    assert configuration.restore_target_s3_region is not None
    assert configuration.restore_target_s3_access_key_id is not None
    assert configuration.restore_target_s3_secret_access_key is not None
    settings = _remote_source_settings(configuration)
    target_storage = _remote_storage(
        endpoint=configuration.restore_target_s3_endpoint,
        bucket=configuration.restore_target_s3_bucket,
        region=configuration.restore_target_s3_region,
        access_key_id=configuration.restore_target_s3_access_key_id,
        secret_access_key=configuration.restore_target_s3_secret_access_key,
    )
    with tempfile.TemporaryDirectory(prefix="revenueos-remote-restore-") as temporary_name:
        source = await _download_remote_backup(configuration, backup_id, Path(temporary_name))
        return await restore_backup(
            settings,
            source,
            configuration.restore_target_database_url.get_secret_value(),
            target_storage,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RevenueOS encrypted backup and isolated restore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup = subparsers.add_parser("create")
    backup.add_argument("--destination", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--source", required=True, type=Path)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--source", required=True, type=Path)
    restore.add_argument("--target-database-url")
    restore.add_argument("--target-storage-directory", required=True, type=Path)
    restore.add_argument("--confirm", required=True)
    subparsers.add_parser("create-remote")
    remote_verify = subparsers.add_parser("verify-remote")
    remote_verify.add_argument("--backup-id", required=True)
    remote_restore = subparsers.add_parser("restore-remote")
    remote_restore.add_argument("--backup-id", required=True)
    remote_restore.add_argument("--confirm", required=True)
    return parser


async def _run(arguments: argparse.Namespace, settings: Settings) -> tuple[int, dict[str, object]]:
    if arguments.command == "create":
        path, manifest = await create_backup(settings, arguments.destination)
        return 0, {
            "status": "complete",
            "backupId": manifest.backupId,
            "backupDirectory": str(path),
            "objectCount": manifest.objectCount,
        }
    if arguments.command == "verify":
        manifest = await verify_backup(settings, arguments.source.resolve())
        return 0, {"status": "verified", "backupId": manifest.backupId, "objectCount": manifest.objectCount}
    manifest = _load_manifest(arguments.source.resolve())
    target_database_url = _restore_target_database_url(arguments.target_database_url)
    target_database = _database_url(target_database_url).database
    if arguments.confirm != f"RESTORE {manifest.backupId} INTO {target_database}":
        return 2, {"status": "blocked", "code": "confirmation_mismatch"}
    target_storage_root = arguments.target_storage_directory.resolve()
    if (
        settings.visual_storage_backend == "local"
        and target_storage_root == Path(settings.visual_storage_directory).resolve()
    ):
        raise BackupError("Restore target storage must not be the source storage directory.")
    target_storage_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_storage_root.chmod(0o700)
    restored = await restore_backup(
        settings,
        arguments.source.resolve(),
        target_database_url,
        LocalVisualStorage(str(target_storage_root)),
    )
    return 0, {"status": "complete", "backupId": restored.backupId, "objectCount": restored.objectCount}


async def _run_remote(arguments: argparse.Namespace) -> tuple[int, dict[str, object]]:
    # Pydantic Settings supplies the required fields from API_BACKUP_* variables.
    configuration = RemoteBackupConfiguration()  # type: ignore[call-arg]
    if arguments.command == "create-remote":
        manifest = await create_remote_backup(configuration)
        return 0, {
            "status": "complete",
            "backupId": manifest.backupId,
            "objectCount": manifest.objectCount,
            "remotePrefix": f"{REMOTE_BACKUP_PREFIX}/{manifest.backupId}",
        }
    if arguments.command == "verify-remote":
        manifest = await verify_remote_backup(configuration, arguments.backup_id)
        return 0, {"status": "verified", "backupId": manifest.backupId, "objectCount": manifest.objectCount}
    expected = f"RESTORE {arguments.backup_id} TO CONFIGURED NAMED TARGET"
    if arguments.confirm != expected:
        return 2, {"status": "blocked", "code": "confirmation_mismatch"}
    manifest = await restore_remote_backup(configuration, arguments.backup_id)
    return 0, {"status": "complete", "backupId": manifest.backupId, "objectCount": manifest.objectCount}


def main() -> None:
    arguments = _parser().parse_args()
    try:
        if arguments.command in {"create-remote", "verify-remote", "restore-remote"}:
            exit_code, result = asyncio.run(_run_remote(arguments))
        else:
            exit_code, result = asyncio.run(_run(arguments, get_settings()))
    except (BackupError, OSError, subprocess.SubprocessError, ValidationError, VisualStorageError):
        exit_code, result = 1, {"status": "blocked", "code": "backup_operation_failed"}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
