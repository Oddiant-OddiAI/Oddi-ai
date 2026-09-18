from __future__ import annotations

from quota.manager import QuotaManager


# ==========================================================
# ISOLATED TEST LIMITS
# ==========================================================
# These are deliberately small so exhaustion can be tested
# quickly without touching real provider APIs.
# ==========================================================

TEST_LIMITS = {

    "gemini": {
        "rpm": 3,
        "rpd": 5,
        "tpm": 100,
        "tpd": 500,

        "custom": {
            "source": "test",
        },

        "capacity_pools": {

            "gemini_key_1": {
                "rpm": 2,
                "rpd": 2,
                "tpm": 50,
                "tpd": 200,

                "custom": {
                    "source": "test",
                },
            },

            "gemini_key_2": {
                "rpm": 2,
                "rpd": 2,
                "tpm": 50,
                "tpd": 200,

                "custom": {
                    "source": "test",
                },
            },
        },
    },

    "cloudflare": {
        "rpm": None,
        "rpd": None,
        "tpm": None,
        "tpd": None,

        "custom": {
            "neurons_per_day": 1000,
            "source": "test",
        },
    },
}


# ==========================================================
# TEST HELPERS
# ==========================================================

PASSED = 0
FAILED = 0


def test(name: str, condition: bool) -> None:
    global PASSED, FAILED

    if condition:
        print(f"PASS  {name}")
        PASSED += 1
    else:
        print(f"FAIL  {name}")
        FAILED += 1


# ==========================================================
# TEST 1 — INITIALIZATION
# ==========================================================

def test_initialization() -> None:

    quota = QuotaManager(TEST_LIMITS)

    test(
        "Quota Manager initializes",
        quota is not None,
    )


# ==========================================================
# TEST 2 — EMPTY CAPACITY AVAILABLE
# ==========================================================

def test_empty_capacity() -> None:

    quota = QuotaManager(TEST_LIMITS)

    test(
        "Empty Gemini K1 has quota",
        quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )

    test(
        "Empty Gemini K2 has quota",
        quota.has_quota(
            "gemini",
            "gemini_key_2",
        ),
    )


# ==========================================================
# TEST 3 — REQUEST COUNT
# ==========================================================

def test_request_count() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "Request counter increments",
        status["requests_used"] == 1,
    )

    test(
        "RPD remaining is correct",
        status["requests_remaining"] == 1,
    )


# ==========================================================
# TEST 4 — TOKEN COUNT
# ==========================================================

def test_token_count() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        tokens=30,
        capacity_id="gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "Token counter increments",
        status["tokens_used"] == 30,
    )

    test(
        "TPD remaining is correct",
        status["tokens_remaining"] == 170,
    )


# ==========================================================
# TEST 5 — CAPACITY ISOLATION
# ==========================================================

def test_capacity_isolation() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        tokens=20,
        capacity_id="gemini_key_1",
    )

    k1 = quota.get_usage(
        "gemini",
        "gemini_key_1",
    )

    k2 = quota.get_usage(
        "gemini",
        "gemini_key_2",
    )

    test(
        "Gemini K1 usage is isolated",
        k1["requests"] == 1,
    )

    test(
        "Gemini K2 starts independently",
        k2["requests"] == 0,
    )


# ==========================================================
# TEST 6 — RPM
# ==========================================================

def test_rpm() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "RPM usage tracked",
        status["rpm_used"] == 2,
    )

    test(
        "RPM exhaustion detected",
        "rpm" in status["exhausted_dimensions"],
    )

    test(
        "RPM blocks next request",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )


# ==========================================================
# TEST 7 — TPM
# ==========================================================

def test_tpm() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        tokens=30,
        capacity_id="gemini_key_1",
    )

    quota.record_request(
        "gemini",
        tokens=20,
        capacity_id="gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "TPM usage tracked",
        status["tpm_used"] == 50,
    )

    test(
        "TPM exhaustion detected",
        "tpm" in status["exhausted_dimensions"],
    )

    test(
        "TPM blocks projected request",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
            tokens=1,
        ),
    )


# ==========================================================
# TEST 8 — RPD
# ==========================================================

def test_rpd() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "RPD exhaustion detected",
        "rpd" in status["exhausted_dimensions"],
    )

    test(
        "RPD blocks next request",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )


# ==========================================================
# TEST 9 — TPD
# ==========================================================

def test_tpd() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        tokens=200,
        capacity_id="gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "TPD exhaustion detected",
        "tpd" in status["exhausted_dimensions"],
    )

    test(
        "TPD blocks next request",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )


# ==========================================================
# TEST 10 — PROJECTED TOKEN CHECK
# ==========================================================

def test_projected_tokens() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        tokens=40,
        capacity_id="gemini_key_1",
    )

    test(
        "Projected request within TPM allowed",
        quota.has_quota(
            "gemini",
            "gemini_key_1",
            tokens=10,
        ),
    )

    test(
        "Projected request exceeding TPM rejected",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
            tokens=11,
        ),
    )


# ==========================================================
# TEST 11 — CUSTOM QUOTA
# ==========================================================

def test_custom_quota() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "cloudflare",
        custom_usage={
            "neurons_per_day": 1000,
        },
    )

    status = quota.quota_status(
        "cloudflare",
    )

    test(
        "Custom quota tracked",
        status["custom"]["neurons_per_day"]["used"] == 1000,
    )

    test(
        "Custom quota exhaustion detected",
        "custom:neurons_per_day"
        in status["exhausted_dimensions"],
    )

    test(
        "Custom quota blocks next request",
        not quota.has_quota(
            "cloudflare",
        ),
    )


# ==========================================================
# TEST 12 — FALLBACK CAPACITY
# ==========================================================

def test_capacity_fallback() -> None:

    quota = QuotaManager(TEST_LIMITS)

    # Exhaust K1.
    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    test(
        "Gemini K1 exhausted",
        not quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )

    test(
        "Gemini K2 remains available",
        quota.has_quota(
            "gemini",
            "gemini_key_2",
        ),
    )


# ==========================================================
# TEST 13 — UNKNOWN CAPACITY
# ==========================================================

def test_unknown_capacity() -> None:

    quota = QuotaManager(TEST_LIMITS)

    try:

        quota.record_request(
            "gemini",
            capacity_id="gemini_key_999",
        )

        test(
            "Unknown capacity rejected",
            False,
        )

    except ValueError:

        test(
            "Unknown capacity rejected",
            True,
        )


# ==========================================================
# TEST 14 — NEGATIVE TOKENS
# ==========================================================

def test_negative_tokens() -> None:

    quota = QuotaManager(TEST_LIMITS)

    try:

        quota.record_request(
            "gemini",
            tokens=-1,
            capacity_id="gemini_key_1",
        )

        test(
            "Negative tokens rejected",
            False,
        )

    except ValueError:

        test(
            "Negative tokens rejected",
            True,
        )


# ==========================================================
# TEST 15 — RESET CAPACITY
# ==========================================================

def test_reset_capacity() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    quota.reset_provider(
        "gemini",
        "gemini_key_1",
    )

    status = quota.quota_status(
        "gemini",
        "gemini_key_1",
    )

    test(
        "Capacity reset clears requests",
        status["requests_used"] == 0,
    )

    test(
        "Capacity available after reset",
        quota.has_quota(
            "gemini",
            "gemini_key_1",
        ),
    )


# ==========================================================
# TEST 16 — RESET ALL
# ==========================================================

def test_reset_all() -> None:

    quota = QuotaManager(TEST_LIMITS)

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_1",
    )

    quota.record_request(
        "gemini",
        capacity_id="gemini_key_2",
    )

    quota.reset_all()

    k1 = quota.get_usage(
        "gemini",
        "gemini_key_1",
    )

    k2 = quota.get_usage(
        "gemini",
        "gemini_key_2",
    )

    test(
        "Global reset clears K1",
        k1["requests"] == 0,
    )

    test(
        "Global reset clears K2",
        k2["requests"] == 0,
    )


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:

    global PASSED, FAILED

    print("=" * 72)
    print("ODDI-AI PHASE 5 QUOTA MANAGER TEST")
    print("REAL PROVIDER API CALLS: DISABLED")
    print("=" * 72)

    test_initialization()
    test_empty_capacity()
    test_request_count()
    test_token_count()
    test_capacity_isolation()
    test_rpm()
    test_tpm()
    test_rpd()
    test_tpd()
    test_projected_tokens()
    test_custom_quota()
    test_capacity_fallback()
    test_unknown_capacity()
    test_negative_tokens()
    test_reset_capacity()
    test_reset_all()

    print("=" * 72)
    print(
        f"RESULT: {PASSED} PASSED / {FAILED} FAILED"
    )
    print("=" * 72)

    if FAILED == 0:
        print(
            "ALL PHASE 5 QUOTA TESTS PASSED"
        )
    else:
        print(
            "PHASE 5 QUOTA TEST FAILED"
        )

    print("=" * 72)

    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()