"""
ODDI-AI — Full Regression Test
Phases 1 → 7

Run from the ODDI-AI project root:

    python tests/test_phases_1_to_6.py

This test is intentionally self-contained and uses isolated quota limits
for Phase 5/6 checks, so it does not consume real provider quotas.
"""

import os
import sys
import importlib
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0


def check(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
        print(f"[PASS] {name}")
    except Exception as exc:
        FAILED += 1
        print(f"[FAIL] {name}")
        print(f"       {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Phase 1 — Foundation & Registry
# ---------------------------------------------------------------------------

def test_phase1_imports():
    modules = [
        "config.platform",
        "config.permissions",
        "config.limits",
        "identity.identity",
        "identity.permissions",
        "oddi_platform.capabilities",
        "oddi_platform.runtime_context",
        "providers.registry",
        "quota.manager",
    ]
    for name in modules:
        importlib.import_module(name)


def test_phase1_identity():
    from identity.identity import create_identity

    user = create_identity("test-user", "test@example.com", "user")
    assert user.user_id == "test-user"
    assert user.email == "test@example.com"
    assert user.role == "user"
    assert user.is_host is False


def test_phase1_registry():
    from providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    providers = registry.enabled_providers()

    assert providers, "No enabled providers found"
    for provider in ("gemini", "mistral", "groq", "cloudflare", "openrouter"):
        assert provider in providers, f"Missing provider: {provider}"


def test_phase1_permissions():
    import config.permissions as permissions

    # Verify the actual permission configuration exported by this project.
    available = [name for name in dir(permissions) if "permission" in name.lower()]
    assert available, "No permission configuration/API found"


# ---------------------------------------------------------------------------
# Phase 2 — Request Analyzer
# ---------------------------------------------------------------------------

def test_phase2_general_analysis():
    from request_analyzer.analyzer import analyze_request

    result = analyze_request("Explain how a transformer works")

    assert isinstance(result, dict)
    assert result.get("intent")
    assert result.get("domain")
    assert "complexity" in result
    assert "requires_web" in result
    assert "required_capabilities" in result


def test_phase2_job_analysis():
    from request_analyzer.analyzer import analyze_request

    result = analyze_request(
        "Find suitable software engineering jobs and help me track my applications"
    )

    assert isinstance(result, dict)
    assert result.get("domain") in {
        "jobs",
        "job",
        "career",
        "general",
    } or "job" in str(result).lower()

    text = str(result).lower()
    assert "job" in text or "application" in text


def test_phase2_capability_flags():
    from request_analyzer.analyzer import analyze_request

    result = analyze_request("Analyze this uploaded PDF and summarize it")

    assert isinstance(result, dict)
    assert "required_capabilities" in result


# ---------------------------------------------------------------------------
# Phase 3 — Routing Engine
# ---------------------------------------------------------------------------

def test_phase3_general_route():
    from routing.engine import route_request

    request = {
        "user_id": "phase3-user",
        "user_role": "user",
        "intent": "question_answering",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "required_capabilities": [],
    }

    result = route_request(request)

    assert isinstance(result, dict)
    assert "candidates" in result
    assert result["candidates"], "Router returned no candidates"


def test_phase3_four_gemini_pools():
    from routing.engine import route_request

    request = {
        "user_id": "phase3-gemini-user",
        "user_role": "user",
        "intent": "question_answering",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "required_capabilities": [],
    }

    result = route_request(request)
    candidates = result.get("candidates", [])

    capacity_text = str(candidates).lower()
    # At least the four configured Gemini pools should be represented
    # when they are configured/eligible.
    for key in ("gemini_key_1", "gemini_key_2", "gemini_key_3", "gemini_key_4"):
        assert key in capacity_text, f"{key} missing from routing candidates"


def test_phase3_provider_fallback_order():
    from routing.engine import FALLBACK_GROUPS

    assert isinstance(FALLBACK_GROUPS, list)
    assert len(FALLBACK_GROUPS) >= 5

    flattened = set()
    for group in FALLBACK_GROUPS:
        if isinstance(group, (set, list, tuple)):
            flattened.update(group)
        elif isinstance(group, dict):
            flattened.update(group.keys())
        elif isinstance(group, str):
            flattened.add(group)

    for provider in ("gemini", "mistral", "groq", "cloudflare", "openrouter"):
        assert provider in flattened, f"Missing fallback provider: {provider}"


def test_phase3_no_openai_primary():
    from routing.engine import CONNECTED_PROVIDERS

    assert "openai" not in CONNECTED_PROVIDERS


# ---------------------------------------------------------------------------
# Phase 4 — Provider Adapters
# ---------------------------------------------------------------------------

def test_phase4_adapter_imports():
    from providers import adapters

    assert hasattr(adapters, "execute_route")


def test_phase4_adapter_configuration():
    from providers import adapters

    # The adapter module must expose execution and provider-specific call paths.
    assert hasattr(adapters, "execute_route")
    provider_text = str(vars(adapters)).lower()
    for provider in ("gemini", "mistral", "groq", "cloudflare", "openrouter"):
        assert provider in provider_text


def test_phase4_gemini_credentials():
    keys = [
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_2",
        "GEMINI_API_KEY_3",
        "GEMINI_API_KEY_4",
    ]

    # Do not fail the full regression merely because .env is absent in CI.
    # If .env exists, verify all four are configured.
    if Path(".env").exists():
        missing = [key for key in keys if not os.getenv(key)]
        assert not missing, f"Missing Gemini keys in environment: {missing}"


def test_phase4_groq_credentials():
    keys = ["GROQ_API_KEY", "GROQ_API_KEY_1"]

    if Path(".env").exists():
        missing = [key for key in keys if not os.getenv(key)]
        assert not missing, f"Missing Groq keys in environment: {missing}"


# ---------------------------------------------------------------------------
# Phase 5 — Provider Quota Manager
# ---------------------------------------------------------------------------

def make_test_quota_manager():
    from quota.manager import QuotaManager

    # Isolated test-only limits. RPM is deliberately high so RPD/TPM tests
    # exercise the intended dimension rather than an earlier rolling limit.
    limits = {
        "test_provider": {
            "rpm": 100,
            "tpm": 100000,
            "rpd": 3,
            "tpd": 100000,
            "capacity_pools": {
                "test_pool_1": {
                    "rpm": 100, "tpm": 100, "rpd": 3, "tpd": 200,
                    "custom": {},
                },
                "test_pool_2": {
                    "rpm": 100, "tpm": 100, "rpd": 3, "tpd": 200,
                    "custom": {},
                },
            },
        }
    }

    return QuotaManager(limits=limits)


def test_phase5_quota_initial_state():
    qm = make_test_quota_manager()

    assert qm.has_quota("test_provider", tokens=10)
    usage = qm.get_usage("test_provider")

    assert usage["requests"] == 0
    assert usage["tokens"] == 0


def test_phase5_rpm_limit():
    from quota.manager import QuotaManager

    qm = QuotaManager(
        limits={
            "test_provider": {
                "rpm": 2,
                "tpm": 100000,
                "rpd": 100,
                "tpd": 100000,
            }
        }
    )

    assert qm.has_quota("test_provider", tokens=10)
    qm.record_request("test_provider", tokens=10)

    assert qm.has_quota("test_provider", tokens=10)
    qm.record_request("test_provider", tokens=10)

    assert not qm.has_quota("test_provider", tokens=1)
   


def test_phase5_rpd_limit():
    qm = make_test_quota_manager()

    for _ in range(3):
        assert qm.has_quota("test_provider", tokens=1)
        qm.record_request("test_provider", tokens=1)

    assert not qm.has_quota("test_provider", tokens=1)


def test_phase5_tpm_projection():
    qm = make_test_quota_manager()

    qm.record_request("test_provider", capacity_id="test_pool_1", tokens=90)

    assert not qm.has_quota("test_provider", capacity_id="test_pool_1", tokens=11)
    assert qm.has_quota("test_provider", capacity_id="test_pool_1", tokens=10)


def test_phase5_capacity_isolation():
    qm = make_test_quota_manager()

    for _ in range(3):
        qm.record_request("test_provider", capacity_id="test_pool_1", tokens=1)

    assert not qm.has_quota("test_provider", capacity_id="test_pool_1", tokens=1)
    assert qm.has_quota("test_provider", capacity_id="test_pool_2", tokens=1)


def test_phase5_reset():
    qm = make_test_quota_manager()

    for _ in range(3):
        qm.record_request("test_provider", tokens=1)

    assert not qm.has_quota("test_provider", tokens=1)

    qm.reset_provider("test_provider")

    assert qm.has_quota("test_provider", tokens=1)


def test_phase5_thread_safety():
    from concurrent.futures import ThreadPoolExecutor

    qm = make_test_quota_manager()

    def worker():
        if qm.has_quota("test_provider", tokens=1):
            qm.record_request("test_provider", tokens=1)
            return 1
        return 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: worker(), range(10)))

    usage = qm.get_usage("test_provider")

    assert usage["requests"] <= 3
    assert usage["tokens"] <= 200
    assert sum(results) == usage["requests"]


# ---------------------------------------------------------------------------
# Phase 5 — Routing + Quota Integration
# ---------------------------------------------------------------------------

def test_phase5_routing_quota_integration():
    from routing.engine import RoutingEngine
    from quota.manager import QuotaManager

    limits = {
        "gemini": {
            "rpm": 100, "tpm": 100000, "rpd": 100, "tpd": 100000,
            "capacity_pools": {
                f"gemini_key_{i}": {
                    "rpm": 100, "tpm": 100000, "rpd": 1 if i == 1 else 100,
                    "tpd": 100000, "custom": {},
                }
                for i in range(1, 5)
            },
        },
        "mistral": {
            "rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000,
            "custom": {},
        },
        "cloudflare": {
            "rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000,
            "custom": {},
        },
        "groq": {
            "rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000,
            "capacity_pools": {
                "groq_key_1": {"rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000, "custom": {}},
                "groq_key_2": {"rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000, "custom": {}},
            },
        },
        "openrouter": {
            "rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000,
            "custom": {},
        },
    }

    qm = QuotaManager(limits=limits)
    engine = RoutingEngine(quota_manager=qm)

    request = {
        "user_id": "phase5-routing-user",
        "user_role": "admin",  # exempt user quota for this provider test
        "intent": "question_answering",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "required_capabilities": [],
    }

    first = engine.route(request)
    assert first.get("candidates"), "No candidates on first route"

    # Consume first Gemini pool.
    qm.record_request("gemini", capacity_id="gemini_key_1", tokens=10)

    second = engine.route(request)
    candidates = second.get("candidates", [])
    assert candidates, "No fallback candidates after pool exhaustion"

    candidate_text = str(candidates).lower()
    assert "gemini_key_1" not in candidate_text


# ---------------------------------------------------------------------------
# Phase 6 — User Quotas / Fair Use
# ---------------------------------------------------------------------------

def make_phase6_manager():
    from quota.manager import QuotaManager

    user_limits = {
        "user": {
            "rpd": 10,
            "tpd": 2000,
            "rpm": 5,
            "tpm": 2000,
        },
        "member": {
            "rpd": 10,
            "tpd": 2000,
            "rpm": 5,
            "tpm": 2000,
        },
        "admin": {
            "rpd": None,
            "tpd": None,
            "rpm": None,
            "tpm": None,
        },
        "owner": {
            "rpd": None,
            "tpd": None,
            "rpm": None,
            "tpm": None,
        },
    }

    return QuotaManager(
        limits={
            "gemini": {
                "rpm": 100, "tpm": 100000, "rpd": 100, "tpd": 100000,
                "capacity_pools": {
                    f"gemini_key_{i}": {
                        "rpm": 100, "tpm": 100000, "rpd": 100, "tpd": 100000,
                        "custom": {},
                    } for i in range(1, 5)
                },
            },
            "mistral": {"rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000, "custom": {}},
            "cloudflare": {"rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000, "custom": {}},
            "groq": {"rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000, "custom": {}},
            "openrouter": {"rpm": 100, "tpm": 10000, "rpd": 100, "tpd": 10000, "custom": {}},
        },
        user_limits=user_limits,
    )


def test_phase6_ten_requests_daily():
    from quota.manager import QuotaManager

    qm = QuotaManager(
        limits={},
        user_limits={
            "user": {"rpd": 10, "tpd": 2000, "rpm": None, "tpm": None},
            "member": {"rpd": 10, "tpd": 2000, "rpm": None, "tpm": None},
            "admin": {"rpd": None, "tpd": None, "rpm": None, "tpm": None},
            "owner": {"rpd": None, "tpd": None, "rpm": None, "tpm": None},
        },
    )

    for i in range(10):
        assert qm.has_user_quota(
            "user-10",
            role="user",
            tokens=100,
        ), f"Request {i + 1} unexpectedly rejected"
        qm.record_user_request(
            "user-10",
            tokens=100,
            role="user",
        )

    assert not qm.has_user_quota(
        "user-10",
        role="user",
        tokens=1,
    )


def test_phase6_two_thousand_token_limit():
    qm = make_phase6_manager()

    for _ in range(4):
        assert qm.has_user_quota("token-user", role="user", tokens=500)
        qm.record_user_request("token-user", tokens=500, role="user")

    assert not qm.has_user_quota("token-user", role="user", tokens=1)


def test_phase6_fair_use_rolling_rpm():
    qm = make_phase6_manager()

    for _ in range(5):
        assert qm.has_user_quota("rpm-user", role="user", tokens=1)
        qm.record_user_request("rpm-user", tokens=1, role="user")

    assert not qm.has_user_quota("rpm-user", role="user", tokens=1)


def test_phase6_users_are_isolated():
    qm = make_phase6_manager()

    for _ in range(10):
        qm.record_user_request("user-a", tokens=100, role="user")

    assert not qm.has_user_quota("user-a", role="user", tokens=1)
    assert qm.has_user_quota("user-b", role="user", tokens=100)


def test_phase6_admin_exemption():
    qm = make_phase6_manager()

    for _ in range(20):
        assert qm.has_user_quota("admin-user", role="admin", tokens=1000)
        qm.record_user_request("admin-user", tokens=1000, role="admin")

    status = qm.user_quota_status("admin-user", role="admin")
    assert status["exempt"] is True


def test_phase6_owner_exemption():
    qm = make_phase6_manager()

    for _ in range(20):
        assert qm.has_user_quota("owner-user", role="owner", tokens=1000)
        qm.record_user_request("owner-user", tokens=1000, role="owner")

    status = qm.user_quota_status("owner-user", role="owner")
    assert status["exempt"] is True


def test_phase6_host_exemption():
    qm = make_phase6_manager()

    assert qm.has_user_quota(
        "host-user",
        role="user",
        tokens=10000,
        is_host=True,
    )

    qm.record_user_request(
        "host-user",
        tokens=10000,
        role="user",
        is_host=True,
    )

    status = qm.user_quota_status(
        "host-user",
        role="user",
        is_host=True,
    )
    assert status["exempt"] is True


def test_phase6_quota_rejection_before_routing():
    from routing.engine import RoutingEngine
    from quota.manager import QuotaManager

    qm = make_phase6_manager()
    engine = RoutingEngine(quota_manager=qm)

    request = {
        "user_id": "blocked-user",
        "user_role": "user",
        "user_priority": "normal",
        "intent": "question_answering",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "required_capabilities": [],
    }

    for _ in range(10):
        qm.record_user_request("blocked-user", tokens=100, role="user")

    result = engine.route(request)

    assert result.get("allowed") is False
    assert result.get("reason") in {
        "user_quota_exceeded",
        "user_daily_limit_reached",
        "user_fair_use_limit_reached",
        "user_token_limit_reached",
    }


def test_phase6_success_recording():
    qm = make_phase6_manager()

    before = qm.get_user_usage("record-user")
    assert before["requests"] == 0
    assert before["tokens"] == 0

    qm.record_user_request(
        "record-user",
        tokens=321,
        role="user",
    )

    after = qm.get_user_usage("record-user")
    assert after["requests"] == 1
    assert after["tokens"] == 321


def test_phase6_reset_user():
    qm = make_phase6_manager()

    qm.record_user_request("reset-user", tokens=500, role="user")
    assert qm.get_user_usage("reset-user")["requests"] == 1

    qm.reset_user("reset-user")

    usage = qm.get_user_usage("reset-user")
    assert usage["requests"] == 0
    assert usage["tokens"] == 0


def test_phase6_priority_context():
    qm = make_phase6_manager()

    assert qm.has_user_quota(
        "priority-user",
        role="user",
        priority="normal",
        tokens=100,
    )

    status = qm.user_quota_status(
        "priority-user",
        role="user",
        priority="normal",
    )

    assert status["role"] == "user"
    assert status["priority"] == "normal"


# ---------------------------------------------------------------------------
# App integration
# ---------------------------------------------------------------------------

def test_phase6_app_engine_signature():
    from app.engine import process_message
    import inspect

    signature = inspect.signature(process_message)
    params = signature.parameters

    assert "user_id" in params
    assert "user_role" in params
    assert "user_priority" in params
    assert "is_host" in params
    assert "quota_exempt" in params


# ---------------------------------------------------------------------------
# Phase 7 — Fallback & Reliability
# ---------------------------------------------------------------------------

def test_phase7_retryable_failure_falls_back():
    from providers import adapters

    original = adapters.call_provider
    calls = []

    def fake_call_provider(provider, model, prompt, capacity_id=None):
        calls.append((provider, model, capacity_id))
        if len(calls) == 1:
            raise adapters.ProviderAdapterError(
                "temporary failure",
                retryable=True,
            )
        return "fallback success"

    adapters.call_provider = fake_call_provider

    try:
        route = {
            "allowed": True,
            "candidates": [
                {
                    "provider": "gemini",
                    "model": "gemini-3.5-flash-lite",
                    "capacity_id": "gemini_key_1",
                },
                {
                    "provider": "mistral",
                    "model": "ministral-3b-2512",
                    "capacity_id": None,
                },
            ],
        }

        result = adapters.execute_route(route, "test prompt")

        assert result.get("success") is True
        assert len(calls) >= 2
        assert calls[0][0] == "gemini"
        assert calls[1][0] == "mistral"

    finally:
        adapters.call_provider = original


def test_phase7_permanent_failure_falls_back():
    from providers import adapters

    original = adapters.call_provider
    calls = []

    def fake_call_provider(provider, model, prompt, capacity_id=None):
        calls.append(provider)
        if len(calls) == 1:
            raise adapters.ProviderAdapterError(
                "provider failure",
                retryable=False,
            )
        return "fallback success"

    adapters.call_provider = fake_call_provider

    try:
        route = {
            "allowed": True,
            "candidates": [
                {
                    "provider": "gemini",
                    "model": "gemini-3.5-flash-lite",
                    "capacity_id": "gemini_key_1",
                },
                {
                    "provider": "groq",
                    "model": "gpt-oss-120b",
                    "capacity_id": "groq_key_1",
                },
            ],
        }

        result = adapters.execute_route(route, "test prompt")

        assert result.get("success") is True
        assert calls == ["gemini", "groq"]

    finally:
        adapters.call_provider = original


def test_phase7_gemini_capacity_isolation():
    from routing.engine import RoutingEngine
    from quota.manager import QuotaManager

    qm = QuotaManager(
        limits={
            "gemini": {
                "rpm": 100,
                "tpm": 100000,
                "rpd": 100,
                "tpd": 100000,
                "capacity_pools": {
                    "gemini_key_1": {
                        "rpm": 0,
                        "tpm": 100000,
                        "rpd": 100,
                        "tpd": 100000,
                        "custom": {},
                    },
                    "gemini_key_2": {
                        "rpm": 100,
                        "tpm": 100000,
                        "rpd": 100,
                        "tpd": 100000,
                        "custom": {},
                    },
                    "gemini_key_3": {
                        "rpm": 100,
                        "tpm": 100000,
                        "rpd": 100,
                        "tpd": 100000,
                        "custom": {},
                    },
                    "gemini_key_4": {
                        "rpm": 100,
                        "tpm": 100000,
                        "rpd": 100,
                        "tpd": 100000,
                        "custom": {},
                    },
                },
            },
            "mistral": {
                "rpm": 100,
                "tpm": 100000,
                "rpd": 100,
                "tpd": 100000,
                "custom": {},
            },
        }
    )

    engine = RoutingEngine(quota_manager=qm)

    request = {
        "user_id": "phase7-isolation-user",
        "user_role": "admin",
        "intent": "question_answering",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "required_capabilities": [],
    }

    result = engine.route(request)
    candidates = result.get("candidates", [])

    assert candidates
    assert "gemini_key_1" not in str(candidates)
    assert "gemini_key_2" in str(candidates)


def test_phase7_unhealthy_capacity_is_skipped():
    from routing.engine import RoutingEngine

    engine = RoutingEngine()

    engine.provider_state = {
        "gemini": {
            "gemini_key_1": {
                "healthy": False,
            }
        }
    }

    request = {
        "user_id": "phase7-health-user",
        "user_role": "admin",
        "intent": "question_answering",
        "domain": "general",
        "complexity": "low",
        "requires_web": False,
        "required_capabilities": [],
    }

    result = engine.route(request)
    candidates = result.get("candidates", [])

    assert candidates
    assert "gemini_key_1" not in str(candidates)


def test_phase7_success_is_recorded():
    from providers import adapters

    original = adapters.call_provider

    def fake_call_provider(provider, model, prompt, capacity_id=None):
        return "success"

    adapters.call_provider = fake_call_provider

    try:
        route = {
            "allowed": True,
            "candidates": [
                {
                    "provider": "gemini",
                    "model": "gemini-3.5-flash-lite",
                    "capacity_id": "gemini_key_1",
                }
            ],
        }

        result = adapters.execute_route(route, "test prompt")

        assert result.get("success") is True

    finally:
        adapters.call_provider = original


def test_phase7_all_candidates_fail():
    from providers import adapters

    original = adapters.call_provider
    calls = []

    def fake_call_provider(provider, model, prompt, capacity_id=None):
        calls.append(provider)
        raise adapters.ProviderAdapterError(
            "failure",
            retryable=True,
        )

    adapters.call_provider = fake_call_provider

    try:
        route = {
            "allowed": True,
            "candidates": [
                {
                    "provider": "gemini",
                    "model": "gemini-3.5-flash-lite",
                    "capacity_id": "gemini_key_1",
                },
                {
                    "provider": "mistral",
                    "model": "ministral-3b-2512",
                    "capacity_id": None,
                },
                {
                    "provider": "groq",
                    "model": "gpt-oss-120b",
                    "capacity_id": "groq_key_1",
                },
            ],
        }

        result = adapters.execute_route(route, "test prompt")

        assert result.get("success") is False
        assert len(calls) == 3

    finally:
        adapters.call_provider = original


def test_phase7_quota_rejection_never_calls_provider():
    from providers import adapters

    original = adapters.call_provider
    calls = []

    def fake_call_provider(provider, model, prompt, capacity_id=None):
        calls.append(provider)
        return "should never happen"

    adapters.call_provider = fake_call_provider

    try:
        route = {
            "allowed": False,
            "reason": "user_quota_exceeded",
            "candidates": [],
        }

        result = adapters.execute_route(route, "test prompt")

        assert result.get("success") is False
        assert result.get("reason") == "user_quota_exceeded"
        assert calls == []

    finally:
        adapters.call_provider = original
# Run
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("ODDI-AI FULL REGRESSION TEST — PHASES 1 → 7")
    print("=" * 72)
    print()

    tests = [
        # Phase 1
        ("P1: imports", test_phase1_imports),
        ("P1: identity", test_phase1_identity),
        ("P1: provider registry", test_phase1_registry),
        ("P1: permissions", test_phase1_permissions),

        # Phase 2
        ("P2: general request analyzer", test_phase2_general_analysis),
        ("P2: job request analyzer", test_phase2_job_analysis),
        ("P2: capability flags", test_phase2_capability_flags),

        # Phase 3
        ("P3: general routing", test_phase3_general_route),
        ("P3: four Gemini pools", test_phase3_four_gemini_pools),
        ("P3: provider fallback groups", test_phase3_provider_fallback_order),
        ("P3: no OpenAI primary provider", test_phase3_no_openai_primary),

        # Phase 4
        ("P4: adapter imports", test_phase4_adapter_imports),
        ("P4: adapter configuration", test_phase4_adapter_configuration),
        ("P4: Gemini credentials", test_phase4_gemini_credentials),
        ("P4: Groq credentials", test_phase4_groq_credentials),

        # Phase 5
        ("P5: quota initial state", test_phase5_quota_initial_state),
        ("P5: RPM limit", test_phase5_rpm_limit),
        ("P5: RPD limit", test_phase5_rpd_limit),
        ("P5: TPM projection", test_phase5_tpm_projection),
        ("P5: capacity isolation", test_phase5_capacity_isolation),
        ("P5: quota reset", test_phase5_reset),
        ("P5: thread safety", test_phase5_thread_safety),
        ("P5: routing + quota integration", test_phase5_routing_quota_integration),

        # Phase 6
        ("P6: 10 daily requests", test_phase6_ten_requests_daily),
        ("P6: 2,000 daily tokens", test_phase6_two_thousand_token_limit),
        ("P6: rolling RPM fair use", test_phase6_fair_use_rolling_rpm),
        ("P6: user isolation", test_phase6_users_are_isolated),
        ("P6: admin exemption", test_phase6_admin_exemption),
        ("P6: owner exemption", test_phase6_owner_exemption),
        ("P6: host exemption", test_phase6_host_exemption),
        ("P6: quota rejection before routing", test_phase6_quota_rejection_before_routing),
        ("P6: successful usage recording", test_phase6_success_recording),
        ("P6: user reset", test_phase6_reset_user),
        ("P6: priority context", test_phase6_priority_context),
        ("P6: app engine integration", test_phase6_app_engine_signature),
        # Phase 7
        ("P7: retryable failure fallback", test_phase7_retryable_failure_falls_back),
        ("P7: permanent failure fallback", test_phase7_permanent_failure_falls_back),
        ("P7: Gemini capacity isolation", test_phase7_gemini_capacity_isolation),
        ("P7: unhealthy capacity skipped", test_phase7_unhealthy_capacity_is_skipped),
        ("P7: successful execution", test_phase7_success_is_recorded),
        ("P7: all candidates fail", test_phase7_all_candidates_fail),
        ("P7: quota rejection blocks API", test_phase7_quota_rejection_never_calls_provider),
    ]

    for name, fn in tests:
        check(name, fn)

    print()
    print("=" * 72)
    print(f"RESULT: {PASSED} PASSED / {FAILED} FAILED")
    print("=" * 72)

    if FAILED:
        print("\nPHASE 1–7 REGRESSION FAILED")
        print("Fix the failing test(s) before moving forward.")
        return 1

    print("\nALL PHASE 1–7 TESTS PASSED")
    print("Phase 1–7 regression is clean.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        raise
    except Exception:
        print("\nFATAL TEST ERROR")
        traceback.print_exc()
        raise
# ---------------------------------------------------------------------------
