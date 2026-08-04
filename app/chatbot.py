from app.config import client
from app.prompts import SYSTEM_PROMPT

def get_response(chat_history):

    try:
        response = client.responses.create(
            model="gpt-5.5",
            instructions=SYSTEM_PROMPT,
            input=chat_history
        )

        return response.output_text
    
    except Exception as e:
        print(f"\n[CHATBOT ERROR]\n{e}\n")
        error = str(e)

        if "RESOURCE_EXHAUSTED" in error:
            return "⚠️ VedAura has reached its daily AI limit. Please try again later."

        return "⚠️ Sorry! Something went wrong."
