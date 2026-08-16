from app import state

from app.database import (
    get_memory,
    save_memory,
    delete_memory,
    clear_memory
)


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
    "my preferred job role is": "preferred_job_role",
    "i want to work as": "preferred_job_role",
    "my skills are": "skills",
    "my experience is": "experience",
    "i have experience in": "experience",
    "my preferred location is": "preferred_location",
    "i want to work in": "preferred_location",
    "my preferred work mode is": "work_mode",
    "i prefer": "work_preference",
    "my employment type is": "employment_type",
    "my expected salary is": "expected_salary",
    "my notice period is": "notice_period",
    "my industry is": "industry",
    "my preferred industry is": "industry",
    "my preferred company is": "preferred_company",
    "my education is": "education",
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
    "preferred_job_role": "💼 Your preferred job role is",
    "skills": "🛠️ Your skills are",
    "experience": "📈 Your experience is",
    "preferred_location": "📍 Your preferred job location is",
    "work_mode": "🏠 Your preferred work mode is",
    "work_preference": "💼 Your work preference is",
    "employment_type": "📋 Your preferred employment type is",
    "expected_salary": "💰 Your expected salary is",
    "notice_period": "📅 Your notice period is",
    "industry": "🏢 Your preferred industry is",
    "preferred_company": "⭐ Your preferred company is",
    "education": "🎓 Your education is",
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
        "remember": "Got it! 🎓 I'll remember that you Explanationat {value}.",
        "recall": "You Explanationat {value}. 🎓"
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
    },
    "preferred_job_role": {
        "remember": "Got it! 💼 I'll remember that you're looking for {value} roles.",
        "recall": "You're looking for {value} roles. 💼"
    },

    "skills": {
        "remember": "Great! 🛠️ I'll remember your skills: {value}.",
        "recall": "Your skills are {value}. 🛠️"
    },

    "experience": {
        "remember": "Got it! 📈 I'll remember that your experience is {value}.",
        "recall": "Your experience is {value}. 📈"
    },

    "preferred_location": {
        "remember": "Got it! 📍 I'll remember that you prefer jobs in {value}.",
        "recall": "You prefer jobs in {value}. 📍"
    },

    "work_mode": {
        "remember": "Understood! 🏠 I'll remember that you prefer {value} work.",
        "recall": "You prefer {value} work. 🏠"
    },

    "work_preference": {
        "remember": "Got it! 💼 I'll remember your work preference: {value}.",
        "recall": "Your work preference is {value}. 💼"
    },

    "employment_type": {
        "remember": "Got it! 📋 I'll remember that you prefer {value} employment.",
        "recall": "You prefer {value} employment. 📋"
    },

    "expected_salary": {
        "remember": "Understood! 💰 I'll remember your expected salary is {value}.",
        "recall": "Your expected salary is {value}. 💰"
    },

    "notice_period": {
        "remember": "Got it! 📅 I'll remember your notice period is {value}.",
        "recall": "Your notice period is {value}. 📅"
    },

    "industry": {
        "remember": "Great! 🏢 I'll remember that you're interested in {value}.",
        "recall": "You're interested in the {value} industry. 🏢"
    },

    "preferred_company": {
        "remember": "Nice! ⭐ I'll remember that you're interested in {value}.",
        "recall": "You're interested in {value}. ⭐"
    },

    "education": {
        "remember": "Got it! 🎓 I'll remember your education is {value}.",
        "recall": "Your education is {value}. 🎓"
    },
}

def remember(data, user_id):

    text = data.lower().strip()

    for phrase, key in MEMORY_RULES.items():

        if text.startswith(phrase):

            value = data[len(phrase):].strip()

            old_value = get_memory(user_id, key)

            if old_value is not None and old_value != value:

                state.pending_update = {
                    "user_id": user_id,
                    "key": key,
                    "old": old_value,
                    "new": value
                }

                return (
                    f"🤔 Earlier you told me your "
                    f"{key.replace('_', ' ')} is '{old_value}'.\n"
                    f"Do you want to update it to '{value}'? (Y/N)"
                )

            save_memory(user_id, key, value)

            return MEMORY_RESPONSES[key]["remember"].format(
                value=value
            )

    save_memory(user_id, "note", data)

    return "🧠 Memory Saved!"

def is_memory_message(data):
    text = data.lower().strip()

    for phrase in MEMORY_RULES:
        if text.startswith(phrase):
            return True

    return False

def recall_memory(message, user_id):

    text = message.lower().strip()

    text = text.replace("what's", "what is")
    text = text.replace("whats", "what is")

    for phrase, replacement in ALIASES.items():
        text = text.replace(phrase, replacement)

    recall_triggers = [
        "what is my",
        "tell me my",
        "do you remember",
        "who am i",
        "where do i",
        "language",
        "company"
    ]

    is_recall_attempt = any(
        trigger in text
        for trigger in recall_triggers
    )

    if not is_recall_attempt:
        return None

    # Direct identity check
    if (
        "who am i" in text
        or "what is my name" in text
        or "tell me my name" in text
    ):

        value = get_memory(user_id, "name")

        if value is not None:
            return f"👤 Your name is {value}."

        return (
            "🤖 I don't know your name yet. "
            "Try telling me: 'My name is [Your Name]!'"
        )

    # Standard memory recall
    for key, reply in MEMORY_KEYS.items():

        if key in text or key.replace("_", " ") in text:

            value = get_memory(user_id, key)

            if value is not None:
                return f"{reply} {value}."

            return (
                f"🤖 I don't know your "
                f"{key.replace('_', ' ')} yet."
            )

    return None

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
def clear_all_memory(user_id):
    clear_memory(user_id)
    return "🗑️ Done! I've forgotten everything you told me."
