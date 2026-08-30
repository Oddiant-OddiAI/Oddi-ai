from app.config import client, groq_client
from app.prompts import SYSTEM_PROMPT


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


def get_response(chat_history, vector_store_id=None):
    """
    Generate an Oddi response.

    OpenAI is the primary engine. Groq is used as the fallback.
    The response is returned as raw Markdown/LaTeX text so the frontend
    rich-content renderer can turn equations and code into proper UI.
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
            tools.append({
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            })

        response = client.responses.create(
            model="gpt-5.5",
            instructions=SYSTEM_PROMPT,
            input=chat_history,
            tools=tools
        )

        # Keep the model's Markdown/LaTeX intact. The browser renderer
        # is responsible for equations, formatting and code blocks.
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
                    "content": SYSTEM_PROMPT
                }
            ]

            for item in chat_history:
                # -------------------------
                # WEB CHAT FORMAT
                # -------------------------
                if isinstance(item, dict):
                    role = item.get("role")
                    content = _normalise_groq_content(
                        item.get("content", "")
                    )

                    if role in ("user", "assistant") and content:
                        groq_messages.append({
                            "role": role,
                            "content": content
                        })

                    continue

                # -------------------------
                # OLD TERMINAL CHAT FORMAT
                # -------------------------
                if isinstance(item, str):
                    if item.startswith("You:"):
                        groq_messages.append({
                            "role": "user",
                            "content": item.replace("You:", "", 1).strip()
                        })

                    elif item.startswith("AI:"):
                        groq_messages.append({
                            "role": "assistant",
                            "content": item.replace("AI:", "", 1).strip()
                        })

            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=groq_messages,
                temperature=0.7
            )

            print("✅ Using Groq fallback.")

            return completion.choices[0].message.content

        except Exception as groq_error:
            print("\n[GROQ ERROR]")
            print(groq_error)

            return (
                "⚠️ OpenAI and Groq are both unavailable right now."
            )
