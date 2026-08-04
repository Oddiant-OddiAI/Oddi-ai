MAX_HISTORY = 11


def trim_history(chat_history):

    if len(chat_history) > MAX_HISTORY:

        system_prompt = chat_history[0]

        recent_history = chat_history[-(MAX_HISTORY - 1):]

        chat_history = [system_prompt] + recent_history

    return chat_history