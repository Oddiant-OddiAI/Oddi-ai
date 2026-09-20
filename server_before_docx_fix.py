import io
import json
import logging
import os
import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
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

from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth

from werkzeug.security import generate_password_hash, check_password_hash
from app.database import (
    create_tables,
    create_user,
    get_user_by_email,
    create_conversation,
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
    update_file_record,
    get_files,
    get_file,
    delete_file_record,
)

from app.engine import process_message
from app.storage import (
    storage_router,
    StorageQuotaExceeded,
    FileNotFound as StorageFileNotFound,
)


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oddi.persistence")


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="ODDI AI",
    version="1.0.0",
)

# Flask's signed session cookie is replaced by Starlette's signed session
# middleware. The 30-day lifetime and the important cookie protections are
# preserved from the old Flask server.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv(
        "FLASK_SECRET_KEY",
        "Oddi-AI_AI_2026_SuperSecretKey",
    ),
    max_age=int(timedelta(days=30).total_seconds()),
    same_site="lax",
    https_only=False,
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


# Initialize the existing database exactly as before.
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


def set_user_session(request: Request, user, auth_provider=None):
    """Store the same user identity fields used by the old Flask server."""
    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    request.session["email"] = user["email"]

    if auth_provider:
        request.session["auth_provider"] = auth_provider


def require_user_id(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return user_id


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

    def close(self):
        return self.stream.close()


def adapt_uploaded_files(uploaded_files):
    return [UploadedFileAdapter(upload) for upload in uploaded_files]


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
    # ODDI is a private authenticated application.
    # A visitor with no valid session must sign in before the main app is
    # rendered. Existing authenticated sessions continue straight to ODDI.
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    response = render_template(
        request,
        "index.html",
        logged_in=True,
        username=request.session.get("username"),
        user_id=request.session.get("user_id"),
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

    return JSONResponse(
        {
            "authenticated": True,
            "user": {
                "id": request.session.get("user_id"),
                "name": request.session.get("username"),
                "email": request.session.get("email"),
            },
            "auth_provider": request.session.get("auth_provider", "password"),
        }
    )


@app.post("/api/auth/logout", name="api_logout")
def api_logout(request: Request):
    request.session.clear()
    return JSONResponse({"success": True})


# =========================================================
# CONVERSATIONS
# =========================================================

@app.get("/api/conversations", name="api_get_conversations")
def api_get_conversations(request: Request):
    logger.info(
        "HTTP GET /api/conversations pid=%s user=%s",
        os.getpid(),
        request.session.get("user_id"),
    )
    user_id = require_user_id(request)
    return JSONResponse(content=jsonable_encoder(get_conversations(user_id)))


@app.post("/api/conversations", name="api_create_conversation")
async def api_create_conversation(request: Request):
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


@app.get("/api/conversations/bin", name="api_get_deleted_conversations")
def api_get_deleted_conversations(request: Request):
    user_id = require_user_id(request)
    return JSONResponse(content=jsonable_encoder(get_deleted_conversations(user_id)))


@app.put("/api/conversations/{conversation_id}/metadata", name="api_update_conversation_metadata")
async def api_update_conversation_metadata(request: Request, conversation_id: int):
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

@app.get("/api/memory", name="api_get_memory")
def api_get_memory(request: Request):
    user_id = require_user_id(request)
    memories = get_memory(user_id) or {}

    return JSONResponse(
        {
            "memories": [
                {"category": key, "memory": value}
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

    existing = get_memory(user_id, key)
    if existing is None:
        return JSONResponse({"error": "Memory not found."}, status_code=404)

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

@app.post("/chat", name="chat")
async def chat(request: Request):
    form = await request.form()

    message = form.get("message")
    if message is None:
        return JSONResponse({"error": "Message is required."}, status_code=400)
    message = str(message)

    raw_conversation_id = form.get("conversation_id")
    try:
        conversation_id = int(raw_conversation_id) if raw_conversation_id else None
    except (TypeError, ValueError):
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

    # Store the actual uploaded bytes through the Storage Router.
    # PostgreSQL keeps metadata/references only for new uploads.
    file_record_ids = []
    stored_file_keys = []

    if engine_files:
        file_payloads = []

        try:
            total_upload_bytes = 0

            for uploaded_file in engine_files:
                uploaded_file.stream.seek(0)
                file_bytes = uploaded_file.stream.read()
                uploaded_file.stream.seek(0)

                file_payloads.append(
                    (uploaded_file, file_bytes)
                )
                total_upload_bytes += len(file_bytes)

            # Check the complete batch before writing anything so a request
            # cannot partially consume the user's quota.  The Storage Router
            # exposes quota information directly; do not reach into its
            # internal FileStorage object here.
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
                        uploaded_file.filename
                        or "unnamed-file"
                    ),
                )

                storage_key = stored["storage_key"]
                stored_file_keys.append(storage_key)

                try:
                    file_record_id = register_file(
                        user_id=user_id,
                        filename=(
                            uploaded_file.filename
                            or "unnamed-file"
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
                    try:
                        storage_router.delete_file(
                            user_id,
                            storage_key,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to roll back physical file %s",
                            storage_key,
                        )

                    logger.warning(
                        "File metadata save failed: %s",
                        file_db_error,
                    )

            # Rewind every upload so the existing engine receives the same
            # file stream it received before the storage migration.
            for uploaded_file, _ in file_payloads:
                uploaded_file.stream.seek(0)

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

            for storage_key in stored_file_keys:
                try:
                    storage_router.delete_file(
                        user_id,
                        storage_key,
                    )
                except Exception:
                    logger.exception(
                        "Failed to roll back physical file %s",
                        storage_key,
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

    if engine_files:
        logger.info("Files received: %s", [f.filename for f in engine_files])
    else:
        logger.info("No files uploaded")

    # Chat is also private: do not allow unauthenticated access to the
    # underlying AI engine even if someone calls /chat directly.
    user_id = require_user_id(request)

    reply = process_message(
        message,
        engine_files,
        conversation_history,
        user_id,
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

    return response_from_engine(reply)


# =========================================================
# DEVELOPMENT ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
