from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


class FileStorageError(Exception):
    pass


class StorageQuotaExceeded(FileStorageError):
    pass


class FileNotFound(FileStorageError):
    pass


class FileStorage:

    DEFAULT_QUOTA_BYTES = 1 * 1024 * 1024 * 1024

    def __init__(self, root=None, quota_bytes=None):

        if root:
            storage_root = Path(root)
        else:
            storage_root = Path(
                os.getenv(
                    "ODDI_STORAGE_ROOT",
                    r"C:\ODDI_STORAGE"
                    if os.name == "nt"
                    else "/var/lib/oddi/storage",
                )
            )

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
            ) if self.quota_bytes else 0,
        }

    def check_quota(self, user_id, additional_bytes):

        additional_bytes = int(additional_bytes)

        if additional_bytes < 0:
            raise ValueError("additional_bytes cannot be negative.")

        used = self.get_usage(user_id)

        return used + additional_bytes <= self.quota_bytes

    def ensure_quota(self, user_id, additional_bytes):

        if not self.check_quota(user_id, additional_bytes):

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
    ):

        if not isinstance(data, bytes):
            raise TypeError("data must be bytes.")

        size_bytes = len(data)

        self.ensure_quota(user_id, size_bytes)

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

        if not path.is_file():
            raise FileNotFound(
                f"Stored file does not exist: {storage_key}"
            )

        return path

    def read_bytes(self, user_id, storage_key):

        path = self.get_path(user_id, storage_key)

        return path.read_bytes()

    def delete(self, user_id, storage_key):

        path = self._safe_path(user_id, storage_key)

        if not path.exists():
            return False

        if not path.is_file():
            raise FileStorageError(
                "Storage key does not point to a file."
            )

        path.unlink()

        return True

    def delete_user_storage(self, user_id):

        user_dir = self.user_directory(user_id)

        if not user_dir.exists():
            return False

        shutil.rmtree(user_dir)

        return True
