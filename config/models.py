MODEL_REGISTRY = {
    "gpt_oss": {
        "gpt-oss-120b": {
            "name": "GPT-OSS 120B",
            "enabled": True,
        },
    },

    "qwen": {
        "qwen3-235b": {
            "name": "Qwen 3 235B",
            "enabled": True,
        },
    },

    "cloudflare": {
        "llama-3.1-8b": {
            "name": "Llama 3.1 8B",
            "enabled": True,
        },
    },

    "mistral": {
        "mistral-small-latest": {
            "name": "Mistral Small",
            "enabled": True,
        },
    },

    "gemini": {
        "gemini-3.6-flash": {
            "name": "Gemini 3.6 Flash",
            "enabled": True,
            "capacity_pools": [
                "gemini_key_1",
                "gemini_key_2",
            ],
        },
    },

    "groq": {
        "gpt-oss-120b": {
            "name": "GPT-OSS 120B via Groq",
            "enabled": True,
            "capacity_pools": [
                "groq_key_1",
            ],
        },
    },
    "openrouter": {
        "openrouter/free": {
            "name": "OpenRouter Free Router",
            "enabled": True,
        },
    },
}
