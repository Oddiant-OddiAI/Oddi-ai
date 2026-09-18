import base64
import os
import subprocess
import tempfile
import shutil
from app.fast_responses import fast_response, is_job_context_question
from app.memory_handler import (
    is_memory_message,
    remember,
    recall_memory
)
from app.chatbot import get_response
from request_analyzer.analyzer import analyze_request
from providers.adapters import execute_route, ProviderAdapterError
from routing.engine import route_request
from quota.manager import quota_manager
from app.commands import handle_command
from app.prompts import SYSTEM_PROMPT
from pypdf import PdfReader
from openpyxl import load_workbook
from pptx import Presentation
from docx import Document

import cv2
from providers.registry import ProviderRegistry
from app.config import client
from app.database import (
    get_vector_store_id,
    save_vector_store_id,
    save_memory,
    get_memory
)
from app import state
from app.memory_ai import analyze_memory

RESUME_ANALYSIS_TRIGGERS = {
    "analyze my resume",
    "analyse my resume",
    "analyze my cv",
    "analyse my cv",
    "resume analysis",
    "analyze resume",
    "analyse resume",
    "review my resume",
    "review my cv",
}


def is_resume_analysis_request(message):
    if not message:
        return False

    text = message.lower().strip()

    return text in RESUME_ANALYSIS_TRIGGERS

def extract_docx_text(uploaded_file):
    document = Document(uploaded_file)

    text = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text.append(paragraph.text.strip())

    # Also read tables because resumes often contain
    # skills, education, experience, etc. inside tables.
    for table in document.tables:

        for row in table.rows:

            cells = []

            for cell in row.cells:
                value = cell.text.strip()

                if value:
                    cells.append(value)

            if cells:
                text.append(" | ".join(cells))

    return "\n".join(text)
def transcribe_audio(audio_file):
    """
    Transcribe an uploaded audio file using OpenAI's audio transcription API.
    """
    audio_file.seek(0)

    transcription = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=audio_file
    )

    return transcription.text

RESUME_ANALYSIS_PROMPT = """
You are Oddi AI's Resume Intelligence system.

The user has uploaded a resume and explicitly asked you to analyze it.

Analyze ONLY the resume content provided in the attached document.
Do not invent education, experience, projects, skills, achievements, certifications,
or other information that is not present.

Give the user a practical and honest resume review.

Your response MUST use this structure:

# 📄 Resume Analysis

## Overall Score
Give a score out of 100.

## ATS Score
Give an estimated ATS-readiness score out of 100.
Explain briefly what affects the score.

## 👤 Profile
Summarize the candidate's profile based only on the resume.

## 🎓 Education
Summarize the education shown in the resume.

## 💻 Technical Skills
List the technical skills actually present.

## 🚀 Projects
List and briefly evaluate the projects shown.

## 💼 Experience
Summarize internships, jobs, training, or other experience shown.

If no experience is present, clearly say so.

## ✅ Strengths
Give the strongest aspects of the resume.

## ⚠️ Weaknesses
Give specific weaknesses or areas that reduce its effectiveness.

## ❌ Missing / Recommended Sections
Mention important sections that appear to be missing.
Do not claim a section is missing if it is actually present.

## 🎯 Suitable Roles
Suggest suitable job roles based only on the candidate's demonstrated
education, skills, projects, and experience.

## 📈 Recommended Improvements
Give specific, actionable improvements.
Prioritize the most important changes first.

## 📝 Final Verdict
Give a concise overall assessment.

IMPORTANT RULES:

- Do not invent information.
- Do not change the candidate's facts.
- Do not judge the candidate's personality or appearance.
- Do not make unrealistic promises about getting a job.
- Scores are estimates, not official ATS scores.
- Be honest but constructive.
- Prefer specific feedback over generic advice.
- Keep the report readable and well formatted.
"""


MAX_KNOWLEDGE_FILES = 21
KNOWLEDGE_BASE_EXTENSIONS = (
    ".txt",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
)

def get_or_create_vector_store(user_id):

    if not user_id:
        return None

    vector_store_id = get_vector_store_id(user_id)

    if vector_store_id:
        return vector_store_id

    vector_store = client.vector_stores.create(
        name=f"Oddi AI User {user_id} Knowledge"
    )

    save_vector_store_id(
        user_id,
        vector_store.id
    )

    print(
        f"Created knowledge base for user {user_id}: "
        f"{vector_store.id}"
    )

    return vector_store.id


def get_knowledge_file_count(vector_store_id):

    files = client.vector_stores.files.list(
        vector_store_id=vector_store_id
    )

    return len(files.data)
def add_file_to_knowledge_base(
    uploaded_file,
    vector_store_id
):

    if not vector_store_id:
        return None

    uploaded_file.stream.seek(0)

    print(
        f"Uploading to knowledge base: "
        f"{uploaded_file.filename}"
    )

    openai_file = None

    try:

        openai_file = client.files.create(
            file=(
                uploaded_file.filename,
                uploaded_file.stream,
                uploaded_file.mimetype
            ),
            purpose="assistants"
        )

        print(
                f"OpenAI file created: "
            f"{openai_file.id}"
        )

        vector_file = (
            client.vector_stores.files.create_and_poll(
                vector_store_id=vector_store_id,
                file_id=openai_file.id
            )
        )

        if vector_file.status != "completed":

            print(
                f"Knowledge indexing failed: "
                f"{vector_file.status}"
            )

            return None

        print(
            f"Indexed successfully: "
            f"{uploaded_file.filename}"
        )

        return openai_file.id

    except Exception:

        if openai_file is not None:

            try:
                client.files.delete(
                    openai_file.id
                )

            except Exception as cleanup_error:

                print(
                    "OpenAI file cleanup failed:",
                    cleanup_error
                )

        raise


PROVIDER_UNAVAILABLE_RESPONSE = (
    "⚠️ ODDI-AI providers are unavailable right now."
)


def _build_routing_prompt(chat_history, documents=""):
    """Build a provider-neutral text prompt for the routing adapters."""
    lines = ["Conversation:"]

    if isinstance(chat_history, list):
        for item in chat_history:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content", "")

            if role not in ("user", "assistant"):
                continue

            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if text:
                            text_parts.append(str(text))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = " ".join(text_parts)

            if content:
                lines.append(
                    f"{role.capitalize()}: {content}"
                )
    else:
        lines.append(str(chat_history or ""))

    if documents:
        lines.extend([
            "",
            "ATTACHED DOCUMENT CONTENT:",
            documents,
        ])

    return "\n".join(lines)



def _resolve_phase6_user_context(
    user_id,
    user_role=None,
    user_priority=None,
    is_host=False,
    quota_exempt=False,
):
    """
    Resolve already-authenticated user context for Phase 6.

    Authentication and identity resolution remain outside app.engine.
    The trusted caller may supply role, priority and host/exemption
    information. Ordinary users default to the normal user policy.
    """

    return {
        "user_id": (
            str(user_id).strip()
            if user_id is not None
            else None
        ),
        "user_role": (
            str(user_role).strip().lower()
            if user_role
            else "user"
        ),
        "user_priority": user_priority,
        "is_host": bool(is_host),
        "quota_exempt": bool(quota_exempt),
    }


def _extract_execution_tokens(
    execution,
    provider_prompt,
    response,
):
    """
    Extract provider-reported token usage when available.

    If the adapter does not expose token metadata, use a conservative
    local estimate so user token accounting never silently records zero.
    """

    execution = (
        execution
        if isinstance(execution, dict)
        else {}
    )

    usage = execution.get("usage")

    if isinstance(usage, dict):
        for key in (
            "total_tokens",
            "total",
        ):
            value = usage.get(key)
            try:
                if value is not None and int(value) >= 0:
                    return int(value)
            except (TypeError, ValueError):
                pass

        input_tokens = usage.get(
            "prompt_tokens",
            usage.get("input_tokens"),
        )
        output_tokens = usage.get(
            "completion_tokens",
            usage.get("output_tokens"),
        )

        if (
            input_tokens is not None
            or output_tokens is not None
        ):
            try:
                total = (
                    int(input_tokens or 0)
                    + int(output_tokens or 0)
                )
                if total >= 0:
                    return total
            except (TypeError, ValueError):
                pass

    for key in (
        "total_tokens",
        "tokens",
    ):
        value = execution.get(key)
        try:
            if value is not None and int(value) >= 0:
                return int(value)
        except (TypeError, ValueError):
            pass

    # Fallback estimate: approximately 4 characters/token.
    source_text = (
        str(provider_prompt or "")
        + "\n"
        + str(response or "")
    )

    return max(
        1,
        (len(source_text) + 3) // 4,
    )


def _phase6_user_quota_gate(
    user_context,
    estimated_tokens=0,
):
    """Check user quota before provider routing."""

    user_id = user_context.get("user_id")

    # Preserve compatibility for internal/legacy calls that do not
    # carry an authenticated user identity.
    if not user_id:
        return {
            "checked": False,
            "allowed": True,
            "reason": (
                "No user_id supplied; user quota gate skipped "
                "for an internal/legacy call."
            ),
        }

    try:
        estimated_tokens = int(
            estimated_tokens or 0
        )
    except (TypeError, ValueError):
        estimated_tokens = 0

    if estimated_tokens < 0:
        estimated_tokens = 0

    allowed = quota_manager.has_user_quota(
        user_id=user_id,
        role=user_context["user_role"],
        priority=user_context["user_priority"],
        is_host=user_context["is_host"],
        quota_exempt=user_context["quota_exempt"],
        requests=1,
        tokens=estimated_tokens,
    )

    status = quota_manager.user_quota_status(
        user_id=user_id,
        role=user_context["user_role"],
        priority=user_context["user_priority"],
        is_host=user_context["is_host"],
        quota_exempt=user_context["quota_exempt"],
    )

    return {
        "checked": True,
        "allowed": bool(allowed),
        "status": status,
        "reason": (
            "User quota available."
            if allowed
            else "User quota exhausted or fair-use limit reached."
        ),
    }


def _phase6_quota_rejection(quota_result):
    """Build the user-facing Phase 6 quota rejection."""

    status = quota_result.get(
        "status",
        {},
    )

    exhausted = status.get(
        "exhausted_dimensions",
        [],
    )

    if exhausted:
        dimensions = ", ".join(
            str(item)
            for item in exhausted
        )
        return (
            "⚠️ **ODDI-AI usage limit reached.**\n\n"
            f"Limit reached: `{dimensions}`.\n\n"
            "Please try again after the applicable limit resets."
        )

    return (
        "⚠️ **ODDI-AI usage limit reached.**\n\n"
        "Your current AI request allowance is exhausted. "
        "Please try again after the applicable limit resets."
    )


def _phase6_record_success(
    user_context,
    execution,
    provider_prompt,
    response,
):
    """Record one successfully completed provider request."""

    user_id = user_context.get("user_id")

    if not user_id:
        return None

    tokens = _extract_execution_tokens(
        execution,
        provider_prompt,
        response,
    )

    return quota_manager.record_user_request(
        user_id=user_id,
        tokens=tokens,
        role=user_context["user_role"],
        priority=user_context["user_priority"],
        is_host=user_context["is_host"],
        quota_exempt=user_context["quota_exempt"],
    )


def process_message(
    user_message,
    uploaded_files=None,
    conversation_history=None,
    user_id=None,
    user_role=None,
    user_priority=None,
    is_host=False,
    quota_exempt=False
):
    if user_id is not None:
        user_id = str(user_id)

    # ==========================================
    # PHASE 6 — USER LIMIT / FAIR-USE CONTEXT
    # ==========================================
    user_context = _resolve_phase6_user_context(
        user_id=user_id,
        user_role=user_role,
        user_priority=user_priority,
        is_host=is_host,
        quota_exempt=quota_exempt,
    )
        # ==========================================
    # PERSISTENT USER KNOWLEDGE
    # ==========================================

    vector_store_id = None

    # Keep the user's persistent vector-store ID available to the
    # response layer, but do NOT automatically index normal chat
    # attachments here. Attachments must go through the local
    # extraction/vision pipeline below first.
    if user_id is not None:
        # Read an existing vector-store ID only. Do not create an OpenAI
        # vector store during every chat request.
        vector_store_id = get_vector_store_id(user_id)

    if uploaded_files:
        uploaded_file = uploaded_files[0]
    else:
        uploaded_file = None

    if uploaded_file:
            print("Engine received:", uploaded_file.filename)

    images = []
    documents = ""

    # Audio/video information
    media_transcripts = ""
    video_frames = []
    
    if uploaded_files:

        for uploaded_file in uploaded_files:

            filename = uploaded_file.filename.lower()
            print("Filename:", filename)
            print("Mimetype:", uploaded_file.mimetype)     
            print("Reached ChatGPT section")
            print("Images:", len(images))
            print("Documents length:", len(documents))


            # ---------- IMAGE ----------
            if filename.endswith((".png", ".jpg", ".jpeg", ".webp")):

                image_bytes = uploaded_file.read()

                images.append({
                    "bytes": image_bytes,
                    "mimetype": uploaded_file.mimetype
                })

                print("Image detected")
                print("Image size:", len(image_bytes))
                print("IMAGE BLOCK")
                        # ---------- AUDIO ----------
            elif filename.endswith((
                ".mp3",
                ".wav",
                ".m4a",
                ".aac",
                ".ogg",
                ".flac"
            )):

                print("Audio detected")

                transcript = transcribe_audio(uploaded_file)

                media_transcripts += (
                    "\n\n===== AUDIO: "
                    + uploaded_file.filename
                    + " =====\n"
                )

                media_transcripts += transcript

                print("Audio transcription completed")
                print("AUDIO BLOCK")

                        # ---------- VIDEO ----------
            elif filename.endswith((
                ".mp4",
                ".mov",
                ".avi",
                ".mkv",
                ".webm"
            )):

                print("Video detected")

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=os.path.splitext(filename)[1]
                ) as temp_video:

                    uploaded_file.save(temp_video.name)
                    video_path = temp_video.name

                try:
                    # ---------- EXTRACT AUDIO ----------
                    audio_path = video_path + ".wav"

                    ffmpeg_result = subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            video_path,
                            "-vn",
                            "-ac",
                            "1",
                            "-ar",
                            "16000",
                            audio_path
                        ],
                        capture_output=True,
                        text=True
                    )

                    if ffmpeg_result.returncode != 0:

                        print(
                            "FFmpeg error:",
                            ffmpeg_result.stderr
                        )

                        raise RuntimeError(
                            "FFmpeg could not extract audio "
                            "from the video."
                        )

                    if os.path.exists(audio_path):

                        with open(audio_path, "rb") as audio_file:

                            transcript = transcribe_audio(audio_file)

                        media_transcripts += (
                            "\n\n===== VIDEO AUDIO: "
                            + uploaded_file.filename
                            + " =====\n"
                        )

                        media_transcripts += transcript

                    # ---------- EXTRACT VIDEO FRAMES ----------
                    cap = cv2.VideoCapture(video_path)

                    total_frames = int(
                        cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    )

                    fps = cap.get(cv2.CAP_PROP_FPS)

                    if fps <= 0:
                        fps = 25

                    duration = total_frames / fps

                    # Maximum 8 representative frames
                    # Extract representative frames across the ENTIRE video
                    # Maximum 12 frames so the AI can understand the video progression.
                    frame_count = min(12, max(2, int(duration) + 1))

                    for i in range(frame_count):
                        if frame_count == 1:
                            timestamp = 0
                        else:
                            timestamp = (
                                duration * i / (frame_count - 1)
                            )

                        cap.set(
                            cv2.CAP_PROP_POS_MSEC,
                            timestamp * 1000
                        )

                        success, frame = cap.read()

                        if not success:
                            continue

                        success, encoded = cv2.imencode(
                            ".jpg",
                            frame
                        )

                        if success:
                            video_frames.append({
                                "bytes": encoded.tobytes(),
                                "mimetype": "image/jpeg",
                                "timestamp": timestamp
                            })

                    cap.release()

                    print(
                        "Video processing completed:",
                        len(video_frames),
                        "frames"
                    )

                finally:

                    if os.path.exists(video_path):
                        os.remove(video_path)

                    if os.path.exists(audio_path):
                        os.remove(audio_path)

                print("VIDEO BLOCK")
            # ---------- TXT ----------
            elif filename.endswith(".txt"):

                documents += "\n\n===== " + uploaded_file.filename + " =====\n"
                documents += uploaded_file.read().decode("utf-8")

                print("TXT detected")
                print(documents[:200])
                print("TXT BLOCK")

                    # ---------- DOCX ----------
            elif filename.endswith(".docx"):

                print("DOCX detected")

                documents += (
                    "\n\n===== "
                    + uploaded_file.filename
                    + " =====\n"
                )

                docx_text = extract_docx_text(uploaded_file)

                documents += docx_text

                print("DOCX extracted")
                print(documents[:500])
                print("DOCX BLOCK")
            # ---------- PDF ----------
            elif filename.endswith(".pdf"):

                print("PDF detected - using local pypdf extraction (not Knowledge Base retrieval).")

                reader = PdfReader(uploaded_file)

                documents += "\n\n===== " + uploaded_file.filename + " =====\n"

                for page in reader.pages:
                    page_text = page.extract_text()

                    if page_text:
                        documents += page_text + "\n"

                print("PDF detected")
                print(documents[:200])
                print("PDF BLOCK")
            # ---------- EXCEL ----------
            elif filename.endswith(".xlsx"):

                workbook = load_workbook(uploaded_file)

                sheet = workbook.active

                documents += "\n\n===== " + uploaded_file.filename + " =====\n"

                for row in sheet.iter_rows(values_only=True):

                    line = " | ".join(str(cell) if cell is not None else "" for cell in row)

                    documents += line + "\n"

                print("EXCEL detected")
                print(documents[:300])
                print("EXCEL BLOCK")

            elif filename.endswith((".pptx", ".ppt")):

                print("PowerPoint detected - using local python-pptx extraction.")

                with tempfile.TemporaryDirectory() as temp_dir:

                    input_path = os.path.join(
                        temp_dir,
                        uploaded_file.filename
                    )

                    uploaded_file.save(input_path)

                    # Convert old .ppt files to .pptx using LibreOffice
                    if filename.endswith(".ppt"):

                        print("Converting .ppt to .pptx using LibreOffice...")

                        soffice_path = shutil.which("soffice")

                        if not soffice_path:
                            soffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"

                        if not os.path.exists(soffice_path):
                            raise RuntimeError(
                                "LibreOffice was installed, but soffice.exe could not be found."
                            )

                        result = subprocess.run(
                            [
                                soffice_path,
                                "--headless",
                                "--convert-to",
                                "pptx",
                                "--outdir",
                                temp_dir,
                                input_path
                            ],
                            capture_output=True,
                            text=True
                        )

                        print("LibreOffice output:")
                        print(result.stdout)
                        print(result.stderr)

                        converted_path = os.path.join(
                            temp_dir,
                            os.path.splitext(
                                uploaded_file.filename
                            )[0] + ".pptx"
                        )

                        if not os.path.exists(converted_path):

                            raise RuntimeError(
                                "LibreOffice could not convert the PowerPoint file."
                            )

                        presentation = Presentation(converted_path)

                    else:

                        presentation = Presentation(input_path)

                    documents += (
                        "\n\n===== "
                        + uploaded_file.filename
                        + " =====\n"
                    )

                    for slide_number, slide in enumerate(
                        presentation.slides,
                        start=1
                    ):

                        documents += (
                            f"\n--- Slide {slide_number} ---\n"
                        )

                        for shape in slide.shapes:

                            if hasattr(shape, "text") and shape.text.strip():

                                documents += (
                                    shape.text.strip()
                                    + "\n"
                                )

                    print("POWERPOINT detected")
                    print(documents[:500])
                    print("POWERPOINT BLOCK")
            else:

                print("Unsupported file:", filename)

            # ---------- POWERPOINT ----------

    # ==========================================
    # 2. GROQ MEMORY AI
    # ==========================================
    # Run Memory AI BEFORE fast responses so that short/direct replies
    # can also create memories in real time.
    memory_notice = ""

    if user_id is not None:
        try:
            memory_result = analyze_memory(user_message)

            # memory_ai.py may return either a dict or a JSON string.
            if isinstance(memory_result, str):
                import json
                memory_result = json.loads(memory_result)

            if (
                isinstance(memory_result, dict)
                and memory_result.get("action") == "ADD"
            ):
                memory_key = memory_result.get("category", "").strip()
                memory_value = memory_result.get("memory", "").strip()

                if memory_key and memory_value:
                    save_memory(
                        user_id,
                        memory_key,
                        memory_value
                    )

                    memory_notice = "🧠 Memory Saved!"

                    print(
                        f"🧠 Memory AI saved for user {user_id}: "
                        f"[{memory_key}] {memory_value}"
                    )

        except Exception as memory_error:
            # A Memory AI/API failure must not break normal ODDI chat.
            print("⚠️ Memory AI error:", memory_error)

    # 2. Fast Responses
    if not uploaded_files:

        fast_reply = fast_response(user_message)

        if fast_reply:
            if memory_notice:
                return fast_reply + "\n\n" + memory_notice
            return fast_reply


    # Job-context follow-up questions must still work
    # even when job files are uploaded.
    if uploaded_files:

        if is_job_context_question(user_message):

            fast_reply = fast_response(user_message, message)

            if fast_reply:
                return fast_reply
    # 2.5 Resume Intelligence
    resume_analysis = is_resume_analysis_request(user_message)
    
    if resume_analysis:

        if not uploaded_files:
            return (
                "📄 **Resume Analysis**\n\n"
                "Please attach your resume first.\n\n"
                "I can analyze **PDF, DOCX, or TXT** resume files."
            )

        if not documents:
            return (
                "⚠️ I received the file, but I couldn't extract readable "
                "resume text from it.\n\n"
                "Please try a PDF, DOCX, or TXT version of your resume."
            )

        user_message = RESUME_ANALYSIS_PROMPT + """

    Here is the extracted resume content:

    """ + documents

    # 1. Commands
    command_reply = handle_command(user_message)
    if command_reply:
        return command_reply


    if user_id is not None:

        if user_id is not None and state.pending_update:
            pending = state.pending_update

            # Make sure this pending update belongs to this user
            if pending.get("user_id") == user_id:

                confirmation = user_message.strip().lower()

                if confirmation in ("y", "yes"):
                    save_memory(
                        user_id,
                        pending["key"],
                        pending["new"]
                    )

                    state.pending_update = None

                    return (
                        f"✅ Updated! I'll remember your "
                        f"{pending['key'].replace('_', ' ')} "
                        f"is '{pending['new']}'."
                    )

                elif confirmation in ("n", "no"):
                    state.pending_update = None

                    return (
                        f"👍 Okay, I'll keep your "
                        f"{pending['key'].replace('_', ' ')} "
                        f"as '{pending['old']}'."
                    )
                memory_reply = recall_memory(user_message, user_id)

                if memory_reply:
                    return memory_reply


    # ==========================================
    # 5. LOAD CURRENT USER'S SAVED MEMORIES
    # ==========================================
    user_memories = {}

    if user_id is not None:
        try:
            user_memories = get_memory(user_id) or {}
        except Exception as memory_load_error:
            print("⚠️ Could not load user memories:", memory_load_error)

    memory_context = ""

    if user_memories:
        memory_lines = [
            "ODDI USER MEMORY",
            "",
            "The following are saved facts about the current user.",
            "Use them naturally when relevant.",
            "Do not mention the memory system unless the user asks.",
            "Do not invent memories that are not listed.",
            ""
        ]

        for key, value in user_memories.items():
            memory_lines.append(f"- {key}: {value}")

        memory_context = "\n".join(memory_lines)

    # ==========================================
    # 6. MAIN ODDI MESSAGE
    # ==========================================
    current_user_text = user_message

    if memory_context:
        current_user_text = (
            memory_context
            + "\n\nCURRENT USER MESSAGE:\n"
            + user_message
        )

    content = [
        {
            "type": "input_text",
            "text": current_user_text
        }
    ]
    if media_transcripts:

        content.append({
            "type": "input_text",
            "text": f"""
    Attached audio/video transcription:

    {media_transcripts}

    Use this transcription when answering questions
    about the uploaded audio or video.
    """
        })

    # Add extracted video frames
    # Add extracted video frames in chronological order
    if video_frames:
        content.append({
            "type": "input_text",
            "text": (
                "IMPORTANT VIDEO ANALYSIS INSTRUCTION:\n"
                "The following images are chronological frames extracted "
                "from ONE uploaded video.\n"
                "Analyze ALL frames together, from the first frame to the "
                "last frame.\n"
                "Do NOT answer based only on the first frame.\n"
                "Use the progression between frames to determine what "
                "happens during the video from beginning to end.\n"
                "When describing actions or changes, consider the order "
                "and timestamps of the frames."
            )
        })

    for frame in video_frames:
        frame_base64 = base64.b64encode(
            frame["bytes"]
        ).decode("utf-8")

        content.append({
            "type": "input_text",
            "text": (
                f"VIDEO FRAME — {frame['timestamp']:.2f} seconds "
                f"from the beginning"
            )
        })

        content.append({
            "type": "input_image",
            "image_url":
            f"data:{frame['mimetype']};base64,{frame_base64}"
        })


    for image in images:
        print("Building content...")
        image_base64 = base64.b64encode(
            image["bytes"]
        ).decode("utf-8")

        content.append({
            "type": "input_image",
            "image_url":
            f"data:{image['mimetype']};base64,{image_base64}"
        })

    if documents:

        content.append({
            "type":"input_text",
            "text":f"""
    Attached documents:

    {documents}
    """
        })
    print("Creating content...")

    chat_history = []

    if conversation_history:

        for message in conversation_history:

            role = message.get("role")
            text = message.get("text", "")

            if role not in ("user", "assistant"):
                continue

            if not text:
                continue

            chat_history.append({
                "role": role,
                "content": text
            })
    if not chat_history or chat_history[-1]["role"] != "user":
        chat_history.append({
            "role": "user",
            "content": content
        })
    else:
        # Replace the current user's plain text entry
        # with the richer content containing files.
        chat_history[-1] = {
            "role": "user",
            "content": content
        }

    chat_history = chat_history[-100:]

    print("Chat history created")
    print("Messages in memory:", len(chat_history))
    print("Images:", len(images))
    print("Documents:", len(documents))

    # ==========================================================
    # PHASE 6 — USER QUOTA GATE
    # ==========================================================
    #
    # Local command/fast-response paths above do not consume the
    # provider AI allowance. This gate protects the actual provider
    # routing pipeline.
    estimated_input_tokens = max(
        0,
        (len(str(user_message or "")) + 3) // 4,
    )

    phase6_quota = _phase6_user_quota_gate(
        user_context=user_context,
        estimated_tokens=estimated_input_tokens,
    )

    if not phase6_quota["allowed"]:
        print(
            "⚠️ Phase 6 user quota rejected request:",
            user_context.get("user_id"),
        )
        return _phase6_quota_rejection(
            phase6_quota
        )

    # ==========================================================
    # MAIN PROVIDER ROUTING
    # ==========================================================
    #
    # Normal text and locally-extracted document/resume requests go
    # through the Phase 2 -> Phase 3 -> Phase 4 pipeline.
    #
    # Gemini Key 1 is explicitly preferred, then Gemini Key 2,
    # followed by the remaining provider fallback chain.
    #
    # Image/video/audio/web requests that need provider-native
    # capabilities remain on the existing specialized path for now.
    #
    request_for_routing = analyze_request(
        user_message,
        uploaded_files=(
            uploaded_files
            if documents
            else []
        ),
        images=images,
        video_frames=video_frames,
    )

    request_for_routing["user_id"] = user_context.get(
        "user_id"
    )
    request_for_routing["user_role"] = user_context.get(
        "user_role",
        "user",
    )
    request_for_routing["user_priority"] = user_context.get(
        "user_priority"
    )
    request_for_routing["is_host"] = user_context.get(
        "is_host",
        False,
    )
    request_for_routing["quota_exempt"] = user_context.get(
        "quota_exempt",
        False,
    )
    request_for_routing["estimated_tokens"] = estimated_input_tokens

    requires_special_provider_capability = any(
        (
            request_for_routing.get("requires_web", False),
            request_for_routing.get("requires_image", False),
            request_for_routing.get("requires_video", False),
        )
    )

    if requires_special_provider_capability:
        print(
            "⚠️ Specialized capability request: "
            "using existing capability handler."
        )

        response = get_response(
            chat_history,
            vector_store_id,
            user_id=user_id
        )

        if memory_notice:
            return response + "\n\n" + memory_notice

        return response

    try:
        route = route_request(request_for_routing)

        if route.get("status") != "routed":
            raise ProviderAdapterError(
                route.get("reason", "No provider route available.")
            )

        candidates = list(route.get("candidates", []))

        # Explicit provider policy:
        #   1. GEMINI_API_KEY
        #   2. GEMINI_API_KEY_2
        #   3. Mistral
        #   4. Cloudflare
        #   5. Groq
        #
        # Keep the routing engine responsible for eligibility, quota,
        # health and capability checks; only apply the requested
        # deterministic priority among eligible candidates.
        provider_order = {
            "gemini": 0,
            "mistral": 1,
            "cloudflare": 2,
            "groq": 3,
        }
        gemini_key_order = {
            "gemini_key_1": 0,
            "gemini_key_2": 1,
        }

        candidates.sort(
            key=lambda candidate: (
                provider_order.get(candidate.get("provider"), 99),
                gemini_key_order.get(
                    candidate.get("capacity_id"),
                    99,
                ),
            )
        )

        route["candidates"] = candidates

        if candidates:
            print(
                "🎯 Route candidates: "
                + " -> ".join(
                    (
                        f"{candidate.get('provider')}/"
                        f"{candidate.get('model')}/"
                        f"{candidate.get('capacity_id')}"
                    )
                    for candidate in candidates
                )
            )

        provider_prompt = (
            SYSTEM_PROMPT
            + "\n\n"
            + _build_routing_prompt(
                chat_history,
                documents=documents,
            )
        )

        execution = execute_route(
            route,
            provider_prompt,
        )

        response = execution.get("response")

        if not response or not str(response).strip():
            raise ProviderAdapterError(
                "Selected provider returned an empty response."
            )

        # ======================================================
        # PHASE 6 — RECORD SUCCESSFUL USER USAGE
        # ======================================================
        # Only successful provider execution consumes the user's
        # daily request allowance.
        phase6_usage = _phase6_record_success(
            user_context=user_context,
            execution=execution,
            provider_prompt=provider_prompt,
            response=response,
        )

        if phase6_usage is not None:
            print(
                "📊 Phase 6 user usage recorded:",
                f"user={user_context.get('user_id')}",
                f"requests={phase6_usage.get('requests')}",
                f"tokens={phase6_usage.get('tokens')}",
            )

        print(
            f"✅ ODDI-AI routed to "
            f"{execution['provider']}/"
            f"{execution['model']}"
        )

        if execution.get("capacity_id"):
            print(
                f"📦 Capacity: "
                f"{execution['capacity_id']}"
            )

        if memory_notice:
            response = response + "\n\n" + memory_notice

        return response

    except Exception as routing_error:
        # Do not silently jump back to OpenAI. OpenAI is not part of
        # the primary ODDI provider chain.
        print("⚠️ Routed providers failed:", routing_error)

        # Final non-OpenAI fallback: Groq.
        try:
            from providers.adapters import call_groq

            fallback_prompt = (
                SYSTEM_PROMPT
                + "\n\n"
                + _build_routing_prompt(
                    chat_history,
                    documents=documents,
                )
            )

            response = call_groq(
                fallback_prompt,
                model="openai/gpt-oss-120b",
            )

            # Successful final fallback is still a successful AI
            # request and must be counted once for Phase 6.
            phase6_usage = _phase6_record_success(
                user_context=user_context,
                execution={
                    "provider": "groq",
                    "model": "openai/gpt-oss-120b",
                },
                provider_prompt=fallback_prompt,
                response=response,
            )

            if phase6_usage is not None:
                print(
                    "📊 Phase 6 user usage recorded:",
                    f"user={user_context.get('user_id')}",
                    f"requests={phase6_usage.get('requests')}",
                    f"tokens={phase6_usage.get('tokens')}",
                )

            print("✅ Using Groq final fallback.")

            if memory_notice:
                response = response + "\n\n" + memory_notice

            return response

        except Exception as groq_error:
            print("❌ Groq final fallback failed:", groq_error)

            if memory_notice:
                return (
                    PROVIDER_UNAVAILABLE_RESPONSE
                    + "\n\n"
                    + memory_notice
                )

            return PROVIDER_UNAVAILABLE_RESPONSE
