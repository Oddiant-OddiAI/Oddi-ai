from __future__ import annotations

import os
import shutil
import uuid
import logging
from pathlib import Path

logger = logging.getLogger("oddi.file_storage")


class FileStorageError(Exception):
    pass


class StorageQuotaExceeded(FileStorageError):
    pass


class FileNotFound(FileStorageError):
    pass


class FileStorage:
    DEFAULT_QUOTA_BYTES = 1 * 1024 * 1024 * 1024

    def __init__(self, root=None, quota_bytes=None):
        local_only = os.getenv("ODDI_LOCAL_ONLY_STORAGE", "").strip().lower() in {
            "1", "true", "yes", "on",
        }
        self.legacy_files_root = None

        if root:
            storage_root = Path(root)
        else:
            file_storage_override = os.getenv("ODDI_FILE_STORAGE_ROOT", "").strip()
            old_storage_override = os.getenv("ODDI_STORAGE_ROOT", "").strip()
            if file_storage_override:
                storage_root = Path(file_storage_override).expanduser()
            elif local_only:
                local_data = Path(
                    os.getenv("LOCALAPPDATA")
                    or (Path.home() / "AppData" / "Local")
                )
                storage_root = local_data / "OddiAI"
            else:
                storage_root = Path(
                    old_storage_override
                    or (
                        r"C:\ODDI_STORAGE"
                        if os.name == "nt"
                        else "/tmp/oddi_storage"
                    )
                ).expanduser()

            if local_only:
                previous_root = Path(
                    old_storage_override
                    or (
                        r"C:\ODDI_STORAGE"
                        if os.name == "nt"
                        else "/tmp/oddi_storage"
                    )
                ).expanduser().resolve()
                next_files_root = (storage_root.resolve() / "files")
                previous_files_root = previous_root / "files"
                if previous_files_root != next_files_root:
                    self.legacy_files_root = previous_files_root

        self.root = storage_root.resolve()
        self.files_root = self.root / "files"
        self.quota_bytes = int(
            quota_bytes
            if quota_bytes is not None
            else os.getenv(
                "ODDI_FILE_QUOTA_BYTES",
                str(self.DEFAULT_QUOTA_BYTES),
            )
        )
        self.files_root.mkdir(parents=True, exist_ok=True)
        if self.legacy_files_root:
            self._migrate_legacy_files()

    def _migrate_legacy_files(self):
        """Copy legacy laptop Library blobs beside the persistent chat data."""
        legacy_root = self.legacy_files_root
        if not legacy_root or not legacy_root.is_dir():
            return

        copied = 0
        failures = 0
        for source in legacy_root.rglob("*"):
            if not source.is_file() or source.name.startswith(".") or source.suffix == ".tmp":
                continue
            try:
                relative = source.relative_to(legacy_root)
                target = self.files_root / relative
                target.resolve().relative_to(self.files_root.resolve())
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.migration")
                try:
                    shutil.copy2(source, temporary)
                    if target.exists():
                        temporary.unlink()
                    else:
                        temporary.replace(target)
                        copied += 1
                finally:
                    if temporary.exists():
                        temporary.unlink()
            except (OSError, ValueError):
                failures += 1
                logger.exception("Could not migrate a legacy Library file into %s", self.files_root)

        if copied or failures:
            logger.info(
                "Legacy Library file migration finished (copied=%s, failures=%s)",
                copied,
                failures,
            )

    def user_directory(self, user_id):
        user_dir = self.files_root / f"user_{int(user_id)}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _safe_path(self, user_id, storage_key):
        user_dir = self.user_directory(user_id).resolve()
        candidate = (user_dir / storage_key).resolve()
        try:
            candidate.relative_to(user_dir)
        except ValueError:
            raise FileStorageError("Invalid storage path.")
        return candidate

    def get_usage(self, user_id):
        user_dir = self.user_directory(user_id)
        total = 0
        for path in user_dir.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
        if self.legacy_files_root:
            legacy_user_dir = self.legacy_files_root / f"user_{int(user_id)}"
            if legacy_user_dir.is_dir():
                for path in legacy_user_dir.rglob("*"):
                    if not path.is_file():
                        continue
                    try:
                        relative = path.relative_to(legacy_user_dir)
                        if not (user_dir / relative).exists():
                            total += path.stat().st_size
                    except OSError:
                        continue
        return total

    def get_quota(self, user_id):
        used = self.get_usage(user_id)
        remaining = max(self.quota_bytes - used, 0)
        return {
            "quota_bytes": self.quota_bytes,
            "used_bytes": used,
            "remaining_bytes": remaining,
            "quota_percent": round(
                (used / self.quota_bytes) * 100,
                2,
            )
            if self.quota_bytes
            else 0,
        }

    def check_quota(self, user_id, additional_bytes, quota_credit_bytes=0):
        additional_bytes = int(additional_bytes)
        quota_credit_bytes = max(0, int(quota_credit_bytes or 0))
        if additional_bytes < 0:
            raise ValueError("additional_bytes cannot be negative.")
        used = self.get_usage(user_id)
        credited_usage = max(0, used - quota_credit_bytes)
        return credited_usage + additional_bytes <= self.quota_bytes

    def ensure_quota(self, user_id, additional_bytes, quota_credit_bytes=0):
        if not self.check_quota(user_id, additional_bytes, quota_credit_bytes):
            info = self.get_quota(user_id)
            raise StorageQuotaExceeded(
                f"File storage quota exceeded. "
                f"Used {info['used_bytes']} bytes of "
                f"{info['quota_bytes']} bytes."
            )

    def save_bytes(
        self,
        user_id,
        data,
        original_filename=None,
        quota_credit_bytes=0,
    ):
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes.")

        size_bytes = len(data)
        self.ensure_quota(user_id, size_bytes, quota_credit_bytes)
        user_dir = self.user_directory(user_id)

        extension = ""
        if original_filename:
            suffix = Path(original_filename).suffix
            if suffix and len(suffix) <= 20:
                safe_suffix = "".join(
                    char
                    for char in suffix
                    if char.isalnum() or char in "._-"
                )
                extension = safe_suffix

        filename = f"{uuid.uuid4().hex}{extension}"
        path = user_dir / filename
        temp_path = user_dir / f".{filename}.tmp"

        try:
            with open(temp_path, "wb") as file:
                file.write(data)
            temp_path.replace(path)
        except Exception:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            raise

        return {
            "storage_backend": "filesystem",
            "storage_key": filename,
            "size_bytes": size_bytes,
            "physical_path": str(path),
        }

    def get_path(self, user_id, storage_key):
        path = self._safe_path(user_id, storage_key)
        if path.is_file():
            return path

        if self.legacy_files_root:
            legacy_user_dir = (self.legacy_files_root / f"user_{int(user_id)}").resolve()
            legacy_path = (legacy_user_dir / str(storage_key)).resolve()
            try:
                legacy_path.relative_to(legacy_user_dir)
            except ValueError as exc:
                raise FileStorageError("Invalid storage path.") from exc
            if legacy_path.is_file():
                return legacy_path

        raise FileNotFound(f"Stored file does not exist: {storage_key}")

    def read_bytes(self, user_id, storage_key):
        path = self.get_path(user_id, storage_key)
        return path.read_bytes()

    def delete(self, user_id, storage_key):
        paths = [self._safe_path(user_id, storage_key)]
        if self.legacy_files_root:
            legacy_user_dir = (self.legacy_files_root / f"user_{int(user_id)}").resolve()
            legacy_path = (legacy_user_dir / str(storage_key)).resolve()
            try:
                legacy_path.relative_to(legacy_user_dir)
            except ValueError as exc:
                raise FileStorageError("Invalid storage path.") from exc
            paths.append(legacy_path)

        deleted = False
        for path in paths:
            if not path.exists():
                continue
            if not path.is_file():
                raise FileStorageError("Storage key does not point to a file.")
            path.unlink()
            deleted = True
        return deleted

    def delete_user_storage(self, user_id):
        user_dir = self.files_root / f"user_{int(user_id)}"
        directories = [user_dir]
        if self.legacy_files_root:
            directories.append(self.legacy_files_root / f"user_{int(user_id)}")

        deleted = False
        for directory in directories:
            if directory.is_dir():
                shutil.rmtree(directory)
                deleted = True
        return deleted
