PLATFORM_CAPABILITIES = {

    "chat": {
        "store": True,
        "retrieve": True,
        "rename": True,
        "delete": True,
    },

    "voice": {
        "available": True,
        "change": True,
    },

    "files": {
        "upload": True,
        "analyze": True,
    },

    "jobs": {
        "search": True,
        "save": True,
        "apply": True,
    },

    "resume": {
        "create": True,
        "edit": True,
        "save": True,
    },

    "applications": {
        "track": True,
        "view": True,
    },

    "settings": {
        "view": True,
        "change": True,
    },
}


def has_capability(capability: str) -> bool:
    """
    Example:
        has_capability("chat.store")
        has_capability("voice.change")
    """

    parts = capability.split(".")

    if len(parts) != 2:
        return False

    category, action = parts

    return PLATFORM_CAPABILITIES.get(
        category,
        {}
    ).get(action, False)