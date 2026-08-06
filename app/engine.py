import base64
from app.fast_responses import fast_response
from app.memory_handler import (
    is_memory_message,
    remember,
    recall_memory
)
from app.chatbot import get_response
from app.commands import handle_command
from app.prompts import SYSTEM_PROMPT
from app.prompts import SYSTEM_PROMPT


def process_message(user_message, uploaded_file=None):

    if uploaded_file:
            print("Engine received:", uploaded_file.filename)
    
    image_bytes = None
    file_text = None

    if uploaded_file:

        filename = uploaded_file.filename.lower()

        # ---------- IMAGE ----------
        if filename.endswith((".png", ".jpg", ".jpeg", ".webp")):

            image_bytes = uploaded_file.read()

            print("Image detected")
            print("Image size:", len(image_bytes))

        # ---------- TXT ----------
        elif filename.endswith(".txt"):

            file_text = uploaded_file.read().decode("utf-8")

            print("TXT detected")
            print(file_text[:200])

        else:

            print("Unsupported file:", filename)
        

    # 2. Fast Responses
    if not uploaded_file:
        fast_reply = fast_response(user_message)
        if fast_reply:
            return fast_reply
    # 1. Commands
    command_reply = handle_command(user_message)
    if command_reply:
        return command_reply



    # 3. Memory Recall
    memory_reply = recall_memory(user_message)
    if memory_reply:
        return memory_reply

    # 4. Save Memory
    if is_memory_message(user_message):
        return remember(user_message)

    # 5. Chatgpt
    if image_bytes:

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        chat_history = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_message
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{uploaded_file.mimetype};base64,{image_base64}"
                    }
                ]
            }
        ]

    elif file_text:

        chat_history = [
            {
                "role": "user",
                "content": f"""
    User message:
    {user_message}

    Attached text file:
    {file_text}
    """
            }
        ]

    else:

        chat_history = [
            {
                "role": "user",
                "content": user_message
            }
        ]

        
    print(chat_history)
    return get_response(chat_history)