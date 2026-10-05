"""Account-scoped chat and account storage in the owner's personal Google Drive."""

import hashlib
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("oddi.drive_storage")

_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_CONFIG_KEYS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
    "GOOGLE_DRIVE_FOLDER_ID",
)
_CHAT_NAME_RE = re.compile(r"^chat-([1-9][0-9]*)\.json$")
_DELETED_ACCOUNT_FILE = "_deleted-account.json"
_LOCK_GUARD = threading.Lock()
_ACCOUNT_LOCKS = {}
_SERVICE_LOCAL = threading.local()
_ROOT_VALIDATION_LOCK = threading.Lock()
_ROOT_VALIDATED = False
_ROOT_DRIVE_ID = None
_FOLDER_CACHE_LOCK = threading.Lock()
_FOLDER_CACHE = {}
_ACCOUNT_CACHE_LOCK = threading.Lock()
_ACCOUNT_CACHE = {}


def _bounded_env_int(name, default, minimum, maximum):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


# httplib2's default socket timeout is unlimited. These settings are bounded
# so a stalled Drive connection cannot hold a Render request forever, while
# remaining configurable for deployments with slower outbound connections.
_DRIVE_HTTP_TIMEOUT_SECONDS = _bounded_env_int(
    "ODDI_DRIVE_HTTP_TIMEOUT_SECONDS", 45, 45, 120
)
_DRIVE_API_RETRIES = _bounded_env_int("ODDI_DRIVE_API_RETRIES", 3, 0, 5)
_DRIVE_WRITE_RETRIES = 1
_DRIVE_RESUMABLE_UPLOAD_THRESHOLD = 4 * 1024 * 1024
_DRIVE_READ_WORKERS = _bounded_env_int("ODDI_DRIVE_READ_WORKERS", 8, 2, 16)
_DRIVE_READ_POOL = ThreadPoolExecutor(
    max_workers=_DRIVE_READ_WORKERS,
    thread_name_prefix="oddi-drive-read",
)


class DriveStorageError(RuntimeError):
    """A safe-to-log Drive configuration or API error."""


def _clean_env(name):
    return str(os.getenv(name) or "").strip().strip("\"'")


def is_configured():
    """True once the Google user OAuth credentials and destination folder exist."""
    values = [_clean_env(key) for key in _CONFIG_KEYS]
    if not all(values):
        return False
    lowered = " ".join(values).casefold()
    return not any(marker in lowered for marker in ("your-project", "your_google", "your-private-key", "replace-me"))


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
    service = getattr(_SERVICE_LOCAL, "service", None)
    if service is not None:
        return service
    if not is_configured():
        raise DriveStorageError(
            "Google Drive OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
            "GOOGLE_REFRESH_TOKEN, and GOOGLE_DRIVE_FOLDER_ID."
        )
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import HttpRequest
        from google_auth_httplib2 import AuthorizedHttp
        from google.oauth2.credentials import Credentials
        import httplib2

        credentials = Credentials(
            token=None,
            refresh_token=_clean_env("GOOGLE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=_clean_env("GOOGLE_CLIENT_ID"),
            client_secret=_clean_env("GOOGLE_CLIENT_SECRET"),
            scopes=[_DRIVE_SCOPE],
        )

        def build_request(_default_http, *args, **kwargs):
            # httplib2.Http is not thread-safe. Give every API request a fresh
            # authenticated transport so concurrent Render requests cannot
            # corrupt or race a shared TLS connection. A fresh connection per
            # request also avoids reusing stale keep-alive sockets.
            transport = AuthorizedHttp(
                credentials,
                http=httplib2.Http(timeout=_DRIVE_HTTP_TIMEOUT_SECONDS),
            )
            return HttpRequest(transport, *args, **kwargs)

        service = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
            requestBuilder=build_request,
        )
        _SERVICE_LOCAL.service = service
        return service
    except ImportError as exc:
        raise DriveStorageError(
            "Google Drive packages are missing. Install the Google Drive dependencies from requirements.txt."
        ) from exc
    except DriveStorageError:
        raise
    except Exception as exc:
        # Avoid writing key material or provider internals to the application
        # logs while still leaving enough information to diagnose the class.
        logger.error("Could not initialize the Google Drive client (error_type=%s)", type(exc).__name__)
        raise DriveStorageError(
            "Google Drive OAuth credentials could not be loaded. Check GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN."
        ) from exc


def _api_call(request):
    try:
        # googleapiclient retries SSL, socket timeout, dropped connection, and
        # retryable HTTP failures using exponential backoff.
        return request.execute(num_retries=_DRIVE_API_RETRIES)
    except Exception as exc:
        if type(exc).__name__ == "RefreshError":
            raise DriveStorageError(
                "Google Drive rejected the OAuth refresh token. Reauthorize the Drive account and update GOOGLE_REFRESH_TOKEN."
            ) from exc
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in {401, 403}:
            raise DriveStorageError(
                "Google Drive rejected the OAuth grant or folder access. Ensure GOOGLE_REFRESH_TOKEN was authorized with the full Drive scope and the Google account can access the configured folder."
            ) from exc
        if status == 404:
            raise DriveStorageError(
                "The configured Google Drive folder was not found or the authorized Google account cannot access it."
            ) from exc
        if _is_retryable_drive_error(exc):
            logger.warning(
                "Google Drive request hit a transient transport error (status=%s, error_type=%s)",
                status,
                type(exc).__name__,
            )
            raise DriveStorageError(
                "Google Drive is temporarily unavailable or the connection was interrupted. Please retry."
            ) from exc
        else:
            logger.exception("Google Drive API request failed (status=%s)", status)
        raise DriveStorageError(f"Google Drive request failed (HTTP {status or 'unknown'}).") from exc
    finally:
        _close_request_transport(request)


def _is_retryable_drive_error(error):
    """Recognize transient network failures after googleapiclient exhausted retries."""
    retryable_statuses = {408, 429, 500, 502, 503, 504}
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (TimeoutError, ConnectionError)):
            return True
        if type(current).__name__ in {
            "SSLError", "ServerNotFoundError", "RemoteDisconnected", "IncompleteRead"
        }:
            return True
        status = getattr(getattr(current, "resp", None), "status", None)
        if status in retryable_statuses:
            return True
        current = current.__cause__ or current.__context__
    return False


def _close_request_transport(request):
    """Close the one-request httplib2 connection, including on failures."""
    transport = getattr(request, "http", None)
    underlying = getattr(transport, "http", transport)
    close = getattr(underlying, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            logger.debug("Could not close a completed Google Drive transport", exc_info=True)


def _validate_root():
    global _ROOT_VALIDATED, _ROOT_DRIVE_ID
    if _ROOT_VALIDATED:
        return
    with _ROOT_VALIDATION_LOCK:
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
        _ROOT_DRIVE_ID = meta.get("driveId")
        _ROOT_VALIDATED = True


def _escape_query(value):
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _supports_shared_drive():
    return _ROOT_DRIVE_ID is not None


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
        list_args = {
            "q": query,
            "pageSize": 1000,
            "pageToken": page_token,
            "fields": "nextPageToken,files(id,name,mimeType,parents,driveId,createdTime,modifiedTime,appProperties)",
        }
        if _ROOT_DRIVE_ID:
            list_args.update(
                corpora="drive",
                driveId=_ROOT_DRIVE_ID,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
        else:
            list_args["corpora"] = "user"
        result = _api_call(_service().files().list(**list_args))
        items.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return items


def _find_child(parent_id, name, mime_type=None):
    items = _list_children(parent_id, name=name, mime_type=mime_type)
    return items[0] if items else None


def _create_folder(parent_id, name):
    drive_params = {"supportsAllDrives": True} if _ROOT_DRIVE_ID else {}
    return _api_call(
        _service().files().create(
            body={"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]},
            fields="id,name,mimeType,driveId",
            **drive_params,
        )
    )


def _root_folder_id():
    _validate_root()
    return os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip().strip('"')


def _accounts_folder(create=False):
    root_id = _root_folder_id()
    cache_key = (root_id, "accounts")
    with _FOLDER_CACHE_LOCK:
        cached_id = _FOLDER_CACHE.get(cache_key)
    if cached_id:
        return cached_id
    folder = _find_child(root_id, "accounts", _FOLDER_MIME)
    if not folder and create:
        folder = _create_folder(root_id, "accounts")
    if folder:
        with _FOLDER_CACHE_LOCK:
            _FOLDER_CACHE[cache_key] = folder["id"]
        return folder["id"]
    return None


def _account_folder(user_id, create=False):
    account_id = _account_key(user_id)
    cache_key = (os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip().strip('"'), f"account-{account_id}")
    with _FOLDER_CACHE_LOCK:
        cached_id = _FOLDER_CACHE.get(cache_key)
    if cached_id:
        return cached_id
    accounts_id = _accounts_folder(create=create)
    if not accounts_id:
        return None
    folder = _find_child(accounts_id, f"account-{account_id}", _FOLDER_MIME)
    if not folder and create:
        folder = _create_folder(accounts_id, f"account-{account_id}")
    if folder:
        with _FOLDER_CACHE_LOCK:
            _FOLDER_CACHE[cache_key] = folder["id"]
        return folder["id"]
    return None


def _read_json_file_meta(meta):
    if not meta or not meta.get("id"):
        return None
    request = None
    try:
        from googleapiclient.http import MediaIoBaseDownload

        request = _service().files().get_media(fileId=meta["id"], supportsAllDrives=_supports_shared_drive())
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=_DRIVE_API_RETRIES)
        return json.loads(output.getvalue().decode("utf-8"))
    except DriveStorageError:
        raise
    except Exception as exc:
        logger.exception("Could not read Drive JSON file %s", meta.get("name", "<unknown>"))
        raise DriveStorageError("A stored Google Drive data file could not be read.") from exc
    finally:
        if request is not None:
            _close_request_transport(request)


def _read_json_file(parent_id, name):
    meta = _find_child(parent_id, name)
    return _read_json_file_meta(meta) if meta else None


def _write_json_file(parent_id, name, value, app_properties=None):
    try:
        from googleapiclient.http import MediaIoBaseUpload

        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        properties = {str(key): str(value) for key, value in (app_properties or {}).items()}
        resumable = len(payload) > _DRIVE_RESUMABLE_UPLOAD_THRESHOLD
        for attempt in range(_DRIVE_WRITE_RETRIES + 1):
            meta = None
            try:
                # Small account/settings/chat JSON files do not benefit from a
                # resumable session; multipart upload avoids an extra TLS round
                # trip. Keep resumable transfer for larger chat histories.
                media = MediaIoBaseUpload(
                    io.BytesIO(payload),
                    mimetype="application/json",
                    chunksize=1024 * 1024 if resumable else -1,
                    resumable=resumable,
                )
                meta = _find_child(parent_id, name)
                if meta:
                    update_args = {}
                    if app_properties is not None:
                        update_args["body"] = {"appProperties": properties}
                    request = _service().files().update(
                        fileId=meta["id"],
                        media_body=media,
                        fields="id,name,modifiedTime,appProperties",
                        supportsAllDrives=_supports_shared_drive(),
                        **update_args,
                    )
                else:
                    request = _service().files().create(
                        body={
                            "name": name,
                            "mimeType": "application/json",
                            "parents": [parent_id],
                            **({"appProperties": properties} if app_properties is not None else {}),
                        },
                        media_body=media,
                        fields="id,name,modifiedTime,appProperties",
                        supportsAllDrives=_supports_shared_drive(),
                    )
                return _api_call(request)
            except DriveStorageError as exc:
                # A timed-out update may already have reached Drive. Re-read
                # the child on the next pass and repeat the idempotent update.
                # Avoid retrying creates, whose response may be lost after the
                # new file was committed and could otherwise make duplicates.
                if (
                    meta
                    and attempt < _DRIVE_WRITE_RETRIES
                    and _is_retryable_drive_error(exc)
                ):
                    logger.warning(
                        "Retrying transient Google Drive JSON update for %s (%s)",
                        name,
                        type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__,
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
        raise DriveStorageError("Google Drive could not save the account or chat file.")
    except DriveStorageError:
        raise
    except Exception as exc:
        logger.exception("Could not write Drive JSON file %s", name)
        raise DriveStorageError("Google Drive could not save the account or chat file.") from exc


def _delete_child(parent_id, name):
    meta = _find_child(parent_id, name)
    if not meta:
        return False
    _api_call(_service().files().delete(fileId=meta["id"], supportsAllDrives=_supports_shared_drive()))
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


def _merge_retried_local_import(existing, incoming, account_id, conversation_id):
    """Merge a retry of a browser chat import without dropping newer messages."""
    current = _normalize_conversation(existing, account_id, conversation_id)
    candidate = _normalize_conversation(incoming, account_id, conversation_id)
    candidate_is_newer = _stamp_key(candidate) >= _stamp_key(current)
    messages = [dict(item) for item in current["messages"]]
    positions = {str(item.get("id")): index for index, item in enumerate(messages) if item.get("id")}
    changed = False
    for item in candidate["messages"]:
        message_id = str(item.get("id") or "")
        if not message_id or message_id not in positions:
            messages.append(dict(item))
            if message_id:
                positions[message_id] = len(messages) - 1
            changed = True
        elif candidate_is_newer and messages[positions[message_id]] != item:
            messages[positions[message_id]] = dict(item)
            changed = True

    merged = dict(current)
    if candidate_is_newer:
        if merged["title"] != candidate["title"] or merged["updated_at"] != candidate["updated_at"]:
            changed = True
        merged["title"] = candidate["title"]
        merged["updated_at"] = candidate["updated_at"]
    merged["messages"] = messages
    if changed:
        merged["revision"] = max(current["revision"], candidate["revision"]) + 1
    return _normalize_conversation(merged, account_id, conversation_id), changed


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
    _write_json_file(
        folder_id,
        _chat_name(normalized["id"]),
        normalized,
        app_properties=_conversation_app_properties(normalized),
    )
    return normalized


def _short_drive_property(value, max_bytes=118):
    """Keep Drive appProperties values within their 124-byte limit."""
    encoded = str(value or "").encode("utf-8")[:max_bytes]
    while encoded:
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError:
            encoded = encoded[:-1]
    return ""


def _conversation_app_properties(conversation):
    messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
    preview = ""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        preview = " ".join(str(message.get("text") or message.get("content") or "").split())
        if preview:
            break
    return {
        "t": _short_drive_property(conversation.get("title") or "New Chat"),
        "c": _short_drive_property(conversation.get("created_at")),
        "u": _short_drive_property(conversation.get("updated_at")),
        "r": str(max(0, int(conversation.get("revision", 0) or 0))),
        "n": str(len(messages)),
        "s": _short_drive_property(preview),
        "p": "1" if conversation.get("pinned") else "0",
        "a": "1" if conversation.get("archived") else "0",
        "d": "1" if conversation.get("deleted") else "0",
        "x": _short_drive_property(conversation.get("deleted_at")),
    }


def _conversation_summary_from_meta(meta):
    match = _CHAT_NAME_RE.fullmatch(meta.get("name", ""))
    if not match:
        return None
    props = meta.get("appProperties") or {}
    try:
        message_count = max(0, int(props.get("n", 0) or 0))
        revision = max(0, int(props.get("r", 0) or 0))
    except (TypeError, ValueError):
        message_count, revision = 0, 0
    return {
        "id": int(match.group(1)),
        "title": props.get("t") or f"Chat {match.group(1)}",
        "created_at": props.get("c") or meta.get("createdTime"),
        "updated_at": props.get("u") or meta.get("modifiedTime") or meta.get("createdTime"),
        "revision": revision,
        "message_count": message_count,
        "preview": props.get("s", ""),
        "pinned": props.get("p") == "1",
        "archived": props.get("a") == "1",
        "deleted": props.get("d") == "1",
        "deleted_at": props.get("x") or None,
        "__summary_only": True,
        "__summary_missing": not bool(props.get("t")),
    }


def get_conversation_summaries(user_id):
    """List account chat metadata without downloading chat bodies from Drive."""
    folder_id = _chat_folder(user_id)
    if not folder_id:
        return []
    summaries = [
        summary for meta in _list_children(folder_id)
        if (summary := _conversation_summary_from_meta(meta)) is not None
    ]
    summaries.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return summaries


def backfill_conversation_summaries(user_id, limit=40):
    """Warm compact Drive metadata for old chat files after the list response."""
    folder_id = _chat_folder(user_id)
    if not folder_id:
        return 0
    missing = [
        meta for meta in _list_children(folder_id)
        if _CHAT_NAME_RE.fullmatch(meta.get("name", ""))
        and not (meta.get("appProperties") or {}).get("t")
    ][:max(0, int(limit))]
    if not missing:
        return 0

    def backfill(meta):
        conversation = _read_conversation_meta(user_id, meta)
        if not conversation:
            return False
        fresh = _api_call(_service().files().get(
            fileId=meta["id"], fields="id,modifiedTime", supportsAllDrives=_supports_shared_drive()
        ))
        if fresh.get("modifiedTime") != meta.get("modifiedTime"):
            return False
        _api_call(_service().files().update(
            fileId=meta["id"],
            body={"appProperties": _conversation_app_properties(conversation)},
            fields="id,appProperties",
            supportsAllDrives=_supports_shared_drive(),
        ))
        return True

    return sum(bool(result) for result in _DRIVE_READ_POOL.map(backfill, missing))


def _read_conversation_meta(user_id, meta):
    match = _CHAT_NAME_RE.fullmatch(meta.get("name", ""))
    if not match:
        return None
    # The directory listing already includes each Drive file ID. Read the JSON
    # directly instead of issuing another name lookup per chat.
    value = _read_json_file_meta(meta)
    if isinstance(value, dict):
        return _normalize_conversation(value, user_id, match.group(1))
    return None


def _all_conversations(user_id):
    folder_id = _chat_folder(user_id)
    if not folder_id:
        return []
    chat_files = [
        meta for meta in _list_children(folder_id)
        if _CHAT_NAME_RE.fullmatch(meta.get("name", ""))
    ]
    if not chat_files:
        return []
    # Chat files are independent. Bounded parallel downloads avoid a
    # many-minute serial wait for accounts with a large history.
    return [
        conversation
        for conversation in _DRIVE_READ_POOL.map(
            lambda meta: _read_conversation_meta(user_id, meta), chat_files
        )
        if conversation is not None
    ]


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

def _invalidate_account_cache(user_id):
    with _ACCOUNT_CACHE_LOCK:
        _ACCOUNT_CACHE.pop(_account_key(user_id), None)


def _read_account_meta(folder_id):
    # One directory listing finds both the live account file and the deletion
    # marker. A valid account.json means the marker is absent; account deletion
    # removes account.json before writing its marker.
    children = _list_children(folder_id)
    return next(
        (meta for meta in children if meta.get("name") == "account.json"),
        None,
    )

def get_account_by_email(email):
    user_id = user_id_for_email(email)
    return get_account_by_id(user_id)


def get_account_by_id(user_id):
    account_id = _account_key(user_id)
    now = time.monotonic()
    with _ACCOUNT_CACHE_LOCK:
        cached = _ACCOUNT_CACHE.get(account_id)
        if cached and cached[0] > now:
            return deepcopy(cached[1]) if cached[1] is not None else None

    folder_id = _account_folder(account_id)
    meta = _read_account_meta(folder_id) if folder_id else None
    account = _read_json_file_meta(meta) if meta else None
    if not isinstance(account, dict):
        account = None
    else:
        account["id"] = int(account_id)
    # Avoid rereading the same password hash from Drive if a user signs out
    # and back in shortly afterward. Account mutation routes invalidate this
    # cache immediately; remote changes become visible within five minutes.
    ttl = 300 if account is not None else 3
    with _ACCOUNT_CACHE_LOCK:
        _ACCOUNT_CACHE[account_id] = (now + ttl, deepcopy(account) if account is not None else None)
    return deepcopy(account) if account is not None else None


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
        _invalidate_account_cache(user_id)
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
        account_meta = _read_account_meta(meta["id"])
        account = _read_json_file_meta(account_meta) if account_meta else None
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
        _invalidate_account_cache(user_id)
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
    _invalidate_account_cache(user_id)
    return True


def update_account_profile(user_id, username):
    account = get_account_by_id(user_id)
    if not account:
        return False
    account["username"] = str(username or "").strip()[:200]
    account["updated_at"] = _iso_timestamp()
    _write_json_file(_account_folder(user_id, create=True), "account.json", account)
    _invalidate_account_cache(user_id)
    return True


def delete_account(user_id):
    folder_id = _account_folder(user_id)
    if not folder_id:
        return False
    # Delete only this account's contents, never files elsewhere in the folder.
    for meta in _list_children(folder_id):
        if meta.get("mimeType") == _FOLDER_MIME:
            for child in _list_children(meta["id"]):
                _api_call(_service().files().delete(fileId=child["id"], supportsAllDrives=_supports_shared_drive()))
        _api_call(_service().files().delete(fileId=meta["id"], supportsAllDrives=_supports_shared_drive()))
    _write_json_file(folder_id, _DELETED_ACCOUNT_FILE, {"deleted_at": _iso_timestamp()})
    _invalidate_account_cache(user_id)
    return True


# ---- Conversation operations (same shape as app.local_chat_files) -------

def create_conversation(user_id, title="New Chat"):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        # A 52-bit random ID has a negligible collision chance. Checking Drive
        # before every create adds a network round trip to the send path and
        # can make the request exceed the hosting gateway timeout.
        chat_id = secrets.randbelow((1 << 52) - 1) + 1
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
    existing_value = _read_json_file(folder_id, _chat_name(imported_id)) if imported_id else None
    if imported_id and isinstance(existing_value, dict):
        existing = _normalize_conversation(existing_value, account_id, imported_id)
        merged, changed = _merge_retried_local_import(
            existing, conversation, account_id, imported_id
        )
        if changed:
            _write_json_file(
                folder_id, _chat_name(imported_id), merged,
                app_properties=_conversation_app_properties(merged),
            )
        return merged
    # Import the local conversation with one ID and one chat write. Calling
    # create_conversation() here first wrote an empty file, then immediately
    # read and replaced it, creating avoidable Drive API requests.
    chat_id = secrets.randbelow((1 << 52) - 1) + 1
    normalized = _normalize_conversation(conversation, account_id, chat_id)
    normalized["id"] = chat_id
    normalized["user_id"] = int(account_id)
    _write_json_file(
        folder_id, _chat_name(chat_id), normalized,
        app_properties=_conversation_app_properties(normalized),
    )
    imports[source_id] = chat_id
    _write_json_file(folder_id, "_local-imports.json", imports)
    return normalized


def get_all_conversations(user_id):
    result = _all_conversations(user_id)
    result.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return result


def get_conversations(user_id):
    return [conversation for conversation in get_all_conversations(user_id) if not conversation["deleted"]]


def get_conversation_summaries_for_user(user_id):
    return [summary for summary in get_conversation_summaries(user_id) if not summary["deleted"]]


def get_deleted_conversations(user_id):
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


def purge_expired_deleted_conversations(now=None, user_id=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=7)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff = cutoff.astimezone(timezone.utc)
    removed = 0
    accounts = ([{"id": int(_account_key(user_id))}] if user_id is not None else list_accounts())
    for account in accounts:
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
