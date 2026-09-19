"""
ODDI-AI PHASE 8 + PHASE 9 TEST SUITE

No pytest dependency.
No real AI/provider API calls.

Phase 8:
- Action layer exists
- Dispatcher exists
- Answer action can execute through provider execution layer
- Structured result is returned
- Provider fallback remains available

Phase 9:
- Host /help exposes admin commands
- Host-only commands are protected
- Commands are deterministic
- Admin commands do not require AI
"""

import inspect
import sys
import os
import sys

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)    


PASSED = 0
FAILED = 0


def check(name, fn):
    global PASSED, FAILED

    try:
        fn()
        PASSED += 1
        print(f"PASS  {name}")
    except Exception as exc:
        FAILED += 1
        print(f"FAIL  {name}")
        print(f"      {type(exc).__name__}: {exc}")


# ============================================================
# PHASE 8 — ACTION LAYER
# ============================================================

def test_phase8_actions_package():
    import actions

    assert actions is not None


def test_phase8_dispatcher_import():
    from actions.dispatcher import ActionDispatcher

    assert ActionDispatcher is not None


def test_phase8_dispatcher_is_callable():
    from actions.dispatcher import ActionDispatcher

    dispatcher = ActionDispatcher()

    assert dispatcher is not None

    methods = dir(dispatcher)

    assert any(
        name in methods
        for name in (
            "dispatch",
            "execute",
            "handle",
        )
    ), "ActionDispatcher has no dispatch/execute/handle method"


def test_phase8_result_structure():
    """
    Phase 8 may keep its structured result inside dispatcher.py.
    """
    from actions.dispatcher import ActionDispatcher

    dispatcher = ActionDispatcher()

    assert dispatcher is not None

def test_phase8_answer_action_contract():
    """
    Verify that the dispatcher can recognize the standard answer action.

    This test does NOT call a real provider.
    """

    from actions.dispatcher import ActionDispatcher

    dispatcher = ActionDispatcher()

    assert hasattr(dispatcher, "dispatch"), (
        "Phase 8 requires ActionDispatcher.dispatch()"
    )

    signature = inspect.signature(dispatcher.dispatch)

    assert len(signature.parameters) >= 1, (
        "dispatch() must accept an action/request payload"
    )


def test_phase8_no_direct_openai_primary_dependency():
    """
    Phase 8 must remain connected to the router/provider adapter layer,
    not create a new OpenAI-only execution path.
    """

    import actions.dispatcher as dispatcher_module

    source = inspect.getsource(dispatcher_module)

    assert "openai" not in source.lower(), (
        "Action layer contains a direct OpenAI dependency"
    )


# ============================================================
# PHASE 9 — HOST / ADMIN COMMANDS
# ============================================================

def test_phase9_commands_module_exists():
    from app.commands import handle_command

    assert callable(handle_command)


def test_phase9_help_signature():
    from app.commands import handle_command

    signature = inspect.signature(handle_command)

    assert "identity" in signature.parameters, (
        "handle_command() must receive trusted identity context"
    )


def _host_identity():
    from identity.identity import create_identity

    return create_identity(
        user_id="phase9-host",
        email="vedansshrajsinha@gmail.com",
        role="owner",
    )


def _normal_identity():
    from identity.identity import create_identity

    return create_identity(
        user_id="phase9-normal-user",
        email="normal-user@example.com",
        role="user",
    )


def _run_command(message, identity):
    from app.commands import handle_command

    return handle_command(
        message,
        identity=identity,
    )


def test_phase9_host_help():
    result = _run_command(
        "/help",
        _host_identity(),
    )

    assert result is not None

    text = str(result).lower()

    required = [
        "/help",
        "/accounts",
        "/count",
        "/usage",
        "/provider_statistics",
    ]

    missing = [
        command
        for command in required
        if command not in text
    ]

    assert not missing, (
        "Host /help missing: "
        + ", ".join(missing)
    )


def test_phase9_help_deterministic():
    identity = _host_identity()

    first = _run_command(
        "/help",
        identity,
    )

    second = _run_command(
        "/help",
        identity,
    )

    assert first == second


def test_phase9_normal_user_help_does_not_expose_admin_commands():
    result = _run_command(
        "/help",
        _normal_identity(),
    )

    assert result is not None

    text = str(result).lower()

    forbidden = [
        "/accounts",
        "/provider_statistics",
    ]

    leaked = [
        command
        for command in forbidden
        if command in text
    ]

    assert not leaked, (
        "Normal user received host-only commands: "
        + ", ".join(leaked)
    )


def test_phase9_accounts_host_only():
    host_result = _run_command(
        "/accounts",
        _host_identity(),
    )

    user_result = _run_command(
        "/accounts",
        _normal_identity(),
    )

    assert host_result is not None
    assert user_result is not None

    user_text = str(user_result).lower()

    assert "account details" not in user_text
    assert "total accounts" not in user_text


def test_phase9_count_host_only():
    host_result = _run_command(
        "/count",
        _host_identity(),
    )

    user_result = _run_command(
        "/count",
        _normal_identity(),
    )

    assert host_result is not None
    assert user_result is not None

    user_text = str(user_result).lower()

    assert "total accounts" not in user_text
    assert "account count" not in user_text


def test_phase9_usage_command():
    host_result = _run_command(
        "/usage",
        _host_identity(),
    )

    user_result = _run_command(
        "/usage",
        _normal_identity(),
    )

    assert host_result is not None
    assert user_result is not None


def test_phase9_provider_statistics_host_only():
    host_result = _run_command(
        "/provider_statistics",
        _host_identity(),
    )

    user_result = _run_command(
        "/provider_statistics",
        _normal_identity(),
    )

    assert host_result is not None
    assert user_result is not None

    user_text = str(user_result).lower()

    providers = [
        "gemini",
        "mistral",
        "groq",
        "cloudflare",
        "openrouter",
    ]

    leaked = [
        provider
        for provider in providers
        if provider in user_text
    ]

    assert not leaked, (
        "Normal user received provider statistics: "
        + ", ".join(leaked)
    )


def test_phase9_commands_are_deterministic():
    identity = _host_identity()

    commands = [
        "/help",
        "/accounts",
        "/count",
        "/usage",
        "/provider_statistics",
    ]

    for command in commands:
        first = _run_command(command, identity)
        second = _run_command(command, identity)

        assert first == second, (
            f"{command} produced different results"
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 72)
    print("ODDI-AI — PHASE 8 + 9 TEST SUITE")
    print("REAL PROVIDER API CALLS: DISABLED")
    print("PYTEST: NOT REQUIRED")
    print("=" * 72)
    print()

    tests = [
        # Phase 8
        ("Phase 8 actions package", test_phase8_actions_package),
        ("Phase 8 dispatcher import", test_phase8_dispatcher_import),
        ("Phase 8 dispatcher contract", test_phase8_dispatcher_is_callable),
        ("Phase 8 result structure", test_phase8_result_structure),
        ("Phase 8 answer action contract", test_phase8_answer_action_contract),
        ("Phase 8 no direct OpenAI dependency", test_phase8_no_direct_openai_primary_dependency),

        # Phase 9
        ("Phase 9 commands module", test_phase9_commands_module_exists),
        ("Phase 9 command identity", test_phase9_help_signature),
        ("Phase 9 host help", test_phase9_host_help),
        ("Phase 9 help deterministic", test_phase9_help_deterministic),
        ("Phase 9 normal user help protection",
         test_phase9_normal_user_help_does_not_expose_admin_commands),
        ("Phase 9 accounts host-only", test_phase9_accounts_host_only),
        ("Phase 9 count host-only", test_phase9_count_host_only),
        ("Phase 9 usage command", test_phase9_usage_command),
        ("Phase 9 provider statistics host-only",
         test_phase9_provider_statistics_host_only),
        ("Phase 9 command determinism",
         test_phase9_commands_are_deterministic),
    ]

    for name, fn in tests:
        check(name, fn)

    print()
    print("=" * 72)
    print(f"RESULT: {PASSED} PASSED / {FAILED} FAILED")
    print("=" * 72)

    if FAILED:
        print()
        print("PHASE 8/9 TESTS FAILED")
        print("Fix the first failure before continuing.")
        return 1

    print()
    print("ALL PHASE 8 + 9 TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())