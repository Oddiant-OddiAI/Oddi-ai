# ==========================================================
# ODDI-AI PROVIDER / CAPACITY LIMITS
# ==========================================================
#
# Quota scope:
# - Provider-level quotas apply to the provider itself.
# - Capacity-level quotas apply to an individual API key/pool.
#
# User quota scope:
# - User-level limits apply independently from provider capacity.
# - Default users receive at least 10 requests/day.
# - Default users receive 2000 tokens/day.
# - Role-based limits allow trusted elevated roles to be exempt.
#
# None means the exact provider limit has not been configured yet.
# Runtime usage is tracked independently for every capacity pool.
#
# Provider limits below describe external provider capacity.
# USER_LIMITS describes ODDI product-level fair-use policy.
# ==========================================================


# ==========================================================
# ODDI-AI USER LIMITS / FAIR-USE POLICY
# ==========================================================
#
# rpd = requests per UTC calendar day
# tpd = tokens per UTC calendar day
# rpm = rolling requests per minute fair-use guard
# tpm = rolling tokens per minute fair-use guard
#
# The 10-request and 2000-token values are the default minimum
# product allowance for ordinary users.
#
# Priority is supplied by the identity / permissions / memory layer;
# this configuration only defines the policy attached to a role.
#
# None means that dimension is not restricted for that role.
# ==========================================================

USER_LIMITS = {

    "user": {
        "rpd": 10,
        "tpd": 2000,

        # Fair-use protection. This is separate from the daily
        # product allowance and prevents short bursts from consuming
        # shared provider capacity.
        "rpm": 5,
        "tpm": 2000,

        "priority": "normal",
    },

    "member": {
        "rpd": 10,
        "tpd": 2000,
        "rpm": 5,
        "tpm": 2000,
        "priority": "normal",
    },

    "admin": {
        "rpd": None,
        "tpd": None,
        "rpm": None,
        "tpm": None,
        "priority": "high",
    },

    "owner": {
        "rpd": None,
        "tpd": None,
        "rpm": None,
        "tpm": None,
        "priority": "highest",
    },
}


# ==========================================================
# ODDI-AI PROVIDER / CAPACITY LIMITS
# ==========================================================

PROVIDER_LIMITS = {

    "gemini": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {
            "source": "provider_runtime",
        },
        "capacity_pools": {

            "gemini_key_1": {
                "rpm": None,
                "rpd": None,
                "tpm": None,
                "tpd": None,
                "custom": {
                    "source": "provider_runtime",
                },
            },

            "gemini_key_2": {
                "rpm": None,
                "rpd": None,
                "tpm": None,
                "tpd": None,
                "custom": {
                    "source": "provider_runtime",
                },
            },

            "gemini_key_3": {
                "rpm": None,
                "rpd": None,
                "tpm": None,
                "tpd": None,
                "custom": {
                    "source": "provider_runtime",
                },
            },

            "gemini_key_4": {
                "rpm": None,
                "rpd": None,
                "tpm": None,
                "tpd": None,
                "custom": {
                    "source": "provider_runtime",
                },
            },
        },
    },

    "mistral": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {
            "source": "provider_runtime",
        },
    },

    "cloudflare": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {
            "neurons_per_day": 10000,
            "source": "workers_ai_free_allocation",
        },
    },

    "groq": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {
            "source": "provider_runtime",
        },
        "capacity_pools": {

            "groq_key_1": {
                "rpm": None,
                "rpd": None,
                "tpm": None,
                "tpd": None,
                "custom": {
                    "source": "provider_runtime",
                },
            },

            "groq_key_2": {
                "rpm": None,
                "rpd": None,
                "tpm": None,
                "tpd": None,
                "custom": {
                    "source": "provider_runtime",
                },
            },
        },
    },

    "openrouter": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {
            "source": "provider_runtime",
        },
    },

    # Registered providers without a currently connected adapter.
    "gpt_oss": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {},
    },

    "qwen": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {},
    },
}