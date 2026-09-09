import json
import os
import importlib.metadata

from dotenv import load_dotenv
from groq import Groq


# ODDI Memory AI uses the Groq Python SDK 1.6.0.
REQUIRED_GROQ_SDK_VERSION = "1.6.0"

load_dotenv()


MEMORY_AI_PROMPT = """
You are ODDI's Memory AI.

Your job is to examine the user's CURRENT message and decide whether
there is a useful, reasonably stable fact about the user that ODDI
should remember for future conversations.

Only remember information about the user, not temporary requests,
questions, greetings, or facts about unrelated people.

Examples worth remembering:
- The user's name
- What the user is learning
- Their education or college
- Long-term goals
- Skills they have or are developing
- Projects they are building
- Important preferences
- Long-term plans
- Stable interests

Examples that should NOT normally be remembered:
- "What is a pointer?"
- "Explain this code."
- "What is the weather?"
- Temporary tasks
- One-off questions
- General facts that are not about the user

Return ONLY a JSON object with exactly these fields:

{
  "action": "ADD" or "NONE",
  "category": "short category name",
  "memory": "short natural-language memory"
}

Rules:
- Use ADD only when the message contains a useful user-specific memory.
- Use NONE when there is nothing worth remembering.
- Do not invent information.
- Do not add explanations outside the JSON object.
- Keep category short, such as "name", "learning", "education",
  "goal", "skill", "project", "preference", or "interest".
- Make the memory concise and useful for future ODDI conversations.
"""


# Keep the Memory AI isolated from ODDI's main Groq API key.
INSTALLED_GROQ_SDK_VERSION = importlib.metadata.version("groq")

if INSTALLED_GROQ_SDK_VERSION != REQUIRED_GROQ_SDK_VERSION:
    print(
        "⚠️ Groq SDK version mismatch: "
        f"expected {REQUIRED_GROQ_SDK_VERSION}, "
        f"found {INSTALLED_GROQ_SDK_VERSION}"
    )

GROQ_API_KEY_1 = os.getenv("GROQ_API_KEY_1")

if not GROQ_API_KEY_1:
    print("⚠️ GROQ_API_KEY_1 is not set. Memory AI is disabled.")
    memory_client = None
else:
    memory_client = Groq(api_key=GROQ_API_KEY_1)


def analyze_memory(user_message):
    """
    Ask Groq Memory AI to classify the user's current message.

    Returns a normalized Python dict:
    {
        "action": "ADD" | "NONE",
        "category": "...",
        "memory": "..."
    }
    """

    try:
        response = memory_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": MEMORY_AI_PROMPT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            temperature=0,
            response_format={
                "type": "json_object"
            }
        )

        content = response.choices[0].message.content

        # Groq's JSON mode returns JSON content as a string.
        result = json.loads(content)

        action = result.get("action", "NONE")
        category = str(result.get("category", "") or "").strip()
        memory = str(result.get("memory", "") or "").strip()

        if action not in ("ADD", "NONE"):
            return {
                "action": "NONE",
                "category": "",
                "memory": ""
            }

        if action == "NONE":
            return {
                "action": "NONE",
                "category": "",
                "memory": ""
            }

        if not category or not memory:
            return {
                "action": "NONE",
                "category": "",
                "memory": ""
            }

        return {
            "action": "ADD",
            "category": category,
            "memory": memory
        }

    except Exception as e:
        print("Memory AI error:", e)

        return {
            "action": "NONE",
            "category": "",
            "memory": ""
        }
