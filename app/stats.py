from app.constants import VERSION
from app.memory_store import memory
from app import state


def show_stats():
    return f"""
📊 Oddi AI Statistics

🚀 Version          : {VERSION}
🧠 Stored Memories  : {len(memory)}
📚 ExplanationMode       : {"ON" if state.study_mode else "OFF"}
🤖 AI Name          : {state.current_name}
"""