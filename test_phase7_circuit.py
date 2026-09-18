import providers.adapters as a
import time


a.RELIABILITY_MANAGER.reset_all()

original_call_provider = a.call_provider
calls = []


def fake_call_provider(
    provider,
    prompt,
    model=None,
    capacity_id=None,
    api_key_number=None,
):
    calls.append(capacity_id)

    # Key 1 initially fails
    if capacity_id == "gemini_key_1":
        raise a.ProviderAdapterError("timeout")

    return "KEY 2 SUCCESS"


a.call_provider = fake_call_provider


route = {
    "candidates": [
        {
            "provider": "gemini",
            "model": "gemini-3.6-flash",
            "capacity_id": "gemini_key_1",
            "api_key_number": 1,
        },
        {
            "provider": "gemini",
            "model": "gemini-3.6-flash",
            "capacity_id": "gemini_key_2",
            "api_key_number": 2,
        },
    ]
}


try:
    # --------------------------------------------------
    # REQUEST 1
    # --------------------------------------------------
    print("=== REQUEST 1 ===")
    print(a.execute_route(route, "test"))

    # --------------------------------------------------
    # REQUEST 2
    # --------------------------------------------------
    print("\n=== REQUEST 2 ===")
    print(a.execute_route(route, "test"))

    # --------------------------------------------------
    # REQUEST 3
    # This opens Key 1's circuit.
    # --------------------------------------------------
    print("\n=== REQUEST 3 ===")
    print(a.execute_route(route, "test"))

    # --------------------------------------------------
    # CHECK OPEN CIRCUIT
    # --------------------------------------------------
    print("\n=== AFTER 3 FAILURES ===")

    print(
        "KEY 1 STATE:",
        a.RELIABILITY_MANAGER.get_state(
            "gemini",
            "gemini_key_1",
        ),
    )

    print(
        "KEY 1 HEALTHY:",
        a.RELIABILITY_MANAGER.is_healthy(
            "gemini",
            "gemini_key_1",
        ),
    )

    # --------------------------------------------------
    # REQUEST 4
    # Key 1 should be skipped.
    # --------------------------------------------------
    print("\n=== REQUEST 4 ===")
    print(a.execute_route(route, "test"))

    # --------------------------------------------------
    # WAIT FOR COOLDOWN
    # --------------------------------------------------
    print("\n=== WAITING FOR COOLDOWN ===")
    print("Waiting 60 seconds...")

    time.sleep(61)

    # --------------------------------------------------
    # CHECK RECOVERY
    # --------------------------------------------------
    print("\n=== AFTER COOLDOWN ===")

    print(
        "KEY 1 HEALTHY:",
        a.RELIABILITY_MANAGER.is_healthy(
            "gemini",
            "gemini_key_1",
        ),
    )

    print(
        "KEY 1 STATE:",
        a.RELIABILITY_MANAGER.get_state(
            "gemini",
            "gemini_key_1",
        ),
    )

finally:
    a.call_provider = original_call_provider