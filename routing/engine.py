from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from providers.registry import ProviderRegistry
from quota.manager import QuotaManager, quota_manager
from config.limits import USER_LIMITS
from reliability.manager import RELIABILITY_MANAGER


load_dotenv()


# One process-wide quota manager keeps provider usage available to all
# RoutingEngine instances during the lifetime of the ODDI process.
QUOTA_MANAGER = quota_manager


# ---------------------------------------------------------------------------
# PROVIDER CONNECTIVITY
# ---------------------------------------------------------------------------
# These providers have working adapters in providers/adapters.py.
CONNECTED_PROVIDERS = {
    "gemini",
    "mistral",
    "groq",
    "cloudflare",
    "openrouter",
}


# ---------------------------------------------------------------------------
# CAPACITY POOLS
# ---------------------------------------------------------------------------
# Gemini quota is project/capacity based, so each configured Gemini key is
# represented independently.  The adapter maps key_number -> .env variable.
#
# Groq is also represented as two independent credentials because the
# adapter supports both GROQ_API_KEY and GROQ_API_KEY_1.
#
# The environment check below means an absent credential is never selected.
GEMINI_CAPACITIES = {
    "gemini_key_1": {"provider": "gemini", "api_key_number": 1, "env": "GEMINI_API_KEY"},
    "gemini_key_2": {"provider": "gemini", "api_key_number": 2, "env": "GEMINI_API_KEY_2"},
    "gemini_key_3": {"provider": "gemini", "api_key_number": 3, "env": "GEMINI_API_KEY_3"},
    "gemini_key_4": {"provider": "gemini", "api_key_number": 4, "env": "GEMINI_API_KEY_4"},
}

GROQ_CAPACITIES = {
    "groq_key_1": {"provider": "groq", "api_key_number": 1, "env": "GROQ_API_KEY"},
    "groq_key_2": {"provider": "groq", "api_key_number": 2, "env": "GROQ_API_KEY_1"},
}

SINGLE_CAPACITIES = {
    "mistral": {"provider": "mistral", "api_key_number": None, "env": "MISTRAL_API_KEY"},
    "cloudflare": {"provider": "cloudflare", "api_key_number": None, "env": "CLOUDFLARE_API_TOKEN"},
    "openrouter": {"provider": "openrouter", "api_key_number": None, "env": "OPENROUTER_API_KEY"},
}


# ---------------------------------------------------------------------------
# ROUTING ORDER
# ---------------------------------------------------------------------------
# The order is deliberately capacity-aware:
#
#   1. Gemini Flash-Lite = primary high-volume lane
#   2. Mistral            = secondary high-throughput lane
#   3. Groq               = quality/reasoning fallback
#   4. Cloudflare         = compute-efficient fallback
#   5. OpenRouter         = final overflow/fallback
#
# The router does not blindly fail over at the provider level: every
# capacity/model candidate is still checked for health, quota, concurrency,
# capability and score.
FALLBACK_GROUPS = [
    {"gemini"},
    {"mistral"},
    {"groq"},
    {"cloudflare"},
    {"openrouter"},
]

PROVIDER_FALLBACK_PRIORITY = {
    provider: index
    for index, group in enumerate(FALLBACK_GROUPS)
    for provider in group
}


# ---------------------------------------------------------------------------
# MODEL PROFILES
# ---------------------------------------------------------------------------
# These are the models that the Phase-4 adapters can actually execute.
# Registry metadata is still consulted when available, but these profiles
# prevent the router from remaining stuck on the old legacy model names.
MODEL_PROFILES: Dict[str, Dict[str, Any]] = {
    "gemini-3.5-flash-lite": {
        "provider": "gemini",
        "strengths": {
            "general_chat",
            "reasoning",
            "coding",
            "education",
            "analysis",
            "simple",
            "fast",
            "complex",
        },
        "supports_web": False,
        "supports_files": True,
        "supports_images": False,
        "supports_video": False,
        "quality": 8,
        "speed": 10,
        "role": "primary",
    },
    "gemini-3.6-flash": {
        "provider": "gemini",
        "strengths": {
            "general_chat",
            "reasoning",
            "coding",
            "education",
            "analysis",
            "simple",
            "fast",
            "complex",
        },
        "supports_web": False,
        "supports_files": True,
        "supports_images": False,
        "supports_video": False,
        "quality": 9,
        "speed": 9,
        "role": "premium",
    },
    "ministral-3b-2512": {
        "provider": "mistral",
        "strengths": {
            "general_chat",
            "reasoning",
            "coding",
            "education",
            "analysis",
            "simple",
            "fast",
        },
        "supports_web": False,
        "supports_files": True,
        "supports_images": False,
        "supports_video": False,
        "quality": 7,
        "speed": 10,
        "role": "secondary",
    },
    "mistral-small-latest": {
        "provider": "mistral",
        "strengths": {
            "general_chat",
            "reasoning",
            "coding",
            "education",
            "analysis",
            "simple",
            "complex",
        },
        "supports_web": False,
        "supports_files": True,
        "supports_images": False,
        "supports_video": False,
        "quality": 8,
        "speed": 8,
        "role": "secondary_premium",
    },
    "gpt-oss-120b": {
        "provider": "groq",
        "strengths": {
            "general_chat",
            "reasoning",
            "coding",
            "education",
            "analysis",
            "complex",
        },
        "supports_web": False,
        "supports_files": True,
        "supports_images": False,
        "supports_video": False,
        "quality": 10,
        "speed": 8,
        "role": "reasoning_fallback",
    },
    "llama-3.1-8b": {
        "provider": "cloudflare",
        "strengths": {
            "general_chat",
            "education",
            "coding",
            "simple",
            "fast",
        },
        "supports_web": False,
        "supports_files": True,
        "supports_images": False,
        "supports_video": False,
        "quality": 6,
        "speed": 10,
        "role": "compute_fallback",
    },
    "openrouter/free": {
        "provider": "openrouter",
        "strengths": {
            "general_chat",
            "reasoning",
            "coding",
            "education",
            "analysis",
            "simple",
            "fast",
            "complex",
        },
        "supports_web": False,
        "supports_files": False,
        "supports_images": False,
        "supports_video": False,
        "quality": 7,
        "speed": 8,
        "role": "overflow",
    },
}


# Provider -> adapter-backed default models.
DEFAULT_MODELS = {
    "gemini": ["gemini-3.5-flash-lite", "gemini-3.6-flash"],
    "mistral": ["ministral-3b-2512", "mistral-small-latest"],
    "groq": ["gpt-oss-120b"],
    "cloudflare": ["llama-3.1-8b"],
    "openrouter": ["openrouter/free"],
}


DEFAULT_PROVIDER_STATE = {
    "healthy": True,
    "quota_available": True,
    "latency_ms": 500,
    "active_requests": 0,
    "max_concurrency": 10,
}


USER_PRIORITY = {
    "owner": 100,
    "admin": 75,
    "user": 50,
}


def _env_configured(name: str) -> bool:
    return bool(os.getenv(name))


class RoutingEngine:
    """
    ODDI-AI routing engine.

    Responsibilities:
      - understand request requirements
      - discover available provider/model/capacity candidates
      - check quota, health and concurrency
      - score candidates
      - return an ordered fallback route

    This layer DOES NOT make API calls.
    """

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        provider_state: Optional[Dict[str, Dict[str, Any]]] = None,
        quota_manager: Optional[QuotaManager] = None,
    ):
        self.registry = registry or ProviderRegistry()
        self.provider_state = provider_state or {}
        self.quota_manager = quota_manager or QUOTA_MANAGER

    # -----------------------------------------------------------------------
    # CAPACITY HELPERS
    # -----------------------------------------------------------------------

    def _capacities_for_provider(self, provider_id: str) -> Dict[str, Dict[str, Any]]:
        if provider_id == "gemini":
            return GEMINI_CAPACITIES

        if provider_id == "groq":
            return GROQ_CAPACITIES

        return {
            provider_id: SINGLE_CAPACITIES.get(
                provider_id,
                {
                    "provider": provider_id,
                    "api_key_number": None,
                    "env": None,
                },
            )
        }

    def _capacity_configured(self, capacity: Dict[str, Any]) -> bool:
        env_name = capacity.get("env")
        if not env_name:
            return True
        return _env_configured(env_name)

    def _quota_available(
        self,
        provider_id: str,
        capacity_id: Optional[str],
    ) -> bool:
        """
        Support both current QuotaManager signatures:
          has_quota(provider, capacity_id)
        and older:
          has_quota(provider_or_capacity)
        """
        try:
            return bool(
                self.quota_manager.has_quota(
                    provider_id,
                    capacity_id,
                )
            )
        except TypeError:
            quota_key = capacity_id or provider_id
            return bool(self.quota_manager.has_quota(quota_key))

    def _reliability_state(
        self,
        provider_id: str,
        capacity_id: Optional[str],
    ) -> Dict[str, Any]:
        try:
            state = RELIABILITY_MANAGER.get_state(
                provider_id,
                capacity_id,
            )
            return state if isinstance(state, dict) else {}
        except (AttributeError, TypeError):
            return {}

    # -----------------------------------------------------------------------
    # PROVIDER STATE
    # -----------------------------------------------------------------------

    def get_provider_state(
        self,
        provider_id: str,
        capacity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = dict(DEFAULT_PROVIDER_STATE)

        state_key = capacity_id or provider_id
        custom_state = self.provider_state.get(
            state_key,
            self.provider_state.get(provider_id, {}),
        )

        if isinstance(custom_state, dict):
            state.update(custom_state)

        state["configured"] = self._capacity_configured(
            self._capacity_config_for(provider_id, capacity_id)
        )

        if not state["configured"]:
            state["healthy"] = False
            state["quota_available"] = False
            return state

        state["quota_available"] = self._quota_available(
            provider_id,
            capacity_id,
        )

        reliability = self._reliability_state(
            provider_id,
            capacity_id,
        )

        if reliability:
            state["reliability"] = reliability
            state["healthy"] = (
                state.get("healthy", True)
                and reliability.get("healthy", True)
            )

        return state

    def _capacity_config_for(
        self,
        provider_id: str,
        capacity_id: Optional[str],
    ) -> Dict[str, Any]:
        capacities = self._capacities_for_provider(provider_id)

        if capacity_id in capacities:
            return capacities[capacity_id]

        return capacities.get(
            provider_id,
            {
                "provider": provider_id,
                "api_key_number": None,
                "env": None,
            },
        )

    # -----------------------------------------------------------------------
    # MODEL DISCOVERY
    # -----------------------------------------------------------------------

    def _registry_models(self, provider_id: str) -> Dict[str, Dict[str, Any]]:
        try:
            models = self.registry.get_models(provider_id)
        except (AttributeError, KeyError, TypeError):
            return {}

        return models if isinstance(models, dict) else {}

    def _model_candidates(self, provider_id: str) -> List[Dict[str, Any]]:
        """
        Build the adapter-backed model list.

        Registry entries are retained when they match an adapter-backed model.
        Current adapter defaults are then added so an old registry entry cannot
        silently prevent the new architecture from routing.
        """
        registry_models = self._registry_models(provider_id)
        result: List[Dict[str, Any]] = []
        seen = set()

        # Prefer current adapter-backed models.
        for model_id in DEFAULT_MODELS.get(provider_id, []):
            if model_id in seen:
                continue

            registry_config = registry_models.get(model_id, {})
            profile = MODEL_PROFILES.get(model_id)

            if not profile:
                continue

            result.append(
                {
                    "model": model_id,
                    "name": registry_config.get(
                        "name",
                        self._display_name(model_id),
                    ),
                    "enabled": registry_config.get("enabled", True),
                    "profile": profile,
                }
            )
            seen.add(model_id)

        # Preserve compatible registered models not already in defaults.
        for model_id, config in registry_models.items():
            if model_id in seen or model_id not in MODEL_PROFILES:
                continue

            if MODEL_PROFILES[model_id].get("provider") != provider_id:
                continue

            result.append(
                {
                    "model": model_id,
                    "name": config.get(
                        "name",
                        self._display_name(model_id),
                    ),
                    "enabled": config.get("enabled", False),
                    "profile": MODEL_PROFILES[model_id],
                }
            )

        return result

    @staticmethod
    def _display_name(model_id: str) -> str:
        names = {
            "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
            "gemini-3.6-flash": "Gemini 3.6 Flash",
            "ministral-3b-2512": "Ministral 3B",
            "mistral-small-latest": "Mistral Small",
            "gpt-oss-120b": "GPT-OSS 120B via Groq",
            "llama-3.1-8b": "Llama 3.1 8B via Cloudflare",
            "openrouter/free": "OpenRouter Free Router",
        }
        return names.get(model_id, model_id)

    # -----------------------------------------------------------------------
    # CANDIDATE DISCOVERY
    # -----------------------------------------------------------------------

    def discover_candidates(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        for provider_id in FALLBACK_PRIORITY_PROVIDERS():
            if provider_id not in CONNECTED_PROVIDERS:
                continue

            models = self._model_candidates(provider_id)
            if not models:
                continue

            capacities = self._capacities_for_provider(provider_id)

            for capacity_id, capacity_config in capacities.items():
                if not self._capacity_configured(capacity_config):
                    continue

                state = self.get_provider_state(
                    provider_id,
                    capacity_id,
                )

                for model in models:
                    if not model.get("enabled", True):
                        continue

                    profile = model["profile"]

                    candidates.append(
                        {
                            "provider": provider_id,
                            "model": model["model"],
                            "name": model["name"],
                            "profile": profile,
                            "provider_state": state,
                            "capacity_id": capacity_id,
                            "api_key_number": capacity_config.get(
                                "api_key_number"
                            ),
                            "fallback_priority": PROVIDER_FALLBACK_PRIORITY[
                                provider_id
                            ],
                        }
                    )

        return candidates

    # -----------------------------------------------------------------------
    # ELIGIBILITY
    # -----------------------------------------------------------------------

    def is_eligible(
        self,
        candidate: Dict[str, Any],
        request: Dict[str, Any],
    ) -> bool:
        profile = candidate.get("profile", {})
        state = candidate.get("provider_state", {})

        if not state.get("configured", True):
            return False

        if not state.get("healthy", False):
            return False

        if not state.get("quota_available", False):
            return False

        active = state.get("active_requests", 0)
        maximum = state.get("max_concurrency", 0)

        if maximum > 0 and active >= maximum:
            return False

        if request.get("requires_web", False) and not profile.get(
            "supports_web",
            False,
        ):
            return False

        if request.get("requires_file", False) and not profile.get(
            "supports_files",
            False,
        ):
            return False

        if request.get("requires_image", False) and not profile.get(
            "supports_images",
            False,
        ):
            return False

        if request.get("requires_video", False) and not profile.get(
            "supports_video",
            False,
        ):
            return False

        required_capabilities = request.get(
            "required_capabilities",
            [],
        ) or []

        # Capability IDs are platform/action capabilities rather than model
        # capabilities. Until a model explicitly declares them, don't route
        # platform-action requests to arbitrary LLMs.
        if request.get("requires_platform_action", False):
            if required_capabilities:
                return False

        return True

    # -----------------------------------------------------------------------
    # SCORING
    # -----------------------------------------------------------------------

    def capability_score(
        self,
        candidate: Dict[str, Any],
        request: Dict[str, Any],
    ) -> int:
        profile = candidate.get("profile", {})
        strengths = profile.get("strengths", set())

        intent = request.get("intent", "general_chat")
        domain = request.get("domain", "general")
        complexity = request.get("complexity", "low")

        score = 0

        if intent in strengths:
            score += 30

        if domain == "coding" and "coding" in strengths:
            score += 25
        elif domain == "education" and "education" in strengths:
            score += 20
        elif domain == "analysis" and "analysis" in strengths:
            score += 20

        if complexity == "high":
            if "complex" in strengths:
                score += 25
        elif complexity == "medium":
            if "reasoning" in strengths:
                score += 15
        elif "simple" in strengths:
            score += 15

        return score

    @staticmethod
    def quality_score(candidate: Dict[str, Any]) -> int:
        return int(candidate.get("profile", {}).get("quality", 0)) * 2

    @staticmethod
    def speed_score(candidate: Dict[str, Any]) -> int:
        return int(candidate.get("profile", {}).get("speed", 0))

    @staticmethod
    def latency_score(candidate: Dict[str, Any]) -> int:
        latency = candidate.get("provider_state", {}).get(
            "latency_ms",
            500,
        )

        if latency <= 200:
            return 20
        if latency <= 400:
            return 15
        if latency <= 700:
            return 10
        if latency <= 1000:
            return 5
        return 0

    @staticmethod
    def concurrency_score(candidate: Dict[str, Any]) -> int:
        state = candidate.get("provider_state", {})
        active = state.get("active_requests", 0)
        maximum = state.get("max_concurrency", 10)

        if maximum <= 0:
            return 0

        utilization = active / maximum

        if utilization <= 0.25:
            return 15
        if utilization <= 0.50:
            return 10
        if utilization <= 0.75:
            return 5
        return 0

    def user_priority_score(self, request: Dict[str, Any]) -> int:
        role = request.get("user_role", "user")
        return USER_PRIORITY.get(
            role,
            USER_PRIORITY["user"],
        ) // 10

    def model_role_score(
        self,
        candidate: Dict[str, Any],
        request: Dict[str, Any],
    ) -> int:
        """
        Keeps Flash-Lite as the volume model while allowing 3.6 Flash to win
        when the request is genuinely complex.

        The provider fallback priority still dominates, so premium models are
        never allowed to bypass an entirely exhausted Gemini provider group.
        """
        role = candidate.get("profile", {}).get("role")

        complexity = request.get("complexity", "low")

        if role == "primary":
            return 8

        if role == "premium":
            if complexity == "high":
                return 14
            if complexity == "medium":
                return 6
            return -2

        if role == "secondary":
            return 7

        if role == "secondary_premium":
            return 10 if complexity in {"medium", "high"} else 2

        if role == "reasoning_fallback":
            return 8 if complexity == "high" else 2

        if role == "compute_fallback":
            return 7

        if role == "overflow":
            return 1

        return 0

    def score_candidate(
        self,
        candidate: Dict[str, Any],
        request: Dict[str, Any],
    ) -> int:
        return (
            self.capability_score(candidate, request)
            + self.quality_score(candidate)
            + self.speed_score(candidate)
            + self.latency_score(candidate)
            + self.concurrency_score(candidate)
            + self.user_priority_score(request)
            + self.model_role_score(candidate, request)
        )

    # -----------------------------------------------------------------------
    # USER QUOTA / FAIR-USE GATE
    # -----------------------------------------------------------------------

    def _user_quota_context(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve user quota context from the trusted request identity.

        Authentication and identity resolution happen outside the router.
        The router only consumes the already-resolved values.

        Backward compatibility:
        - Existing internal route previews/tests that do not provide a
          user_id continue to behave as provider-routing previews.
        - Production requests should always provide user_id.
        """

        return {
            "user_id": request.get("user_id"),
            "user_role": request.get(
                "user_role",
                "user",
            ),
            "user_priority": request.get(
                "user_priority",
            ),
            "is_host": bool(
                request.get(
                    "is_host",
                    False,
                )
            ),
            "quota_exempt": bool(
                request.get(
                    "quota_exempt",
                    False,
                )
            ),
        }

    def _user_quota_allowed(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Perform the Phase-6 user quota gate BEFORE provider routing.

        The quota manager remains authoritative for usage/accounting.
        USER_LIMITS is imported here as the configured product policy
        and exposed in the route result for diagnostics.
        """

        context = self._user_quota_context(request)

        user_id = context["user_id"]

        # No user_id means this is a legacy/internal route preview.
        # Authenticated application traffic should always have one.
        if user_id is None:
            return {
                "checked": False,
                "allowed": True,
                "reason": "No user_id supplied; provider-only routing mode.",
                "user_id": None,
                **{
                    key: context[key]
                    for key in (
                        "user_role",
                        "user_priority",
                        "is_host",
                        "quota_exempt",
                    )
                },
            }

        estimated_tokens = request.get(
            "estimated_tokens",
            request.get(
                "tokens",
                0,
            ),
        )

        try:
            estimated_tokens = int(
                estimated_tokens or 0
            )
        except (TypeError, ValueError):
            estimated_tokens = 0

        if estimated_tokens < 0:
            estimated_tokens = 0

        allowed = self.quota_manager.has_user_quota(
            user_id=user_id,
            role=context["user_role"],
            priority=context["user_priority"],
            is_host=context["is_host"],
            quota_exempt=context["quota_exempt"],
            requests=1,
            tokens=estimated_tokens,
        )

        status = self.quota_manager.user_quota_status(
            user_id=user_id,
            role=context["user_role"],
            priority=context["user_priority"],
            is_host=context["is_host"],
            quota_exempt=context["quota_exempt"],
        )

        return {
            "checked": True,
            "allowed": bool(allowed),
            "reason": (
                "user_quota_available"
                if allowed
                else "user_quota_exceeded"
            ),
            "user_id": user_id,
            "user_role": context["user_role"],
            "user_priority": context["user_priority"],
            "is_host": context["is_host"],
            "quota_exempt": context["quota_exempt"],
            "status": status,
            "policy": USER_LIMITS.get(
                context["user_role"],
                USER_LIMITS.get("user", {}),
            ),
        }

    def _no_user_quota_route(
        self,
        user_quota: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a consistent pre-routing quota rejection."""

        return {
            "status": "user_quota_exhausted",
            "allowed": False,
            "provider": None,
            "model": None,
            "name": None,
            "score": None,
            "capacity_id": None,
            "api_key_number": None,
            "fallback_priority": None,
            "candidates": [],
            "user_quota": user_quota,
            "reason": user_quota.get(
                "reason",
                "user_quota_exceeded",
            ),
        }


    # -----------------------------------------------------------------------
    # ROUTING
    # -----------------------------------------------------------------------

    def route(self, request: Dict[str, Any]) -> Dict[str, Any]:
        # ---------------------------------------------------------------
        # PHASE 6: USER QUOTA GATE
        # ---------------------------------------------------------------
        # This must happen before candidate discovery/provider routing.
        user_quota = self._user_quota_allowed(request)

        if not user_quota["allowed"]:
            return self._no_user_quota_route(
                user_quota
            )

        candidates = self.discover_candidates()
        eligible: List[Dict[str, Any]] = []

        for candidate in candidates:
            if not self.is_eligible(candidate, request):
                continue

            eligible.append(
                {
                    **candidate,
                    "score": self.score_candidate(
                        candidate,
                        request,
                    ),
                }
            )

        if not eligible:
            return {
                "status": "no_route",
                "provider": None,
                "model": None,
                "name": None,
                "score": None,
                "capacity_id": None,
                "api_key_number": None,
                "candidates": [],
                "user_quota": user_quota,
                "reason": (
                    "No configured, healthy, available model currently "
                    "satisfies the request requirements."
                ),
            }

        # Provider fallback priority is the hard reliability boundary.
        # Within the same provider group, score decides the best model/capacity.
        eligible.sort(
            key=lambda item: (
                item["fallback_priority"],
                -item["score"],
                -item["profile"].get("quality", 0),
                item["provider_state"].get("latency_ms", 500),
                item["capacity_id"],
            )
        )

        best = eligible[0]

        return {
            "status": "routed",
            "provider": best["provider"],
            "model": best["model"],
            "name": best["name"],
            "score": best["score"],
            "capacity_id": best["capacity_id"],
            "api_key_number": best.get("api_key_number"),
            "fallback_priority": best["fallback_priority"],
            "user_quota": user_quota,
            "candidates": [
                {
                    "provider": item["provider"],
                    "model": item["model"],
                    "name": item["name"],
                    "score": item["score"],
                    "capacity_id": item["capacity_id"],
                    "api_key_number": item.get("api_key_number"),
                    "fallback_priority": item["fallback_priority"],
                }
                for item in eligible
            ],
            "reason": (
                "Selected the best healthy and available candidate using "
                "provider fallback priority, request capability, model "
                "quality, speed, latency, concurrency, user priority, "
                "user quota/fair-use eligibility, and model-role scoring. "
                "Gemini uses four independent capacity "
                "pools; Groq uses two; Mistral, Cloudflare, and OpenRouter "
                "provide secondary/fallback capacity."
            ),
        }


def FALLBACK_PRIORITY_PROVIDERS() -> List[str]:
    return [
        provider
        for provider, _ in sorted(
            PROVIDER_FALLBACK_PRIORITY.items(),
            key=lambda item: item[1],
        )
    ]


# ---------------------------------------------------------------------------
# QUOTA RECORDING
# ---------------------------------------------------------------------------

def record_provider_usage(
    provider: str,
    tokens: int = 0,
    custom_usage: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    return QUOTA_MANAGER.record_request(
        provider=provider,
        tokens=tokens,
        custom_usage=custom_usage,
    )


def record_capacity_usage(
    provider: str,
    capacity_id: str,
    tokens: int = 0,
    custom_usage: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    return QUOTA_MANAGER.record_request(
        provider=provider,
        capacity_id=capacity_id,
        tokens=tokens,
        custom_usage=custom_usage,
    )


# ---------------------------------------------------------------------------
# PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def route_request(request: Dict[str, Any]) -> Dict[str, Any]:
    return RoutingEngine().route(request)


if __name__ == "__main__":
    # Safe local route-preview test. This does not make an API call.
    preview_request = {
        "intent": "general_chat",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "requires_file": False,
        "requires_image": False,
        "requires_video": False,
        "requires_platform_action": False,
        "required_capabilities": [],
        "user_role": "user",
    }

    import json

    print(
        json.dumps(
            route_request(preview_request),
            indent=2,
            default=str,
        )
    )
    