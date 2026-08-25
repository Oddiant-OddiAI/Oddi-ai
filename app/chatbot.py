from app.config import client, groq_client
from app.prompts import SYSTEM_PROMPT


def get_response(chat_history, vector_store_id=None):

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
                "vector_store_ids": [
                    vector_store_id
                ]
            })

        response = client.responses.create(

            model="gpt-5.5",

            instructions=SYSTEM_PROMPT,

            input=chat_history,

            tools=tools
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
                    "content": SYSTEM_PROMPT
                }
            ]

            for item in chat_history:

                # -------------------------
                # WEB CHAT FORMAT
                # -------------------------
                if isinstance(item, dict):

                    role = item.get("role")
                    content = item.get("content", "")

                    # Handle content that may not be plain text
                    if isinstance(content, list):
                        text_parts = []

                        for part in content:
                            if isinstance(part, dict):
                                text = part.get("text") or part.get("content")

                                if text:
                                    text_parts.append(str(text))
                            elif isinstance(part, str):
                                text_parts.append(part)

                        content = " ".join(text_parts)

                    if role in ("user", "assistant") and content:
                        groq_messages.append({
                            "role": role,
                            "content": str(content)
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