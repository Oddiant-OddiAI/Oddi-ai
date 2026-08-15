from app.config import client
from app.prompts import SYSTEM_PROMPT


def get_response(chat_history, vector_store_id=None):

    try:

        tools = [
            {
                "type": "web_search"
            }
        ]

        # ------------------------------------------
        # FILE SEARCH
        # ------------------------------------------

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

    except Exception as e:

        print(f"\n[CHATBOT ERROR]\n{e}\n")

        error = str(e)

        if "RESOURCE_EXHAUSTED" in error:

            return (
                "⚠️ Oddi-AI has reached its daily AI limit. "
                "Please try again later."
            )

        return "⚠️ Sorry! Something went wrong."