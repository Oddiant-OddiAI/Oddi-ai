"""Grounded, user-facing help about the features in the ODDI application.

Keep this reference aligned with the actual sidebar, Settings page, workspace,
upload pipeline, and chat controls. It is added to a model request only when the
user asks a question about ODDI or one of its in-app features.
"""

from __future__ import annotations

import re


PLATFORM_HELP_REFERENCE = r"""
ODDI PLATFORM HELP REFERENCE (grounded in the current application UI)

Answer questions about ODDI from this reference. Use the user's language and
give a short, concrete navigation path first. Explain a capability only when
relevant. Do not invent controls, data, account state, or completed actions.
If a detail is not listed here or supplied in live context, say you cannot
confirm it and give the closest available path.

SIDEBAR AND CHAT MANAGEMENT
- Open the left sidebar to start a New Chat, search conversations, and open
  recent or pinned conversations. Long-pressing/selecting chats enables bulk
  actions where available.
- In the current sidebar utility list the order is Library, Archive, Settings,
  Memory. Settings is near the bottom of the sidebar, directly above Memory.
  Click Settings (gear icon).
- Chat actions include pin/unpin, rename, archive/unarchive, and move to Bin.
  Archived chats are available from Archive; chats moved to Bin can be restored
  there until permanently removed. Selected chats can be shared, downloaded, or
  moved to Bin together.
- The chat's three-dot menu opens export/share actions. Chat exports include
  document and text formats, JSON backup, copy, and share options shown in the
  export dialog. Explain that the browser/device may determine which share
  targets are available.

SETTINGS
Open sidebar -> Settings. The Settings workspace has these sections:
- Appearance: Light/Dark/System theme, interface language, startup splash
  screen, chat font size, and compact message spacing.
- Personalize: user-message bubble, thinking-indicator, and send-button colors;
  color presets and reset.
- Voice & Response: choose/preview a read-aloud voice, typing animation, and
  browser notifications.
- Data: move all conversations to Bin.
- Privacy: saved consent choices for analytics, training-data use, request
  logging, and crash reporting; a conversation-retention preference; and JSON
  account-data export. Retention expiry is not automated in this deployment,
  and analytics/training/crash-reporting integrations are not configured, so
  never claim those choices currently transmit data.
- Account: profile/avatar, app lock, sign out on this device, and account
  deletion.
- Chat Preference: Enter-to-send behavior, response streaming, token/latency/
  provider indicators, and context-window size (5-50 messages).
- Memory: long-term-memory and automatic-extraction switches, saved-memory
  list/categories, add/edit/delete controls, and clear-all.

MEMORY
- Memory is user-controlled. When long-term Memory is off, saved facts should
  not be sent to the answer model. Automatic extraction also requires its own
  switch to be on. If asked where to manage it: sidebar -> Memory, or Settings
  -> Memory for the controls.
- Automatic extraction is deferred until the account has been inactive for
  about 30 minutes, then saves only useful stable details if the feature and
  memory providers are available. Do not claim a fact was saved unless the app
  confirms it. Users can inspect and edit categories in Memory.

LIBRARY AND FILES
- Library is the user's account-scoped uploaded-file area. To see it: sidebar
  -> Library. ODDI can answer the current file count/list only from a supplied
  live Library inventory. When that inventory is absent or failed, ask the user
  to open/refresh Library; never guess names or counts.
- If the user asks ODDI to read, summarize, analyze, or use a particular Library
  file, use the supplied Library-file context/attachment. If no matching file
  was supplied, ask which listed file they mean. Never claim to have opened or
  read a file without its contents being provided to this request.
- The upload pipeline reads common text/code files, PDF and Office documents,
  images, audio, and video (video is sampled into frames/audio where possible).
  A capable provider must be available for visual/audio inputs, so do not say
  every individual AI provider accepts every file type. The application limit
  is 64 MB per upload; actual extraction can depend on file contents.
- Resume drafts are displayed in a dedicated Resume Draft section when the
  resume builder recognizes one. That section supports formatted copy, edit and
  save, and downloads as PDF by default with Word (.docx), HTML, TXT, and
  Markdown options.

WORKSPACE AND OTHER FEATURES
- Open the top-right three-dot menu -> Workspace & Prompts. Its tabs are
  Projects (group/link chats), Tasks (track next steps and send a task to ODDI),
  Prompt library (use built-in starters or save reusable prompts), and
  Personalize (home cards and preferred answer style).
- ODDI can help with career questions, resumes, job applications, interview
  practice, writing, learning, coding, and analysis of supplied files. It can
  prepare application materials, but do not claim it submitted an application
  or operates an external job tracker unless a live platform action confirms
  that.
- Voice read-aloud is controlled through Voice & Response; microphone/voice
  input availability can depend on browser permissions and device support.

For live user-specific facts (Library entries, saved memories, chat status,
selected theme, login state), trust only the current request's application
context. This reference describes navigation and implemented capabilities; it
does not prove that a particular save, upload, export, or action succeeded.
""".strip()


_PLATFORM_TOPIC = re.compile(
    r"\b(?:setting|settings|sidebar|library|memory|memories|archive|archived|"
    r"bin|workspace|prompt library|conversation|conversations|chat history|"
    r"new chat|pinned chat|upload|uploaded file|export|share chat|resume draft|"
    r"voice|theme|appearance|privacy|account|features?|button|option)\b",
    re.IGNORECASE,
)
_PLATFORM_INTENT = re.compile(
    r"\b(?:where|where's|how|what|which|can i|can you|does|do i|open|find|"
    r"access|use|manage|change|turn on|turn off|count|list|download|share|"
    r"kahan|kaha|kidhar|kaise|kya|konsa|konsi|konse|batao|dikhega|milega|"
    r"karu|karoon|karta|karti|option|button)\b",
    re.IGNORECASE,
)
_PLATFORM_ANCHOR = re.compile(
    r"\b(?:oddi|this app|the app|in-app|platform|inside the app|app mein|"
    r"oddi mein|oddi ka|oddi ke|oddi ki)\b",
    re.IGNORECASE,
)
_GENERIC_CAPABILITY_QUESTIONS = {
    "what can you do",
    "what can i do here",
    "what features do you have",
    "what features does oddi have",
    "what can oddi do",
    "what does oddi do",
    "oddi ke features kya hain",
    "oddi kya kar sakta hai",
    "oddi kya kar sakti hai",
}


def is_platform_help_question(message: object) -> bool:
    """Return True for app-feature/navigation questions that need this guide."""
    text = re.sub(r"\s+", " ", str(message or "")).strip().lower()
    if not text:
        return False
    if text.rstrip("?!., ") in _GENERIC_CAPABILITY_QUESTIONS:
        return True

    has_topic = bool(_PLATFORM_TOPIC.search(text))
    has_intent = bool(_PLATFORM_INTENT.search(text))
    return bool(_PLATFORM_ANCHOR.search(text) and has_topic) or (has_topic and has_intent)


def platform_help_context(message: object) -> str:
    """Return the grounded help guide only for platform-related questions."""
    if not is_platform_help_question(message):
        return ""
    return PLATFORM_HELP_REFERENCE
