"""Account-scoped chat and account storage in an operator-owned Google Drive.

This adapter uses a Google service account and therefore requires the target
folder to be inside a Google Workspace Shared Drive. Google service accounts
cannot own files in a consumer My Drive. Keep data separated by a stable,
non-reversible account key; never accept a folder ID from a web request.
"""

import hashlib
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("oddi.drive_storage")

_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_CONFIG_KEYS = (
    "GOOGLE_DRIVE_CLIENT_EMAIL",
    "GOOGLE_DRIVE_PRIVATE_KEY",
    "GOOGLE_DRIVE_FOLDER_ID",
)
_CHAT_NAME_RE = re.compile(r"^chat-([1-9][0-9]*)\.json$")
_DELETED_ACCOUNT_FILE = "_deleted-account.json"
_LOCK_GUARD = threading.Lock()
_ACCOUNT_LOCKS = {}
_SERVICE = None
_SERVICE_LOCK = threading.Lock()
_ROOT_VALIDATED = False
_ROOT_DRIVE_ID = None


class DriveStorageError(RuntimeError):
    """A safe-to-log Drive configuration or API error."""


def is_configured():
    """True only after the user replaces all sample values with real values."""
    values = {key: os.getenv(key, "").strip() for key in _CONFIG_KEYS}
    if not all(values.values()):
        return False
    lowered = " ".join(values.values()).casefold()
    return not any(marker in lowered for marker in ("your-project", "your_google", "your-private-key"))


def _lock_for(account_id):
    with _LOCK_GUARD:
        return _ACCOUNT_LOCKS.setdefault(str(account_id), threading.RLock())


def user_id_for_email(email):
    normalized = str(email or "").strip().casefold()
    if not normalized or "@" not in normalized:
        raise ValueError("A valid email address is required for Drive account storage.")
    # Keep the generated id within JavaScript's exact integer range. It is a
    # stable account key, not an authentication secret.
    value = int.from_bytes(hashlib.sha256(normalized.encode("utf-8")).digest()[:8], "big") & ((1 << 52) - 1)
    return value or 1


def _account_key(user_id):
    try:
        value = int(user_id)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Drive storage requires a valid account ID.") from exc
    if value <= 0:
        raise ValueError("Drive storage requires a valid account ID.")
    return str(value)


def _chat_key(conversation_id):
    try:
        value = int(conversation_id)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Drive storage requires a valid conversation ID.") from exc
    if value <= 0:
        raise ValueError("Drive storage requires a valid conversation ID.")
    return str(value)


def _service():
    global _SERVICE
    if _SERVICE is not None:
        return _SERVICE
    if not is_configured():
        raise DriveStorageError(
            "Google Drive storage is not configured. Replace the sample values for "
            "GOOGLE_DRIVE_CLIENT_EMAIL, GOOGLE_DRIVE_PRIVATE_KEY, and GOOGLE_DRIVE_FOLDER_ID."
        )
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        private_key = os.getenv("GOOGLE_DRIVE_PRIVATE_KEY", "").strip().lstrip("\ufeff")
        client_email = os.getenv("GOOGLE_DRIVE_CLIENT_EMAIL", "").strip().strip('"\'')
        if private_key.startswith("{"):
            try:
                service_account_json = json.loads(private_key)
            except json.JSONDecodeError:
                service_account_json = None
            if isinstance(service_account_json, dict):
                private_key = str(service_account_json.get("private_key") or "")
                client_email = str(service_account_json.get("client_email") or client_email)
        elif private_key.startswith('"') and private_key.endswith('"'):
            try:
                private_key = json.loads(private_key)
            except json.JSONDecodeError:
                private_key = private_key[1:-1]
        elif private_key.startswith("'") and private_key.endswith("'"):
            private_key = private_key[1:-1]

        private_key = private_key.replace("\\\\n", "\n").replace("\\n", "\n")
        private_key = private_key.replace("\r\n", "\n").replace("\r", "\n").strip()
        begin_marker = "-----BEGIN PRIVATE KEY-----"
        end_marker = "-----END PRIVATE KEY-----"
        begin = private_key.find(begin_marker)
        end = private_key.find(end_marker)
        if begin < 0 or end < begin:
            raise DriveStorageError(
                "GOOGLE_DRIVE_PRIVATE_KEY must contain the complete BEGIN/END PRIVATE KEY block."
            )
        private_key = private_key[begin:end + len(end_marker)].strip() + "\n"
        info = {
            "type": "service_account",
            "client_email": client_email,
            "private_key": private_key,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=[_DRIVE_SCOPE],
        )
        _SERVICE = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return _SERVICE
    except ImportError as exc:
        raise DriveStorageError(
            "Google Drive packages are missing. Install the Google Drive dependencies from requirements.txt."
        ) from exc
    except DriveStorageError:
        raise
    except Exception as exc:
        logger.exception("Could not initialize the Google Drive client")
        raise DriveStorageError(
            "Google Drive credentials could not be loaded. Check that GOOGLE_DRIVE_PRIVATE_KEY is the complete, unmodified PEM key and that GOOGLE_DRIVE_CLIENT_EMAIL matches its service account."
        ) from exc


def _api_call(request):
    try:
        return request.execute(num_retries=3)
    except Exception as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in {401, 403}:
            raise DriveStorageError(
                "Google Drive rejected the service account. Check its credentials and access to the configured Shared Drive folder."
            ) from exc
        if status == 404:
            raise DriveStorageError(
                "The configured Google Drive folder was not found or is not shared with the service account."
            ) from exc
        logger.exception("Google Drive API request failed (status=%s)", status)
        raise DriveStorageError(f"Google Drive request failed (HTTP {status or 'unknown'}).") from exc


def _validate_root():
    global _ROOT_VALIDATED, _ROOT_DRIVE_ID
    if _ROOT_VALIDATED:
        return
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip().strip('"')
    meta = _api_call(
        _service().files().get(
            fileId=folder_id,
            fields="id,name,mimeType,driveId",
            supportsAllDrives=True,
        )
    )
    if meta.get("mimeType") != _FOLDER_MIME:
        raise DriveStorageError("GOOGLE_DRIVE_FOLDER_ID must point to a folder.")
    if not meta.get("driveId"):
        raise DriveStorageError(
            "This folder is in personal My Drive. Service accounts cannot create or own files there; "
            "use a Workspace Shared Drive folder or configure Google user OAuth instead."
        )
    _ROOT_DRIVE_ID = meta["driveId"]
    _ROOT_VALIDATED = True


def _escape_query(value):
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _list_children(parent_id, name=None, mime_type=None):
    _validate_root()
    clauses = [f"'{_escape_query(parent_id)}' in parents", "trashed = false"]
    if name is not None:
        clauses.append(f"name = '{_escape_query(name)}'")
    if mime_type is not None:
        clauses.append(f"mimeType = '{_escape_query(mime_type)}'")
    query = " and ".join(clauses)
    page_token = None
    items = []
    while True:
        result = _api_call(
            _service().files().list(
                q=query,
                pageSize=1000,
                pageToken=page_token,
                fields="nextPageToken,files(id,name,mimeType,parents,driveId,modifiedTime)",
                corpora="drive",
                driveId=_ROOT_DRIVE_ID,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
        )
        items.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return items


def _find_child(parent_id, name, mime_type=None):
    items = _list_children(parent_id, name=name, mime_type=mime_type)
    return items[0] if items else None


def _create_folder(parent_id, name):
    return _api_call(
        _service().files().create(
            body={"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]},
            fields="id,name,mimeType,driveId",
            supportsAllDrives=True,
        )
    )


def _root_folder_id():
    _validate_root()
    return os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip().strip('"')


def _accounts_folder(create=False):
    root_id = _root_folder_id()
    folder = _find_child(root_id, "accounts", _FOLDER_MIME)
    if folder or not create:
        return folder["id"] if folder else None
    return _create_folder(root_id, "accounts")["id"]


def _account_folder(user_id, create=False):
    account_id = _account_key(user_id)
    accounts_id = _accounts_folder(create=create)
    if not accounts_id:
        return None
    folder = _find_child(accounts_id, f"account-{account_id}", _FOLDER_MIME)
    if folder or not create:
        return folder["id"] if folder else None
    return _create_folder(accounts_id, f"account-{account_id}")["id"]


def _read_json_file(parent_id, name):
    meta = _find_child(parent_id, name)
    if not meta:
        return None
    try:
        from googleapiclient.http import MediaIoBaseDownload

        request = _service().files().get_media(fileId=meta["id"], supportsAllDrives=True)
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=3)
        return json.loads(output.getvalue().decode("utf-8"))
    except DriveStorageError:
        raise
    except Exception as exc:
        logger.exception("Could not read Drive JSON file %s", name)
        raise DriveStorageError("A stored Google Drive data file could not be read.") from exc


def _write_json_file(parent_id, name, value):
    try:
        from googleapiclient.http import MediaIoBaseUpload

        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        media = MediaIoBaseUpload(
            io.BytesIO(payload),
            mimetype="application/json",
            chunksize=1024 * 1024,
            resumable=True,
        )
        meta = _find_child(parent_id, name)
        if meta:
            return _api_call(
                _service().files().update(
                    fileId=meta["id"],
                    media_body=media,
                    fields="id,name,modifiedTime",
                    supportsAllDrives=True,
                )
            )
        return _api_call(
            _service().files().create(
                body={"name": name, "mimeType": "application/json", "parents": [parent_id]},
                media_body=media,
                fields="id,name,modifiedTime",
                supportsAllDrives=True,
            )
        )
    except DriveStorageError:
        raise
    except Exception as exc:
        logger.exception("Could not write Drive JSON file %s", name)
        raise DriveStorageError("Google Drive could not save the account or chat file.") from exc


def _delete_child(parent_id, name):
    meta = _find_child(parent_id, name)
    if not meta:
        return False
    _api_call(_service().files().delete(fileId=meta["id"], supportsAllDrives=True))
    return True


def _iso_timestamp(value=None, fallback=None):
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError):
            parsed = fallback or datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _normalize_conversation(value, account_id, conversation_id=None):
    if not isinstance(value, dict):
        raise ValueError("Conversation data must be an object.")
    chat_id = int(conversation_id if conversation_id is not None else value.get("id"))
    now = _iso_timestamp()
    messages = []
    for index, message in enumerate(value.get("messages") if isinstance(value.get("messages"), list) else []):
        item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
        if not item.get("id"):
            item["id"] = f"legacy-{chat_id}-{index}"
        messages.append(item)
    deleted_at = value.get("deleted_at")
    return {
        "id": chat_id,
        "user_id": int(account_id),
        "title": str(value.get("title") or "New Chat").strip()[:500] or "New Chat",
        "messages": messages,
        "created_at": _iso_timestamp(value.get("created_at")),
        "updated_at": _iso_timestamp(value.get("updated_at")),
        "revision": max(0, int(value.get("revision", 0) or 0)),
        "pinned": bool(value.get("pinned", False)),
        "archived": bool(value.get("archived", False)),
        "deleted": bool(value.get("deleted", bool(deleted_at))),
        "deleted_at": _iso_timestamp(deleted_at) if deleted_at else None,
    }


def _stamp_key(value):
    parsed = _iso_timestamp(value)
    return parsed, int(value.get("revision", 0) or 0)


def _chat_folder(user_id, create=False):
    return _account_folder(user_id, create=create)


def _chat_name(conversation_id):
    return f"chat-{_chat_key(conversation_id)}.json"


def _read_conversation(user_id, conversation_id):
    account_id = _account_key(user_id)
    folder_id = _chat_folder(account_id)
    if not folder_id:
        return None
    value = _read_json_file(folder_id, _chat_name(conversation_id))
    return _normalize_conversation(value, account_id, conversation_id) if value else None


def _write_conversation(user_id, conversation):
    account_id = _account_key(user_id)
    normalized = _normalize_conversation(conversation, account_id, conversation.get("id"))
    folder_id = _chat_folder(account_id, create=True)
    _write_json_file(folder_id, _chat_name(normalized["id"]), normalized)
    return normalized


def _all_conversations(user_id):
    folder_id = _chat_folder(user_id)
    if not folder_id:
        return []
    result = []
    for meta in _list_children(folder_id):
        match = _CHAT_NAME_RE.fullmatch(meta.get("name", ""))
        if not match:
            continue
        value = _read_json_file(folder_id, meta["name"])
        if isinstance(value, dict):
            result.append(_normalize_conversation(value, user_id, match.group(1)))
    return result


def _tombstone_name():
    return "_chat-tombstones.json"


def get_tombstones(user_id):
    folder_id = _chat_folder(user_id)
    if not folder_id:
        return {}
    state = _read_json_file(folder_id, _tombstone_name()) or {}
    deleted = state.get("deleted", {})
    return deleted if isinstance(deleted, dict) else {}


def apply_tombstone(user_id, conversation_id, deleted_at=None):
    folder_id = _chat_folder(user_id, create=True)
    key = _chat_key(conversation_id)
    state = _read_json_file(folder_id, _tombstone_name()) or {"deleted": {}}
    deleted = state.get("deleted") if isinstance(state.get("deleted"), dict) else {}
    deleted[key] = _iso_timestamp(deleted_at)
    state["deleted"] = deleted
    _write_json_file(folder_id, _tombstone_name(), state)
    _delete_child(folder_id, _chat_name(key))


def clear_tombstones(user_id, conversation_ids=None):
    folder_id = _chat_folder(user_id)
    if not folder_id:
        return
    state = _read_json_file(folder_id, _tombstone_name()) or {"deleted": {}}
    deleted = state.get("deleted") if isinstance(state.get("deleted"), dict) else {}
    if conversation_ids is None:
        deleted = {}
    else:
        for conversation_id in conversation_ids:
            deleted.pop(_chat_key(conversation_id), None)
    state["deleted"] = deleted
    _write_json_file(folder_id, _tombstone_name(), state)


# ---- Account records -----------------------------------------------------

def get_account_by_email(email):
    user_id = user_id_for_email(email)
    return get_account_by_id(user_id)


def get_account_by_id(user_id):
    folder_id = _account_folder(user_id)
    if not folder_id:
        return None
    if _read_json_file(folder_id, _DELETED_ACCOUNT_FILE):
        return None
    account = _read_json_file(folder_id, "account.json")
    if not isinstance(account, dict):
        return None
    account["id"] = int(_account_key(user_id))
    return account


def create_account(username, email, password_hash):
    normalized_email = str(email or "").strip().casefold()
    user_id = user_id_for_email(normalized_email)
    with _lock_for(user_id):
        existing = get_account_by_id(user_id)
        if existing:
            raise sqlite3.IntegrityError("Account email already exists.")
        folder_id = _account_folder(user_id, create=True)
        _delete_child(folder_id, _DELETED_ACCOUNT_FILE)
        now = _iso_timestamp()
        account = {
            "id": user_id,
            "username": str(username or "").strip()[:200],
            "email": normalized_email,
            "password_hash": str(password_hash or ""),
            "created_at": now,
            "updated_at": now,
            "settings": {},
            "settings_updated_at": now,
        }
        _write_json_file(folder_id, "account.json", account)
        return account


def list_accounts():
    accounts_id = _accounts_folder()
    if not accounts_id:
        return []
    result = []
    for meta in _list_children(accounts_id, mime_type=_FOLDER_MIME):
        if not re.fullmatch(r"account-[1-9][0-9]*", meta.get("name", "")):
            continue
        account_id = meta["name"].split("-", 1)[1]
        if _read_json_file(meta["id"], _DELETED_ACCOUNT_FILE):
            continue
        account = _read_json_file(meta["id"], "account.json")
        if isinstance(account, dict) and account.get("email"):
            account["id"] = int(account_id)
            result.append(account)
    return result


def list_deleted_accounts():
    accounts_id = _accounts_folder()
    if not accounts_id:
        return []
    result = []
    for meta in _list_children(accounts_id, mime_type=_FOLDER_MIME):
        match = re.fullmatch(r"account-([1-9][0-9]*)", meta.get("name", ""))
        if not match:
            continue
        marker = _read_json_file(meta["id"], _DELETED_ACCOUNT_FILE)
        if isinstance(marker, dict):
            result.append({"id": int(match.group(1)), "deleted_at": marker.get("deleted_at")})
    return result


def upsert_account_from_local(account):
    """Create an account mirror from the laptop without replacing existing auth."""
    user_id = user_id_for_email(account.get("email"))
    with _lock_for(user_id):
        current = get_account_by_id(user_id)
        folder_id = _account_folder(user_id, create=True)
        _delete_child(folder_id, _DELETED_ACCOUNT_FILE)
        if current:
            # Local user profile is authoritative for password/account recovery;
            # preserve Drive settings that may have been changed on another device.
            current["username"] = str(account.get("username") or current.get("username") or "")[:200]
            current["password_hash"] = str(account.get("password_hash") or current.get("password_hash") or "")
            current["updated_at"] = _iso_timestamp()
            value = current
        else:
            settings = account.get("settings") if isinstance(account.get("settings"), dict) else {}
            value = {
                "id": user_id,
                "username": str(account.get("username") or "")[:200],
                "email": str(account.get("email") or "").strip().casefold(),
                "password_hash": str(account.get("password_hash") or ""),
                "created_at": _iso_timestamp(account.get("created_at")),
                "updated_at": _iso_timestamp(),
                "settings": settings,
                "settings_updated_at": _iso_timestamp(account.get("settings_updated_at")) if account.get("settings_updated_at") else _iso_timestamp(),
            }
        _write_json_file(folder_id, "account.json", value)
        return value


def update_account_settings(user_id, settings):
    account = get_account_by_id(user_id)
    if not account:
        return False
    account["settings"] = settings if isinstance(settings, dict) else {}
    now = _iso_timestamp()
    account["updated_at"] = now
    account["settings_updated_at"] = now
    folder_id = _account_folder(user_id, create=True)
    _write_json_file(folder_id, "account.json", account)
    return True


def update_account_profile(user_id, username):
    account = get_account_by_id(user_id)
    if not account:
        return False
    account["username"] = str(username or "").strip()[:200]
    account["updated_at"] = _iso_timestamp()
    _write_json_file(_account_folder(user_id, create=True), "account.json", account)
    return True


def delete_account(user_id):
    folder_id = _account_folder(user_id)
    if not folder_id:
        return False
    # Delete only this account's contents, never files elsewhere in the folder.
    for meta in _list_children(folder_id):
        if meta.get("mimeType") == _FOLDER_MIME:
            for child in _list_children(meta["id"]):
                _api_call(_service().files().delete(fileId=child["id"], supportsAllDrives=True))
        _api_call(_service().files().delete(fileId=meta["id"], supportsAllDrives=True))
    _write_json_file(folder_id, _DELETED_ACCOUNT_FILE, {"deleted_at": _iso_timestamp()})
    return True


# ---- Conversation operations (same shape as app.local_chat_files) -------

def create_conversation(user_id, title="New Chat"):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        while True:
            chat_id = secrets.randbelow((1 << 52) - 1) + 1
            if not _read_conversation(account_id, chat_id):
                break
        now = _iso_timestamp()
        conversation = {
            "id": chat_id,
            "user_id": int(account_id),
            "title": str(title or "New Chat").strip()[:500] or "New Chat",
            "messages": [],
            "created_at": now,
            "updated_at": now,
            "revision": 0,
            "pinned": False,
            "archived": False,
            "deleted": False,
            "deleted_at": None,
        }
        _write_conversation(account_id, conversation)
        return chat_id


def import_conversation(user_id, conversation):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation.get("id"))
    with _lock_for(account_id):
        tombstone = get_tombstones(account_id).get(chat_id)
        if tombstone and _iso_timestamp(tombstone) >= _iso_timestamp(conversation.get("updated_at")):
            return int(chat_id)
        existing = _read_conversation(account_id, chat_id)
        incoming = _normalize_conversation(conversation, account_id, chat_id)
        if existing and _stamp_key(existing) >= _stamp_key(incoming):
            return int(chat_id)
        _write_conversation(account_id, incoming)
        return int(chat_id)


def import_local_conversation(user_id, source_id, conversation):
    source_id = str(source_id or "").strip()
    if not source_id.startswith("local-") or len(source_id) > 220:
        raise ValueError("Invalid local conversation ID.")
    account_id = _account_key(user_id)
    folder_id = _chat_folder(account_id, create=True)
    imports = _read_json_file(folder_id, "_local-imports.json") or {}
    imported_id = imports.get(source_id)
    if imported_id and _read_conversation(account_id, imported_id):
        return _read_conversation(account_id, imported_id)
    chat_id = create_conversation(account_id, conversation.get("title") or "New Chat")
    normalized = _normalize_conversation(conversation, account_id, chat_id)
    normalized["id"] = chat_id
    normalized["user_id"] = int(account_id)
    _write_conversation(account_id, normalized)
    imports[source_id] = chat_id
    _write_json_file(folder_id, "_local-imports.json", imports)
    return normalized


def get_all_conversations(user_id):
    result = _all_conversations(user_id)
    result.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return result


def get_conversations(user_id):
    purge_expired_deleted_conversations()
    return [conversation for conversation in get_all_conversations(user_id) if not conversation["deleted"]]


def get_deleted_conversations(user_id):
    purge_expired_deleted_conversations()
    result = [conversation for conversation in get_all_conversations(user_id) if conversation["deleted"]]
    result.sort(key=lambda item: (str(item.get("deleted_at") or ""), int(item["id"])), reverse=True)
    return result


def get_conversation(conversation_id, user_id):
    with _lock_for(_account_key(user_id)):
        return _read_conversation(user_id, conversation_id)


def find_conversation(conversation_id, user_id, include_deleted=True):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or (conversation["deleted"] and not include_deleted):
        return None, None
    owner = "archive_memory" if conversation["archived"] or conversation["deleted"] else "chat"
    return owner, conversation


def _store_updated(account_id, conversation, messages=None, **patch):
    if messages is not None:
        normalized = []
        for index, message in enumerate(messages if isinstance(messages, list) else []):
            item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
            item.setdefault("id", f"legacy-{conversation['id']}-{index}")
            normalized.append(item)
        conversation["messages"] = normalized
    conversation.update(patch)
    conversation["revision"] = int(conversation.get("revision", 0) or 0) + 1
    conversation["updated_at"] = _iso_timestamp()
    return _write_conversation(account_id, conversation)


def update_conversation(conversation_id, user_id, title, messages, expected_revision=None):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        conversation = _read_conversation(account_id, conversation_id)
        if not conversation or conversation["deleted"]:
            return {"ok": False, "found": False, "conflict": False, "conversation": None}
        revision = int(conversation.get("revision", 0) or 0)
        if expected_revision is not None and int(expected_revision) != revision:
            return {"ok": False, "found": True, "conflict": True, "conversation": conversation}
        updated = _store_updated(
            account_id,
            conversation,
            messages=messages,
            title=str(title or "New Chat").strip()[:500] or "New Chat",
        )
        return {"ok": True, "found": True, "conflict": False, "conversation": updated}


def append_conversation_message(conversation_id, user_id, message):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        conversation = _read_conversation(account_id, conversation_id)
        if not conversation or conversation["deleted"]:
            return None
        messages = list(conversation["messages"])
        item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
        item.setdefault("id", f"legacy-{conversation_id}-{len(messages)}")
        if str(item["id"]) in {str(existing.get("id")) for existing in messages if existing.get("id")}:
            return conversation
        messages.append(item)
        return _store_updated(account_id, conversation, messages=messages)


def update_conversation_message(conversation_id, user_id, message_id, patch):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or conversation["deleted"]:
        return None
    for message in conversation["messages"]:
        if str(message.get("id")) == str(message_id):
            for key, value in (patch or {}).items():
                if key in {"text", "content", "pinned", "feedback", "stopped"}:
                    message[key] = value
            return update_conversation(
                conversation_id, user_id, conversation["title"], conversation["messages"],
                expected_revision=conversation["revision"],
            ).get("conversation")
    return None


def delete_conversation_message(conversation_id, user_id, message_id):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or conversation["deleted"]:
        return None
    messages = [item for item in conversation["messages"] if str(item.get("id")) != str(message_id)]
    if len(messages) == len(conversation["messages"]):
        return None
    result = update_conversation(
        conversation_id, user_id, conversation["title"], messages,
        expected_revision=conversation["revision"],
    )
    return result.get("conversation") if result.get("ok") else None


def update_conversation_metadata(conversation_id, user_id, pinned=None, archived=None, deleted=None):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        conversation = _read_conversation(account_id, conversation_id)
        if not conversation:
            return None
        next_deleted = conversation["deleted"] if deleted is None else bool(deleted)
        next_archived = conversation["archived"] if archived is None else bool(archived)
        next_pinned = conversation["pinned"] if pinned is None else bool(pinned)
        if next_deleted:
            next_archived = False
            next_pinned = False
            deleted_at = conversation.get("deleted_at") or _iso_timestamp()
        else:
            deleted_at = None
        return _store_updated(
            account_id, conversation, pinned=next_pinned, archived=next_archived,
            deleted=next_deleted, deleted_at=deleted_at,
        )


def delete_conversation(conversation_id, user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        existed = _read_conversation(account_id, conversation_id) is not None
        if existed:
            apply_tombstone(account_id, conversation_id)
        return existed


def apply_permanent_tombstone(user_id, conversation_id, deleted_at=None):
    apply_tombstone(user_id, conversation_id, deleted_at)


def delete_all_conversations(user_id):
    account_id = _account_key(user_id)
    for conversation in _all_conversations(account_id):
        apply_tombstone(account_id, conversation["id"])
    return True


def delete_account_chats(user_id):
    folder_id = _account_folder(user_id)
    if not folder_id:
        return
    for conversation in _all_conversations(user_id):
        apply_tombstone(user_id, conversation["id"])


def purge_expired_deleted_conversations(now=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=15)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff = cutoff.astimezone(timezone.utc)
    removed = 0
    for account in list_accounts():
        for conversation in _all_conversations(account["id"]):
            if not conversation.get("deleted_at"):
                continue
            try:
                deleted_at = datetime.fromisoformat(str(conversation["deleted_at"]).replace("Z", "+00:00"))
                if deleted_at.tzinfo is None:
                    deleted_at = deleted_at.replace(tzinfo=timezone.utc)
                if deleted_at.astimezone(timezone.utc) <= cutoff:
                    apply_tombstone(account["id"], conversation["id"], conversation["deleted_at"])
                    removed += 1
            except (TypeError, ValueError, OSError):
                logger.exception("Could not purge expired Drive chat %s", conversation.get("id"))
    return removed
