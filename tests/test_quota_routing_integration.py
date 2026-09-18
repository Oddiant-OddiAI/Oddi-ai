from __future__ import annotations

from quota.manager import QuotaManager
from routing.engine import RoutingEngine


# ==========================================================
# CONTROLLED TEST LIMITS
# ==========================================================
# Deliberately tiny limits.
# NO REAL PROVIDER API CALLS ARE MADE.
# ==========================================================

TEST_LIMITS = {
    "gemini": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,
        "custom": {},
        "capacity_pools": {
            "gemini_key_1": {
                "rpm": None,
                "rpd": 1,
                "tpm": None,
                "tpd": None,
                "custom": {},
            },
            "gemini_key_2": {
                "rpm": None,
                "rpd": 1,
                "tpm": None,
                "tpd": None,
                "custom": {},
            },
            "gemini_key_3": {
                "rpm": None,
                "rpd": 1,
                "tpm": None,
                "tpd": None,
                "custom": {},
            },
            "gemini_key_4": {
                "rpm": None,
                "rpd": 1,
                "tpm": None,
                "tpd": None,
                "custom": {},
            },
        },
    },

    "mistral": {
        "rpm": None,
        "rpd": 10,
        "tpm": None,
        "tpd": None,
        "custom": {},
    },

    "groq": {
        "rpm": None,
        "rpd": 10,
        "tpm": None,
        "tpd": None,
        "custom": {},
        "capacity_pools": {
            "groq_key_1": {
                "rpm": None,
                "rpd": 10,
                "tpm": None,
                "tpd": None,
                "custom": {},
            },
            "groq_key_2": {
                "rpm": None,
                "rpd": 10,
                "tpm": None,
                "tpd": None,
                "custom": {},
            },
        },
    },

    "cloudflare": {
        "rpm": None,
        "rpd": 10,
        "tpm": None,
        "tpd": None,
        "custom": {},
    },

    "openrouter": {
        "rpm": None,
        "rpd": 10,
        "tpm": None,
        "tpd": None,
        "custom": {},
    },
}


# ==========================================================
# REQUEST
# ==========================================================

REQUEST = {
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


# ==========================================================
# HELPERS
# ==========================================================

PASSED = 0
FAILED = 0


def check(name: str, condition: bool) -> None:
    global PASSED, FAILED

    if condition:
        print(f"PASS  {name}")
        PASSED += 1
    else:
        print(f"FAIL  {name}")
        FAILED += 1


def make_engine(quota: QuotaManager) -> RoutingEngine:
    """
    Create a real RoutingEngine using the controlled
    QuotaManager.

    Provider state is forced healthy/configured so this
    test isolates quota behavior.
    """

    provider_state = {
        "gemini_key_1": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "gemini_key_2": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "gemini_key_3": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "gemini_key_4": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "mistral": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "groq_key_1": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "groq_key_2": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "cloudflare": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
        "openrouter": {
            "healthy": True,
            "configured": True,
            "active_requests": 0,
            "max_concurrency": 10,
            "latency_ms": 100,
        },
    }

    return RoutingEngine(
        provider_state=provider_state,
        quota_manager=quota,
    )


# ==========================================================
# TEST 1
# Empty router has Gemini K1 available
# ==========================================================

def test_initial_route() -> None:

    quota = QuotaManager(TEST_LIMITS)

    engine = make_engine(quota)

    route = engine.route(REQUEST)

    check(
        "Initial route exists",
        route["status"] == "routed",
    )

    check(
        "Initial route uses Gemini",
        route["provider"] == "gemini",
    )

    check(
        "Initial route uses Gemini K1",
        route["capacity_id"] == "gemini_key_1",
    )


# ==========================================================
# TEST 2
# Exhaust Gemini K1
# ==========================================================

def test_k1_exhaustion() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    engine = make_engine(quota)

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    check(
        "Gemini K1 quota exhausted",
        not status["quota_available"],
    )

    route = engine.route(REQUEST)

    check(
        "Router skips exhausted Gemini K1",
        route["capacity_id"] != "gemini_key_1",
    )

    check(
        "Router remains on Gemini fallback group",
        route["provider"] == "gemini",
    )


# ==========================================================
# TEST 3
# Exhaust K1 + K2
# ==========================================================

def test_k1_k2_exhaustion() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_2",
    )

    engine = make_engine(quota)

    route = engine.route(REQUEST)

    check(
        "Router skips Gemini K1 and K2",
        route["capacity_id"]
        not in {
            "gemini_key_1",
            "gemini_key_2",
        },
    )

    check(
        "Gemini K3 remains selectable",
        route["capacity_id"] == "gemini_key_3",
    )


# ==========================================================
# TEST 4
# Exhaust K1 + K2 + K3
# ==========================================================

def test_k1_k2_k3_exhaustion() -> None:

    quota = QuotaManager(TEST_LIMITS)

    for capacity_id in (
        "gemini_key_1",
        "gemini_key_2",
        "gemini_key_3",
    ):
        quota.record_request(
            "gemini",
            capacity_id=capacity_id,
        )

    engine = make_engine(quota)

    route = engine.route(REQUEST)

    check(
        "Router skips first three Gemini pools",
        route["capacity_id"] == "gemini_key_4",
    )


# ==========================================================
# TEST 5
# Exhaust ALL Gemini
# ==========================================================

def test_all_gemini_exhaustion() -> None:

    quota = QuotaManager(TEST_LIMITS)

    for capacity_id in (
        "gemini_key_1",
        "gemini_key_2",
        "gemini_key_3",
        "gemini_key_4",
    ):
        quota.record_request(
            "gemini",
            capacity_id=capacity_id,
        )

    engine = make_engine(quota)

    route = engine.route(REQUEST)

    check(
        "All Gemini capacities exhausted",
        all(
            not quota.has_quota(
                "gemini",
                capacity_id,
            )
            for capacity_id in (
                "gemini_key_1",
                "gemini_key_2",
                "gemini_key_3",
                "gemini_key_4",
            )
        ),
    )

    check(
        "Router falls back to next provider",
        route["provider"] == "mistral",
    )

    check(
        "Fallback route is valid",
        route["status"] == "routed",
    )


# ==========================================================
# TEST 6
# Quota does not affect another provider
# ==========================================================

def test_provider_isolation() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    check(
        "Gemini K1 exhausted",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )

    check(
        "Gemini K2 unaffected",
        quota.has_quota(
            "gemini",
            "gemini_key_2",
        ),
    )

    check(
        "Mistral unaffected",
        quota.has_quota(
            "mistral",
            "mistral",
        ),
    )


# ==========================================================
# TEST 7
# Record usage after routing
# ==========================================================

def test_usage_recording() -> None:

    quota = QuotaManager(TEST_LIMITS)

    engine = make_engine(quota)

    route = engine.route(REQUEST)

    selected_provider = route["provider"]
    selected_capacity = route["capacity_id"]

    before = quota.get_usage(
        selected_provider,
        selected_capacity,
    )

    quota.record_request(
        selected_provider,
        capacity_id=selected_capacity,
        tokens=25,
    )

    after = quota.get_usage(
        selected_provider,
        selected_capacity,
    )

    check(
        "Selected capacity usage recorded",
        after["requests"]
        == before["requests"] + 1,
    )

    check(
        "Selected capacity tokens recorded",
        after["tokens"]
        == before["tokens"] + 25,
    )


# ==========================================================
# TEST 8
# Reset restores routing capacity
# ==========================================================

def test_reset_restores_capacity() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    check(
        "K1 initially exhausted",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )

    quota.reset_provider(
        "gemini",
        "gemini_key_1",
    )

    check(
        "K1 available after reset",
        quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )

    engine = make_engine(quota)

    route = engine.route(REQUEST)

    check(
        "Router selects restored K1",
        route["capacity_id"]
        == "gemini_key_1",
    )


# ==========================================================
# TEST 9
# Candidate list respects quota
# ==========================================================

def test_candidate_filtering() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    engine = make_engine(quota)

    candidates = engine.discover_candidates()

    gemini_k1 = [
        candidate
        for candidate in candidates
        if candidate["provider"] == "gemini"
        and candidate["capacity_id"]
        == "gemini_key_1"
    ]

    check(
        "Exhausted K1 candidates are marked unavailable",
        all(
            not candidate["provider_state"]
            ["quota_available"]
            for candidate in gemini_k1
        ),
    )


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:

    global PASSED, FAILED

    print("=" * 72)
    print("ODDI-AI PHASE 5 ROUTING + QUOTA INTEGRATION TEST")
    print("REAL PROVIDER API CALLS: DISABLED")
    print("=" * 72)

    tests = [
        test_initial_route,
        test_k1_exhaustion,
        test_k1_k2_exhaustion,
        test_k1_k2_k3_exhaustion,
        test_all_gemini_exhaustion,
        test_provider_isolation,
        test_usage_recording,
        test_reset_restores_capacity,
        test_candidate_filtering,
    ]

    for test_function in tests:
        try:
            test_function()
        except Exception as exc:
            print(
                f"FAIL  {test_function.__name__}: "
                f"{type(exc).__name__}: {exc}"
            )
            FAILED += 1

    print("=" * 72)
    print(
        f"RESULT: {PASSED} PASSED / "
        f"{FAILED} FAILED"
    )
    print("=" * 72)

    if FAILED == 0:
        print(
            "PHASE 5 ROUTING + QUOTA INTEGRATION PASSED"
        )
    else:
        print(
            "PHASE 5 ROUTING + QUOTA INTEGRATION FAILED"
        )

    print("=" * 72)

    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()