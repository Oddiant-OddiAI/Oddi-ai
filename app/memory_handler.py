from app.memory_store import memory
import json
from app import state
import string


MEMORY_RULES = {
    "my name is": "name",
    "my favorite color is": "favorite_color",
    "my college is": "college",
    "my university is": "university",
    "my hometown is": "hometown",
    "my age is": "age",
    "i work at": "company",
    "my hobby is": "hobby",
    "my goal is": "goal",
    "my favorite subject is": "favorite_subject",

    "my pet is": "pet",
    "my favorite food is": "favorite_food",
    "my dream job is": "dream_job",
    "my favorite movie is": "favorite_movie",
    "my favorite music is": "favorite_music",
    "i speak": "language",
    "my favorite sport is": "sport",
    "my favorite book is": "favorite_book",
    "my favorite game is": "favorite_game",
    "my favorite tv show is": "favorite_show",
}

MEMORY_KEYS = {
    "name": "👤 Your name is",
    "who am I": "👤 You are",  # Add this line here!
    "favorite_color": "🎨 Your favorite color is",
    "college": "🎓 Your college is",
    "university": "🏛️ Your university is",
    "hometown": "🏠 Your hometown is",
    "age": "🎂 Your age is",
    "company": "💼 You work at",
    "hobby": "🎯 Your hobby is",
    "goal": "🚀 Your goal is",
    "favorite_subject": "📚 Your favorite subject is",
    "pet": "🐶 Your pet is",
    "favorite_food": "🍕 Your favorite food is",
    "dream_job": "💼 Your dream job is",
    "favorite_movie": "🎬 Your favorite movie is",
    "favorite_music": "🎵 Your favorite music is",
    "language": "🌍 You speak",
    "sport": "🏀 Your favorite sport is",
    "favorite_book": "📖 Your favorite book is",
    "favorite_game": "🎮 Your favorite game is",
    "favorite_show": "📺 Your favorite TV show is",
}
MEMORY_RESPONSES = {
    "name": {
        "remember": "Hello {value}! 👏 It's great to meet you. I'll remember your name...",
        "recall": "Your name is {value}! 👏✨"
    },
    "favorite_color": {
        "remember": "Awesome! 🎨 I'll remember that your favorite color is {value}.",
        "recall": "Your favorite color is {value}. 🎨"
    },
    "college": {
        "remember": "Got it! 🎓 I'll remember that you study at {value}.",
        "recall": "You study at {value}. 🎓"
    },
    "university": {
        "remember": "Got it! 🏛️ I'll remember that you attend university at {value}.",
        "recall": "You attend university at {value}. 🏛️"
    },
    "hometown": {
        "remember": "Neat! 🏠 I'll remember that your hometown is {value}.",
        "recall": "Your hometown is {value}. 🏠"
    },
    "hobby": {
        "remember": "Awesome! ⚽ I'll remember your hobby is {value}.",
        "recall": "🎯 Your hobby is {value}."
    },
    "age": {
        "remember": "Got it! 🎂 You are {value} years old.",
        "recall": "🎂 Your age is {value}."
    },
    "company": {
        "remember": "Cool! 💼 I'll remember that you work at {value}.",
        "recall": "You work at {value}. 💼"
    },
    "goal": {
        "remember": "That's inspiring! 🚀 I'll remember your goal is {value}.",
        "recall": "Your goal is {value}. 🚀"
    },
    "favorite_subject": {
        "remember": "Fascinating! 📚 I'll remember your favorite subject is {value}.",
        "recall": "Your favorite subject is {value}. 📚"
    },
    "pet": {
        "remember": "How cute! 🐾 I'll remember your pet is named {value}.",
        "recall": "Your pet is named {value}. 🐾"
    },
    "favorite_food": {
        "remember": "Yum! 🍕 I'll remember your favorite food is {value}.",
        "recall": "Your favorite food is {value}. 🍕"
    },
    "dream_job": {
        "remember": "Aim high! ✨ I'll remember your dream job is {value}.",
        "recall": "Your dream job is {value}. ✨"
    },
    "favorite_movie": {
        "remember": "Great choice! 🎬 I'll remember your favorite movie is {value}.",
        "recall": "Your favorite movie is {value}. 🎬"
    },
    "favorite_music": {
        "remember": "Good taste! 🎵 I'll remember you love listening to {value}.",
        "recall": "You love listening to {value}. 🎵"
    },
    "language": {
        "remember": "Awesome! 🌍 I'll remember you speak {value}.",
        "recall": "You speak {value}. 🌍"
    },
    "sport": {
        "remember": "Let's go! 🏀 I'll remember your favorite sport is {value}.",
        "recall": "Your favorite sport is {value}. 🏀"
    },
    "favorite_book": {
        "remember": "Nice read! 📖 I'll remember your favorite book is {value}.",
        "recall": "Your favorite book is {value}. 📖"
    },
    "favorite_game": {
        "remember": "Epic! 🎮 I'll remember your favorite game is {value}.",
        "recall": "Your favorite game is {value}. 🎮"
    },
    "favorite_show": {
        "remember": "Binge-worthy! 🍿 I'll remember your favorite TV show is {value}.",
        "recall": "Your favorite TV show is {value}. 🍿"
    }
}

def remember(data):
    text = data.lower().strip()

    for phrase, key in MEMORY_RULES.items():
        if text.startswith(phrase):
            value = data[len(phrase):].strip()
            if key in memory and memory[key] != value:
                state.pending_update = {
                    "key": key,
                    "old": memory[key],
                    "new": value
                }
                return (
                    f"🤔 Earlier you told me your {key.replace('_',' ')} "
                    f"is '{memory[key]}'.\n"
                    f"Do you want to update it to '{value}'? (Y/N)"
                )
            memory[key] = value

            with open("database/memory.json", "w") as file:
                json.dump(memory, file, indent=4)

            return MEMORY_RESPONSES[key]["remember"].format(value=value)
    memory["note"] = data

    return "🧠 Memory Saved!"

def is_memory_message(data):
    text = data.lower().strip()

    for phrase in MEMORY_RULES:
        if text.startswith(phrase):
            return True

    return False

def recall_memory(message):
    text = message.lower().strip()
    
    text = text.replace("what's", "what is")
    text = text.replace("whats", "what is")

    for phrase, replacement in ALIASES.items():
        text = text.replace(phrase, replacement)   
    # Only trigger recall if the user is explicitly asking to retrieve info
    recall_triggers = [
    "what is my",
    "tell me my",
    "do you remember",
    "who am i",
    "where do i",
    "language",
    "company"
    ]
    is_recall_attempt = any(trigger in text for trigger in recall_triggers)
    

    if not is_recall_attempt:
        return None

    # Handle direct identity check
    if "who am i" in text or "what is my name" in text or "tell me my name" in text:
        if "name" in memory:
            return f"👤 Your name is {memory['name']}."
        else:
            return "🤖 I don't know your name yet. Try telling me: 'My name is [Your Name]!'"

    # Standard check for other keys
    for key, reply in MEMORY_KEYS.items():
        if key in text or key.replace("_", " ") in text:
            if key in memory:
                return f"{reply} {memory[key]}."
            else:
                return f"🤖 I don't know your {key.replace('_', ' ')} yet."

    return None

def clear_all_memory():
    memory.clear()
    with open("database/memory.json", "w") as file:
        json.dump(memory, file, indent=4)
    return "🗑️ Done! I've forgotten everything you told me."

CONFIRM_UPDATE = {
    "name",
    "age",
    "birthday",
    "college",
    "university",
    "company",
    "hometown"
}

ALIASES = {
    "where do i work": "company",
    "what language do i speak": "language",
    "favorite tv show": "favorite_show",
}
