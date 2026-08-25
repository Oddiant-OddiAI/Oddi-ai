from constants import APP_NAME, EXIT_COMMAND, ERROR_MESSAGE
from utils import response_timer
from memory import trim_history
from prompts import SYSTEM_PROMPT, EXPLANATION_MODE_PROMPT
from chatbot import get_response
from config import client
from config import groq_client
import time

import state
from memory_store import memory
from memory_handler import (
    remember,
    is_memory_message,
    recall_memory,
    clear_all_memory
)
from fast_responses import fast_response
import shutil
import textwrap
import json
from banner import show_banner
from help_menu import show_help
from about import show_about
from stats import show_stats
from commands import handle_command
from logger import info, success, warning, error


# Track whether an introduction has already happened
has_introduced = False
# Ask Gemini a question
chat_history = []

chat_history.append(SYSTEM_PROMPT)
show_banner()
while True:
    message = input("You: ") 
    if handle_command(message):
        continue
    # ---------- Pending Memory Update ----------
    if state.pending_update is not None:

        if message.lower() == "y":

            key = state.pending_update["key"]
            value = state.pending_update["new"]

            memory[key] = value

            with open("database/memory.json", "w") as file:
                json.dump(memory, file, indent=4)

            print(f"✅ Done! I'll remember your {key.replace('_',' ')} as {value}.")

            state.pending_update = None
            continue

        elif message.lower() == "n":

            print("👍 Okay! I'll keep the previous memory.")

            state.pending_update = None
            continue

        else:

            print("Please reply with Y or N.")
            continue

    if message.lower() == "/explantion":
        state.explanation_mode = True
        chat_history[0] = SYSTEM_PROMPT + "\n\n" + EXPLANATION_MODE_PROMPT
        success("ExplanationMode Activated!")
        continue

    if message.lower() == "/normal":
        state.explanation_mode = False
        chat_history[0] = SYSTEM_PROMPT
        print("😊 Normal Mode Activated!")
        continue

    if message.lower() == "/mode":
        if state.explanation_mode:
            print("Current Mode: 📚 ExplanationMode")
        else:
            print("Current Mode: 😊 Normal Mode")
            continue

    if message.lower() == "/clear":
        state.explanation_mode = False
        chat_history.clear()

        chat_history.append(SYSTEM_PROMPT)
        print("🧹 Chat history cleared!")
        print("😊 Normal Mode Activated!")

        continue

    chat_history.append("You: " + message)
    chat_history = trim_history(chat_history)

    if message.lower() == EXIT_COMMAND:   
        print("Chat ended. Goodbye!")
        break

    if message.lower().startswith("/rename "):
        new_name = message[8:]
        state.current_name = new_name
        print(f"🤖 AI renamed to {state.current_name}!")
        continue

    if message.lower() == "/remember":
        warning("Please tell me what to remember.")
        continue


    if message.lower().startswith("/remember "):
        data = message[10:]
        if data.strip() == "":
            warning("Please tell me what to remember.")
            continue
        print(remember(data))
        continue

    if message.lower() == "/memory":
        if len(memory) == 0:
            print("🧠 Memory is empty.")
        else:
            print("🧠 Stored Memories:")
            for key, value in memory.items():
                print(f"- {key}: {value}")
        continue

    answer = fast_response(message)
    
    if answer:
        print(state.current_name + ": " + answer)
        continue
    
    answer = fast_response(message)
    
    if answer:
        state.has_introduced = True  # Mark that introduction happened via shortcut
        print(state.current_name + ": " + answer)
        continue

    if message.lower() == "/about":
        show_about()
        continue

    if message.lower() == "/stats":
        show_stats()
        continue

    # (Your existing start = time.time() stays right here where you already had it)
    start = time.time()
    
    if is_memory_message(message):
        print(remember(message))
        continue

    answer = recall_memory(message)
    if answer:
        print(answer)
        continue

    print("🤔 Let me think... This may take a few seconds.")

    if message.lower() == "/forget all":
        response = clear_all_memory()
        print(f"Oddi AI: {response}")
        continue   

    if message.lower() == "/forget":
        print("🗑️ Please tell me what to forget.")
        continue

    if message.lower().startswith("/forget "):
        key = message[8:].strip().lower()
        if key in memory:
            del memory[key]

            with open("database/memory.json", "w") as file:
                json.dump(memory, file, indent=4)

            print(f"✨ Done! I no longer remember your {key}.")
        else:
            print(f"❌ I don't remember your {key}.")
        continue
    
    print("🤔 Let me think... This may take a few seconds.")

    # --- CRITICAL FIX FOR LATE INTRODUCTIONS ---
    current_chat_history = list(chat_history)
    
    # Initialize state variable safely if it doesn't exist yet
    if not hasattr(state, "has_introduced"):
        state.has_introduced = False

    if not state.has_introduced:
        state.has_introduced = True # First time hitting the LLM
    else:
        # Force a prompt addition to stop late introductions
        current_chat_history.append("System Notice: You have already been introduced in this conversation. Do NOT introduce yourself.")

    response = get_response(current_chat_history)


    answer = recall_memory(message)
    if answer:
        print(answer)
        continue

    print("🤔 Let me think... This may take a few seconds.")

    response = get_response(chat_history)

    if response is None:
        error(ERROR_MESSAGE)
        continue




    chat_history.append("AI: " + response)

    response_timer(start)
    # Get your current terminal window width dynamically
    terminal_width = shutil.get_terminal_size((80, 20)).columns

    # Wrap the AI's response cleanly using response!
    clean_response = textwrap.fill(f"{state.current_name}: {response}", width=terminal_width)

    print(clean_response)
