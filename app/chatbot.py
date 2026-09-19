from app.config import client, groq_client
from app.prompts import SYSTEM_PROMPT

from limits.user_limits import UserLimitManager

from providers.adapters import (
    execute_route,
    ProviderAdapterError,
)

# Primary AI provider priority is controlled by the routing engine.
# Gemini capacity 1 (GEMINI_API_KEY) is the first Gemini pool,
# followed by the other configured capacities/providers.

from request_analyzer.analyzer import analyze_request


# ==========================================
# PHASE 6 — USER LIMIT MANAGER
# ==========================================

user_limit_manager = UserLimitManager()

# Conservative output allowance used when checking whether
# a request can fit inside the user's remaining daily quota.
#
# Provider adapters currently return plain text rather than
# provider-native token usage metadata, so we use an estimate.
ESTIMATED_OUTPUT_TOKEN_BUFFER = 1000

USER_QUOTA_ERROR = (
    "⚠️ You have reached your daily ODDI-AI "
    "usage limit of 5,000 tokens. "
    "Please try again tomorrow."
)

PROVIDER_UNAVAILABLE_RESPONSE = (
    "⚠️ ODDI-AI providers are unavailable right now."
)


def _normalise_groq_content(content):
    """Convert Responses-style content parts into plain text for Groq."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")

                if text:
                    parts.append(str(text))

            elif isinstance(part, str):
                parts.append(part)

        return " ".join(parts)

    return str(content) if content is not None else ""


def _latest_user_message(chat_history):
    """Extract the latest user message for local request analysis."""

    if not isinstance(chat_history, list):
        return str(chat_history or "")

    for item in reversed(chat_history):

        if isinstance(item, dict):
            if item.get("role") == "user":
                return _normalise_groq_content(
                    item.get("content", "")
                )

        elif isinstance(item, str):
            if item.startswith("You:"):
                return item.replace(
                    "You:",
                    "",
                    1,
                ).strip()

    return ""


def _build_provider_prompt(chat_history):
    """Build a plain-text prompt for the currently connected providers."""

    lines = [
        SYSTEM_PROMPT,
        "",
        "Conversation:",
    ]

    if isinstance(chat_history, list):

        for item in chat_history:

            if isinstance(item, dict):

                role = item.get("role")

                content = _normalise_groq_content(
                    item.get("content", "")
                )

                if role in ("user", "assistant") and content:
                    lines.append(
                        f"{role.capitalize()}: {content}"
                    )

            elif isinstance(item, str) and item.strip():

                lines.append(
                    item.strip()
                )

    else:
        lines.append(
            str(chat_history or "")
        )

    return "\n".join(lines)


# ==========================================
# PHASE 6 — TOKEN ESTIMATION
# ==========================================

def _estimate_tokens(text) -> int:
    """
    Conservative approximate token counter.

    Until provider adapters expose actual usage metadata,
    ODDI estimates tokens using roughly 4 characters per token.

    This is an estimate, not provider-native token accounting.
    """

    if text is None:
        return 0

    text = str(text)

    if not text:
        return 0

    return max(
        1,
        (len(text) + 3) // 4,
    )


def _estimate_request_tokens(chat_history) -> int:
    """
    Estimate the token cost of an upcoming AI request.

    Includes:
        - estimated input/prompt tokens
        - conservative output buffer

    The output buffer prevents a request from being allowed
    when the user has too little remaining daily quota.
    """

    provider_prompt = _build_provider_prompt(
        chat_history
    )

    input_tokens = _estimate_tokens(
        provider_prompt
    )

    return (
        input_tokens
        + ESTIMATED_OUTPUT_TOKEN_BUFFER
    )


def _record_user_usage(
    user_id,
    chat_history,
    response,
):
    """
    Record estimated input + output token usage.

    Provider adapters currently return plain text, so actual
    provider usage metadata is not available yet.
    """

    if user_id is None:
        return

    if not response:
        return

    # Do not count the generic provider-unavailable message
    # as AI usage.
    if response == PROVIDER_UNAVAILABLE_RESPONSE:
        return

    input_tokens = _estimate_tokens(
        _build_provider_prompt(chat_history)
    )

    output_tokens = _estimate_tokens(
        response
    )

    total_tokens = (
        input_tokens
        + output_tokens
    )

    usage = user_limit_manager.record_usage(
        user_id=user_id,
        tokens=total_tokens,
    )

    print(
        f"📊 User {user_id} usage: "
        f"{usage['tokens']}/"
        f"{usage['daily_token_limit']} tokens"
    )


def _check_user_quota(
    user_id,
    chat_history,
) -> bool:
    """
    Check whether the user has enough remaining daily quota
    for the estimated request.

    Returns:
        True  -> request may continue
        False -> request must be blocked
    """

    if user_id is None:
        # Legacy/terminal callers without an authenticated
        # user ID are not subject to per-user limits.
        return True

    estimated_tokens = _estimate_request_tokens(
        chat_history
    )

    if not user_limit_manager.can_consume(
        user_id,
        estimated_tokens,
    ):
        quota = user_limit_manager.quota_status(
            user_id
        )

        print(
            f"⚠️ User {user_id} exceeded "
            f"available daily quota. "
            f"Usage: {quota['tokens_used']}/"
            f"{quota['tokens_limit']} tokens"
        )

        return False

    return True


# ==========================================
# SPECIAL-CAPABILITY OPENAI / GROQ PATH
# ==========================================

def _special_capability_response(
    chat_history,
    vector_store_id=None,
):
    """
    Existing ODDI response path.

    This is retained for requests that currently require
    web/file capabilities because the new Phase 4 adapters
    currently provide text generation only.
    """

    # -------------------------
    # OPENAI FIRST
    # -------------------------

    try:
        tools = [
            {
                "type": "web_search"
            }
        ]

        if vector_store_id:
            tools.append(
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        vector_store_id
                    ]
                }
            )

        response = client.responses.create(
            model="gpt-5.5",
            instructions=SYSTEM_PROMPT,
            input=chat_history,
            tools=tools,
        )

        return response.output_text

    except Exception as openai_error:

        print("\n⚠️ OpenAI failed.")
        print(openai_error)

        # -------------------------
        # GROQ FALLBACK
        # -------------------------

        try:
            groq_messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                }
            ]

            for item in chat_history:

                if isinstance(item, dict):

                    role = item.get("role")

                    content = _normalise_groq_content(
                        item.get("content", "")
                    )

                    if (
                        role in ("user", "assistant")
                        and content
                    ):
                        groq_messages.append(
                            {
                                "role": role,
                                "content": content,
                            }
                        )

                    continue

                if isinstance(item, str):

                    if item.startswith("You:"):

                        groq_messages.append(
                            {
                                "role": "user",
                                "content": item.replace(
                                    "You:",
                                    "",
                                    1,
                                ).strip(),
                            }
                        )

                    elif item.startswith("AI:"):

                        groq_messages.append(
                            {
                                "role": "assistant",
                                "content": item.replace(
                                    "AI:",
                                    "",
                                    1,
                                ).strip(),
                            }
                        )

            completion = (
                groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=groq_messages,
                    temperature=0.7,
                )
            )

            print("✅ Using Groq fallback.")

            return completion.choices[0].message.content

        except Exception as groq_error:

            print("\n[GROQ ERROR]")
            print(groq_error)

            return PROVIDER_UNAVAILABLE_RESPONSE


# ==========================================
# MAIN ODDI-AI RESPONSE FUNCTION
# ==========================================

def get_response(
    chat_history,
    vector_store_id=None,
    user_role="user",
    user_id=None,
):
    """
    Generate an ODDI-AI response.

    Phase 2:
        Local deterministic request analysis.

    Phase 3:
        Routing engine selects the best eligible
        connected provider/model.

    Phase 4:
        Provider adapters execute the selected
        model request.

    Phase 6:
        Per-user daily AI usage limit.

    Provider policy:
        Normal requests must use the routing engine.
        Only requests requiring provider tools not yet exposed
        by the adapters may use the special-capability OpenAI/Groq path.
    """

    # ==========================================
    # PHASE 6 — CHECK USER QUOTA
    # ==========================================

    if not _check_user_quota(
        user_id,
        chat_history,
    ):
        return USER_QUOTA_ERROR

    # ==========================================
    # PHASE 2 — REQUEST ANALYSIS
    # ==========================================

    latest_message = _latest_user_message(
        chat_history
    )

    # Analyze locally.
    # No AI/API call is made here.
    request = analyze_request(
        latest_message
    )

    request["user_role"] = user_role

    # ==========================================
    # SPECIAL CAPABILITY REQUESTS
    # ==========================================
    #
    # Gemini is the primary ODDI-AI path for normal
    # text requests AND platform-action requests.
    #
    # Keep the special-capability OpenAI/Groq path only for
    # capabilities that currently require provider
    # tools which the Gemini adapter does not expose:
    # web search, file search, image input, or video.
    #
    # This prevents platform requests such as memory/
    # conversation actions from unnecessarily jumping
    # to OpenAI before Gemini.

    requires_legacy_capability = any(
        [
            request.get(
                "requires_web",
                False,
            ),
            request.get(
                "requires_file",
                False,
            ),
            request.get(
                "requires_image",
                False,
            ),
            request.get(
                "requires_video",
                False,
            ),
        ]
    )

    if requires_legacy_capability:

        response = _special_capability_response(
            chat_history,
            vector_store_id,
        )

        _record_user_usage(
            user_id,
            chat_history,
            response,
        )

        return response

    # ==========================================
    # PHASE 3 — ROUTING
    # ==========================================

    try:
        from routing.engine import route_request

        route = route_request(
            request
        )

        if route.get("status") == "routed":

            provider_prompt = (
                _build_provider_prompt(
                    chat_history
                )
            )

            # ==========================================
            # PHASE 4 / PHASE 7-READY EXECUTION
            # ==========================================

            try:

                execution = execute_route(
                    route,
                    provider_prompt,
                )

                if execution.get("success") is True:
                    response = execution.get("response")

                    if response and str(response).strip():

                        print(
                            f"✅ ODDI-AI routed to "
                            f"{execution.get('provider')}/"
                            f"{execution.get('model')}"
                        )

                        if execution.get("capacity_id"):
                            print(
                                f"📦 Capacity: "
                                f"{execution['capacity_id']}"
                            )

                        _record_user_usage(
                            user_id,
                            chat_history,
                            response,
                        )

                        return response

                print("⚠️ All routed providers failed.")
                print(
                    execution.get(
                        "reason",
                        "all_candidates_failed",
                    )
                )

            except ProviderAdapterError as provider_error:

                print("⚠️ Provider execution failed.")
                print(provider_error)

    except Exception as routing_error:

        print(
            "\n⚠️ Routing layer failed."
        )
        print(
            routing_error
        )

    # ==========================================
    # NO ROUTER BYPASS
    # ==========================================
    #
    # Normal requests must never bypass the routing engine
    # and silently jump to OpenAI/Groq. Provider fallback is
    # handled inside execute_route() using routed candidates.

    print(
        "⚠️ ODDI-AI routing failed: "
        "no routed provider could serve this request."
    )

    return PROVIDER_UNAVAILABLE_RESPONSE