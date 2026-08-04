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


def process_message(user_message):

    # 1. Commands
    command_reply = handle_command(user_message)
    if command_reply:
        return command_reply

    # 2. Fast Responses
    fast_reply = fast_response(user_message)
    if fast_reply:
        return fast_reply

    # 3. Memory Recall
    memory_reply = recall_memory(user_message)
    if memory_reply:
        return memory_reply

    # 4. Save Memory
    if is_memory_message(user_message):
        return remember(user_message)

    # 5. Chatgpt

    chat_history = [
        {
            "role":"user",
            "content":user_message
        }
    ]

    return get_response(chat_history)