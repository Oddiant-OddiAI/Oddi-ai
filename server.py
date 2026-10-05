import io
import asyncio
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
from dotenv import load_dotenv

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
    create_tables,
    create_user,
    get_user_by_email,
    create_conversation,
    import_local_conversation,
    get_conversations,
    get_conversation,
    update_conversation,
    delete_conversation,
    delete_all_conversations,
    get_deleted_conversations,
    update_conversation_metadata,
    append_conversation_message,
    update_conversation_message,
    delete_conversation_message,
    get_memory,
    save_memory,
    delete_memory,
    register_file,
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
)
from app.google_drive_storage import DriveStorageError

from app.engine import process_message
from app.config import client
from app.fast_responses import fast_response
from identity.identity import create_identity
from app.memory_ai import update_user_memory_from_chat
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

_chat_generation_lock = threading.Lock()
_active_chat_generations = {}


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="ODDI AI",
    version="1.0.0",
)


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
        while True:
            try:
                await run_in_threadpool(purge_expired_deleted_conversations)
            except Exception:
                logger.exception("Automatic Bin retention cleanup failed")
            await asyncio.sleep(60 * 60)

    app.state.bin_retention_task = asyncio.create_task(cleanup_expired_bin_chats())

    if ODDI_LOCAL_ONLY_STORAGE:
        from app import google_drive_storage
        if google_drive_storage.is_configured():
            async def sync_laptop_chats():
                from app.drive_sync import sync_laptop_once
                while True:
                    try:
                        await run_in_threadpool(sync_laptop_once)
                    except Exception:
                        logger.exception("Laptop to Google Drive chat sync failed; it will retry")
                    await asyncio.sleep(30)

            app.state.drive_sync_task = asyncio.create_task(sync_laptop_chats())


@app.on_event("shutdown")
async def stop_bin_retention_cleanup():
    for task_name in ("bin_retention_task", "drive_sync_task"):
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
    # from the already-required persistent database credentials. Never log or
    # expose this material. Setting FLASK_SECRET_KEY remains the preferred
    # option because rotating database credentials then won't invalidate login
    # cookies.
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
            for name in ("GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
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
        from app.drive_sync import sync_laptop_once
        await run_in_threadpool(sync_laptop_once)
    except Exception:
        logger.exception("Could not refresh laptop accounts from Google Drive")


def set_user_session(request: Request, user, auth_provider=None):
    """Store the same user identity fields used by the old Flask server."""
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["email"] = user["email"]

    if auth_provider:
        request.session["auth_provider"] = auth_provider


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

    user = _get_session_user(request)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="This account is no longer available. Sign in again.")
    return user["id"] if ODDI_LOCAL_ONLY_STORAGE else user_id


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

    user = get_user_by_email(email)
    if user is None:
        await sync_laptop_accounts_from_drive()
        user = get_user_by_email(email)

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

    user = get_user_by_email(email)
    if user is None:
        await sync_laptop_accounts_from_drive()
        user = get_user_by_email(email)

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


@app.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        logger.warning("Google OAuth failed: %s", error)
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
            current[key] = value
    save_user_settings(user_id, current)
    return JSONResponse({"success": True, "settings": current})


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
    if _request_logging_enabled(request):
        logger.info(
            "HTTP GET /api/conversations pid=%s user=%s",
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    return JSONResponse(content=jsonable_encoder(get_conversations(user_id)))


@app.post("/api/conversations", name="api_create_conversation")
async def api_create_conversation(request: Request):
    if not ODDI_BROWSER_LOCAL_CHATS and _request_logging_enabled(request):
        logger.info(
            "HTTP POST /api/conversations pid=%s user=%s",
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    data = await safe_json(request)
    title = data.get("title", "New Chat")

    conversation_id = create_conversation(user_id, title)
    conversation = get_conversation(conversation_id, user_id)

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
    user_id = require_user_id(request)
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
        imported = import_local_conversation(user_id, source_id, conversation)
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
    return JSONResponse(content=jsonable_encoder(get_deleted_conversations(user_id)))


@app.put("/api/conversations/{conversation_id}/metadata", name="api_update_conversation_metadata")
async def api_update_conversation_metadata(request: Request, conversation_id: int):
    if _request_logging_enabled(request):
        logger.info(
            "HTTP PUT /api/conversations/%s/metadata pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    data = await safe_json(request)

    allowed = {"pinned", "archived", "deleted"}
    patch = {key: data[key] for key in allowed if key in data}

    if not patch:
        return JSONResponse(
            {"error": "No metadata changes supplied."},
            status_code=400,
        )

    updated = update_conversation_metadata(
        conversation_id,
        user_id,
        pinned=patch.get("pinned"),
        archived=patch.get("archived"),
        deleted=patch.get("deleted"),
    )

    if not updated:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    return JSONResponse(content=jsonable_encoder({"success": True, "conversation": updated}))


@app.get("/api/conversations/{conversation_id}", name="api_get_conversation")
def api_get_conversation(request: Request, conversation_id: int):
    user_id = require_user_id(request)
    conversation = get_conversation(conversation_id, user_id)

    if not conversation:
        return JSONResponse({"error": "Conversation not found."}, status_code=404)

    return JSONResponse(content=jsonable_encoder(conversation))


@app.put("/api/conversations/{conversation_id}", name="api_update_conversation")
async def api_update_conversation(request: Request, conversation_id: int):
    if _request_logging_enabled(request):
        logger.info(
            "HTTP PUT /api/conversations/%s pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    data = await safe_json(request)

    title = data.get("title", "New Chat")
    messages = data.get("messages", [])
    expected_revision = data.get("expected_revision")

    result = update_conversation(
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
    if _request_logging_enabled(request):
        logger.info(
            "HTTP POST /api/conversations/%s/messages pid=%s user=%s",
            conversation_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    data = await safe_json(request)
    message = data.get("message")

    if not isinstance(message, dict):
        return JSONResponse(
            {"error": "Message object is required."},
            status_code=400,
        )

    conversation = append_conversation_message(
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
    if _request_logging_enabled(request):
        logger.info(
            "HTTP PUT /api/conversations/%s/messages/%s pid=%s user=%s",
            conversation_id,
            message_id,
            os.getpid(),
            request.session.get("user_id"),
        )
    user_id = require_user_id(request)
    data = await safe_json(request)
    patch = data.get("patch", data)

    if not isinstance(patch, dict):
        return JSONResponse(
            {"error": "Message patch must be an object."},
            status_code=400,
        )

    conversation = update_conversation_message(
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

    return JSONResponse(
        {
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

    save_memory(user_id, key, memory)

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

    existing = get_memory(user_id, key)
    if existing is None:
        return JSONResponse({"error": "Memory not found."}, status_code=404)

    delete_memory(user_id, key)
    return JSONResponse({"success": True, "deleted": key})


# =========================================================
# FILES
# =========================================================

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
    form = await request.form()

    message = form.get("message")
    if message is None:
        return JSONResponse({"error": "Message is required."}, status_code=400)
    message = str(message)
    memory_message = str(form.get("memory_message") or message).strip()
    assistant_message_id = str(form.get("assistant_message_id") or "").strip()
    if not assistant_message_id or len(assistant_message_id) > 128:
        assistant_message_id = str(uuid.uuid4())
    generation_id = str(form.get("generation_id") or "").strip()
    if not generation_id or len(generation_id) > 128:
        generation_id = str(uuid.uuid4())
    memory_enabled_value = form.get("memory_enabled")
    memory_enabled = (
        str(memory_enabled_value).strip().casefold() in {"1", "true", "yes", "on"}
        if memory_enabled_value is not None
        else False
    )
    auto_extract_value = form.get("memory_auto_extract")
    memory_auto_extract = (
        str(auto_extract_value).strip().casefold() in {"1", "true", "yes", "on"}
        if auto_extract_value is not None
        else memory_enabled
    )
    if ODDI_BROWSER_LOCAL_CHATS:
        # A cloud process may generate a response, but it must not persist
        # chat-derived memory alongside the browser-local conversation.
        memory_enabled = False
        memory_auto_extract = False

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

    # Chat is private. Authenticate before storing uploaded files.
    user_id = require_user_id(request)
    user_settings = get_user_settings(user_id)
    privacy_settings = user_settings.get("privacy", {}) if isinstance(user_settings, dict) else {}
    request_logging_enabled = (
        not ODDI_BROWSER_LOCAL_CHATS
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
    if conversation_id is not None:
        existing_conversation = get_conversation(conversation_id, user_id)
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
            response_meta = existing_reply.get("response_meta") if isinstance(existing_reply.get("response_meta"), dict) else {}
            response.headers["X-Oddi-Provider"] = str(response_meta.get("provider") or "Auto routing")
            response.headers["X-Oddi-Latency-Ms"] = str(response_meta.get("latency_ms") or 0)
            response.headers["X-Oddi-Token-Estimate"] = str(response_meta.get("token_estimate") or 0)
            return response

    # Store the actual uploaded bytes through the Storage Router.
    # PostgreSQL keeps metadata/references only for new uploads.
    file_record_ids = []
    stored_file_keys = []

    if engine_files and not ODDI_BROWSER_LOCAL_CHATS:
        file_payloads = []

        try:
            total_upload_bytes = 0

            for uploaded_file in engine_files:
                uploaded_file.stream.seek(0)
                file_bytes = uploaded_file.stream.read()
                uploaded_file.stream.seek(0)

                file_payloads.append((uploaded_file, file_bytes))
                total_upload_bytes += len(file_bytes)

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
                current_file_count = count_files(user_id)
                if current_file_count + len(engine_files) > USER_FILE_LIMIT:
                    return JSONResponse(
                        {
                            "error": "Your Library is full (30 files). Delete an older file from Library before uploading more.",
                            "file_limit": USER_FILE_LIMIT,
                            "file_count": current_file_count,
                        },
                        status_code=413,
                    )

            # Check the complete batch before writing anything so a request
            # cannot partially consume the user's quota.
            if not is_upload_retry:
                quota = storage_router.get_file_quota(user_id)
                remaining_bytes = int(quota.get("remaining_bytes", 0) or 0)

                if total_upload_bytes > remaining_bytes:
                    return JSONResponse(
                        {
                            "error": "File storage quota exceeded.",
                            "storage": quota,
                        },
                        status_code=413,
                    )

                for uploaded_file, file_bytes in file_payloads:
                    stored = storage_router.save_file(
                        user_id=user_id,
                        data=file_bytes,
                        original_filename=(
                            uploaded_file.filename or "unnamed-file"
                        ),
                    )
                    storage_key = stored["storage_key"]
                    stored_file_keys.append(storage_key)

                    try:
                        file_record_id = register_file(
                            user_id=user_id,
                            filename=(
                                uploaded_file.filename or "unnamed-file"
                            ),
                            mime_type=uploaded_file.mimetype,
                            size_bytes=len(file_bytes),
                            conversation_id=conversation_id,
                            storage_backend="filesystem",
                            storage_key=storage_key,
                            external_file_id=None,
                            file_data=None,
                            status="received",
                        )
                        file_record_ids.append(file_record_id)

                    except Exception as file_db_error:
                        logger.exception(
                            "File metadata save failed for user %s: %s",
                            user_id,
                            file_db_error,
                        )
                        # Metadata failure is a transaction failure. Do not let
                        # the engine process a file ODDI can no longer account for.
                        raise

            # Rewind every upload so the existing engine receives the same
            # file stream it received before the storage migration.
            for uploaded_file, _ in file_payloads:
                uploaded_file.stream.seek(0)

        except FileLimitExceeded as file_limit_error:
            logger.info(
                "File count limit reached for user %s: %s",
                user_id,
                file_limit_error,
            )
            rollback_stored_files(
                user_id,
                stored_file_keys,
                file_record_ids,
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
            rollback_stored_files(
                user_id,
                stored_file_keys,
                file_record_ids,
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
            rollback_stored_files(
                user_id,
                stored_file_keys,
                file_record_ids,
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

    # Chat is also private: do not allow unauthenticated access to the
    # underlying AI engine even if someone calls /chat directly.
    user_id = require_user_id(request)

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
        fast_reply = (
            fast_response(memory_message)
            if not engine_files
            else None
        )

        if fast_reply is not None:
            reply = fast_reply
        else:
            reply = await run_in_threadpool(
                process_message,
                message,
                engine_files,
                conversation_history,
                user_id=user_id,
                identity=identity,
                long_term_memory_enabled=memory_enabled,
            )
        if cancel_event.is_set():
            return PlainTextResponse("Generation stopped.", status_code=409)
    except Exception:
        # If AI processing fails after files have been persisted, roll back
        # both the physical objects and their metadata so quota is not leaked.
        rollback_stored_files(
            user_id,
            stored_file_keys,
            file_record_ids,
        )
        logger.exception(
            "Chat processing failed for user %s; uploaded files rolled back.",
            user_id,
        )
        raise
    finally:
        with _chat_generation_lock:
            _active_chat_generations.pop(generation_id, None)

    if engine_files and not ODDI_BROWSER_LOCAL_CHATS:
        _remember_chat_upload_retry_fingerprint(
            user_id,
            generation_id,
            upload_fingerprint,
        )

    completed_at = datetime.now(timezone.utc).isoformat()
    latency_ms = max(0, int((time.perf_counter() - generation_started) * 1000))
    token_estimate = max(1, (len(str(reply)) + 3) // 4) if isinstance(reply, str) else 0
    if conversation_id is not None and isinstance(reply, str):
        saved_conversation = append_conversation_message(
            conversation_id,
            user_id,
            {
                "id": assistant_message_id,
                "role": "assistant",
                "text": reply,
                "pinned": False,
                "feedback": None,
                "background_completion": True,
                "completed_at": completed_at,
                "response_meta": {
                    "latency_ms": latency_ms,
                    "token_estimate": token_estimate,
                    "provider": "Auto routing",
                },
            },
        )
        if not saved_conversation:
            logger.warning(
                "Completed chat response could not be saved conversation=%s user=%s",
                conversation_id,
                user_id,
            )

    if not ODDI_LOCAL_ONLY_STORAGE and not ODDI_BROWSER_LOCAL_CHATS and memory_enabled and memory_auto_extract and memory_message:
        background_tasks.add_task(
            update_user_memory_from_chat,
            str(user_id),
            conversation_history,
            memory_message,
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
