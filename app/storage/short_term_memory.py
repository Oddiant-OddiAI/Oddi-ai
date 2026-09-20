from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path


class ShortTermMemoryStorage:
    """
    ODDI internal temporary storage.

    This storage is NOT user-accessible.

    Physical structure:

        C:\\ODDI_STORAGE\\
        └── short_term_memory\\
            ├── user_1\\
            ├── user_2\\
            └── ...

    Every memory has a TTL.
    """

    DEFAULT_TTL_SECONDS = 60 * 60  # 1 hour

    def __init__(
        self,
        root: str | None = None,
        default_ttl_seconds: int | None = None,
    ):
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
        self.memory_root = self.root / "short_term_memory"

        self.default_ttl_seconds = int(
            default_ttl_seconds
            if default_ttl_seconds is not None
            else os.getenv(
                "ODDI_SHORT_TERM_MEMORY_TTL",
                str(self.DEFAULT_TTL_SECONDS),
            )
        )

        self.memory_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ---------------------------------------------------------
    # USER DIRECTORY
    # ---------------------------------------------------------

    def user_directory(
        self,
        user_id: int | str,
    ) -> Path:
        user_dir = self.memory_root / f"user_{int(user_id)}"

        user_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        return user_dir

    # ---------------------------------------------------------
    # SECURITY
    # ---------------------------------------------------------

    def _safe_path(
        self,
        user_id: int | str,
        filename: str,
    ) -> Path:
        user_dir = self.user_directory(user_id).resolve()
        candidate = (user_dir / filename).resolve()

        try:
            candidate.relative_to(user_dir)
        except ValueError:
            raise ValueError("Invalid short-term memory path.")

        return candidate

    # ---------------------------------------------------------
    # STORE
    # ---------------------------------------------------------

    def store(
        self,
        user_id: int | str,
        data: bytes,
        ttl_seconds: int | None = None,
    ) -> str:
        """
        Store temporary data.

        Returns a unique memory ID.
        """

        if not isinstance(data, bytes):
            raise TypeError("data must be bytes.")

        memory_id = uuid.uuid4().hex

        user_dir = self.user_directory(user_id)

        data_filename = f"{memory_id}.bin"
        metadata_filename = f"{memory_id}.json"

        data_path = user_dir / data_filename
        metadata_path = user_dir / metadata_filename

        ttl = (
            int(ttl_seconds)
            if ttl_seconds is not None
            else self.default_ttl_seconds
        )

        created_at = time.time()
        expires_at = created_at + ttl

        data_path.write_bytes(data)

        metadata = {
            "memory_id": memory_id,
            "user_id": int(user_id),
            "created_at": created_at,
            "expires_at": expires_at,
            "size_bytes": len(data),
        }

        metadata_path.write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )

        return memory_id

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------

    def get(
        self,
        user_id: int | str,
        memory_id: str,
    ) -> bytes | None:
        """
        Retrieve temporary memory.

        Expired memory is automatically deleted.
        """

        metadata_path = self._safe_path(
            user_id,
            f"{memory_id}.json",
        )

        data_path = self._safe_path(
            user_id,
            f"{memory_id}.bin",
        )

        if not metadata_path.exists():
            return None

        try:
            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            self.delete(user_id, memory_id)
            return None

        if time.time() >= metadata["expires_at"]:
            self.delete(user_id, memory_id)
            return None

        if not data_path.exists():
            return None

        return data_path.read_bytes()

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def delete(
        self,
        user_id: int | str,
        memory_id: str,
    ) -> bool:
        data_path = self._safe_path(
            user_id,
            f"{memory_id}.bin",
        )

        metadata_path = self._safe_path(
            user_id,
            f"{memory_id}.json",
        )

        deleted = False

        if data_path.exists():
            data_path.unlink()
            deleted = True

        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        return deleted

    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------

    def cleanup_expired(
        self,
        user_id: int | str | None = None,
    ) -> int:
        """
        Delete expired temporary memories.

        Returns the number of deleted memories.
        """

        if user_id is not None:
            directories = [self.user_directory(user_id)]
        else:
            directories = [
                path
                for path in self.memory_root.glob("user_*")
                if path.is_dir()
            ]

        deleted_count = 0

        now = time.time()

        for directory in directories:
            for metadata_path in directory.glob("*.json"):
                try:
                    metadata = json.loads(
                        metadata_path.read_text(
                            encoding="utf-8"
                        )
                    )

                    if now >= metadata["expires_at"]:
                        memory_id = metadata["memory_id"]

                        try:
                            numeric_user_id = int(
                                directory.name.split(
                                    "user_",
                                    1,
                                )[1]
                            )
                        except (ValueError, IndexError):
                            continue

                        if self.delete(
                            numeric_user_id,
                            memory_id,
                        ):
                            deleted_count += 1

                except Exception:
                    continue

        return deleted_count

    # ---------------------------------------------------------
    # DELETE USER MEMORY
    # ---------------------------------------------------------

    def delete_user_storage(
        self,
        user_id: int | str,
    ) -> bool:
        user_dir = self.user_directory(user_id)

        if not user_dir.exists():
            return False

        shutil.rmtree(user_dir)

        return True