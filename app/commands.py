from app.help_menu import show_help
from app.stats import show_stats

def handle_command(message):

    if message.lower() == "/help":
        return show_help()
    elif message.lower() == "/stats":
        return show_stats()
    
    return None

