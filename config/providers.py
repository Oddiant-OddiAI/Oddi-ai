PROVIDER_REGISTRY = {
    "gemini": {
        "name": "Google Gemini",
        "enabled": True,
        "adapter": "gemini",
        "quota_type": "provider_defined",
        "models": {},
    },

    "cloudflare": {
        "name": "Cloudflare Workers AI",
        "enabled": True,
        "adapter": "cloudflare",
        "quota_type": "neurons",
        "models": {},
    },

    "mistral": {
        "name": "Mistral AI",
        "enabled": True,
        "adapter": "mistral",
        "quota_type": "provider_defined",
        "models": {},
    },
}