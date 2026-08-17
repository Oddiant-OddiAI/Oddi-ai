import string
import re
from app.job_fast_responses import JOB_FAST_RESPONSES
def is_job_context_question(message):
    text = normalize_text(message)
    
    return text in JOB_CONTEXTS and JOB_CONTEXTS[text] == "__JOB_CONTEXT__"

FAST_RESPONSES = {
# Greetings
    "hi": "Hello! 👋 How are you today?",
    "hello": "Hello! 👋 It's great to see you!",
    "hey": "Hey! 😄 What's up?",
    "yo": "Yo! What's on your mind?",
    "namaste": "Namaste! 🙏 Welcome! How can I help?",
    "good morning": "☀️ Good morning! Hope you have an amazing day!",
    "good evening": "🌆 Good evening! Hope you had a productive day.",
    "good night": "🌙 Good night! Sleep well and take care!",
    "morning": "Morning! ☕ Ready to tackle the day?",
    "night": "Night! Catch you later. 🌙",

# General conversation
    "how are you": "I'm doing well, thanks! How can I help you today?",
    "how are you doing": "I'm doing fantastic, thank you! Ready when you are.",
    "how do you do": "I'm doing well, thanks! How can I help you today?",
    "whats up": "Not much! Just hanging out in the cloud, ready to help. ☁️",
    "what are you doing": "Just waiting here to chat with you and help out with your work!",
    "can you help me": "I'd love to! What do you need help with? 💡",
    "help": "I'm here! What do you need help with? 💡",
    "nice to meet you": "Nice to meet you too! Glad to have you here. ✨",
    "are you okay": "I'm an AI, so I'm always running at 100%! Thanks for asking. 👍",
    "what can you do": "I can chat, help you brainstorm, and answer questions! 💡",
    "tell me about yourself": "I am Oddi AI, a smart and friendly virtual assistant created by Oddiant. I'm here to help answer your questions, chat with you, and keep track of cool details you share with me! 🚀",

# Identity
    "who are you": "I'm Oddi AI 🤖, created by Oddiant. I'm here to help you!",
    "what is your name": "I'm Oddi AI. 😊",
    "whats your name": "I'm Oddi AI. 😊",
    "who made you": "I was created by Oddiant. 🚀",
    "who created you": "I was created by Oddiant. 🚀",
    "are you a bot": "Yes, I'm a virtual assistant chatbot! 🤖",
    "are you human": "Nope, I'm pure code and AI! 💻",
    "bot": "At your service! What do you need? 💡",
    "ai": "That's me! Brains made of code. 🧠💻",
    "oddi": "Yo! Oddi in the house. What's up?",
    "oddii": "That's my name! How can I help you today?",

# Positive / short responses
    "cool": "Right? 😎",
    "awesome": "Glad you think so! 🚀",
    "nice": "✨ Awesome!",
    "great": "Awesome! 😄",
    "ok": "Alright! Let me know what's next. 👍",
    "okay": "Got it! What would you like to do next?",
    "sounds good": "Awesome! Let's do it. 👍",
    "no": "No problem! Let me know if you change your mind.",
    "idk": "That's totally fine, we can figure it out together! 🔍",
    "idc": "Fair enough! What else do you want to talk about?",
    "nvm": "No worries at all! Let me know if you need anything else.",
    "nw": "No worries! You got it. 👍",

# Thanks
    "thanks": "😊 You're always welcome!",
    "thank you": "You're welcome! 😄",
    "thank you so much": "You're so welcome! Happy to help out. ✨",
    "thx": "Anytime! 😎",
    "thanks a lot": "You're so welcome! Happy to help out. ✨",
    "appreciate it": "Happy to help! That's what I'm here for.",

# Goodbye
    "bye": "👋 Goodbye! Have a wonderful day!",
    "goodbye": "Goodbye! Feel free to come back whenever you need help.",
    "see you": "See you later! Take care! 👋",
    "see you later": "Catch you later! Have a great day!",
    "talk to you later": "Talk to you later! I'll be right here whenever you need me.",
    "farewell": "Farewell! Wishing you the best.",
    "take care": "Take care! Have an amazing day! 🌟",

# Fun / casual
    "hmm": "Yes, How can I help you today?",
    "lol": "Glad I could make you smile! 😄",
    "lmao": "Haha, love the energy! 😂",
    "haha": "😄 Always happy to bring good vibes!",
    "hehe": "Hehe! What's making you laugh? 👀",
    "omg": "Right?! Wild stuff! 😲",
    "bruh": "Bruh. 💀 What happened?",
    "fr": "For real! No cap. 🧢💯",
    "no cap": "Facts only! 💯 What's on your mind?",
    "bet": "Bet! Let's make it happen. 🤝",
    "lets go": "Let's gooo! 🚀 Fire it up!",
    "hype": "The hype is real! 🔥 Let's do this.",
    "gg": "GG! That was a fun interaction. 🎮",
    "sheesh": "Sheesh! 🥶 Looking clean!",
    "sus": "Hmm, looks a bit sus... 👀",
    "valid": "Completely valid! What's next? ✅",
    "w": "Absolute W! Let's keep the streak going. 🏆",
    "l": "Oof, we take those as learning experiences! 💪",

# Status / testing
    "ping": "Pong! 🏓 I'm super fast and ready!",
    "status": "All systems nominal and running at 100%! ⚡",
    "test": "Test received loud and clear! 🎤✨",

# Coding
    "python": "Python is awesome! Clean and readable code. 🐍",
    "javascript": "JS powers the web! 💛 Got a script you're working on?",
    "html": "The backbone of the web! 🌐 Need help structuring a page?",
    "css": "Make it look pretty! 🎨 Need styling tips?",
    "code": "Code mode activated! 💻 Drop your snippet or question.",
    "bug": "Let's squash it! 🐛 Send over the error message.",
    "error": "Don't panic, errors just mean we're learning! Paste it here. 🛠️",
    "debug": "Debugging time! 🔍 What's breaking your code?",

# Language
    "what languages do you speak": "I can communicate in English right now. 🌍💬",
    "can you speak hindi": "Not yet! 😅 Right now I communicate in English, but I hope to support more languages in the future. 🇮🇳✨",
    "can you speak every language": "Not yet! 😅 I'm still learning. One language at a time! 🌍🚀",
    "how many languages do you know": "I currently communicate in English. 🌍 I'm always evolving, so more languages may come in future versions! 🚀",

# Miscellaneous
    "why are you so slow": "My circuits are running as fast as they can! ⚡ Let me know how I can help.",
    "why are you too slow": "I'm doing my best! 😅 What can I do for you right now?",
    "zipit": "🤐 Got it! I'm here quietly whenever you need me.",
    "are you maried": "No, I am an AI, so I don't get married or have a personal life! 😄",
    "good job": "Thank you! I appreciate that. 🙌",
    "well done": "Thanks so much! 😊",
    "congrats": "Woohoo! 🎉 Thanks!",
    "good luck": "Thank you! I'll do my best! 🍀",
}

import string
import re


# Different ways of asking the same question
# ============================================================
# QUESTION ALIASES
# Different ways of asking the same question
# ============================================================

QUESTION_ALIASES = {


# HR INTERVIEW


    "prepare me for hr interview": "prepare me for hr interview",
    "help me prepare for hr interview": "prepare me for hr interview",
    "hr interview preparation": "prepare me for hr interview",
    "prepare for hr interview": "prepare me for hr interview",
    "how should i prepare for hr interview": "prepare me for hr interview",
    "how do i prepare for hr interview": "prepare me for hr interview",
    "help me with hr interview": "prepare me for hr interview",
    "i have an hr interview": "prepare me for hr interview",
    "i have a hr interview": "prepare me for hr interview",
    "help me prepare for my hr interview": "prepare me for hr interview",
    "can you prepare me for hr interview": "prepare me for hr interview",
    "get me ready for hr interview": "prepare me for hr interview",
    "make me ready for hr interview": "prepare me for hr interview",


# SOFTWARE ENGINEER INTERVIEW


    "prepare me for software engineer interview":
        "prepare me for software engineer interview",

    "help me prepare for software engineer interview":
        "prepare me for software engineer interview",

    "software engineer interview preparation":
        "prepare me for software engineer interview",

    "prepare for software engineer interview":
        "prepare me for software engineer interview",

    "how should i prepare for software engineer interview":
        "prepare me for software engineer interview",

    "how do i prepare for software engineer interview":
        "prepare me for software engineer interview",

    "help me with software engineer interview":
        "prepare me for software engineer interview",

    "i have a software engineer interview":
        "prepare me for software engineer interview",

    "help me prepare for my software engineer interview":
        "prepare me for software engineer interview",

    "can you prepare me for software engineer interview":
        "prepare me for software engineer interview",

    "get me ready for software engineer interview":
        "prepare me for software engineer interview",


# SOFTWARE DEVELOPER


    "prepare me for software developer interview":
        "prepare me for software developer interview",

    "help me prepare for software developer interview":
        "prepare me for software developer interview",

    "software developer interview preparation":
        "prepare me for software developer interview",

    "prepare for software developer interview":
        "prepare me for software developer interview",

    "how do i prepare for software developer interview":
        "prepare me for software developer interview",

    "help me with software developer interview":
        "prepare me for software developer interview",


# BACKEND DEVELOPER


    "prepare me for backend developer interview":
        "prepare me for backend developer interview",

    "help me prepare for backend developer interview":
        "prepare me for backend developer interview",

    "backend developer interview preparation":
        "prepare me for backend developer interview",

    "prepare for backend developer interview":
        "prepare me for backend developer interview",

    "how do i prepare for backend developer interview":
        "prepare me for backend developer interview",


# FRONTEND DEVELOPER


    "prepare me for frontend developer interview":
        "prepare me for frontend developer interview",

    "help me prepare for frontend developer interview":
        "prepare me for frontend developer interview",

    "frontend developer interview preparation":
        "prepare me for frontend developer interview",

    "prepare for frontend developer interview":
        "prepare me for frontend developer interview",

    "how do i prepare for frontend developer interview":
        "prepare me for frontend developer interview",


# FULL STACK DEVELOPER


    "prepare me for full stack developer interview":
        "prepare me for full stack developer interview",

    "help me prepare for full stack developer interview":
        "prepare me for full stack developer interview",

    "full stack developer interview preparation":
        "prepare me for full stack developer interview",

    "prepare for full stack developer interview":
        "prepare me for full stack developer interview",


# JAVA DEVELOPER


    "prepare me for java developer interview":
        "prepare me for java developer interview",

    "help me prepare for java developer interview":
        "prepare me for java developer interview",

    "java developer interview preparation":
        "prepare me for java developer interview",

    "prepare for java developer interview":
        "prepare me for java developer interview",


# PYTHON DEVELOPER


    "prepare me for python developer interview":
        "prepare me for python developer interview",

    "help me prepare for python developer interview":
        "prepare me for python developer interview",

    "python developer interview preparation":
        "prepare me for python developer interview",

    "prepare for python developer interview":
        "prepare me for python developer interview",


# RESUME


    "help me with my resume": "help me with my resume",
    "resume help": "help me with my resume",
    "help with my resume": "help me with my resume",
    "can you help with my resume": "help me with my resume",
    "help me improve my resume": "help me with my resume",
    "how can i improve my resume": "help me with my resume",
    "review my resume": "help me with my resume",
    "resume preparation": "help me with my resume",


# JOB SEARCH


    "help me find a job": "help me find a job",
    "help me find jobs": "help me find a job",
    "how can i find a job": "help me find a job",
    "how do i find a job": "help me find a job",
    "help with job search": "help me find a job",
    "help me search for jobs": "help me find a job",
    "i need a job": "help me find a job",


# CAREER


    "help me with my career": "help me with my career",
    "career advice": "help me with my career",
    "give me career advice": "help me with my career",
    "i need career advice": "help me with my career",
    "help me choose a career": "help me with my career",
    "which career should i choose": "help me with my career",


# INTERVIEW PRACTICE


    "practice interview with me": "practice interview with me",
    "help me practice for interview": "practice interview with me",
    "interview practice": "practice interview with me",
    "practice interview": "practice interview with me",
    "can we practice interview": "practice interview with me",
    "can you interview me": "practice interview with me",
    "give me an interview": "practice interview with me",
    "mock interview": "practice interview with me",
}

# ============================================================
# JOB CONVERSATION CONTEXT
# ============================================================

LAST_JOB_CONTEXT = None
def get_job_context_from_history(history):
    """
    Find the most recently discussed interview/job role
    from previous user messages.
    """

    if not history:
        return None

# Search newest messages first
    for item in reversed(history):

    # Support both dictionary messages and simple strings
        if isinstance(item, dict):
            message = item.get("content", "") or item.get("message", "")
        else:
            message = str(item)

        text = normalize_text(message)

    # Direct job context
        if text in JOB_CONTEXTS:
            context = JOB_CONTEXTS[text]

            if context != "__JOB_CONTEXT__":
                return context

    # Alias → canonical → job context
        canonical = QUESTION_ALIASES.get(text)

        if canonical and canonical in JOB_CONTEXTS:
            context = JOB_CONTEXTS[canonical]

            if context != "__JOB_CONTEXT__":
                return context

    return None
JOB_CONTEXTS = {
    "prepare me for hr interview": "HR",
    "prepare me for software engineer interview": "Software Engineer",
    "prepare me for software developer interview": "Software Developer",
    "prepare me for backend developer interview": "Backend Developer",
    "prepare me for frontend developer interview": "Frontend Developer",
    "prepare me for full stack developer interview": "Full-Stack Developer",
    "prepare me for java developer interview": "Java Developer",
    "prepare me for python developer interview": "Python Developer",
    "which job were you talking about": "__JOB_CONTEXT__",
    "which job were we talking about": "__JOB_CONTEXT__",
    "what job were you talking about": "__JOB_CONTEXT__",
    "what job was that": "__JOB_CONTEXT__",
    "which position were you talking about": "__JOB_CONTEXT__",
    "what position were you talking about": "__JOB_CONTEXT__",
    "which role were you talking about": "__JOB_CONTEXT__",
    "what role were you talking about": "__JOB_CONTEXT__",
    "what position was that": "__JOB_CONTEXT__",
    "what role was that": "__JOB_CONTEXT__",
    "which role was that": "__JOB_CONTEXT__",
    "what job was that for": "__JOB_CONTEXT__",
    "which position was that for": "__JOB_CONTEXT__",
    "what were we preparing for": "__JOB_CONTEXT__",
    "what interview were we talking about": "__JOB_CONTEXT__",
    "which interview were you talking about": "__JOB_CONTEXT__",
}
def normalize_text(message):

# Convert to lowercase
    text = message.lower().strip()

# Remove punctuation
    text = text.translate(
        str.maketrans("", "", string.punctuation)
    )

# Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def fast_response(message, history=None):

# -----------------------------------------
# 1. NORMALIZE USER MESSAGE
# -----------------------------------------
    text = normalize_text(message)

    global LAST_JOB_CONTEXT
    history_context = get_job_context_from_history(history)

    if history_context:
        LAST_JOB_CONTEXT = history_context
# -----------------------------------------
# 1.5 DETECT JOB CONTEXT BEFORE RESPONDING
# -----------------------------------------

# Direct canonical job question
    if text in JOB_CONTEXTS:
        context = JOB_CONTEXTS[text]

        if context != "__JOB_CONTEXT__":
            LAST_JOB_CONTEXT = context

# Alias → canonical question → job context
    canonical = QUESTION_ALIASES.get(text)

    if canonical in JOB_CONTEXTS:
        context = JOB_CONTEXTS[canonical]

        if context != "__JOB_CONTEXT__":
            LAST_JOB_CONTEXT = context
# -----------------------------------------
# 2. CHECK NORMAL FAST RESPONSES
# -----------------------------------------
    if text in FAST_RESPONSES:
        return FAST_RESPONSES[text]

# -----------------------------------------
# 3. CHECK JOB FAST RESPONSES
# -----------------------------------------
    if text in JOB_FAST_RESPONSES:
        return JOB_FAST_RESPONSES[text]

# -----------------------------------------
# 4. CHECK QUESTION ALIASES
# -----------------------------------------
    canonical = QUESTION_ALIASES.get(text)
    if canonical in JOB_CONTEXTS:
        LAST_JOB_CONTEXT = JOB_CONTEXTS[canonical]
    if canonical:

    # Job-context follow-up
        if canonical == "__JOB_CONTEXT__":
            if LAST_JOB_CONTEXT:
                return (
                    f"We were talking about a {LAST_JOB_CONTEXT} interview. "
                    f"That was the job you were preparing for."
                )
            else:
                return (
                    "We haven't discussed a specific job yet. "
                    "Tell me which job or role you want to prepare for."
                )

    # Normal alias
        if canonical in FAST_RESPONSES:
            return FAST_RESPONSES[canonical]

        if canonical in JOB_FAST_RESPONSES:
            return JOB_FAST_RESPONSES[canonical]

# -----------------------------------------
# 5. REMOVE COMMON FILLER WORDS
# -----------------------------------------
    fillers = {
        "bro",
        "buddy",
        "man",
        "mate",
        "please",
        "hello",
        "hi",
        "hey",
        "dear"
    }

    words = text.split()

    cleaned_words = [
        word for word in words
        if word not in fillers
    ]

    cleaned = " ".join(cleaned_words)

# -----------------------------------------
# 6. CHECK NORMAL RESPONSES AGAIN
# -----------------------------------------
    if cleaned in FAST_RESPONSES:
        return FAST_RESPONSES[cleaned]

# -----------------------------------------
# 7. CHECK JOB RESPONSES AGAIN
# -----------------------------------------
    if cleaned in JOB_FAST_RESPONSES:
        return JOB_FAST_RESPONSES[cleaned]

# -----------------------------------------
# 8. CHECK ALIASES AGAIN
# -----------------------------------------
    canonical = QUESTION_ALIASES.get(cleaned)

    if canonical:

        if canonical in FAST_RESPONSES:
            return FAST_RESPONSES[canonical]

        if canonical in JOB_FAST_RESPONSES:
            return JOB_FAST_RESPONSES[canonical]

# -----------------------------------------
# 9. UNKNOWN → MAIN AI
# -----------------------------------------
    return None