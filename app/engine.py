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
from pypdf import PdfReader
from openpyxl import load_workbook


def process_message(user_message, uploaded_file=None):

    if uploaded_file:
            print("Engine received:", uploaded_file.filename)
    
    image_bytes = None
    file_text = None

    if uploaded_file:

        filename = uploaded_file.filename.lower()
        print("Filename:", filename)
        print("Mimetype:", uploaded_file.mimetype)

        # ---------- IMAGE ----------
        if filename.endswith((".png", ".jpg", ".jpeg", ".webp")):

            image_bytes = uploaded_file.read()

            print("Image detected")
            print("Image size:", len(image_bytes))
            print("IMAGE BLOCK")

        # ---------- TXT ----------
        elif filename.endswith(".txt"):

            file_text = uploaded_file.read().decode("utf-8")

            print("TXT detected")
            print(file_text[:200])
            print("TXT BLOCK")
        # ---------- PDF ----------
        elif filename.endswith(".pdf"):

            reader = PdfReader(uploaded_file)

            file_text = ""

            for page in reader.pages:
                page_text = page.extract_text()

                if page_text:
                    file_text += page_text + "\n"

            print("PDF detected")
            print(file_text[:200])
            print("PDF BLOCK")
        # ---------- EXCEL ----------
        elif filename.endswith(".xlsx"):

            workbook = load_workbook(uploaded_file)

            sheet = workbook.active

            file_text = ""

            for row in sheet.iter_rows(values_only=True):

                line = " | ".join(str(cell) if cell is not None else "" for cell in row)

                file_text += line + "\n"

            print("EXCEL detected")
            print(file_text[:300])
            print("EXCEL BLOCK")
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

    Attached file type: {uploaded_file.mimetype}
    Document content:
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