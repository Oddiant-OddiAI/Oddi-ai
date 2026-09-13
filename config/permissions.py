ROLE_PERMISSIONS = {

    "owner": {
        "analytics.read": True,
        "analytics.manage": True,
        "users.read": True,
        "users.manage": True,
        "limits.read": True,
        "limits.manage": True,
        "providers.read": True,
        "providers.manage": True,
        "platform.read": True,
        "platform.manage": True,
    },

    "admin": {
        "analytics.read": True,
        "analytics.manage": False,
        "users.read": True,
        "users.manage": False,
        "limits.read": True,
        "limits.manage": False,
        "providers.read": True,
        "providers.manage": False,
        "platform.read": True,
        "platform.manage": False,
    },

    "user": {
        "analytics.read": False,
        "analytics.manage": False,
        "users.read": False,
        "users.manage": False,
        "limits.read": False,
        "limits.manage": False,
        "providers.read": False,
        "providers.manage": False,
        "platform.read": True,
        "platform.manage": False,
    },
}