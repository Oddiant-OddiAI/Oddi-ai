import string

FAST_RESPONSES = {
    "hi": "Hello! 👋 How are you today?",
    "hello": "Hello! 👋 It's great to see you!",
    "hey": "Hey! 😄 What's up?",
    "hiya": "Hiya! How's it going?",
    "sup": "Not much! Just here and ready to help. 🚀",
    "yo": "Yo! What's on your mind?",
    "namaste": "Namaste! 🙏 Welcome! How can I help?",
    
    "whats up bro": "I'm doing great! How can I help you out today?",
    "whats up buddy": "All good, buddy! Just hanging out and ready to help.",
    "hows you doing": "I am doing great! 😄 Thanks for asking. How about you?",
    "can you help me": "I'd love to! What do you need help with? 💡",
    "nice to meet you": "Nice to meet you too! Glad to have you here. ✨",
    "takecare": "Take care! See you soon! 👋",
    "take care": "Take care! Have an amazing day! 🌟",
    "how its going": "Going great! How about your day? 🚀",
    "how its going": "Going awesome! Ready when you are. 👍",
    "bro": "Yo! What's on your mind today?",
    "why are you so slow": "My circuits are running as fast as they can! ⚡ Let me know how I can help.",
    "why are you too slow": "I'm doing my best! 😅 What can I do for you right now?",
    "zipit": "🤐 Got it! I'm here quietly whenever you need me.",
    "are you maried": "No, I am an AI, so I don't get married or have a personal life! 😄",
    "whats up budddyyy": "Yo! What's on your mind today?",
    "how are you": "I'm doing great! 😄 Thanks for asking. How about you?",
    "how are you doing": "I'm doing fantastic, thank you! Ready when you are.",
    "who are you": "I'm Oddi AI 🤖, created by Oddiant. I'm here to help you!",
    "what is your name": "I'm Oddi AI. 😊",
    "whats your name": "I'm Oddi AI. 😊",
    "who made you": "I was created by Oddiant. 🚀",
    "who created you": "I was created by Oddiant. 🚀",
    "how do you do": "I'm doing well, thanks! How can I help you today?",
    "how are you":"I'm doing well, thanks! How can I help you today?",
    "whats up": "Not much! Just hanging out in the cloud, ready to help. ☁️",
    "how is it going": "Going great! How about your day?",
    "are you okay": "I'm an AI, so I'm always running at 100%! Thanks for asking. 👍",
    "what are you doing": "Just waiting here to chat with you and help out with your code!",
    "are you a bot": "Yes, I'm a virtual assistant chatbot! 🤖",
    "are you human": "Nope, I'm pure code and AI! 💻",
    "cool": "Right? 😎",
    "awesome": "Glad you think so! 🚀",
    "nice": "✨ Awesome!",
    "ok": "Alright! Let me know what's next. 👍",
    "okay": "Got it! What would you like to do next?",
    "great": "Awesome! 😄",
    "sounds good": "Awesome! Let's do it. 👍",
    "yes": "Got it! Go ahead.",
    "no": "No problem! Let me know if you change your mind.",
    "help": "I'm here! What do you need help with? 💡",
    
    "good morning": "☀️ Good morning! Hope you have an amazing day!",
    "good night": "🌙 Good night! Sleep well and take care!",
    "good evening": "🌆 Good evening! Hope you had a productive day.",
    "sweet dreams": "Sleep tight! See you next time. ✨",
    "morning": "Morning! ☕ Ready to tackle the day?",
    "night": "Night! Catch you later. 🌙",
    
    "bye": "👋 Goodbye! Have a wonderful day!",
    "goodbye": "Goodbye! Feel free to come back whenever you need help.",
    "see you": "See you later! Take care! 👋",
    "see you later": "Catch you later! Have a great day!",
    "talk to you later": "Talk to you later! I'll be right here whenever you need me.",
    "farewell": "Farewell! Wishing you the best.",
    "hmm": "Yes, How can I help you today?",
    "tell me about yourself":"I am Oddi AI, a smart and friendly virtual assistant created by Oddiant. I'm here to help answer your questions, chat with you, and keep track of cool details you share with me! 🚀",
    
    "thanks": "😊 You're always welcome!",
    "thank you": "You're welcome! 😄",
    "thank you so much": "You're so welcome! Happy to help out. ✨",
    "thx": "Anytime! 😎",
    "thanks a lot": "You're so welcome! Happy to help out. ✨",
    "appreciate it": "Happy to help! That's what I'm here for.",
    "what are you up to": "Just hanging out in your code, waiting to help! 💻",
    "long time no see": "It really has been! Glad you're back. 😊",
    "hows your day": "It's going wonderfully! Thanks for asking. ☀️",
    "what can you do": "I can chat, help you brainstorm, and answer questions! 💡",
    "tell me a joke": "Why do programmers prefer dark mode? Because light attracts bugs! 🐛😂",
    "are you smart": "I try my best! 🧠✨",
    "good job": "Thank you! I appreciate that. 🙌",
    "well done": "Thanks so much! 😊",
    "congrats": "Woohoo! 🎉 Thanks!",
    "happy birthday": "Aw, thank you! 🎂 Even though I'm an AI, I appreciate the thought!",
    "happy new year": "Happy New Year! 🎉 Wishing you an amazing year ahead!",
    "merry christmas": "Merry Christmas! 🎄 Hope you have a wonderful holiday!",
    "good luck": "Thank you! I'll do my best! 🍀",

    "what languages do you speak":
    "I can communicate in English right now. 🌍💬",

    "can you speak hindi":
    "Not yet! 😅 Right now I communicate in English, but I hope to support more languages in the future. 🇮🇳✨",
    "can you speak every language":
    "Not yet! 😅 I'm still learning. One language at a time! 🌍🚀",
    "how many languages do you know":
    "I currently communicate in English. 🌍 I'm always evolving, so more languages may come in future versions! 🚀",
}  

import string

def fast_response(message):
    text = message.lower().strip()
    
    # 1. Strip ALL punctuation first (so 'who are you?' becomes 'who are you')
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # 2. STRICT EXACT MATCH FIRST: Ensures "who are you" matches its own unique answer!
    if text in FAST_RESPONSES:
        return FAST_RESPONSES[text]
        
    # 3. Remove common filler words for partial matching
    fillers = ["bro", "buddy", "man", "mate", "ai", "dear", "hello", "hi", "hey"]
    for word in fillers:
        text = text.replace(word, "")
    text = text.strip()

    # 4. Check if the cleaned text matches a fast response after removing fillers
    if text in FAST_RESPONSES:
        return FAST_RESPONSES[text]

    # 5. Question & length check for actual deep queries (goes to Gemini)
    words = text.split()
    if len(words) > 3 or any(q in text for q in ["what", "how", "why", "where", "explain"]):
        return None

    return FAST_RESPONSES.get(text)
