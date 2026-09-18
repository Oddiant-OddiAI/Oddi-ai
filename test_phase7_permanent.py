import providers.adapters as a


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

    if capacity_id == "gemini_key_1":
        raise a.ProviderAdapterError("401 Unauthorized")

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
    print("=== REQUEST 1 ===")
    print(a.execute_route(route, "test"))

    print("\n=== KEY 1 STATE ===")
    print(
        a.RELIABILITY_MANAGER.get_state(
            "gemini",
            "gemini_key_1",
        )
    )

    print("\n=== REQUEST 2 ===")
    print(a.execute_route(route, "test"))

    print("\n=== FINAL CALLS ===")
    print(calls)

finally:
    a.call_provider = original_call_provider