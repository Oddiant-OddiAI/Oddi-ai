import io
import asyncio
from contextlib import nullcontext
import hashlib
import json
import logging
import os
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi.encoders import jsonable_encoder
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv, set_key

# Load local configuration before importing app modules. app.database reads
# DATABASE_URL_* at import time, so loading dotenv below those imports left it
# using stale process-environment values (or the local fallback).
load_dotenv()

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth

from werkzeug.security import generate_password_hash, check_password_hash
from app.database import (
    ODDI_LOCAL_ONLY_STORAGE,
    ODDI_BROWSER_LOCAL_CHATS,
    ODDI_CHAT_FILES_STORAGE,
    ODDI_DRIVE_CHAT_STORAGE,
    ODDI_RENDER_LAPTOP_REDIRECT,
    MEMORY_EXTRACTION_BATCH_SIZE,
    create_tables,
    create_user,
    get_user_by_email,
    create_conversation,
    import_local_conversation,
    get_conversations,
    get_conversation_summaries,
    get_conversation,
    update_conversation,
    delete_conversation,
    delete_all_conversations,
    get_deleted_conversations,
    get_deleted_conversation_summaries,
    update_conversation_metadata,
    append_conversation_message,
    update_conversation_message,
    delete_conversation_message,
    get_memory,
    save_memory,
    delete_memory,
    register_files,
    count_files,
    FileLimitExceeded,
    USER_FILE_LIMIT,
    purge_expired_deleted_conversations,
    update_file_record,
    get_files,
    get_file,
    delete_file_record,
    delete_user_record,
    get_user_settings,
    get_user_by_id,
    save_user_settings,
    update_user_profile,
    clear_memory,
    get_vector_store_id,
    enqueue_memory_message,
    get_memory_extraction_status,
    clear_memory_extraction_queue,
    recover_stale_memory_claims,
)
from app.google_drive_storage import (
    DriveStorageError,
    backfill_conversation_summaries,
    user_id_for_email as drive_user_id_for_email,
)

from app.engine import process_message
from app.attachments import MAX_UPLOAD_BYTES
from app.config import client
from app.fast_responses import fast_response
from identity.identity import create_identity
from app.memory_ai import (
    is_safe_memory_message,
    memory_provider_keys_configured,
    memory_user_disabled,
    memory_user_lock,
    memory_user_opted_out,
    set_memory_user_disabled,
    set_memory_user_opt_out,
    normalize_memory_settings,
    process_one_memory_batch,
)
from app.storage import (
    storage_router,
    StorageQuotaExceeded,
    FileNotFound as StorageFileNotFound,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oddi.persistence")

# A browser Retry action resends the same generation ID and attachments. Keep
# a bounded in-memory idempotency cache so those exact files are not stored in
# the user's Library twice when the original request reached storage but its
# response failed on the way back to the browser.
_chat_upload_retry_lock = threading.Lock()
_chat_upload_retry_cache = OrderedDict()
_CHAT_UPLOAD_RETRY_CACHE_LIMIT = 512


def _uploaded_batch_fingerprint(file_payloads):
    digest = hashlib.sha256()
    for uploaded_file, file_bytes in file_payloads:
        for value in (
            uploaded_file.filename or "unnamed-file",
            uploaded_file.mimetype or "application/octet-stream",
            str(len(file_bytes)),
            hashlib.sha256(file_bytes).hexdigest(),
        ):
            digest.update(value.encode("utf-8", errors="replace"))
            digest.update(b"\0")
    return digest.hexdigest()


def _get_chat_upload_retry_fingerprint(user_id, generation_id):
    key = (str(user_id), str(generation_id))
    with _chat_upload_retry_lock:
        fingerprint = _chat_upload_retry_cache.get(key)
        if fingerprint is not None:
            _chat_upload_retry_cache.move_to_end(key)
        return fingerprint


def _remember_chat_upload_retry_fingerprint(user_id, generation_id, fingerprint):
    key = (str(user_id), str(generation_id))
    with _chat_upload_retry_lock:
        _chat_upload_retry_cache[key] = fingerprint
        _chat_upload_retry_cache.move_to_end(key)
        while len(_chat_upload_retry_cache) > _CHAT_UPLOAD_RETRY_CACHE_LIMIT:
            _chat_upload_retry_cache.popitem(last=False)


def _library_filename_key(filename):
    value = str(filename or "unnamed-file").replace("\\", "/").rsplit("/", 1)[-1]
    return value.strip().casefold() or "unnamed-file"


def _unique_library_filename(filename, occupied_names):
    """Keep older same-named Library files by giving each new version a label."""
    filename = str(filename or "unnamed-file")
    if _library_filename_key(filename) not in occupied_names:
        return filename

    stem, extension = os.path.splitext(filename)
    stem = stem or filename
    version = 2
    while True:
        candidate = f"{stem} ({version}){extension}"
        if _library_filename_key(candidate) not in occupied_names:
            return candidate
        version += 1


def _read_library_file_bytes(user_id, record):
    storage_key = record.get("storage_key")
    if storage_key:
        try:
            return storage_router.read_file(user_id, storage_key)
        except Exception:
            pass

    try:
        full_record = get_file(record.get("id"), user_id)
    except Exception:
        return None
    if not full_record:
        return None
    data = full_record.get("file_data")
    if isinstance(data, memoryview):
        data = data.tobytes()
    return data if isinstance(data, bytes) else None


def _library_record_content_details(user_id, record):
    cached_hash = str(record.get("content_hash") or "").strip().lower()
    if len(cached_hash) == 64:
        try:
            int(cached_hash, 16)
        except ValueError:
            cached_hash = ""

    storage_key = record.get("storage_key")
    if storage_key:
        try:
            path = storage_router.get_file_path(user_id, storage_key)
            physical_size = int(path.stat().st_size)
            if cached_hash:
                return cached_hash, physical_size

            digest = hashlib.sha256()
            with open(path, "rb") as stored_file:
                for chunk in iter(lambda: stored_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest(), physical_size
        except Exception:
            # A hash is only meaningful while its backing blob still exists.
            cached_hash = ""

    if cached_hash:
        return cached_hash, 0
    data = _read_library_file_bytes(user_id, record)
    if data is None:
        return None, 0
    return hashlib.sha256(data).hexdigest(), 0


def _plan_chat_library_uploads(user_id, file_payloads):
    """Plan content deduplication while preserving distinct same-named files."""
    library_records = get_files(user_id, include_content_hash=True)
    library_hashes = set()
    library_file_ids_by_hash = {}
    occupied_names = set()

    for record in library_records:
        digest, _ = _library_record_content_details(user_id, record)
        if digest:
            library_hashes.add(digest)
            library_file_ids_by_hash[digest] = record.get("id")
            if str(record.get("content_hash") or "").lower() != digest:
                try:
                    update_file_record(record.get("id"), user_id, content_hash=digest)
                except Exception:
                    logger.debug("Could not cache content hash for Library file %s", record.get("id"))
        occupied_names.add(_library_filename_key(record.get("filename")))

    planned_uploads = []
    already_exists_count = 0
    already_existing_files = []
    duplicate_uploads = []
    planned_upload_index_by_hash = {}
    seen_hashes = set(library_hashes)
    for upload_index, (uploaded_file, file_bytes) in enumerate(file_payloads):
        original_filename = uploaded_file.filename or "unnamed-file"
        digest = hashlib.sha256(file_bytes).hexdigest()
        if digest in seen_hashes:
            already_exists_count += 1
            if digest in library_hashes:
                existing_file_id = library_file_ids_by_hash.get(digest)
                if existing_file_id is not None:
                    already_existing_files.append({
                        "upload_index": upload_index,
                        "file_id": existing_file_id,
                    })
            else:
                planned_upload_index = planned_upload_index_by_hash.get(digest)
                if planned_upload_index is not None:
                    duplicate_uploads.append({
                        "upload_index": upload_index,
                        "planned_upload_index": planned_upload_index,
                    })
            continue

        seen_hashes.add(digest)
        filename = _unique_library_filename(original_filename, occupied_names)
        occupied_names.add(_library_filename_key(filename))
        planned_upload_index_by_hash[digest] = upload_index
        planned_uploads.append({
            "uploaded_file": uploaded_file,
            "file_bytes": file_bytes,
            "filename": filename,
            "digest": digest,
            "upload_index": upload_index,
        })

    return {
        "uploads": planned_uploads,
        "replace_file_ids": [],
        "replace_storage_keys": [],
        "quota_credit_bytes": 0,
        "already_exists_count": already_exists_count,
        "already_existing_files": already_existing_files,
        "duplicate_uploads": duplicate_uploads,
    }


def _persist_chat_library_uploads(user_id, conversation_id, plan):
    uploads = plan.get("uploads") or []
    if not uploads:
        return []

    stored_keys = []
    records = []
    try:
        for entry in uploads:
            uploaded_file = entry["uploaded_file"]
            file_bytes = entry["file_bytes"]
            stored = storage_router.save_file(
                user_id=user_id,
                data=file_bytes,
                original_filename=entry["filename"],
                quota_credit_bytes=plan.get("quota_credit_bytes", 0),
            )
            storage_key = stored["storage_key"]
            stored_keys.append(storage_key)
            records.append({
                "filename": entry["filename"],
                "mime_type": uploaded_file.mimetype,
                "size_bytes": len(file_bytes),
                "conversation_id": conversation_id,
                "storage_backend": "filesystem",
                "storage_key": storage_key,
                "external_file_id": None,
                "file_data": None,
                "content_hash": entry["digest"],
                "status": "processed",
            })

        new_record_ids = register_files(
            user_id,
            records,
            replace_file_ids=plan.get("replace_file_ids"),
        )
    except Exception:
        rollback_stored_files(user_id, stored_keys)
        raise

    # Distinct uploads are saved as separate records, even when their
    # original filenames match an older Library file.
    return new_record_ids

_chat_generation_lock = threading.Lock()
_active_chat_generations = {}


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="ODDI AI",
    version="1.0.0",
)

_SUMMARY_BACKFILL_LOCK = threading.Lock()
_SUMMARY_BACKFILL_USERS = set()
_WORKSPACE_MUTATION_LOCK = threading.RLock()
_LAPTOP_DRIVE_SYNC_STATE_LOCK = threading.RLock()
app.state.laptop_drive_sync = {
    "state": "idle",
    "last_attempt_at": None,
    "last_success_at": None,
    "last_error_code": None,
    "last_result": {},
}


def _drive_sync_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_laptop_drive_sync():
    """Run one laptop mirror pass and keep a safe, user-visible status snapshot."""
    from app import drive_sync

    attempt_at = _drive_sync_timestamp()
    with _LAPTOP_DRIVE_SYNC_STATE_LOCK:
        previous_status = dict(app.state.laptop_drive_sync)
        status = dict(previous_status)
        status.update({"state": "syncing", "last_attempt_at": attempt_at, "last_error_code": None})
        app.state.laptop_drive_sync = status

    try:
        result = drive_sync.sync_laptop_once()
    except Exception as error:
        message = str(error).casefold()
        auth_rejected = any(token in message for token in ("refresh token", "invalid_grant", "oauth", "authorization rejected"))
        with _LAPTOP_DRIVE_SYNC_STATE_LOCK:
            status = dict(app.state.laptop_drive_sync)
            status.update({
                "state": "authorization_required" if auth_rejected else "retrying",
                "last_error_code": "authorization_required" if auth_rejected else "sync_failed",
                "last_error_at": _drive_sync_timestamp(),
            })
            app.state.laptop_drive_sync = status
        raise

    if result.get("skipped"):
        with _LAPTOP_DRIVE_SYNC_STATE_LOCK:
            current = dict(app.state.laptop_drive_sync)
            if current.get("last_attempt_at") == attempt_at:
                app.state.laptop_drive_sync = previous_status
    else:
        with _LAPTOP_DRIVE_SYNC_STATE_LOCK:
            status = dict(app.state.laptop_drive_sync)
            status.update({
                "state": "synced",
                "last_success_at": _drive_sync_timestamp(),
                "last_error_code": None,
                "last_result": {
                    key: int(value or 0)
                    for key, value in result.items()
                    if key in {"accounts", "chats", "uploaded_chats", "downloaded_chats"}
                },
            })
            status.pop("last_error_at", None)
            app.state.laptop_drive_sync = status
    return result


def _storage_sync_status_payload(user_id):
    from app import google_drive_storage, local_chat_files

    if ODDI_LOCAL_ONLY_STORAGE:
        pending = local_chat_files.get_sync_status(user_id)
        local_chats = len(local_chat_files.get_conversations(user_id))
        configured = google_drive_storage.is_configured()
        with _LAPTOP_DRIVE_SYNC_STATE_LOCK:
            runtime = dict(app.state.laptop_drive_sync)
        if not configured:
            state = "not_configured"
        elif runtime.get("state") in {"authorization_required", "retrying", "syncing"}:
            state = runtime["state"]
        elif pending["pending_chat_count"] or pending["pending_delete_count"]:
            state = "pending"
        elif runtime.get("state") == "idle":
            state = "checking"
        elif pending["initialized"]:
            state = "synced"
        else:
            state = "checking"
        return {
            "storage_mode": "laptop",
            "state": state,
            "local_chat_count": local_chats,
            "pending_known": pending["initialized"],
            "pending_chat_count": pending["pending_chat_count"],
            "pending_delete_count": pending["pending_delete_count"],
            "last_sync_at": pending["last_sync_at"],
            "last_sync_result": pending["last_sync_result"],
            "last_attempt_at": runtime.get("last_attempt_at"),
            "error_code": runtime.get("last_error_code"),
            "drive_configured": configured,
            "can_reconnect": bool(configured and oauth.create_client("google")),
        }

    chat_count = len(get_conversations(user_id))
    if ODDI_DRIVE_CHAT_STORAGE:
        return {
            "storage_mode": "drive",
            "state": "cloud",
            "local_chat_count": chat_count,
            "pending_known": True,
            "pending_chat_count": 0,
            "pending_delete_count": 0,
            "last_sync_at": None,
            "last_sync_result": {},
            "drive_configured": True,
            "can_reconnect": False,
        }
    return {
        "storage_mode": "server",
        "state": "server_storage",
        "local_chat_count": chat_count,
        "pending_known": False,
        "pending_chat_count": 0,
        "pending_delete_count": 0,
        "last_sync_at": None,
        "last_sync_result": {},
        "drive_configured": False,
        "can_reconnect": False,
    }


def _backfill_chat_summaries(user_id):
    try:
        backfill_conversation_summaries(user_id, 40)
    except Exception:
        logger.exception("Could not update legacy chat summary metadata for account %s", user_id)
    finally:
        with _SUMMARY_BACKFILL_LOCK:
            _SUMMARY_BACKFILL_USERS.discard(str(user_id))


def _enqueue_memory_message_if_enabled(user_id, event_id, message):
    """Queue a quick-reply turn after sending only if account consent allows it."""
    if (
        ODDI_BROWSER_LOCAL_CHATS
        or not memory_provider_keys_configured()
        or memory_user_disabled(user_id)
        or memory_user_opted_out(user_id)
    ):
        return
    try:
        settings = normalize_memory_settings(get_user_settings(user_id).get("memory"))
        if settings["enabled"] and settings["auto_extract"]:
            safe_message = message if is_safe_memory_message(message) else ""
            enqueue_memory_message(str(user_id), event_id, safe_message)
    except Exception:
        logger.exception("Could not queue a quick chat turn for memory extraction")
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def identify_unhandled_chat_errors(request: Request, call_next):
    """Give unexpected /chat failures a support reference and a traceback log."""
    if request.url.path != "/chat":
        return await call_next(request)
    request_id = uuid.uuid4().hex[:12]
    request.state.chat_request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled /chat request failure request_id=%s", request_id)
        response = JSONResponse(
            {
                "error": "The chat server could not complete this request. Please retry.",
                "request_id": request_id,
            },
            status_code=500,
        )
    response.headers["X-Oddi-Request-ID"] = request_id
    return response


@app.middleware("http")
async def require_drive_storage_configuration(request: Request, call_next):
    """Do not accept public accounts or chats before persistent Drive is ready."""
    if ODDI_RENDER_LAPTOP_REDIRECT:
        if request.url.path == "/healthz":
            return JSONResponse({"status": "drive-storage-not-configured"})
        return HTMLResponse(
            """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ODDI storage is not configured</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:#090a0a;color:#f4f4f4;font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main{width:min(520px,100%);padding:32px;border:1px solid #292b2b;border-radius:20px;background:#111313;box-shadow:0 24px 80px #0008}h1{margin:0 0 12px;font-size:24px;letter-spacing:-.03em}p{margin:10px 0;color:#b8bcbc}.badge{display:inline-flex;align-items:center;gap:8px;margin-bottom:20px;padding:6px 10px;border:1px solid #6c4d20;border-radius:999px;color:#ffd38a;font-size:12px}.dot{width:8px;height:8px;border-radius:50%;background:#efad4d}small{display:block;margin-top:24px;color:#858a8a}
</style>
<main><div class="badge"><span class="dot"></span> Drive storage is not connected</div>
<h1>ODDI needs its shared chat storage</h1>
<p>The public site uses Google Drive for account records and chat history while the laptop is offline.</p>
<p>No account or chat was saved on Render. Configure Drive access in Render's Environment settings, then redeploy.</p>
<small>Set <code>GOOGLE_CLIENT_ID</code>, <code>GOOGLE_CLIENT_SECRET</code>, <code>GOOGLE_REFRESH_TOKEN</code>, and <code>GOOGLE_DRIVE_FOLDER_ID</code> in the laptop and Render environments.</small>
</main></html>""",
            status_code=503,
            headers={"Cache-Control": "no-store", "Retry-After": "60"},
        )

    if ODDI_BROWSER_LOCAL_CHATS and request.url.path.startswith("/api/conversations"):
        if request.method == "GET":
            return JSONResponse([])
        return JSONResponse(
            {"error": "Chat history is saved in this browser on your device."},
            status_code=410,
        )
    return await call_next(request)


@app.on_event("startup")
async def start_bin_retention_cleanup():
    if ODDI_RENDER_LAPTOP_REDIRECT:
        return

    async def cleanup_expired_bin_chats():
        # Do not compete with the first account/history requests when Render
        # starts. Drive-backed cleanup is user-scoped when the Bin is opened;
        # the all-account sweep only needs to run once per day.
        if ODDI_DRIVE_CHAT_STORAGE:
            await asyncio.sleep(5 * 60)
            cleanup_interval = 24 * 60 * 60
        else:
            cleanup_interval = 60 * 60
        while True:
            try:
                await run_in_threadpool(purge_expired_deleted_conversations)
            except Exception:
                logger.exception("Automatic Bin retention cleanup failed")
            await asyncio.sleep(cleanup_interval)

    app.state.bin_retention_task = asyncio.create_task(cleanup_expired_bin_chats())

    if not ODDI_BROWSER_LOCAL_CHATS and memory_provider_keys_configured():
        await run_in_threadpool(recover_stale_memory_claims)

        async def extract_queued_memories():
            # Let the app finish its first account and conversation requests.
            await asyncio.sleep(20)
            while True:
                try:
                    result = await run_in_threadpool(process_one_memory_batch)
                except Exception:
                    logger.exception("Memory extraction worker hit a storage error; it will retry")
                    result = "retry"
                await asyncio.sleep(3 if result == "processed" else 15)

        app.state.memory_extraction_task = asyncio.create_task(extract_queued_memories())

    if ODDI_LOCAL_ONLY_STORAGE:
        from app import google_drive_storage
        if google_drive_storage.is_configured():
            async def sync_laptop_chats():
                retry_delay = 30
                auth_failure_reported = False
                while True:
                    try:
                        await run_in_threadpool(_run_laptop_drive_sync)
                    except google_drive_storage.DriveStorageError as error:
                        message = str(error).casefold()
                        if "refresh token" in message or "oauth" in message:
                            if not auth_failure_reported:
                                logger.error(
                                    "Google Drive sync is paused because its authorization was rejected. "
                                    "Local chats remain saved on this laptop; reconnect at /auth/google/drive."
                                )
                                auth_failure_reported = True
                            await asyncio.sleep(retry_delay)
                            retry_delay = min(retry_delay * 2, 300)
                            continue
                        logger.exception("Laptop to Google Drive chat sync failed; it will retry")
                    except Exception:
                        logger.exception("Laptop to Google Drive chat sync failed; it will retry")
                    else:
                        auth_failure_reported = False
                        retry_delay = 30
                    await asyncio.sleep(30)

            app.state.drive_sync_task = asyncio.create_task(sync_laptop_chats())


@app.on_event("shutdown")
async def stop_bin_retention_cleanup():
    for task_name in ("bin_retention_task", "drive_sync_task", "memory_extraction_task"):
        task = getattr(app.state, task_name, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

# Flask's signed session cookie is replaced by Starlette's signed session
# middleware. The 30-day lifetime and the important cookie protections are
# preserved from the old Flask server.
_IS_RENDER_SERVER = (
    os.getenv("RENDER", "").strip().lower() in {"1", "true", "yes", "on"}
    or bool(os.getenv("RENDER_SERVICE_ID", "").strip())
)
_IS_PRODUCTION_SERVER = (
    os.getenv("ENVIRONMENT", "").strip().lower() in {"production", "prod"}
    or _IS_RENDER_SERVER
)
_SECURE_SESSION_COOKIES = (
    _IS_PRODUCTION_SERVER
    or os.getenv("ODDI_SECURE_COOKIES", "").strip().lower() in {"1", "true", "yes", "on"}
)
_SESSION_SECRET = (
    os.getenv("FLASK_SECRET_KEY", "").strip()
    or os.getenv("ODDI_SESSION_SECRET", "").strip()
    or os.getenv("SECRET_KEY", "").strip()
)
if _SECURE_SESSION_COOKIES and ODDI_RENDER_LAPTOP_REDIRECT and len(_SESSION_SECRET) < 32:
    # Render never handles an account session in laptop-storage mode.
    _SESSION_SECRET = secrets.token_urlsafe(48)
elif _SECURE_SESSION_COOKIES and ODDI_BROWSER_LOCAL_CHATS and len(_SESSION_SECRET) < 32:
    # Browser-local mode has no persistent account sessions. Use a
    # cryptographically random process key when none is configured; the
    # temporary guest session can safely be recreated.
    _SESSION_SECRET = secrets.token_urlsafe(48)
elif _SECURE_SESSION_COOKIES and len(_SESSION_SECRET) < 32:
    # Render needs a stable signing key across restarts so account cookies keep
    # working. If the operator has not set a dedicated session key, derive one
    # from persistent storage credentials. Never log or expose this material.
    _database_secret_material = "\0".join(
        os.getenv(name, "").strip()
        for name in (
            "DATABASE_URL",
            "DATABASE_URL_CHAT",
            "DATABASE_URL_FILES",
            "DATABASE_URL_ARCHIVE_MEMORY",
        )
        if os.getenv(name, "").strip()
    )
    if _database_secret_material:
        _SESSION_SECRET = hashlib.sha256(
            b"oddi-session-cookie-signing-v1\0"
            + _database_secret_material.encode("utf-8")
        ).hexdigest()
    elif ODDI_DRIVE_CHAT_STORAGE:
        _drive_secret_material = "\0".join(
            os.getenv(name, "").strip()
            # Refresh tokens can be replaced during Drive reauthorization.
            # Keep existing sessions valid across that storage credential
            # rotation; the OAuth client secret remains the stable key source.
            for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
            if os.getenv(name, "").strip()
        )
        _SESSION_SECRET = hashlib.sha256(
            b"oddi-drive-session-cookie-signing-v1\0"
            + _drive_secret_material.encode("utf-8")
        ).hexdigest()
    else:
        if ODDI_CHAT_FILES_STORAGE:
            raise RuntimeError(
                "Set FLASK_SECRET_KEY to a persistent random value of at least 32 characters "
                "before exposing the laptop-hosted ODDI service."
            )
        raise RuntimeError(
            "Set FLASK_SECRET_KEY to a persistent random value of at least 32 characters, "
            "or configure a persistent PostgreSQL DATABASE_URL for production."
        )
if not _SESSION_SECRET:
    _SESSION_SECRET = "local-development-only-secret-change-before-deploy"

app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    max_age=int(timedelta(days=30).total_seconds()),
    same_site="lax",
    https_only=_SECURE_SESSION_COOKIES,
)


@app.exception_handler(DriveStorageError)
async def drive_storage_error_handler(request: Request, exc: DriveStorageError):
    message = str(exc)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"success": False, "error": message}, status_code=503)
    safe_message = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>ODDI storage setup</title>"
        "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#080909;color:#eee;"
        "font:16px/1.6 system-ui;padding:24px}main{max-width:620px;padding:28px;border:1px solid #333;"
        "border-radius:18px;background:#111}h1{font-size:23px}p{color:#bbb}</style>"
        f"<main><h1>ODDI storage needs setup</h1><p>{safe_message}</p></main>",
        status_code=503,
        headers={"Cache-Control": "no-store"},
    )

# Keep the existing static directory available under the same /static URL.
# This is important because the existing HTML references /static/... assets.
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Keep the existing Jinja templates.
templates = Jinja2Templates(directory="templates")


# =========================================================
# TEMPLATE URL COMPATIBILITY
# =========================================================

# Existing ODDI templates were written for Flask's url_for(), including the
# Flask-specific `filename=` argument for static files. This helper keeps the
# existing templates working during the framework migration instead of forcing
# a rewrite of index.html/login.html/signup.html right now.
def template_url_for(request: Request, endpoint: str, **values):
    if endpoint == "static":
        filename = values.pop("filename", values.pop("path", ""))
        return str(request.url_for("static", path=filename))

    return str(request.url_for(endpoint, **values))


def render_template(request: Request, template_name: str, **context):
    context["request"] = request
    context["url_for"] = lambda endpoint, **values: template_url_for(
        request,
        endpoint,
        **values,
    )
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )


# =========================================================
# GOOGLE OAUTH
# =========================================================

oauth = OAuth()

google_client_id = os.getenv("GOOGLE_CLIENT_ID")
google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

if google_client_id and google_client_secret:
    oauth.register(
        name="google",
        server_metadata_url=(
            "https://accounts.google.com/"
            ".well-known/openid-configuration"
        ),
        client_id=google_client_id,
        client_secret=google_client_secret,
        client_kwargs={
            "scope": "openid profile email",
        },
    )
else:
    logger.warning(
        "Google OAuth is not configured. Set "
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."
    )


# Initialize the existing database exactly as before. Bin retention cleanup is
# started in the application startup task below; keeping Drive I/O out of module
# import ensures a temporary credential/API problem cannot make Render crash
# before Uvicorn opens its port.
create_tables()


# =========================================================
# HELPERS
# =========================================================

async def safe_json(request: Request):
    """Flask-compatible equivalent of request.get_json(silent=True)."""
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def sync_laptop_accounts_from_drive():
    """Load Drive-created accounts before local authentication/registration."""
    if not ODDI_LOCAL_ONLY_STORAGE:
        return
    from app import google_drive_storage
    if not google_drive_storage.is_configured():
        return
    try:
        await run_in_threadpool(_run_laptop_drive_sync)
    except Exception:
        logger.exception("Could not refresh laptop accounts from Google Drive")


def set_user_session(request: Request, user, auth_provider=None):
    """Store the same user identity fields used by the old Flask server."""
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["email"] = user["email"]

    if auth_provider:
        request.session["auth_provider"] = auth_provider
    else:
        request.session.pop("auth_provider", None)


def _trusted_drive_session_user(request: Request):
    """Validate the signed account identity without a Drive round trip."""
    if not ODDI_DRIVE_CHAT_STORAGE:
        return None
    email = str(request.session.get("email") or "").strip().casefold()
    provider = str(request.session.get("auth_provider") or "").casefold()
    if not email or email.endswith("@local.oddi.invalid") or provider == "browser-local":
        return None
    try:
        session_id = int(request.session.get("user_id"))
        expected_id = drive_user_id_for_email(email)
    except (TypeError, ValueError, OverflowError):
        return None
    if session_id != expected_id:
        return None
    return {
        "id": session_id,
        "username": str(request.session.get("username") or email.split("@", 1)[0]),
        "email": email,
    }


def _get_session_user(request: Request):
    is_browser_local_identity = (
        request.session.get("auth_provider") == "browser-local"
        or str(request.session.get("email") or "").strip().casefold().endswith("@local.oddi.invalid")
    )
    if is_browser_local_identity and not ODDI_BROWSER_LOCAL_CHATS:
        return None
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    # The session cookie is signed, and the Drive account ID is a stable hash
    # of its email. Rechecking Drive on every page/API request made regular
    # navigation depend on several remote calls and caused repeated sign-ins.
    trusted_drive_user = _trusted_drive_session_user(request)
    if trusted_drive_user:
        return trusted_drive_user

    user = get_user_by_id(user_id)
    session_email = str(request.session.get("email") or "").strip()
    if not session_email:
        return None
    user_email = str(user["email"] if user else "").strip()
    if user and user_email.casefold() == session_email.casefold():
        return user
    if not ODDI_LOCAL_ONLY_STORAGE:
        return None

    # A cloud session's numeric ID can collide with a different local account.
    # Match by email and rebind the cookie to the corresponding local ID.
    user = get_user_by_email(session_email)
    if user:
        set_user_session(
            request,
            user,
            auth_provider=request.session.get("auth_provider"),
        )
    return user


def _request_logging_enabled(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return True
    if ODDI_LOCAL_ONLY_STORAGE:
        user = _get_session_user(request)
        if not user:
            return False
        user_id = user["id"]
    try:
        privacy = get_user_settings(user_id).get("privacy", {})
        return privacy.get("request_logging", True) is not False
    except Exception:
        return True


def require_user_id(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in.")

    trusted_drive_user = _trusted_drive_session_user(request)
    if trusted_drive_user:
        return trusted_drive_user["id"]

    try:
        user = _get_session_user(request)
    except DriveStorageError:
        # The session cookie is signed by this app and the Drive-backed account
        # ID is derived from its email. If Drive is temporarily unreachable,
        # allow an already-authenticated account to keep chatting; its pending
        # conversation remains browser-local until Drive recovers.
        email = str(request.session.get("email") or "").strip().casefold()
        provider = str(request.session.get("auth_provider") or "").casefold()
        try:
            session_id = int(user_id)
            expected_id = drive_user_id_for_email(email)
        except (TypeError, ValueError, OverflowError):
            session_id = None
            expected_id = None
        if (
            ODDI_DRIVE_CHAT_STORAGE
            and provider != "browser-local"
            and not email.endswith("@local.oddi.invalid")
            and session_id is not None
            and session_id == expected_id
        ):
            logger.warning("Google Drive account lookup failed; continuing with the signed-in session.")
            return session_id
        raise
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="This account is no longer available. Sign in again.")
    return user["id"] if ODDI_LOCAL_ONLY_STORAGE else user_id


def is_temporary_browser_account(request: Request):
    """Return true for the throwaway browser identity that cannot sync across devices."""
    provider = str(request.session.get("auth_provider") or "").strip().casefold()
    email = str(request.session.get("email") or "").strip().casefold()
    return provider == "browser-local" or email.endswith("@local.oddi.invalid")


async def require_user_id_async(request: Request):
    """Resolve Drive-backed account records without blocking Uvicorn's loop."""
    return await run_in_threadpool(require_user_id, request)


async def request_logging_enabled_async(request: Request):
    return await run_in_threadpool(_request_logging_enabled, request)


def _uploaded_file_size(uploaded_file):
    """Return upload size without consuming the upload stream."""
    try:
        current = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0, 2)
        size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(current)
        return int(size or 0)
    except Exception:
        return int(getattr(uploaded_file, "content_length", 0) or 0)


class UploadedFileAdapter:
    """Small compatibility wrapper for code that previously received Flask FileStorage.

    FastAPI/Starlette uses UploadFile. ODDI's existing engine can continue to
    receive an object with the old attributes: filename, mimetype and stream.
    """

    def __init__(self, upload):
        self._upload = upload
        self.filename = upload.filename or "unnamed-file"
        self.mimetype = upload.content_type or "application/octet-stream"
        self.content_type = self.mimetype
        self.content_length = getattr(upload, "size", None)
        self.stream = upload.file

    def read(self, size=-1):
        return self.stream.read(size)

    def seek(self, offset, whence=0):
        return self.stream.seek(offset, whence)

    def tell(self):
        return self.stream.tell()

    def seekable(self):
        """Expose the underlying stream's seek support to zipfile/python-docx."""
        return self.stream.seekable()

    def readable(self):
        return self.stream.readable()

    def writable(self):
        return self.stream.writable()

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        return self.stream.close()


def adapt_uploaded_files(uploaded_files):
    return [UploadedFileAdapter(upload) for upload in uploaded_files]


def rollback_stored_files(user_id, storage_keys, file_record_ids=None):
    """Best-effort rollback for a failed upload/chat transaction.

    Physical storage and metadata are kept in sync: if processing fails after
    the files were stored, remove both the filesystem objects and their DB
    records. This prevents orphaned files from consuming the user's quota.
    """
    file_record_ids = list(file_record_ids or [])

    for storage_key in list(storage_keys or []):
        try:
            storage_router.delete_file(user_id, storage_key)
        except StorageFileNotFound:
            pass
        except Exception as error:
            logger.exception(
                "Failed to roll back physical file %s for user %s: %s",
                storage_key,
                user_id,
                error,
            )

    for file_record_id in file_record_ids:
        try:
            delete_file_record(file_record_id, user_id)
        except Exception as error:
            logger.exception(
                "Failed to roll back file metadata %s for user %s: %s",
                file_record_id,
                user_id,
                error,
            )


def response_from_engine(reply):
    """Convert common engine return values into FastAPI responses.

    The old Flask endpoint returned `reply` directly. This compatibility layer
    lets existing engine code return text, dict/list JSON data, or an already
    constructed Starlette/FastAPI response without forcing an engine rewrite.
    """
    if isinstance(reply, (HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse, RedirectResponse)):
        return reply

    if isinstance(reply, (dict, list, tuple, int, float, bool)) or reply is None:
        return JSONResponse(content=reply)

    if isinstance(reply, str):
        return PlainTextResponse(reply)

    # Last-resort compatibility for JSON-serializable objects.
    try:
        return JSONResponse(content=reply)
    except Exception:
        return PlainTextResponse(str(reply))


# =========================================================
# PAGES / BASIC AUTH
# =========================================================

@app.get("/", response_class=HTMLResponse, name="home")
def home(request: Request):
    # Browser-local mode uses a throwaway account solely for request
    # authorization; history remains in that browser.
    if ODDI_BROWSER_LOCAL_CHATS and not _get_session_user(request):
        local_email = f"browser-{uuid.uuid4().hex}@local.oddi.invalid"
        create_user(
            "Local user",
            local_email,
            generate_password_hash(secrets.token_urlsafe(32)),
        )
        local_user = get_user_by_email(local_email)
        if local_user:
            set_user_session(request, local_user, auth_provider="browser-local")

    # ODDI uses real persisted accounts in sync mode. Discard anonymous
    # browser-local cookies before they can be mistaken for a real account.
    if not request.session.get("user_id") or not _get_session_user(request):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    response = render_template(
        request,
        "index.html",
        logged_in=True,
        username=request.session.get("username"),
        user_id=request.session.get("user_id"),
        browser_local_chats=ODDI_BROWSER_LOCAL_CHATS,
        library_sync_enabled=not is_temporary_browser_account(request),
    )

    # Preserve Flask's no-cache behavior for the live conversation-sync page.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/login", response_class=HTMLResponse, name="login_page")
def login_page(request: Request):
    return render_template(request, "login.html")


@app.post("/login", name="login")
async def login(request: Request):
    form = await request.form()

    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))

    user = await run_in_threadpool(get_user_by_email, email)
    if user is None:
        await sync_laptop_accounts_from_drive()
        user = await run_in_threadpool(get_user_by_email, email)

    if not user:
        return PlainTextResponse("Email not found.")

    if check_password_hash(user["password_hash"], password):
        set_user_session(request, user)
        return RedirectResponse(url="/", status_code=303)

    return PlainTextResponse("Incorrect password.")


@app.get("/logout", name="logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/profile", response_class=HTMLResponse, name="profile")
def profile(request: Request):
    if "user_id" not in request.session:
        return PlainTextResponse("Not logged in.")

    return HTMLResponse(
        f"""
        User ID: {request.session['user_id']}<br>
        Username: {request.session['username']}<br>
        Email: {request.session['email']}
        """
    )


@app.get("/signup", response_class=HTMLResponse, name="signup_page")
def signup_page(request: Request):
    return render_template(request, "signup.html")


@app.post("/signup", name="signup")
async def signup(request: Request):
    form = await request.form()

    username = str(form.get("username", "")).strip()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))

    await sync_laptop_accounts_from_drive()

    if get_user_by_email(email):
        return PlainTextResponse("Email already exists.")

    password_hash = generate_password_hash(password)
    create_user(username, email, password_hash)

    user = get_user_by_email(email)
    if user is None:
        return PlainTextResponse("Account was created but could not be loaded.", status_code=500)

    set_user_session(request, user)
    return RedirectResponse(url="/", status_code=303)


# =========================================================
# AUTH API
# =========================================================

@app.post("/api/auth/login", name="api_login")
async def api_login(request: Request):
    data = await safe_json(request)

    email = str(data.get("email", "")).strip()
    password = data.get("password", "")

    if not email or not password:
        return JSONResponse(
            {"success": False, "error": "Email and password are required."},
            status_code=400,
        )

    user = await run_in_threadpool(get_user_by_email, email)
    if user is None:
        await sync_laptop_accounts_from_drive()
        user = await run_in_threadpool(get_user_by_email, email)

    if user is None:
        return JSONResponse(
            {"success": False, "error": "Email not found."},
            status_code=401,
        )

    if not check_password_hash(user["password_hash"], password):
        return JSONResponse(
            {"success": False, "error": "Incorrect password."},
            status_code=401,
        )

    set_user_session(request, user)

    return JSONResponse(
        {
            "success": True,
            "user": {
                "id": user["id"],
                "name": user["username"],
                "email": user["email"],
            },
        }
    )


@app.post("/api/auth/register", name="api_register")
async def api_register(request: Request):
    data = await safe_json(request)

    username = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    password = data.get("password", "")

    await sync_laptop_accounts_from_drive()

    if not username or not email or not password:
        return JSONResponse(
            {
                "success": False,
                "error": "Name, email and password are required.",
            },
            status_code=400,
        )

    existing_user = get_user_by_email(email)

    if existing_user:
        return JSONResponse(
            {
                "success": False,
                "error": "An account with this email already exists.",
            },
            status_code=409,
        )

    password_hash = generate_password_hash(password)
    create_user(username, email, password_hash)

    user = get_user_by_email(email)

    if user is None:
        return JSONResponse(
            {
                "success": False,
                "error": "Account was created but could not be loaded.",
            },
            status_code=500,
        )

    set_user_session(request, user)

    return JSONResponse(
        {
            "success": True,
            "user": {
                "id": user["id"],
                "name": user["username"],
                "email": user["email"],
            },
        }
    )


# =========================================================
# GOOGLE OAUTH
# =========================================================

@app.get("/auth/google", name="google_login")
async def google_login(request: Request):
    if not google_client_id or not google_client_secret:
        logger.error("Google OAuth requested but credentials are missing.")
        return PlainTextResponse(
            "Google sign-in is not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
            status_code=503,
        )

    redirect_uri = str(request.url_for("google_callback"))

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
    )


@app.get("/auth/google/drive", name="google_drive_reauthorize")
async def google_drive_reauthorize(request: Request):
    """Refresh the laptop's Drive grant without exposing its token."""
    if not ODDI_LOCAL_ONLY_STORAGE:
        return PlainTextResponse("Drive reconnection is available from the laptop only.", status_code=404)
    if not _get_session_user(request):
        return RedirectResponse(url="/login", status_code=303)
    if not google_client_id or not google_client_secret:
        return PlainTextResponse("Google sign-in is not configured on this laptop.", status_code=503)

    current_user = _get_session_user(request)
    request.session["drive_reauthorization_pending"] = True
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        scope="openid profile email https://www.googleapis.com/auth/drive",
        access_type="offline",
        prompt="consent",
        login_hint=str(current_user["email"] or ""),
    )


@app.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    drive_reauthorization = bool(request.session.pop("drive_reauthorization_pending", False))
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        logger.warning("Google OAuth failed: %s", error)
        if drive_reauthorization:
            return HTMLResponse(
                "<main><h1>Drive was not reconnected</h1><p>Your chats are still saved on this laptop. "
                "Please retry Google Drive reconnection from this laptop.</p></main>",
                status_code=400,
            )
        return RedirectResponse(url="/login", status_code=303)

    userinfo = token.get("userinfo")

    if not userinfo:
        try:
            userinfo = await oauth.google.userinfo(token=token)
        except Exception as error:
            logger.exception(
                "Unable to retrieve Google user information: %s",
                error,
            )
            return PlainTextResponse(
                "Google account information could not be retrieved.",
                status_code=502,
            )

    if drive_reauthorization:
        if not ODDI_LOCAL_ONLY_STORAGE or not _get_session_user(request):
            return PlainTextResponse("Drive reconnection must start from a signed-in laptop session.", status_code=403)
        refresh_token = str(token.get("refresh_token") or "").strip()
        if not refresh_token:
            return HTMLResponse(
                "<main><h1>Google did not issue a Drive refresh token</h1><p>Your chats are still saved on this laptop. "
                "Retry Drive reconnection and approve offline Drive access.</p></main>",
                status_code=400,
            )
        granted_scopes = set(str(token.get("scope") or "").split())
        drive_scope = "https://www.googleapis.com/auth/drive"
        if granted_scopes and drive_scope not in granted_scopes:
            return HTMLResponse(
                "<main><h1>Drive access was not granted</h1><p>Your chats are still saved on this laptop. "
                "Retry and approve the requested Google Drive access.</p></main>",
                status_code=403,
            )

        from app import google_drive_storage

        try:
            await run_in_threadpool(
                google_drive_storage.validate_access_token,
                token.get("access_token"),
            )
            dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
            saved, _, _ = set_key(
                dotenv_path,
                "GOOGLE_REFRESH_TOKEN",
                refresh_token,
                quote_mode="always",
            )
            if not saved:
                raise OSError("Could not save the refreshed Google Drive credential.")
            os.environ["GOOGLE_REFRESH_TOKEN"] = refresh_token
        except Exception as error:
            logger.warning(
                "Could not save the renewed local Google Drive grant (error_type=%s)",
                type(error).__name__,
            )
            message = (
                str(error)
                if isinstance(error, DriveStorageError)
                else "The renewed Google Drive credential could not be saved on this laptop."
            )
            return HTMLResponse(
                f"<main><h1>Drive reconnection could not finish</h1><p>{message}</p>"
                "<p>Your existing laptop chats are untouched.</p></main>",
                status_code=503,
            )

        try:
            from app.drive_sync import sync_laptop_once

            sync_result = await run_in_threadpool(sync_laptop_once)
        except Exception:
            logger.exception("Initial laptop-to-Drive sync failed after Drive reauthorization; retrying in background")
            return HTMLResponse(
                "<main><h1>Drive reconnected on this laptop</h1><p>The credential was saved securely. "
                "Chat sync will retry automatically; your laptop copies remain safe.</p>"
                "<p>To restore the public website, update GOOGLE_REFRESH_TOKEN in the ODDI web service's "
                "Render Environment settings with the renewed value from this laptop's .env, then redeploy.</p></main>",
                status_code=503,
            )

        checked_chats = int(sync_result.get("chats", 0) or 0)
        return HTMLResponse(
            "<main><h1>Drive reconnected on this laptop</h1>"
            f"<p>Initial sync completed; {checked_chats} chat records were checked.</p>"
            "<p>To restore the public website, update GOOGLE_REFRESH_TOKEN in the ODDI web service's "
            "Render Environment settings with the renewed value from this laptop's .env, then redeploy. "
            "The token was saved in this laptop's local .env file and was not shown on this page.</p>"
            "<p><a href='/'>Return to ODDI</a></p></main>"
        )

    email = str(userinfo.get("email") or "").strip().lower()
    name = str(userinfo.get("name") or "").strip()
    email_verified = userinfo.get("email_verified", False)

    if not email:
        return PlainTextResponse("Google did not provide an email address.", status_code=400)

    if email_verified is not True:
        return PlainTextResponse("Google email is not verified.", status_code=403)

    # Preserve the current ODDI behavior: Gmail accounts only.
    if not email.endswith("@gmail.com"):
        return PlainTextResponse(
            "Please use a Gmail account to sign in to ODDI.",
            status_code=403,
        )

    if not name:
        name = email.split("@")[0]

    user = get_user_by_email(email)
    if user is None:
        await sync_laptop_accounts_from_drive()
        user = get_user_by_email(email)

    if user is None:
        temporary_password = secrets.token_urlsafe(32)
        password_hash = generate_password_hash(temporary_password)

        create_user(name, email, password_hash)
        user = get_user_by_email(email)

    if user is None:
        return PlainTextResponse(
            "Google login succeeded, but the ODDI account could not be created.",
            status_code=500,
        )

    set_user_session(request, user, auth_provider="google")

    return RedirectResponse(url="/", status_code=303)


@app.get("/api/auth/me", name="api_auth_me")
def api_auth_me(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        return JSONResponse({"authenticated": False}, status_code=401)

    user = _get_session_user(request)
    if not user:
        request.session.clear()
        return JSONResponse({"authenticated": False}, status_code=401)

    return JSONResponse(
        {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "name": user["username"],
                "email": user["email"],
            },
            "auth_provider": request.session.get("auth_provider", "password"),
        }
    )


@app.get("/api/settings", name="api_get_settings")
def api_get_settings(request: Request):
    user_id = require_user_id(request)
    settings = get_user_settings(user_id)
    return JSONResponse({"settings": settings})


@app.put("/api/settings", name="api_update_settings")
async def api_update_settings(request: Request):
    user_id = require_user_id(request)
    data = await safe_json(request)
    incoming = data.get("settings")
    if not isinstance(incoming, dict):
        return JSONResponse({"error": "Settings must be an object."}, status_code=400)
    memory_update = incoming.get("memory")
    requested_memory = (
        normalize_memory_settings(memory_update)
        if isinstance(memory_update, dict)
        else None
    )
    if requested_memory:
        # Publish the opt-out before waiting for any in-flight extraction to
        # finish, so it cannot start a fallback provider request meanwhile.
        if not requested_memory["enabled"]:
            set_memory_user_disabled(user_id, True)
        if not requested_memory["enabled"] or not requested_memory["auto_extract"]:
            set_memory_user_opt_out(user_id, True)

    def update_settings():
        # Turning extraction off waits for any already-running provider request,
        # saves the opt-out, then drops queued messages before the API returns.
        preference_lock = (
            memory_user_lock(user_id)
            if requested_memory and (not requested_memory["enabled"] or not requested_memory["auto_extract"])
            else nullcontext()
        )
        with preference_lock:
            with _WORKSPACE_MUTATION_LOCK:
                current = get_user_settings(user_id)
                # Only settings used by the UI are accepted. Never store arbitrary payloads.
                if isinstance(current.get("chat_preferences"), dict):
                    current["chat_preferences"].pop("default_provider", None)
                allowed = {"privacy", "chat_preferences", "profile", "memory"}
                for key in allowed:
                    value = incoming.get(key)
                    if isinstance(value, dict):
                        if key == "chat_preferences":
                            value = {name: item for name, item in value.items() if name != "default_provider"}
                        elif key == "memory":
                            value = normalize_memory_settings(value)
                        current[key] = value
                save_user_settings(user_id, current)
                if requested_memory:
                    set_memory_user_disabled(user_id, not requested_memory["enabled"])
                    set_memory_user_opt_out(
                        user_id,
                        not requested_memory["enabled"] or not requested_memory["auto_extract"],
                    )
                    if not requested_memory["enabled"] or not requested_memory["auto_extract"]:
                        clear_memory_extraction_queue(user_id)
                return current

    current = await run_in_threadpool(update_settings)
    return JSONResponse({"success": True, "settings": current})


def _workspace_operation_result(user_id, operation):
    """Apply one idempotent workspace edit to the latest account settings."""
    with _WORKSPACE_MUTATION_LOCK:
        settings = get_user_settings(user_id)
        if not isinstance(settings, dict):
            settings = {}
        workspace = settings.get("workspace")
        if not isinstance(workspace, dict):
            workspace = {"projects": [], "tasks": [], "prompts": [], "hiddenHomeCards": [], "responseStyle": ""}
        workspace = json.loads(json.dumps(workspace, ensure_ascii=False))
        for key in ("projects", "tasks", "prompts", "hiddenHomeCards"):
            if not isinstance(workspace.get(key), list):
                workspace[key] = []

        op_id = str(operation.get("id") or "").strip()
        if not op_id or len(op_id) > 128:
            return None, "Workspace operation ID is invalid.", 400
        applied_ids = settings.get("workspace_operation_ids")
        if not isinstance(applied_ids, list):
            applied_ids = []
        if op_id in applied_ids:
            return {"workspace": workspace, "revision": int(settings.get("workspace_revision") or 0)}, None, 200

        kind = str(operation.get("type") or "")
        item = operation.get("item") if isinstance(operation.get("item"), dict) else {}
        item_id = str(operation.get("item_id") or item.get("id") or "").strip()

        def upsert(collection, value):
            value_id = str(value.get("id") or "").strip()
            if not value_id or len(value_id) > 128:
                raise ValueError("Workspace item ID is invalid.")
            values = workspace[collection]
            for index, existing in enumerate(values):
                if isinstance(existing, dict) and str(existing.get("id")) == value_id:
                    if collection == "projects" and isinstance(existing.get("conversationIds"), list) and not isinstance(value.get("conversationIds"), list):
                        value["conversationIds"] = existing["conversationIds"]
                    values[index] = value
                    break
            else:
                if collection == "tasks":
                    values.insert(0, value)
                else:
                    values.append(value)
            if collection == "tasks":
                del values[300:]
            else:
                del values[:-{"projects": 100, "prompts": 100}[collection]]

        try:
            if kind in {"project.upsert", "task.upsert", "prompt.upsert"}:
                collection = kind.split(".", 1)[0] + "s"
                limits = {"project": ("name", 80), "task": ("text", 240), "prompt": ("name", 60)}
                field, maximum = limits[kind.split(".", 1)[0]]
                value = {"id": str(item.get("id") or ""), field: str(item.get(field) or "").strip()[:maximum]}
                if kind == "project.upsert":
                    value["conversationIds"] = [str(x) for x in item.get("conversationIds", []) if x][:500] if isinstance(item.get("conversationIds", []), list) else []
                elif kind == "task.upsert":
                    value.update({"done": bool(item.get("done")), "chatTitle": str(item.get("chatTitle") or "")[:120]})
                else:
                    value["text"] = str(item.get("text") or "")[:1200]
                if not value.get(field):
                    return None, f"{field.capitalize()} cannot be empty.", 400
                upsert(collection, value)
            elif kind in {"project.delete", "task.delete", "prompt.delete"}:
                collection = kind.split(".", 1)[0] + "s"
                if not item_id:
                    return None, "Workspace item ID is required.", 400
                workspace[collection] = [x for x in workspace[collection] if not isinstance(x, dict) or str(x.get("id")) != item_id]
            elif kind == "project.link":
                chat_id = str(operation.get("conversation_id") or "").strip()
                project = next((x for x in workspace["projects"] if isinstance(x, dict) and str(x.get("id")) == item_id), None)
                if not project or not chat_id:
                    return None, "Project or conversation could not be found.", 404
                linked = project.get("conversationIds") if isinstance(project.get("conversationIds"), list) else []
                project["conversationIds"] = list(dict.fromkeys([*map(str, linked), chat_id]))[-500:]
            elif kind == "project.unlink":
                chat_id = str(operation.get("conversation_id") or "").strip()
                project = next((x for x in workspace["projects"] if isinstance(x, dict) and str(x.get("id")) == item_id), None)
                if not project or not chat_id:
                    return None, "Project or conversation could not be found.", 404
                project["conversationIds"] = [str(x) for x in project.get("conversationIds", []) if str(x) != chat_id]
            elif kind == "home.set_card":
                card_id = str(operation.get("card_id") or "")
                hidden = operation.get("hidden")
                if not card_id.startswith("quick-") or len(card_id) > 80 or not isinstance(hidden, bool):
                    return None, "Home card preferences are invalid.", 400
                cards = list(dict.fromkeys(x for x in workspace["hiddenHomeCards"] if isinstance(x, str)))
                if hidden and card_id not in cards:
                    cards.append(card_id)
                elif not hidden:
                    cards = [x for x in cards if x != card_id]
                workspace["hiddenHomeCards"] = cards[-20:]
            elif kind == "style.set":
                style = str(operation.get("style") or "")
                if style not in {"", "concise", "step_by_step", "table", "detailed"}:
                    return None, "Answer style is invalid.", 400
                workspace["responseStyle"] = style
            else:
                return None, "Workspace operation is not supported.", 400
        except (TypeError, ValueError) as exc:
            return None, str(exc), 400

        try:
            size = len(json.dumps(workspace, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError):
            return None, "Workspace data must be valid JSON.", 400
        if size > 256 * 1024:
            return None, "Workspace data is too large. Remove old projects or prompts and try again.", 413

        revision = int(settings.get("workspace_revision") or 0) + 1
        settings["workspace"] = workspace
        settings["workspace_revision"] = revision
        settings["workspace_operation_ids"] = [*applied_ids, op_id][-1000:]
        save_user_settings(user_id, settings)
        return {"workspace": workspace, "revision": revision}, None, 200


@app.get("/api/workspace", name="api_get_workspace")
def api_get_workspace(request: Request):
    user_id = require_user_id(request)
    settings = get_user_settings(user_id)
    settings = settings if isinstance(settings, dict) else {}
    workspace = settings.get("workspace")
    return JSONResponse({
        "workspace": workspace if isinstance(workspace, dict) else {},
        "revision": int(settings.get("workspace_revision") or 0),
        "account_id": str(user_id),
    })


@app.post("/api/workspace/operations", name="api_apply_workspace_operation")
async def api_apply_workspace_operation(request: Request):
    user_id = await require_user_id_async(request)
    data = await safe_json(request)
    operation = data.get("operation")
    if not isinstance(operation, dict):
        return JSONResponse({"error": "Workspace operation is required."}, status_code=400)
    result, error, status = await run_in_threadpool(_workspace_operation_result, user_id, operation)
    if error:
        return JSONResponse({"error": error}, status_code=status)
    return JSONResponse({"success": True, **result})


@app.put("/api/account/profile", name="api_update_profile")
async def api_update_profile(request: Request):
    user_id = require_user_id(request)
    data = await safe_json(request)
    name = str(data.get("name") or "").strip()
    bio = str(data.get("bio") or "").strip()
    avatar = str(data.get("avatar") or "").strip()
    if not name or len(name) > 80:
        return JSONResponse({"error": "Enter a name up to 80 characters."}, status_code=400)
    if len(bio) > 500:
        return JSONResponse({"error": "Bio must be 500 characters or less."}, status_code=400)
    allowed_avatar_prefixes = (
        "data:image/png;base64,", "data:image/jpeg;base64,",
        "data:image/gif;base64,", "data:image/webp;base64,",
    )
    if avatar and (len(avatar) > 2_800_000 or not avatar.startswith(allowed_avatar_prefixes)):
        return JSONResponse({"error": "Choose an image smaller than 2 MB."}, status_code=400)
    with _WORKSPACE_MUTATION_LOCK:
        update_user_profile(user_id, name)
        request.session["username"] = name
        settings = get_user_settings(user_id)
        profile = settings.get("profile", {})
        profile.update({"bio": bio, "avatar": avatar})
        settings["profile"] = profile
        save_user_settings(user_id, settings)
    return JSONResponse({"success": True, "user": {"name": name, "email": request.session.get("email", "")}, "profile": profile})


@app.get("/api/account/export", name="api_export_account_data")
def api_export_account_data(request: Request):
    user_id = require_user_id(request)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {"id": str(user_id), "name": request.session.get("username"), "email": request.session.get("email")},
        "conversations": get_conversations(user_id),
        "deleted_conversations": get_deleted_conversations(user_id),
        "memories": get_memory(user_id) or {},
        "files": get_files(user_id),
        "settings": get_user_settings(user_id),
    }
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": 'attachment; filename="oddi-data-export.json"'},
    )


@app.delete("/api/account", name="api_delete_account")
async def api_delete_account(request: Request):
    user_id = require_user_id(request)
    email = str(request.session.get("email") or "")
    data = await safe_json(request)
    if not email or str(data.get("email") or "").strip().casefold() != email.strip().casefold():
        return JSONResponse({"error": "Enter the exact email address on your account to confirm deletion."}, status_code=400)

    # Remove the user's remote document index before erasing its identifier.
    vector_store_id = get_vector_store_id(user_id) if not ODDI_LOCAL_ONLY_STORAGE else None
    if vector_store_id:
        try:
            client.vector_stores.delete(vector_store_id)
        except Exception:
            logger.exception("Could not delete account vector store for user %s", user_id)
            return JSONResponse({"error": "Your remote document index could not be deleted; the account was left intact."}, status_code=502)

    for file_record in get_files(user_id):
        if file_record.get("storage_backend") == "filesystem" and file_record.get("storage_key"):
            try:
                storage_router.delete_file(user_id, file_record["storage_key"])
            except Exception:
                logger.exception("Could not delete account file %s", file_record.get("id"))
                return JSONResponse({"error": "An uploaded file could not be deleted; the account was left intact."}, status_code=502)
        delete_file_record(file_record.get("id"), user_id)

    delete_all_conversations(user_id)
    clear_memory(user_id)
    delete_user_record(user_id)
    request.session.clear()
    return JSONResponse({"success": True, "redirect": "/login"})


@app.post("/api/auth/logout", name="api_logout")
def api_logout(request: Request):
    request.session.clear()
    return JSONResponse({"success": True})


# =========================================================
# CONVERSATIONS
# =========================================================

@app.get("/api/conversations", name="api_get_conversations")
def api_get_conversations(request: Request):
    # Looking up a Drive-backed privacy setting for each periodic history
    # refresh adds several extra Drive round trips. Keep those refreshes quiet.
    if not ODDI_DRIVE_CHAT_STORAGE and _request_logging_enabled(request):
        logger.info(
            "HTTP GET /api/conversations pid=%s user=%s",
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    return JSONResponse(content=jsonable_encoder(get_conversations(user_id)))


@app.get("/api/conversations/index", name="api_get_conversation_index")
def api_get_conversation_index(request: Request, background_tasks: BackgroundTasks):
    """Load the chat sidebar without downloading every chat's full history."""
    user_id = require_user_id(request)
    summaries = get_conversation_summaries(user_id)
    needs_backfill = ODDI_DRIVE_CHAT_STORAGE and any(item.get("__summary_missing") for item in summaries)
    schedule_backfill = False
    if needs_backfill:
        with _SUMMARY_BACKFILL_LOCK:
            key = str(user_id)
            if key not in _SUMMARY_BACKFILL_USERS:
                _SUMMARY_BACKFILL_USERS.add(key)
                schedule_backfill = True
    if schedule_backfill:
        # Existing Drive files predate the compact metadata index. Resolve up
        # to 40 titles after sending the fast response; new writes carry these
        # properties immediately. Remaining files are picked up on next visit.
        background_tasks.add_task(_backfill_chat_summaries, user_id)
    return JSONResponse(content=jsonable_encoder(summaries))


@app.post("/api/conversations", name="api_create_conversation")
async def api_create_conversation(request: Request):
    if not ODDI_BROWSER_LOCAL_CHATS and await request_logging_enabled_async(request):
        logger.info(
            "HTTP POST /api/conversations pid=%s user=%s",
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = await require_user_id_async(request)
    data = await safe_json(request)
    title = data.get("title", "New Chat")

    conversation_id = await run_in_threadpool(create_conversation, user_id, title)
    if ODDI_DRIVE_CHAT_STORAGE:
        # The newly written chat is already known to be empty. Reading it back
        # from Drive adds extra list/download requests to the send request.
        created_at = datetime.now(timezone.utc).isoformat()
        conversation = {
            "id": conversation_id,
            "title": str(title or "New Chat").strip()[:500] or "New Chat",
            "messages": [],
            "revision": 0,
            "created_at": created_at,
            "updated_at": created_at,
        }
    else:
        conversation = await run_in_threadpool(get_conversation, conversation_id, user_id)

    return JSONResponse(
        content=jsonable_encoder({
            "success": True,
            **(
                conversation
                or {
                    "id": conversation_id,
                    "title": title,
                    "messages": [],
                    "revision": 0,
                }
            ),
        }),
        status_code=201,
    )


@app.post("/api/conversations/import-local", name="api_import_local_conversation")
async def api_import_local_conversation(request: Request):
    user_id = await require_user_id_async(request)
    data = await safe_json(request)
    source_id = str(data.get("source_id") or "").strip()
    conversation = data.get("conversation")
    if not isinstance(conversation, dict):
        return JSONResponse({"error": "Conversation data is required."}, status_code=400)
    if not isinstance(conversation.get("messages", []), list):
        return JSONResponse({"error": "Conversation messages must be a list."}, status_code=400)
    try:
        payload_size = len(json.dumps(conversation, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "Conversation data is not valid JSON."}, status_code=400)
    if payload_size > 6 * 1024 * 1024:
        return JSONResponse({"error": "This chat is too large to sync in one request."}, status_code=413)
    try:
        imported = await run_in_threadpool(
            import_local_conversation, user_id, source_id, conversation
        )
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    if not imported:
        return JSONResponse({"error": "The chat could not be imported."}, status_code=500)
    return JSONResponse(
        {"success": True, "conversation": jsonable_encoder(imported)},
        status_code=200,
    )


@app.get("/api/conversations/bin", name="api_get_deleted_conversations")
def api_get_deleted_conversations(request: Request):
    user_id = require_user_id(request)
    return JSONResponse(content=jsonable_encoder(get_deleted_conversation_summaries(user_id)))


@app.put("/api/conversations/{conversation_id}/metadata", name="api_update_conversation_metadata")
async def api_update_conversation_metadata(request: Request, conversation_id: int):
    if await request_logging_enabled_async(request):
        logger.info(
            "HTTP PUT /api/conversations/%s/metadata pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = await require_user_id_async(request)
    data = await safe_json(request)

    allowed = {"pinned", "archived", "deleted", "title"}
    patch = {key: data[key] for key in allowed if key in data}

    if not patch:
        return JSONResponse(
            {"error": "No metadata changes supplied."},
            status_code=400,
        )

    updated = await run_in_threadpool(
        update_conversation_metadata,
        conversation_id,
        user_id,
        pinned=patch.get("pinned"),
        archived=patch.get("archived"),
        deleted=patch.get("deleted"),
        title=patch.get("title"),
    )

    if not updated:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    metadata_fields = (
        "id", "user_id", "title", "created_at", "updated_at", "revision",
        "pinned", "archived", "deleted", "deleted_at",
    )
    metadata = {key: updated[key] for key in metadata_fields if key in updated}
    return JSONResponse(content=jsonable_encoder({"success": True, "conversation": metadata}))


@app.get("/api/conversations/{conversation_id}", name="api_get_conversation")
def api_get_conversation(request: Request, conversation_id: int):
    user_id = require_user_id(request)
    conversation = get_conversation(conversation_id, user_id)

    if not conversation:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    return JSONResponse(content=jsonable_encoder(conversation))


@app.put("/api/conversations/{conversation_id}", name="api_update_conversation")
async def api_update_conversation(request: Request, conversation_id: int):
    if await request_logging_enabled_async(request):
        logger.info(
            "HTTP PUT /api/conversations/%s pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = await require_user_id_async(request)
    data = await safe_json(request)

    title = data.get("title", "New Chat")
    messages = data.get("messages", [])
    expected_revision = data.get("expected_revision")

    result = await run_in_threadpool(
        update_conversation,
        conversation_id,
        user_id,
        title,
        messages,
        expected_revision=expected_revision,
    )

    if not result.get("found"):
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    if result.get("conflict"):
        return JSONResponse(
            {
                "success": False,
                "conflict": True,
                "conversation": result["conversation"],
            },
            status_code=409,
        )

    return JSONResponse(
        content=jsonable_encoder({
            "success": True,
            "conversation": result["conversation"],
        })
    )


@app.post("/api/conversations/{conversation_id}/messages", name="api_append_conversation_message")
async def api_append_conversation_message(request: Request, conversation_id: int):
    if await request_logging_enabled_async(request):
        logger.info(
            "HTTP POST /api/conversations/%s/messages pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = await require_user_id_async(request)
    data = await safe_json(request)
    message = data.get("message")

    if not isinstance(message, dict):
        return JSONResponse(
            {"error": "Message object is required."},
            status_code=400,
        )

    conversation = await run_in_threadpool(
        append_conversation_message,
        conversation_id,
        user_id,
        message,
    )

    if not conversation:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    return JSONResponse(content=jsonable_encoder({"success": True, "conversation": conversation}))


@app.put("/api/conversations/{conversation_id}/messages/{message_id}", name="api_update_conversation_message")
async def api_update_conversation_message(
    request: Request,
    conversation_id: int,
    message_id: str,
):
    if await request_logging_enabled_async(request):
        logger.info(
            "HTTP PUT /api/conversations/%s/messages/%s pid=%s user=%s",
            conversation_id,
            message_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = await require_user_id_async(request)
    data = await safe_json(request)
    patch = data.get("patch", data)

    if not isinstance(patch, dict):
        return JSONResponse(
            {"error": "Message patch must be an object."},
            status_code=400,
        )

    conversation = await run_in_threadpool(
        update_conversation_message,
        conversation_id,
        user_id,
        message_id,
        patch,
    )

    if not conversation:
        return JSONResponse(
            {"error": "Conversation or message not found."},
            status_code=404,
        )

    return JSONResponse(content=jsonable_encoder({"success": True, "conversation": conversation}))


@app.delete("/api/conversations/{conversation_id}/messages/{message_id}", name="api_delete_conversation_message")
def api_delete_conversation_message(
    request: Request,
    conversation_id: int,
    message_id: str,
):
    if _request_logging_enabled(request):
        logger.warning(
            "HTTP DELETE /api/conversations/%s/messages/%s pid=%s user=%s",
            conversation_id,
            message_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)

    conversation = delete_conversation_message(
        conversation_id,
        user_id,
        message_id,
    )

    if not conversation:
        return JSONResponse(
            {"error": "Conversation or message not found."},
            status_code=404,
        )

    return JSONResponse(content=jsonable_encoder({"success": True, "conversation": conversation}))


@app.delete("/api/conversations/clear", name="api_clear_conversations")
def api_clear_conversations(request: Request):
    if _request_logging_enabled(request):
        logger.warning(
            "HTTP DELETE /api/conversations/clear pid=%s user=%s",
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    delete_all_conversations(user_id)
    return JSONResponse({"success": True})


@app.delete("/api/conversations/{conversation_id}", name="api_delete_conversation")
def api_delete_conversation(request: Request, conversation_id: int):
    if _request_logging_enabled(request):
        logger.warning(
            "HTTP DELETE /api/conversations/%s pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)

    conversation = get_conversation(conversation_id, user_id)

    if not conversation:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    delete_conversation(conversation_id, user_id)
    return JSONResponse({"success": True})


# =========================================================
# MEMORY CONTROLS
# =========================================================

MEMORY_CATEGORY_LABELS = {
    "goal": "Goals",
    "project": "Projects",
    "preference": "Preferences",
    "interest": "Interests",
    "person": "People",
    "skill": "Learning",
}


def _memory_category_label(category, all_categories):
    label = MEMORY_CATEGORY_LABELS.get(str(category).strip().casefold())
    if not label:
        return category

    identity = label.casefold()
    for other_category in all_categories:
        if other_category == category:
            continue
        other = str(other_category).strip().casefold()
        other_label = MEMORY_CATEGORY_LABELS.get(other, str(other_category)).casefold()
        if other == identity or other_label == identity:
            return category

    return label


@app.get("/api/memory", name="api_get_memory")
def api_get_memory(request: Request):
    user_id = require_user_id(request)
    memories = get_memory(user_id) or {}
    try:
        memory_settings = normalize_memory_settings(get_user_settings(user_id).get("memory"))
    except Exception as error:
        logger.warning("Memory preference lookup failed while opening Memory (%s).", type(error).__name__)
        memory_settings = {"enabled": False, "auto_extract": False}

    try:
        queue_status = get_memory_extraction_status(user_id)
    except Exception as error:
        logger.warning("Memory queue status lookup failed (%s).", type(error).__name__)
        queue_status = {
            "queued_count": 0,
            "processing_count": 0,
            "next_available_at": None,
            "last_activity": None,
            "lookup_failed": True,
        }
    provider_configured = memory_provider_keys_configured()
    memory_available = (
        not ODDI_BROWSER_LOCAL_CHATS
        and memory_settings.get("enabled") is True
        and memory_settings.get("auto_extract") is True
        and provider_configured
    )

    return JSONResponse(
        {
            "memory_settings": memory_settings,
            "auto_memory": {
                "available": memory_available,
                "batch_size": MEMORY_EXTRACTION_BATCH_SIZE,
                "browser_local_chats": ODDI_BROWSER_LOCAL_CHATS,
                "provider_configured": provider_configured,
                "queue": queue_status,
            },
            "memories": [
                {
                    "key": key,
                    "category": _memory_category_label(key, memories),
                    "memory": value,
                }
                for key, value in memories.items()
            ]
        }
    )


@app.put("/api/memory", name="api_update_memory")
async def api_update_memory(request: Request):
    user_id = require_user_id(request)
    data = await safe_json(request)

    key = str(data.get("key") or data.get("category") or "").strip()
    memory = str(data.get("memory") or data.get("value") or "").strip()

    if not key:
        return JSONResponse({"error": "Memory key is required."}, status_code=400)
    if not memory:
        return JSONResponse({"error": "Memory cannot be empty."}, status_code=400)

    def save_manual_memory():
        with memory_user_lock(user_id):
            save_memory(user_id, key, memory)

    await run_in_threadpool(save_manual_memory)

    return JSONResponse(
        {
            "success": True,
            "category": key,
            "memory": memory,
        }
    )


@app.delete("/api/memory", name="api_delete_memory")
async def api_delete_memory(request: Request):
    user_id = require_user_id(request)
    data = await safe_json(request)

    key = str(data.get("key") or data.get("category") or "").strip()

    if not key:
        return JSONResponse({"error": "Memory key is required."}, status_code=400)

    def delete_manual_memory():
        with memory_user_lock(user_id):
            existing = get_memory(user_id, key)
            if existing is None:
                return False
            delete_memory(user_id, key)
            return True

    deleted = await run_in_threadpool(delete_manual_memory)
    if not deleted:
        return JSONResponse({"error": "Memory not found."}, status_code=404)
    return JSONResponse({"success": True, "deleted": key})


# =========================================================
# FILES
# =========================================================

_PREVIEW_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_PREVIEW_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".log", ".json", ".xml", ".html", ".htm",
    ".yaml", ".yml", ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".sql",
    ".ini", ".cfg", ".toml", ".rtf", ".csv", ".tsv",
}


def _preview_cell_value(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)[:1000]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return str(value)[:1000]


def _extract_upload_preview(filename, data, content_type=""):
    """Read common office and text formats for the transient file-preview UI."""
    import csv
    import io
    import os
    import re
    import zipfile

    extension = os.path.splitext(filename)[1].casefold()
    office_extensions = {
        ".docx", ".xlsx", ".xlsm", ".xltx", ".xltm", ".xls", ".pptx",
    }

    if extension in office_extensions - {".xls"}:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                expanded_bytes = sum(member.file_size for member in members)
                if len(members) > 5000 or expanded_bytes > 120 * 1024 * 1024:
                    raise ValueError("This office file is too large to preview safely.")
        except zipfile.BadZipFile as exc:
            raise ValueError("This office file is damaged or has an unsupported format.") from exc

    if extension == ".docx":
        from docx import Document

        document = Document(io.BytesIO(data))
        blocks = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = str(getattr(paragraph.style, "name", ""))
            if style_name.lower().startswith("heading"):
                level = re.search(r"(\d+)$", style_name)
                text = "#" * min(6, int(level.group(1)) if level else 2) + " " + text
            blocks.append(text)
        for table_index, table in enumerate(document.tables, start=1):
            rows = []
            for row_index, row in enumerate(table.rows):
                if row_index >= 300:
                    break
                rows.append("\t".join(cell.text.replace("\n", " ").strip()[:500] for cell in row.cells[:30]))
            if rows:
                blocks.append(f"Table {table_index}\n" + "\n".join(rows))
        content = "\n\n".join(blocks) or "This Word document has no readable text."
        truncated = len(content) > 1_000_000
        return {"kind": "text", "content": content[:1_000_000], "truncated": truncated}

    if extension in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets = []
        try:
            for worksheet in workbook.worksheets[:12]:
                max_row = min(max(worksheet.max_row or 1, 1), 500)
                max_column = min(max(worksheet.max_column or 1, 1), 30)
                rows = [
                    [_preview_cell_value(value) for value in row]
                    for row in worksheet.iter_rows(
                        max_row=max_row,
                        max_col=max_column,
                        values_only=True,
                    )
                ]
                sheets.append({
                    "name": worksheet.title,
                    "rows": rows,
                    "truncated": (worksheet.max_row or 0) > 500 or (worksheet.max_column or 0) > 30,
                })
        finally:
            workbook.close()
        return {"kind": "spreadsheet", "sheets": sheets}

    if extension == ".xls":
        import xlrd

        workbook = xlrd.open_workbook(file_contents=data, on_demand=True)
        sheets = []
        try:
            for worksheet in workbook.sheets()[:12]:
                row_limit = min(worksheet.nrows, 500)
                column_limit = min(worksheet.ncols, 30)
                rows = [
                    [_preview_cell_value(value) for value in worksheet.row_values(row_index, 0, column_limit)]
                    for row_index in range(row_limit)
                ]
                sheets.append({
                    "name": worksheet.name,
                    "rows": rows,
                    "truncated": worksheet.nrows > 500 or worksheet.ncols > 30,
                })
        finally:
            workbook.release_resources()
        return {"kind": "spreadsheet", "sheets": sheets}

    if extension == ".pptx":
        from pptx import Presentation

        presentation = Presentation(io.BytesIO(data))
        slides = []
        for number, slide in enumerate(presentation.slides, start=1):
            if number > 100:
                break
            lines = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    text = "\n".join(paragraph.text for paragraph in shape.text_frame.paragraphs).strip()
                    if text:
                        lines.append(text)
                if getattr(shape, "has_table", False):
                    for row_index, row in enumerate(shape.table.rows):
                        if row_index >= 100:
                            break
                        lines.append("\t".join(cell.text.strip() for cell in row.cells[:30]))
            slides.append(f"Slide {number}\n" + "\n".join(lines))
        content = "\n\n".join(slides) or "This presentation has no readable slide text."
        truncated = len(content) > 1_000_000 or len(presentation.slides) > 100
        return {"kind": "text", "content": content[:1_000_000], "truncated": truncated}

    if extension in _PREVIEW_TEXT_EXTENSIONS or str(content_type).casefold().startswith("text/"):
        text = data[:2 * 1024 * 1024].decode("utf-8-sig", errors="replace")
        truncated = len(data) > 2 * 1024 * 1024
        if extension in {".csv", ".tsv"}:
            delimiter = "\t" if extension == ".tsv" else ","
            if extension == ".csv":
                try:
                    delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
                except csv.Error:
                    pass
            rows = []
            for row in csv.reader(io.StringIO(text), delimiter=delimiter):
                rows.append([str(cell)[:1000] for cell in row[:30]])
                if len(rows) >= 500:
                    truncated = True
                    break
            return {"kind": "spreadsheet", "sheets": [{"name": filename, "rows": rows, "truncated": truncated}]}
        if extension == ".rtf":
            text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
            text = re.sub(r"\\(?:par|line)\b ?", "\n", text)
            text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text).replace("{", "").replace("}", "")
        return {"kind": "text", "content": text[:1_000_000], "truncated": truncated or len(text) > 1_000_000}

    raise ValueError("This file type cannot be previewed. It can still be attached to your message.")


@app.post("/api/preview-file", name="api_preview_file")
async def api_preview_file(request: Request):
    require_user_id(request)
    try:
        content_length = int(request.headers.get("content-length") or 0)
    except ValueError:
        content_length = 0
    if content_length > _PREVIEW_MAX_UPLOAD_BYTES + 256 * 1024:
        return JSONResponse({"error": "Preview is limited to files up to 20 MB."}, status_code=413)
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "The preview upload could not be read."}, status_code=400)
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return JSONResponse({"error": "Choose a file to preview."}, status_code=400)

    filename = os.path.basename(str(getattr(upload, "filename", "") or "attachment"))
    content_type = str(getattr(upload, "content_type", "") or "")
    try:
        data = await upload.read(_PREVIEW_MAX_UPLOAD_BYTES + 1)
        if len(data) > _PREVIEW_MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "Preview is limited to files up to 20 MB."}, status_code=413)
        preview = await run_in_threadpool(_extract_upload_preview, filename, data, content_type)
        return JSONResponse(preview)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=415)
    except ImportError as exc:
        logger.exception("File preview dependency is missing for %s", filename)
        return JSONResponse({"error": f"Preview support for this format is unavailable: {exc.name or 'missing reader'}"}, status_code=503)
    except Exception:
        logger.exception("File preview failed for %s", filename)
        return JSONResponse({"error": "This file could not be previewed. It can still be attached to your message."}, status_code=422)
    finally:
        await upload.close()

@app.get("/api/files", name="api_get_files")
def api_get_files(request: Request):
    user_id = require_user_id(request)
    raw_conversation_id = request.query_params.get("conversation_id")

    try:
        conversation_id = (
            int(raw_conversation_id)
            if raw_conversation_id
            else None
        )
    except (TypeError, ValueError):
        conversation_id = None

    return JSONResponse(
        content=jsonable_encoder(
            get_files(
                user_id,
                conversation_id=conversation_id,
            )
        )
    )


@app.post("/api/files/import", name="api_import_library_file")
async def api_import_library_file(request: Request):
    user_id = await require_user_id_async(request)
    if is_temporary_browser_account(request):
        return JSONResponse(
            {"error": "Sign in to an account to sync Library files across devices."},
            status_code=403,
        )

    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "The uploaded file could not be read."}, status_code=400)
    upload = form.get("file")
    if not hasattr(upload, "file") or not hasattr(upload, "filename"):
        return JSONResponse({"error": "Choose a file to add to your Library."}, status_code=400)

    adapted_upload = adapt_uploaded_files([upload])[0]
    adapted_upload.filename = os.path.basename(str(adapted_upload.filename or "").replace("\\", "/")) or "uploaded-file"
    file_bytes = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        await upload.close()
        return JSONResponse(
            {"error": "This file is larger than the 64 MB upload limit."},
            status_code=413,
        )
    await upload.close()

    plan = await run_in_threadpool(
        _plan_chat_library_uploads,
        user_id,
        [(adapted_upload, file_bytes)],
    )
    existing_file_ids = [
        int(entry["file_id"])
        for entry in plan.get("already_existing_files") or []
        if entry.get("file_id") is not None
    ]
    if not plan.get("uploads"):
        existing_record = (
            await run_in_threadpool(get_file, existing_file_ids[0], user_id)
            if existing_file_ids else None
        )
        return JSONResponse({
            "success": True,
            "file_ids": existing_file_ids,
            "filename": (existing_record or {}).get("filename"),
            "added_count": 0,
        })

    try:
        current_count = await run_in_threadpool(count_files, user_id)
        replacement_count = len(plan.get("replace_file_ids") or [])
        planned_count = len(plan.get("uploads") or [])
        if current_count - replacement_count + planned_count > USER_FILE_LIMIT:
            return JSONResponse(
                {"error": "Your Library is full (30 files). Delete an older file from Library before uploading more."},
                status_code=413,
            )

        planned_bytes = sum(len(entry.get("file_bytes") or b"") for entry in plan["uploads"])
        if planned_bytes:
            quota = await run_in_threadpool(storage_router.get_file_quota, user_id)
            if planned_bytes > int(quota.get("remaining_bytes", 0) or 0) + int(plan.get("quota_credit_bytes") or 0):
                return JSONResponse(
                    {"error": "File storage quota exceeded.", "storage": quota},
                    status_code=413,
                )

        file_ids = await run_in_threadpool(
            _persist_chat_library_uploads,
            user_id,
            None,
            plan,
        )
    except FileLimitExceeded as error:
        return JSONResponse({"error": str(error)}, status_code=413)
    except StorageQuotaExceeded as error:
        logger.info("Local Library file import exceeded quota for user %s: %s", user_id, error)
        return JSONResponse(
            {"error": "File storage quota exceeded.", "storage": storage_router.get_file_quota(user_id)},
            status_code=413,
        )
    except Exception:
        logger.exception("Local Library file import failed for user %s", user_id)
        return JSONResponse({"error": "This file could not be synced to your Library."}, status_code=500)

    synced_file_ids = [int(file_id) for file_id in file_ids] + existing_file_ids
    synced_record = (
        await run_in_threadpool(get_file, synced_file_ids[0], user_id)
        if synced_file_ids else None
    )
    return JSONResponse({
        "success": True,
        "file_ids": synced_file_ids,
        "filename": (synced_record or {}).get("filename"),
        "added_count": len(file_ids),
    })


@app.get("/api/storage", name="api_storage_info")
def api_storage_info(request: Request):
    """
    Return user-visible storage information.

    Only persistent user file storage is exposed here.
    ODDI short-term memory is intentionally not exposed.
    """
    user_id = require_user_id(request)

    return JSONResponse(
        content=jsonable_encoder(
            storage_router.get_user_storage_info(user_id)
        )
    )


@app.get("/api/storage/sync-status", name="api_storage_sync_status")
async def api_storage_sync_status(request: Request):
    user_id = await require_user_id_async(request)
    payload = await run_in_threadpool(_storage_sync_status_payload, user_id)
    return JSONResponse(content=jsonable_encoder(payload))


@app.post("/api/storage/sync-now", name="api_storage_sync_now")
async def api_storage_sync_now(request: Request):
    user_id = await require_user_id_async(request)
    if not ODDI_LOCAL_ONLY_STORAGE:
        return JSONResponse(
            {"success": False, "error": "Manual laptop sync is available in the laptop app."},
            status_code=409,
        )

    from app import google_drive_storage
    if not google_drive_storage.is_configured():
        return JSONResponse(
            {"success": False, "error": "Google Drive sync is not configured on this laptop."},
            status_code=503,
        )

    try:
        await run_in_threadpool(_run_laptop_drive_sync)
    except DriveStorageError:
        logger.warning("Manual Google Drive sync failed for account %s", user_id)
        status = await run_in_threadpool(_storage_sync_status_payload, user_id)
        return JSONResponse({"success": False, "sync": status}, status_code=503)
    except Exception:
        logger.exception("Manual Google Drive sync failed for account %s", user_id)
        status = await run_in_threadpool(_storage_sync_status_payload, user_id)
        return JSONResponse({"success": False, "sync": status}, status_code=503)

    status = await run_in_threadpool(_storage_sync_status_payload, user_id)
    return JSONResponse({"success": True, "sync": status})


@app.get("/api/files/{file_id}", name="api_download_file")
def api_download_file(request: Request, file_id: int):
    user_id = require_user_id(request)
    record = get_file(file_id, user_id)

    if not record:
        return JSONResponse(
            {"error": "File not found."},
            status_code=404,
        )

    filename = record.get("filename") or "download"
    media_type = record.get("mime_type") or "application/octet-stream"
    storage_backend = record.get("storage_backend") or "database"

    # New files live in the filesystem storage layer.
    if storage_backend == "filesystem":
        storage_key = record.get("storage_key")

        if not storage_key:
            return JSONResponse(
                {"error": "File storage reference is missing."},
                status_code=500,
            )

        try:
            path = storage_router.get_file_path(
                user_id,
                storage_key,
            )
        except StorageFileNotFound:
            return JSONResponse(
                {"error": "Stored file content is missing."},
                status_code=404,
            )

        response = FileResponse(
            path=str(path),
            media_type=media_type,
            filename=filename,
        )

        response.headers["Content-Disposition"] = (
            f"inline; filename*=UTF-8''{quote(filename)}"
        )

        return response

    # Backward compatibility for legacy database-backed files.
    data = record.get("file_data")

    if data is None:
        return JSONResponse(
            {"error": "File content is not stored for this record."},
            status_code=404,
        )

    response = StreamingResponse(
        io.BytesIO(bytes(data)),
        media_type=media_type,
    )
    response.headers["Content-Disposition"] = (
        f"inline; filename*=UTF-8''{quote(filename)}"
    )

    return response


@app.delete("/api/files/{file_id}", name="api_delete_file")
def api_delete_file(request: Request, file_id: int):
    user_id = require_user_id(request)
    record = get_file(file_id, user_id)

    if not record:
        return JSONResponse(
            {"error": "File not found."},
            status_code=404,
        )

    storage_backend = record.get("storage_backend") or "database"

    if storage_backend == "filesystem":
        storage_key = record.get("storage_key")

        if storage_key:
            try:
                storage_router.delete_file(
                    user_id,
                    storage_key,
                )
            except Exception as storage_error:
                logger.exception(
                    "Physical file deletion failed for file %s: %s",
                    file_id,
                    storage_error,
                )
                return JSONResponse(
                    {"error": "File content could not be deleted."},
                    status_code=500,
                )

    deleted = delete_file_record(file_id, user_id)

    if not deleted:
        return JSONResponse(
            {"error": "File not found."},
            status_code=404,
        )

    return JSONResponse(
        {
            "success": True,
            "deleted": file_id,
        }
    )


# =========================================================
# CHAT / FILE UPLOAD
# =========================================================

def _persist_completed_chat_message(conversation_id, user_id, message):
    """Retry a failed generated-answer save after returning the response."""
    try:
        saved = append_conversation_message(conversation_id, user_id, message)
        if not saved:
            logger.warning(
                "Completed chat response could not be saved conversation=%s user=%s",
                conversation_id,
                user_id,
            )
    except Exception:
        logger.exception(
            "Background save failed for completed chat conversation=%s user=%s",
            conversation_id,
            user_id,
        )

@app.post("/api/chat-generations/{generation_id}/cancel", name="cancel_chat_generation")
async def cancel_chat_generation(request: Request, generation_id: str):
    user_id = str(require_user_id(request))
    with _chat_generation_lock:
        generation = _active_chat_generations.get(generation_id)
        if generation and generation["user_id"] == user_id:
            generation["cancelled"].set()
            return JSONResponse({"success": True, "cancelled": True})
    return JSONResponse({"success": True, "cancelled": False})


@app.post("/chat", name="chat")
async def chat(request: Request, background_tasks: BackgroundTasks):
    generation_started = time.perf_counter()
    chat_request_id = getattr(request.state, "chat_request_id", uuid.uuid4().hex[:12])
    form = await request.form()

    message = form.get("message")
    if message is None:
        return JSONResponse({"error": "Message is required."}, status_code=400)
    message = str(message)
    response_style = str(form.get("response_style") or "").strip().casefold()
    response_style_instructions = {
        "concise": "Answer concisely, prioritizing the most useful information.",
        "step_by_step": "Explain the answer as clear, numbered steps.",
        "table": "When comparing multiple items, use a compact Markdown table; otherwise answer normally.",
        "detailed": "Give a thorough, well-structured explanation with useful examples.",
    }
    memory_message = str(form.get("memory_message") or message).strip()
    assistant_message_id = str(form.get("assistant_message_id") or "").strip()
    if not assistant_message_id or len(assistant_message_id) > 128:
        assistant_message_id = str(uuid.uuid4())
    document_workspace_requested = str(form.get("document_workspace") or "").strip().casefold() in {"1", "true", "yes", "on"}
    document_title = str(form.get("document_title") or "").strip()[:120]
    generation_id = str(form.get("generation_id") or "").strip()
    if not generation_id or len(generation_id) > 128:
        generation_id = str(uuid.uuid4())
    memory_enabled_value = form.get("memory_enabled")
    client_memory_enabled = (
        str(memory_enabled_value).strip().casefold() in {"1", "true", "yes", "on"}
        if memory_enabled_value is not None
        else None
    )
    auto_extract_value = form.get("memory_auto_extract")
    client_memory_auto_extract = (
        str(auto_extract_value).strip().casefold() in {"1", "true", "yes", "on"}
        if auto_extract_value is not None
        else None
    )
    if ODDI_BROWSER_LOCAL_CHATS:
        # A cloud process may generate a response, but it must not persist
        # chat-derived memory alongside the browser-local conversation.
        client_memory_enabled = False
        client_memory_auto_extract = False

    raw_conversation_id = form.get("conversation_id")
    try:
        conversation_id = int(raw_conversation_id) if raw_conversation_id else None
    except (TypeError, ValueError):
        conversation_id = None
    if ODDI_BROWSER_LOCAL_CHATS:
        # Client-generated IDs are intentionally not mapped to a server row.
        conversation_id = None

    # Starlette FormData supports multiple values for the same field name.
    raw_uploaded_files = form.getlist("files")
    uploaded_files = [
        item for item in raw_uploaded_files
        if hasattr(item, "file") and hasattr(item, "filename")
    ]

    # Convert FastAPI UploadFile objects into a Flask-FileStorage-compatible
    # object before passing them to the existing ODDI engine.
    engine_files = adapt_uploaded_files(uploaded_files)
    library_source_indexes = set()
    for raw_index in form.getlist("library_source_indexes"):
        try:
            library_source_indexes.add(int(raw_index))
        except (TypeError, ValueError):
            continue
    requested_source_file_ids = list(dict.fromkeys(
        str(raw_id).strip()
        for raw_id in form.getlist("source_file_ids")
        if str(raw_id).strip() and len(str(raw_id).strip()) <= 128
    ))
    requested_source_file_id_set = set(requested_source_file_ids)

    # Chat is private. Authenticate before storing uploaded files.
    user_id = await require_user_id_async(request)
    persist_library_uploads = not is_temporary_browser_account(request)
    verified_library_records = {}
    if requested_source_file_ids:
        try:
            verified_library_records = {
                str(record.get("id")): record
                for record in get_files(user_id)
                if record.get("id") is not None
                and str(record.get("id")) in requested_source_file_id_set
            }
        except Exception as source_lookup_error:
            logger.warning("Could not verify cited Library files for user %s: %s", user_id, type(source_lookup_error).__name__)
    fast_reply = fast_response(memory_message) if not engine_files else None
    settings_loaded = fast_reply is None
    user_settings = {}
    if settings_loaded:
        try:
            # Memory consent is server-authoritative, including for Drive-backed
            # accounts. A failed lookup fails closed for memory while chat itself
            # remains available.
            user_settings = await run_in_threadpool(get_user_settings, user_id)
        except Exception as error:
            logger.warning("User settings lookup failed; memory is disabled for this turn (%s).", type(error).__name__)
            user_settings = {}
            settings_loaded = False
    server_memory = normalize_memory_settings(user_settings.get("memory"))
    memory_enabled = (
        settings_loaded
        and server_memory["enabled"]
        and client_memory_enabled is not False
        and not memory_user_disabled(user_id)
    )
    memory_auto_extract = (
        memory_enabled
        and server_memory["auto_extract"]
        and client_memory_auto_extract is not False
        and not memory_user_opted_out(user_id)
    )
    privacy_settings = user_settings.get("privacy", {}) if isinstance(user_settings, dict) else {}
    request_logging_enabled = (
        not ODDI_BROWSER_LOCAL_CHATS
        and fast_reply is None
        and privacy_settings.get("request_logging", True) is not False
    )

    # Build the authoritative identity from the authenticated session.
    # The message itself must never be allowed to determine host/admin status.
    identity = create_identity(
        user_id=str(user_id),
        email=str(request.session.get("email", "")),
    )

    # If the browser lost the successful response, its Retry action repeats
    # this assistant message ID. Return the already-saved reply instead of
    # generating a second answer for the same turn.
    if conversation_id is not None and not ODDI_DRIVE_CHAT_STORAGE:
        try:
            existing_conversation = await run_in_threadpool(
                get_conversation, conversation_id, user_id
            )
        except DriveStorageError:
            logger.warning("Google Drive chat lookup failed; generating without server-side deduplication.")
            existing_conversation = None
        except Exception:
            logger.exception(
                "Conversation lookup failed request_id=%s conversation=%s; continuing without server-side deduplication",
                chat_request_id,
                conversation_id,
            )
            existing_conversation = None
        existing_reply = next(
            (
                item for item in (existing_conversation or {}).get("messages", [])
                if str(item.get("id") or "") == assistant_message_id
                and item.get("role") == "assistant"
            ),
            None,
        )
        if existing_reply is not None:
            response = response_from_engine(str(existing_reply.get("text") or existing_reply.get("content") or ""))
            response.headers["X-Oddi-Assistant-Message-Id"] = assistant_message_id
            response.headers["X-Oddi-Completed-At"] = str(existing_reply.get("completed_at") or datetime.now(timezone.utc).isoformat())
            response.headers["X-Oddi-Conversation-Persisted"] = "1"
            response.headers["X-Oddi-Conversation-Revision"] = str((existing_conversation or {}).get("revision") or 0)
            response_meta = existing_reply.get("response_meta") if isinstance(existing_reply.get("response_meta"), dict) else {}
            response.headers["X-Oddi-Provider"] = str(response_meta.get("provider") or "Auto routing")
            response.headers["X-Oddi-Latency-Ms"] = str(response_meta.get("latency_ms") or 0)
            response.headers["X-Oddi-Token-Estimate"] = str(response_meta.get("token_estimate") or 0)
            existing_sources = existing_reply.get("sources") if isinstance(existing_reply.get("sources"), list) else []
            if existing_sources:
                response.headers["X-Oddi-Sources"] = json.dumps(existing_sources[:48], separators=(",", ":"))
            return response

    # Plan Library persistence before generation, but commit only after the
    # AI successfully processes the uploads. This keeps replacements reversible.
    file_record_ids = []
    upload_fingerprint = None
    is_upload_retry = False
    upload_library_plan = {
        "uploads": [],
        "replace_file_ids": [],
        "replace_storage_keys": [],
        "quota_credit_bytes": 0,
        "already_exists_count": 0,
    }

    if engine_files and persist_library_uploads:
        file_payloads = []

        try:
            library_upload_payloads = []
            for upload_index, uploaded_file in enumerate(engine_files):
                uploaded_file.stream.seek(0)
                file_bytes = uploaded_file.stream.read()
                uploaded_file.stream.seek(0)

                payload = (uploaded_file, file_bytes)
                file_payloads.append(payload)
                if upload_index not in library_source_indexes:
                    library_upload_payloads.append(payload)

            upload_fingerprint = _uploaded_batch_fingerprint(file_payloads)
            previous_fingerprint = _get_chat_upload_retry_fingerprint(
                user_id,
                generation_id,
            )
            is_upload_retry = previous_fingerprint is not None
            if is_upload_retry and previous_fingerprint != upload_fingerprint:
                return JSONResponse(
                    {"error": "This retry does not match the original attachments. Start a new message to upload different files."},
                    status_code=409,
                )

            if not is_upload_retry:
                upload_library_plan = _plan_chat_library_uploads(user_id, library_upload_payloads)
                current_file_count = count_files(user_id)
                replacement_count = len(upload_library_plan["replace_file_ids"])
                planned_count = len(upload_library_plan["uploads"])
                projected_count = current_file_count - replacement_count + planned_count
                if projected_count > USER_FILE_LIMIT:
                    return JSONResponse(
                        {
                            "error": "Your Library is full (30 files). Delete an older file from Library before uploading more.",
                            "file_limit": USER_FILE_LIMIT,
                            "file_count": current_file_count,
                        },
                        status_code=413,
                    )

                # Validate the projected size with credit for replaced objects.
                # Exact duplicates contribute zero bytes and do not consume a
                # Library slot.
                planned_bytes = sum(
                    len(entry["file_bytes"])
                    for entry in upload_library_plan["uploads"]
                )
                if planned_bytes:
                    quota = storage_router.get_file_quota(user_id)
                    remaining_bytes = int(quota.get("remaining_bytes", 0) or 0)
                    quota_credit_bytes = int(upload_library_plan["quota_credit_bytes"] or 0)
                else:
                    quota = None
                    remaining_bytes = 0
                    quota_credit_bytes = 0

                if planned_bytes > remaining_bytes + quota_credit_bytes:
                    return JSONResponse(
                        {
                            "error": "File storage quota exceeded.",
                            "storage": quota,
                        },
                        status_code=413,
                    )

            for uploaded_file, _ in file_payloads:
                uploaded_file.stream.seek(0)

        except FileLimitExceeded as file_limit_error:
            logger.info(
                "File count limit reached for user %s: %s",
                user_id,
                file_limit_error,
            )
            return JSONResponse(
                {
                    "error": str(file_limit_error),
                    "file_limit": USER_FILE_LIMIT,
                    "file_count": count_files(user_id),
                },
                status_code=413,
            )

        except StorageQuotaExceeded as quota_error:
            logger.warning(
                "File storage quota exceeded for user %s: %s",
                user_id,
                quota_error,
            )
            return JSONResponse(
                {
                    "error": "File storage quota exceeded.",
                    "storage": storage_router.get_file_quota(user_id),
                },
                status_code=413,
            )

        except Exception as storage_error:
            logger.exception(
                "File storage failed for user %s: %s",
                user_id,
                storage_error,
            )
            return JSONResponse(
                {"error": "Uploaded file could not be stored."},
                status_code=500,
            )

    history_json = str(form.get("history", "[]"))

    try:
        conversation_history = json.loads(history_json)
    except (json.JSONDecodeError, TypeError):
        conversation_history = []

    conversation_history = conversation_history[-100:]

    if request_logging_enabled:
        if engine_files:
            logger.info("Files received: %s", [f.filename for f in engine_files])
        else:
            logger.info("No files uploaded")

    cancel_event = threading.Event()
    with _chat_generation_lock:
        _active_chat_generations[generation_id] = {
            "user_id": str(user_id),
            "cancelled": cancel_event,
        }

    try:
        # Match the original text the user typed before the frontend's
        # Library-recall instructions or other internal context can alter it.
        # Requests with attachments continue through the document-aware engine.
        if fast_reply is not None:
            reply = fast_reply
        else:
            engine_message = message
            style_instruction = response_style_instructions.get(response_style)
            if style_instruction:
                engine_message += f"\n\n[Response format guidance: {style_instruction}]"
            reply = await run_in_threadpool(
                process_message,
                engine_message,
                engine_files,
                conversation_history,
                user_id=user_id,
                identity=identity,
                long_term_memory_enabled=memory_enabled,
            )
        if cancel_event.is_set():
            return PlainTextResponse("Generation stopped.", status_code=409)
    except Exception:
        logger.exception(
            "Chat processing failed request_id=%s user=%s; uploaded Library files were left unchanged.",
            chat_request_id,
            user_id,
        )
        return JSONResponse(
            {
                "error": "The chat service could not complete this reply. Please retry.",
                "request_id": chat_request_id,
            },
            status_code=503,
        )
    finally:
        with _chat_generation_lock:
            _active_chat_generations.pop(generation_id, None)

    if upload_library_plan.get("uploads"):
        try:
            file_record_ids = await run_in_threadpool(
                _persist_chat_library_uploads,
                user_id,
                conversation_id,
                upload_library_plan,
            )
        except FileLimitExceeded as file_limit_error:
            logger.info(
                "File count changed before Library replacement for user %s: %s",
                user_id,
                file_limit_error,
            )
            return JSONResponse(
                {
                    "error": str(file_limit_error),
                    "file_limit": USER_FILE_LIMIT,
                    "file_count": count_files(user_id),
                },
                status_code=413,
            )
        except StorageQuotaExceeded as quota_error:
            logger.warning(
                "File storage quota changed before Library replacement for user %s: %s",
                user_id,
                quota_error,
            )
            return JSONResponse(
                {
                    "error": "File storage quota exceeded.",
                    "storage": storage_router.get_file_quota(user_id),
                },
                status_code=413,
            )
        except Exception as storage_error:
            logger.exception(
                "Could not update Library files for user %s: %s",
                user_id,
                storage_error,
            )
            return JSONResponse(
                {"error": "Uploaded file could not be stored."},
                status_code=500,
            )

    if engine_files and persist_library_uploads:
        _remember_chat_upload_retry_fingerprint(
            user_id,
            generation_id,
            upload_fingerprint,
        )

    # Keep the exact source set with the assistant message so retry and chat
    # history can render the same citations after a reload.
    library_file_mappings = []
    planned_file_ids_by_upload_index = {}
    for index, (entry, file_record_id) in enumerate(
        zip(upload_library_plan.get("uploads") or [], file_record_ids)
    ):
        upload_index = int(entry.get("upload_index", index))
        file_id = int(file_record_id)
        planned_file_ids_by_upload_index[upload_index] = file_id
        library_file_mappings.append([upload_index, file_id])
    for entry in upload_library_plan.get("duplicate_uploads") or []:
        upload_index = int(entry.get("upload_index", -1))
        file_id = planned_file_ids_by_upload_index.get(
            int(entry.get("planned_upload_index", -1))
        )
        if upload_index >= 0 and file_id is not None:
            library_file_mappings.append([upload_index, file_id])
    library_file_mappings.extend(
        [int(entry.get("upload_index", 0)), int(entry["file_id"])]
        for entry in upload_library_plan.get("already_existing_files") or []
        if entry.get("file_id") is not None
    )
    library_file_ids_by_index = {
        int(upload_index): int(file_id)
        for upload_index, file_id in library_file_mappings
    }
    direct_engine_files = [
        uploaded_file for upload_index, uploaded_file in enumerate(engine_files)
        if upload_index not in library_source_indexes
    ]
    capability_sources = getattr(reply, "sources", []) or []
    has_file_search_citations = any(
        isinstance(source, dict) and source.get("type") == "file_reference"
        for source in capability_sources
    )
    if file_record_ids or library_file_ids_by_index or has_file_search_citations:
        try:
            all_library_records = get_files(user_id)
            verified_library_records.update({
                str(record.get("id")): record
                for record in all_library_records
                if record.get("id") is not None
            })
        except Exception as source_lookup_error:
            logger.warning("Could not load Library filenames for citations for user %s: %s", user_id, type(source_lookup_error).__name__)

    response_sources = []
    seen_source_keys = set()

    def add_response_source(source):
        if not isinstance(source, dict):
            return
        if source.get("type") == "web":
            url = str(source.get("url") or "").strip()
            if not url.startswith(("https://", "http://")):
                return
            key = ("web", url.rstrip("/").casefold())
            normalized = {"type": "web", "title": str(source.get("title") or url)[:240], "url": url[:1800]}
        elif source.get("type") == "file":
            file_id = str(source.get("id") or "").strip()
            filename = str(source.get("name") or source.get("filename") or "").strip()
            if not file_id or not filename:
                return
            key = ("file", file_id)
            normalized = {"type": "file", "storage": "server", "id": file_id, "name": filename[:240]}
        else:
            return
        if key in seen_source_keys:
            return
        seen_source_keys.add(key)
        if len(response_sources) < 48:
            response_sources.append(normalized)

    for file_id in requested_source_file_ids:
        record = verified_library_records.get(file_id)
        if record:
            add_response_source({
                "type": "file",
                "id": file_id,
                "name": record.get("filename") or record.get("name") or "Library file",
            })

    for upload_index, file_id in library_file_ids_by_index.items():
        record = verified_library_records.get(str(file_id))
        uploaded_name = ""
        if 0 <= upload_index < len(direct_engine_files):
            uploaded_name = str(direct_engine_files[upload_index].filename or "")
        add_response_source({
            "type": "file",
            "id": str(file_id),
            "name": (record or {}).get("filename") or (record or {}).get("name") or uploaded_name or "Library file",
        })

    for source in capability_sources:
        if isinstance(source, dict) and source.get("type") == "file_reference":
            cited_name = str(source.get("name") or "").strip().casefold()
            matched_record = next((
                record for record in verified_library_records.values()
                if str(record.get("filename") or record.get("name") or "").strip().casefold() == cited_name
            ), None)
            if matched_record:
                add_response_source({
                    "type": "file",
                    "id": str(matched_record.get("id")),
                    "name": matched_record.get("filename") or matched_record.get("name") or source.get("name"),
                })
            continue
        add_response_source(source)

    completed_at = datetime.now(timezone.utc).isoformat()
    latency_ms = max(0, int((time.perf_counter() - generation_started) * 1000))
    reply_text = str(reply)
    token_estimate = max(1, (len(reply_text) + 3) // 4) if isinstance(reply, str) else 0
    assistant_saved_to_conversation = False
    saved_conversation_revision = 0
    if conversation_id is not None and isinstance(reply, str):
        assistant_message = {
            "id": assistant_message_id,
            "role": "assistant",
            "text": reply_text,
            "sources": response_sources,
            "pinned": False,
            "feedback": None,
            "background_completion": True,
            "completed_at": completed_at,
            "response_meta": {
                "latency_ms": latency_ms,
                "token_estimate": token_estimate,
                "provider": "Auto routing",
            },
        }
        if document_workspace_requested:
            assistant_message["document_workspace"] = True
            if document_title:
                assistant_message["document_title"] = document_title
        try:
            # Persist before sending the completed answer to the browser. A
            # background-only Drive write allowed a reload to win this race.
            saved_conversation = await run_in_threadpool(
                append_conversation_message,
                conversation_id,
                user_id,
                assistant_message,
            )
        except DriveStorageError:
            logger.warning(
                "Google Drive save failed before reply delivery; keeping local recovery and scheduling a retry."
            )
            saved_conversation = None
        except Exception:
            logger.exception(
                "Completed reply persistence failed request_id=%s conversation=%s user=%s; returning reply for local recovery",
                chat_request_id,
                conversation_id,
                user_id,
            )
            saved_conversation = None

        if not saved_conversation:
            logger.warning(
                "Completed chat response could not be saved conversation=%s user=%s",
                conversation_id,
                user_id,
            )
            if ODDI_DRIVE_CHAT_STORAGE:
                background_tasks.add_task(
                    _persist_completed_chat_message,
                    conversation_id,
                    user_id,
                    assistant_message,
                )
        else:
            assistant_saved_to_conversation = True
            saved_conversation_revision = int(saved_conversation.get("revision", 0) or 0)

    if (
        fast_reply is not None
        and client_memory_enabled is not False
        and client_memory_auto_extract is not False
    ):
        background_tasks.add_task(
            _enqueue_memory_message_if_enabled,
            str(user_id),
            assistant_message_id,
            memory_message,
        )
    elif (
        not ODDI_BROWSER_LOCAL_CHATS
        and memory_provider_keys_configured()
        and memory_enabled
        and memory_auto_extract
    ):
        background_tasks.add_task(
            enqueue_memory_message,
            str(user_id),
            assistant_message_id,
            memory_message if is_safe_memory_message(memory_message) else "",
        )

    if file_record_ids:
        for file_record_id in file_record_ids:
            try:
                update_file_record(
                    file_record_id,
                    user_id,
                    status="processed",
                )
            except Exception as file_db_error:
                logger.warning(
                    "File metadata status update failed: %s",
                    file_db_error,
                )

    response = response_from_engine(reply)
    response.headers["X-Oddi-Assistant-Message-Id"] = assistant_message_id
    response.headers["X-Oddi-Completed-At"] = completed_at
    response.headers["X-Oddi-Provider"] = "Auto routing"
    response.headers["X-Oddi-Latency-Ms"] = str(latency_ms)
    response.headers["X-Oddi-Token-Estimate"] = str(token_estimate)
    response.headers["X-Oddi-Conversation-Persisted"] = "1" if assistant_saved_to_conversation else "0"
    if assistant_saved_to_conversation:
        response.headers["X-Oddi-Conversation-Revision"] = str(saved_conversation_revision)
    if response_sources:
        response.headers["X-Oddi-Sources"] = json.dumps(response_sources, separators=(",", ":"))
    planned_count = len(upload_library_plan.get("uploads") or [])
    replaced_count = min(planned_count, len(upload_library_plan.get("replace_file_ids") or []))
    response.headers["X-Oddi-Library-Added-Count"] = str(max(0, planned_count - replaced_count))
    response.headers["X-Oddi-Library-Updated-Count"] = str(replaced_count)
    response.headers["X-Oddi-Library-Existing-Count"] = str(int(upload_library_plan.get("already_exists_count") or 0))
    if library_file_mappings:
        response.headers["X-Oddi-Library-File-Indexes"] = json.dumps(
            library_file_mappings,
            separators=(",", ":"),
        )
    return response


# =========================================================
# DEVELOPMENT ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="127.0.0.1" if ODDI_LOCAL_ONLY_STORAGE else "0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=not ODDI_LOCAL_ONLY_STORAGE,
    )
