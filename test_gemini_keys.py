import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

KEYS = {
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "GEMINI_API_KEY_2": os.getenv("GEMINI_API_KEY_2"),
    "GEMINI_API_KEY_3": os.getenv("GEMINI_API_KEY_3"),
    "GEMINI_API_KEY_4": os.getenv("GEMINI_API_KEY_4"),
}

MODEL = "gemini-3.5-flash-lite"

for name, api_key in KEYS.items():
    print("\n" + "=" * 60)
    print(f"TESTING: {name}")
    print("=" * 60)

    if not api_key:
        print("❌ API KEY NOT FOUND")
        continue

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=MODEL,
            contents="Reply with exactly: GEMINI_OK"
        )

        print("✅ API RESPONSE RECEIVED")
        print("Response:", response.text)

    except Exception as e:
        print("❌ FAILED")
        print("Error:", type(e).__name__)
        print(str(e))