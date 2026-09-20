from __future__ import annotations

from .files import (
    FileStorage,
    FileStorageError,
    FileNotFound,
    StorageQuotaExceeded,
)

from .short_term_memory import (
    ShortTermMemoryStorage,
)


class StorageRouter:
    CHAT = "chat"
    FILES = "files"
    SHORT_TERM_MEMORY = "short_term_memory"

    def __init__(self):
        self.files = FileStorage()
        self.short_term_memory = ShortTermMemoryStorage()

    def get_storage(self, storage_type):
        if storage_type == self.FILES:
            return self.files

        if storage_type == self.SHORT_TERM_MEMORY:
            return self.short_term_memory

        if storage_type == self.CHAT:
            return None

        raise ValueError(
            f"Unknown storage type: {storage_type}"
        )

    def save_file(
        self,
        user_id,
        data,
        original_filename=None,
    ):
        return self.files.save_bytes(
            user_id=user_id,
            data=data,
            original_filename=original_filename,
        )

    def get_file_path(
        self,
        user_id,
        storage_key,
    ):
        return self.files.get_path(
            user_id,
            storage_key,
        )

    def read_file(
        self,
        user_id,
        storage_key,
    ):
        return self.files.read_bytes(
            user_id,
            storage_key,
        )

    def delete_file(
        self,
        user_id,
        storage_key,
    ):
        return self.files.delete(
            user_id,
            storage_key,
        )

    def get_file_quota(self, user_id):
        return self.files.get_quota(user_id)

    def store_short_term_memory(
        self,
        user_id,
        data,
        ttl_seconds=None,
    ):
        return self.short_term_memory.store(
            user_id=user_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )

    def get_short_term_memory(
        self,
        user_id,
        memory_id,
    ):
        return self.short_term_memory.get(
            user_id,
            memory_id,
        )

    def delete_short_term_memory(
        self,
        user_id,
        memory_id,
    ):
        return self.short_term_memory.delete(
            user_id,
            memory_id,
        )

    def cleanup_short_term_memory(
        self,
        user_id=None,
    ):
        return self.short_term_memory.cleanup_expired(
            user_id
        )

    def get_user_storage_info(self, user_id):
        return {
            "files": self.get_file_quota(user_id),
        }


storage_router = StorageRouter()


__all__ = [
    "StorageRouter",
    "storage_router",
    "FileStorageError",
    "FileNotFound",
    "StorageQuotaExceeded",
]
