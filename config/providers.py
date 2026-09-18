PROVIDER_REGISTRY = {
    "gemini": {
        "name": "Google Gemini",
        "enabled": True,
        "adapter": "gemini",
        "quota_type": "provider_defined",
        "models": ["gemini-3.6-flash"],
        "capacity_pools": {
            "gemini_key_1": {
                "name": "Gemini API Key 1",
                "env_key": "GEMINI_API_KEY",
                "enabled": True,
                "adapter": "gemini",
                "api_key_number": 1,
            },
            "gemini_key_2": {
                "name": "Gemini API Key 2",
                "env_key": "GEMINI_API_KEY_2",
                "enabled": True,
                "adapter": "gemini",
                "api_key_number": 2,
            },
        },
    },

    "gpt_oss": {
        "name": "GPT-OSS 120B",
        "enabled": True,
        "adapter": "gpt_oss",
        "quota_type": "provider_defined",
        "models": ["gpt-oss-120b"],
    },

    "qwen": {
        "name": "Qwen 3 235B",
        "enabled": True,
        "adapter": "qwen",
        "quota_type": "provider_defined",
        "models": ["qwen3-235b"],
    },

    "cloudflare": {
        "name": "Cloudflare Workers AI",
        "enabled": True,
        "adapter": "cloudflare",
        "quota_type": "neurons",
        "models": ["llama-3.1-8b"],
    },

    "mistral": {
        "name": "Mistral AI",
        "enabled": True,
        "adapter": "mistral",
        "quota_type": "provider_defined",
        "models": ["mistral-small-latest"],
    },

    "groq": {
        "name": "Groq",
        "enabled": True,
        "adapter": "groq",
        "quota_type": "provider_defined",
        "models": ["gpt-oss-120b"],
        "capacity_pools": {
            "groq_key_1": {
                "name": "Groq API Key 1",
                "env_key": "GROQ_API_KEY",
                "enabled": True,
                "adapter": "groq",
                "api_key_number": 1,
            },
        },
    },

    "llama": {
        "name": "Llama 3.1 8B",
        "enabled": True,
        "adapter": "llama",
        "quota_type": "provider_defined",
        "models": ["llama-3.1-8b"],
    },
        "openrouter": {
        "name": "OpenRouter",
        "enabled": True,
        "adapter": "openrouter",
        "quota_type": "provider_defined",
        "models": ["openrouter/free"],
    },
}
