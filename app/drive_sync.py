"""Best-effort two-way mirror between laptop chat files and Google Drive."""

import logging
import threading
from datetime import datetime, timezone

from app import google_drive_storage, local_chat_files

logger = logging.getLogger("oddi.drive_sync")
_SYNC_LOCK = threading.Lock()


def _is_newer(left, right):
    left_updated = str(left.get("updated_at") or left.get("created_at") or "")
    right_updated = str(right.get("updated_at") or right.get("created_at") or "")
    if left_updated != right_updated:
        return left_updated > right_updated
    return int(left.get("revision", 0) or 0) > int(right.get("revision", 0) or 0)


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sync_account_settings(database, local_user, cloud_account):
    """Copy whichever account settings copy was changed most recently."""
    local_settings = local_user.get("settings")
    if not isinstance(local_settings, dict):
        local_settings = {}
    cloud_settings = cloud_account.get("settings")
    if not isinstance(cloud_settings, dict):
        cloud_settings = {}

    local_stamp = _parse_timestamp(local_user.get("settings_updated_at"))
    cloud_stamp = _parse_timestamp(cloud_account.get("settings_updated_at"))
    remote_id = int(cloud_account["id"])
    local_id = int(local_user["id"])

    if local_stamp and (not cloud_stamp or local_stamp > cloud_stamp):
        google_drive_storage.update_account_settings(remote_id, local_settings)
    elif cloud_stamp and (not local_stamp or cloud_stamp > local_stamp):
        database.save_user_settings(local_id, cloud_settings)
    elif local_settings != cloud_settings:
        if local_stamp:
            google_drive_storage.update_account_settings(remote_id, local_settings)
        else:
            database.save_user_settings(local_id, cloud_settings)


def sync_laptop_once():
    """Import cloud accounts/chats, then upload laptop-only changes."""
    if not google_drive_storage.is_configured():
        return {"accounts": 0, "chats": 0}
    if not _SYNC_LOCK.acquire(blocking=False):
        return {"accounts": 0, "chats": 0, "skipped": True}

    try:
        return _sync_laptop_once_locked()
    finally:
        _SYNC_LOCK.release()


def _sync_laptop_once_locked():
    from app import database

    local_users = database.get_users_for_drive_sync()
    local_by_email = {str(user.get("email") or "").strip().casefold(): user for user in local_users}
    for tombstone in google_drive_storage.list_deleted_accounts():
        for email, user in list(local_by_email.items()):
            if google_drive_storage.user_id_for_email(email) != int(tombstone["id"]):
                continue
            # Account deletion on either side must not be undone by the next
            # laptop upload pass.
            database.delete_user_record(user["id"])
            local_by_email.pop(email, None)
    cloud_accounts = google_drive_storage.list_accounts()

    # Refresh existing accounts too so laptop login credentials/profile match
    # accounts created or changed on another device.
    for account in cloud_accounts:
        email = str(account.get("email") or "").strip().casefold()
        if email:
            local_id = database.import_drive_account_to_local(account)
            if local_id:
                local_by_email[email] = {
                    "id": local_id,
                    "username": account.get("username", ""),
                    "email": email,
                    "password_hash": account.get("password_hash", ""),
                    "created_at": account.get("created_at"),
                }

    # Reload settings and local IDs after imports so sync compares the current
    # local copy with the Drive copy before processing conversations.
    local_users = database.get_users_for_drive_sync()
    local_by_email = {
        str(user.get("email") or "").strip().casefold(): user
        for user in local_users
    }

    cloud_by_email = {
        str(account.get("email") or "").strip().casefold(): account
        for account in cloud_accounts
    }
    synced_chats = 0

    for email, local_user in local_by_email.items():
        if not email:
            continue
        cloud_account = cloud_by_email.get(email)
        if cloud_account is None:
            cloud_account = google_drive_storage.upsert_account_from_local(local_user)
            if not cloud_account:
                continue
            cloud_by_email[email] = cloud_account
        _sync_account_settings(database, local_user, cloud_account)
        remote_id = int(cloud_account["id"])
        local_id = int(local_user["id"])

        local_tombstones = local_chat_files.get_tombstones(local_id)
        remote_tombstones = google_drive_storage.get_tombstones(remote_id)
        tombstoned = set(local_tombstones) | set(remote_tombstones)

        for conversation_id, deleted_at in local_tombstones.items():
            google_drive_storage.apply_permanent_tombstone(remote_id, conversation_id, deleted_at)
        for conversation_id, deleted_at in remote_tombstones.items():
            local_chat_files.apply_permanent_tombstone(local_id, conversation_id, deleted_at)

        local_chats = {
            str(chat["id"]): chat
            for chat in local_chat_files.get_all_conversations(local_id)
        }
        remote_chats = {
            str(chat["id"]): chat
            for chat in google_drive_storage.get_all_conversations(remote_id)
        }

        for conversation_id in set(local_chats) | set(remote_chats):
            if conversation_id in tombstoned:
                continue
            local_chat = local_chats.get(conversation_id)
            remote_chat = remote_chats.get(conversation_id)
            if local_chat and remote_chat:
                if _is_newer(local_chat, remote_chat):
                    copy = dict(local_chat)
                    copy["user_id"] = remote_id
                    google_drive_storage.import_conversation(remote_id, copy)
                elif _is_newer(remote_chat, local_chat):
                    copy = dict(remote_chat)
                    copy["user_id"] = local_id
                    local_chat_files.import_conversation(local_id, copy)
            elif local_chat:
                copy = dict(local_chat)
                copy["user_id"] = remote_id
                google_drive_storage.import_conversation(remote_id, copy)
            elif remote_chat:
                copy = dict(remote_chat)
                copy["user_id"] = local_id
                local_chat_files.import_conversation(local_id, copy)
            synced_chats += 1

        if tombstoned:
            local_chat_files.clear_tombstones(local_id, tombstoned)
            google_drive_storage.clear_tombstones(remote_id, tombstoned)

    return {"accounts": len(local_by_email), "chats": synced_chats}
