from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy.engine import URL, make_url

from revenueos.config import Settings, get_settings
from revenueos.visual_storage import LocalVisualStorage, VisualStorage, VisualStorageError, create_visual_storage

BACKUP_FORMAT_VERSION = 1
ENCRYPTED_FILE_MAGIC = b"ROSBK1"
CHUNK_BYTES = 1024 * 1024


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


def database_fingerprint(value: str | None) -> str:
    url = _database_url(value)
    assert url.host is not None
    canonical = f"{url.host.casefold()}:{url.port or 5432}/{url.database}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _postgres_environment(url: URL) -> dict[str, str]:
    environment = os.environ.copy()
    if url.password is not None:
        environment["PGPASSWORD"] = url.password
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


def _safe_storage_key(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or any(not part for part in path.parts):
        raise BackupError("Object storage returned an unsafe key.")
    return str(path)


async def _write_storage_archive(storage: VisualStorage, archive_path: Path) -> int:
    keys = await storage.list_keys("")
    with tarfile.open(archive_path, "w") as archive:
        for key in keys:
            safe_key = _safe_storage_key(key)
            content = await storage.read(key)
            info = tarfile.TarInfo(safe_key)
            info.size = len(content)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    return len(keys)


async def create_backup(settings: Settings, destination_root: Path) -> tuple[Path, BackupManifest]:
    database_url = _database_url(settings.database_url)
    key = _encryption_key(settings)
    backup_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    resolved_root = destination_root.expanduser().resolve()
    temporary_roots = {
        Path("/tmp").resolve(),
        Path("/private/tmp").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    }
    if settings.private_beta_real_data_enabled and any(
        resolved_root == temporary_root or temporary_root in resolved_root.parents for temporary_root in temporary_roots
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
                env=_postgres_environment(database_url),
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
        )
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
        with tarfile.open(archive, "r") as source:
            for member in source.getmembers():
                key = _safe_storage_key(member.name)
                if not member.isfile():
                    raise BackupError("Object backup contains an unsupported entry.")
                extracted: IO[bytes] | None = source.extractfile(member)
                if extracted is None:
                    raise BackupError("Object backup entry could not be read.")
                await storage.write(key, extracted.read(), "application/octet-stream")
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
            env=_postgres_environment(target_url),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        await _restore_storage(target_storage, storage_archive)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RevenueOS encrypted backup and isolated restore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup = subparsers.add_parser("create")
    backup.add_argument("--destination", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--source", required=True, type=Path)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--source", required=True, type=Path)
    restore.add_argument("--target-database-url", required=True)
    restore.add_argument("--target-storage-directory", required=True, type=Path)
    restore.add_argument("--confirm", required=True)
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
    target_database = _database_url(arguments.target_database_url).database
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
        arguments.target_database_url,
        LocalVisualStorage(str(target_storage_root)),
    )
    return 0, {"status": "complete", "backupId": restored.backupId, "objectCount": restored.objectCount}


def main() -> None:
    arguments = _parser().parse_args()
    try:
        exit_code, result = asyncio.run(_run(arguments, get_settings()))
    except (BackupError, OSError, subprocess.SubprocessError, VisualStorageError):
        exit_code, result = 1, {"status": "blocked", "code": "backup_operation_failed"}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
