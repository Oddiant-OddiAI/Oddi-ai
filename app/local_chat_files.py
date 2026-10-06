"""Account-scoped JSON chat files for a laptop-hosted ODDI instance.

This store is selected only when ODDI_LOCAL_ONLY_STORAGE is enabled. Files are
written below the current Windows user's LocalAppData by default, rather than
inside the source checkout or a cloud-mounted directory.
"""

import json
import logging
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("oddi.persistence")


def _default_root():
    configured = os.getenv("ODDI_CHAT_FILES_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "OddiAI" / "ChatHistory"


ROOT = _default_root()
_LOCKS_GUARD = threading.Lock()
_ACCOUNT_LOCKS = {}
_ACCOUNT_ID_RE = re.compile(r"^[1-9][0-9]*$")
_CHAT_ID_RE = re.compile(r"^[1-9][0-9]*$")


def _account_key(user_id):
    value = str(user_id or "").strip()
    if not _ACCOUNT_ID_RE.fullmatch(value):
        raise ValueError("Chat storage requires a valid account ID.")
    return value


def _chat_key(conversation_id):
    value = str(conversation_id or "").strip()
    if not _CHAT_ID_RE.fullmatch(value):
        raise ValueError("Chat storage requires a valid conversation ID.")
    return value


def _lock_for(account_id):
    with _LOCKS_GUARD:
        return _ACCOUNT_LOCKS.setdefault(account_id, threading.RLock())


def _account_dir(account_id):
    path = ROOT / f"account-{account_id}"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        try:
            path.chmod(0o700)
        except OSError:
            logger.warning("Could not restrict chat folder permissions: %s", path)
    return path


def _conversation_path(account_id, conversation_id):
    return _account_dir(account_id) / f"{_chat_key(conversation_id)}.json"


def _state_path(account_id):
    return _account_dir(account_id) / ".state.json"


def _atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_state(account_id):
    path = _state_path(account_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("Invalid account chat index")
    except FileNotFoundError:
        value = {}
    except (OSError, json.JSONDecodeError, ValueError):
        logger.exception("Could not read local chat index for account %s", account_id)
        value = {}
    imports = value.get("imports")
    try:
        next_id = max(1, int(value.get("next_id", 1) or 1))
    except (TypeError, ValueError, OverflowError):
        next_id = 1
    return {
        "next_id": next_id,
        "imports": imports if isinstance(imports, dict) else {},
        "tombstones": value.get("tombstones", {}) if isinstance(value.get("tombstones"), dict) else {},
    }


def _write_state(account_id, state):
    _atomic_write(_state_path(account_id), state)


def _iso_timestamp(value, fallback=None):
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


def _normalize_messages(messages, conversation_id):
    normalized = []
    for index, message in enumerate(messages if isinstance(messages, list) else []):
        item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
        if not item.get("id"):
            item["id"] = f"legacy-{conversation_id}-{index}"
        normalized.append(item)
    return normalized


def _normalize_conversation(value, account_id, conversation_id=None):
    if not isinstance(value, dict):
        raise ValueError("Conversation data must be an object.")
    chat_id = int(conversation_id if conversation_id is not None else value.get("id"))
    now = _iso_timestamp(None)
    created_at = _iso_timestamp(value.get("created_at"), fallback=datetime.now(timezone.utc))
    updated_at = _iso_timestamp(value.get("updated_at"), fallback=datetime.now(timezone.utc))
    deleted_at = value.get("deleted_at")
    return {
        "id": chat_id,
        "user_id": int(account_id),
        "title": str(value.get("title") or "New Chat").strip()[:500] or "New Chat",
        "messages": _normalize_messages(value.get("messages"), chat_id),
        "created_at": created_at or now,
        "updated_at": updated_at or now,
        "revision": max(0, int(value.get("revision", 0) or 0)),
        "pinned": bool(value.get("pinned", False)),
        "archived": bool(value.get("archived", False)),
        "deleted": bool(value.get("deleted", bool(deleted_at))),
        "deleted_at": _iso_timestamp(deleted_at) if deleted_at else None,
    }


def _merge_retried_local_import(existing, incoming, account_id, conversation_id):
    """Keep a retried browser import from returning an older partial chat."""
    current = _normalize_conversation(existing, account_id, conversation_id)
    candidate = _normalize_conversation(incoming, account_id, conversation_id)
    candidate_is_newer = (
        str(candidate.get("updated_at") or ""), int(candidate.get("revision", 0))
    ) >= (
        str(current.get("updated_at") or ""), int(current.get("revision", 0))
    )
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
    return _normalize_conversation(merged, account_id, conversation_id)


def _read_conversation_locked(account_id, conversation_id):
    path = _conversation_path(account_id, conversation_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return _normalize_conversation(value, account_id, conversation_id)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        logger.exception("Could not read chat file for account %s conversation %s", account_id, conversation_id)
        raise


def _write_conversation_locked(account_id, conversation):
    normalized = _normalize_conversation(conversation, account_id, conversation.get("id"))
    _atomic_write(_conversation_path(account_id, normalized["id"]), normalized)
    state = _read_state(account_id)
    state["next_id"] = max(state["next_id"], int(normalized["id"]) + 1)
    _write_state(account_id, state)
    return normalized


def _all_conversations_locked(account_id):
    directory = _account_dir(account_id)
    result = []
    for path in directory.glob("*.json"):
        if not _CHAT_ID_RE.fullmatch(path.stem):
            continue
        try:
            conversation = _read_conversation_locked(account_id, path.stem)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if conversation:
            result.append(conversation)
    return result


def _allocate_id_locked(account_id, state=None):
    state = state or _read_state(account_id)
    try:
        from app.google_drive_storage import is_configured
        drive_sync = is_configured()
    except Exception:
        drive_sync = False
    if drive_sync:
        # The laptop and Drive can create IDs independently while disconnected.
        # Safe JavaScript integers keep those new IDs numeric and collision-safe.
        chat_id = secrets.randbelow((1 << 52) - 1) + 1
        while str(chat_id) in state["tombstones"] or _conversation_path(account_id, chat_id).exists():
            chat_id = secrets.randbelow((1 << 52) - 1) + 1
    else:
        directory = _account_dir(account_id)
        largest = max(
            (int(path.stem) for path in directory.glob("*.json") if _CHAT_ID_RE.fullmatch(path.stem)),
            default=0,
        )
        chat_id = max(state["next_id"], largest + 1)
    state["next_id"] = chat_id + 1
    return chat_id, state


def create_conversation(user_id, title="New Chat"):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        state = _read_state(account_id)
        chat_id, state = _allocate_id_locked(account_id, state)
        now = _iso_timestamp(None)
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
        _atomic_write(_conversation_path(account_id, chat_id), conversation)
        _write_state(account_id, state)
        return chat_id


def import_conversation(user_id, conversation):
    account_id = _account_key(user_id)
    if not isinstance(conversation, dict):
        raise ValueError("Conversation data must be an object.")
    with _lock_for(account_id):
        state = _read_state(account_id)
        old_id = conversation.get("id")
        try:
            chat_id = int(old_id)
            _chat_key(chat_id)
        except (TypeError, ValueError):
            chat_id, state = _allocate_id_locked(account_id, state)
        existing = _read_conversation_locked(account_id, chat_id)
        if str(chat_id) in state["tombstones"]:
            return int(chat_id)
        if existing and (
            int(existing.get("revision", 0)) > int(conversation.get("revision", 0) or 0)
            or (
                int(existing.get("revision", 0)) == int(conversation.get("revision", 0) or 0)
                and str(existing.get("updated_at") or "") >= str(conversation.get("updated_at") or "")
            )
        ):
            return existing["id"]
        migrated = _normalize_conversation(conversation, account_id, chat_id)
        _atomic_write(_conversation_path(account_id, chat_id), migrated)
        state["next_id"] = max(state["next_id"], chat_id + 1)
        _write_state(account_id, state)
        return chat_id


def import_local_conversation(user_id, source_id, conversation):
    account_id = _account_key(user_id)
    source_id = str(source_id or "").strip()
    if not source_id.startswith("local-") or len(source_id) > 220:
        raise ValueError("Invalid local conversation ID.")
    if not isinstance(conversation, dict):
        raise ValueError("Conversation data must be an object.")
    with _lock_for(account_id):
        state = _read_state(account_id)
        imported_id = state["imports"].get(source_id)
        if imported_id:
            existing = _read_conversation_locked(account_id, imported_id)
            if existing:
                migrated = _merge_retried_local_import(existing, conversation, account_id, imported_id)
                if migrated != existing:
                    _atomic_write(_conversation_path(account_id, imported_id), migrated)
                return migrated
        chat_id, state = _allocate_id_locked(account_id, state)
        migrated = _normalize_conversation(conversation, account_id, chat_id)
        _atomic_write(_conversation_path(account_id, chat_id), migrated)
        state["imports"][source_id] = chat_id
        _write_state(account_id, state)
        return migrated


def get_conversations(user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        result = [
            chat for chat in _all_conversations_locked(account_id)
            if not chat["deleted"]
        ]
    result.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return result


def get_deleted_conversations(user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        result = [chat for chat in _all_conversations_locked(account_id) if chat["deleted"]]
    result.sort(key=lambda item: (str(item.get("deleted_at") or ""), int(item["id"])), reverse=True)
    return result


def get_conversation(conversation_id, user_id):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        return _read_conversation_locked(account_id, chat_id)


def find_conversation(conversation_id, user_id, include_deleted=True):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or (conversation["deleted"] and not include_deleted):
        return None, None
    owner = "archive_memory" if conversation["archived"] or conversation["deleted"] else "chat"
    return owner, conversation


def _store_updated_locked(account_id, conversation, messages=None, **patch):
    if messages is not None:
        conversation["messages"] = _normalize_messages(messages, conversation["id"])
    conversation.update(patch)
    conversation["revision"] = int(conversation.get("revision", 0) or 0) + 1
    conversation["updated_at"] = _iso_timestamp(None)
    return _write_conversation_locked(account_id, conversation)


def update_conversation(conversation_id, user_id, title, messages, expected_revision=None):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        conversation = _read_conversation_locked(account_id, chat_id)
        if not conversation or conversation["deleted"]:
            return {"ok": False, "found": False, "conflict": False, "conversation": None}
        revision = int(conversation.get("revision", 0) or 0)
        if expected_revision is not None and int(expected_revision) != revision:
            return {"ok": False, "found": True, "conflict": True, "conversation": conversation}
        updated = _store_updated_locked(
            account_id,
            conversation,
            messages=messages,
            title=str(title or "New Chat").strip()[:500] or "New Chat",
        )
        return {"ok": True, "found": True, "conflict": False, "conversation": updated}


def append_conversation_message(conversation_id, user_id, message):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        conversation = _read_conversation_locked(account_id, chat_id)
        if not conversation or conversation["deleted"]:
            return None
        messages = list(conversation["messages"])
        item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
        if not item.get("id"):
            item["id"] = f"legacy-{chat_id}-{len(messages)}"
        if str(item["id"]) in {str(existing.get("id")) for existing in messages if existing.get("id")}:
            return conversation
        messages.append(item)
        return _store_updated_locked(account_id, conversation, messages=messages)


def update_conversation_message(conversation_id, user_id, message_id, patch):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        conversation = _read_conversation_locked(account_id, chat_id)
        if not conversation or conversation["deleted"]:
            return None
        messages = list(conversation["messages"])
        found = False
        for message in messages:
            if str(message.get("id")) != str(message_id):
                continue
            for key, value in (patch or {}).items():
                if key in {"text", "content", "pinned", "feedback", "stopped", "resume_draft"}:
                    message[key] = value
            found = True
            break
        return _store_updated_locked(account_id, conversation, messages=messages) if found else None


def delete_conversation_message(conversation_id, user_id, message_id):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        conversation = _read_conversation_locked(account_id, chat_id)
        if not conversation or conversation["deleted"]:
            return None
        original = list(conversation["messages"])
        messages = [item for item in original if str(item.get("id")) != str(message_id)]
        if len(messages) == len(original):
            return None
        return _store_updated_locked(account_id, conversation, messages=messages)


def update_conversation_metadata(conversation_id, user_id, pinned=None, archived=None, deleted=None, title=None):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        conversation = _read_conversation_locked(account_id, chat_id)
        if not conversation:
            return None
        next_deleted = conversation["deleted"] if deleted is None else bool(deleted)
        next_archived = conversation["archived"] if archived is None else bool(archived)
        next_pinned = conversation["pinned"] if pinned is None else bool(pinned)
        next_title = conversation.get("title") or "New Chat"
        if title is not None:
            next_title = str(title).strip()[:500] or "New Chat"
        if next_deleted:
            next_archived = False
            next_pinned = False
            deleted_at = conversation.get("deleted_at") or _iso_timestamp(None)
        else:
            deleted_at = None
        return _store_updated_locked(
            account_id,
            conversation,
            pinned=next_pinned,
            archived=next_archived,
            deleted=next_deleted,
            deleted_at=deleted_at,
            title=next_title,
        )


def delete_conversation(conversation_id, user_id):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        path = _conversation_path(account_id, chat_id)
        try:
            path.unlink()
            state = _read_state(account_id)
            state["tombstones"][chat_id] = _iso_timestamp(None)
            _write_state(account_id, state)
            return True
        except FileNotFoundError:
            return False


def delete_all_conversations(user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        directory = _account_dir(account_id)
        state = _read_state(account_id)
        for path in directory.glob("*.json"):
            if _CHAT_ID_RE.fullmatch(path.stem):
                path.unlink(missing_ok=True)
                state["tombstones"][path.stem] = _iso_timestamp(None)
        state["imports"] = {}
        _write_state(account_id, state)


def get_all_conversations(user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        return _all_conversations_locked(account_id)


def get_tombstones(user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        return dict(_read_state(account_id)["tombstones"])


def apply_permanent_tombstone(user_id, conversation_id, deleted_at=None):
    account_id = _account_key(user_id)
    chat_id = _chat_key(conversation_id)
    with _lock_for(account_id):
        state = _read_state(account_id)
        state["tombstones"][chat_id] = _iso_timestamp(deleted_at)
        _write_state(account_id, state)
        _conversation_path(account_id, chat_id).unlink(missing_ok=True)


def clear_tombstones(user_id, conversation_ids=None):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        state = _read_state(account_id)
        if conversation_ids is None:
            state["tombstones"] = {}
        else:
            for conversation_id in conversation_ids:
                state["tombstones"].pop(_chat_key(conversation_id), None)
        _write_state(account_id, state)


def delete_account_chats(user_id):
    account_id = _account_key(user_id)
    with _lock_for(account_id):
        directory = _account_dir(account_id)
        for path in directory.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
        try:
            directory.rmdir()
        except OSError:
            logger.warning("Account chat folder still contains files after deletion: %s", account_id)


def purge_expired_deleted_conversations(now=None, user_id=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=7)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff = cutoff.astimezone(timezone.utc)
    if not ROOT.exists():
        return 0
    removed = 0
    if user_id is None:
        directories = ROOT.glob("account-*")
    else:
        directories = [ROOT / f"account-{_account_key(user_id)}"]
    for directory in directories:
        match = re.fullmatch(r"account-([1-9][0-9]*)", directory.name)
        if not match or not directory.is_dir():
            continue
        account_id = match.group(1)
        with _lock_for(account_id):
            for path in directory.glob("*.json"):
                if not _CHAT_ID_RE.fullmatch(path.stem):
                    continue
                conversation = _read_conversation_locked(account_id, path.stem)
                if not conversation or not conversation["deleted_at"]:
                    continue
                try:
                    deleted_at = datetime.fromisoformat(str(conversation["deleted_at"]).replace("Z", "+00:00"))
                    if deleted_at.tzinfo is None:
                        deleted_at = deleted_at.replace(tzinfo=timezone.utc)
                    if deleted_at.astimezone(timezone.utc) <= cutoff:
                        path.unlink(missing_ok=True)
                        state = _read_state(account_id)
                        state["tombstones"][path.stem] = _iso_timestamp(deleted_at)
                        _write_state(account_id, state)
                        removed += 1
                except (TypeError, ValueError, OSError):
                    logger.exception("Could not purge expired chat file %s", path.name)
    return removed
