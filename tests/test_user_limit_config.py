from importlib import reload

import quota.manager as quota_module
from config.limits import USER_LIMITS


def test_shared_quota_manager_uses_configured_user_policy():
    original_tpd = USER_LIMITS["user"]["tpd"]
    original_tpm = USER_LIMITS["user"]["tpm"]

    try:
        USER_LIMITS["user"]["tpd"] = 20000
        USER_LIMITS["user"]["tpm"] = 20000
        reload(quota_module)

        assert quota_module.quota_manager.user_limits["user"]["tpd"] == 20000
        assert quota_module.quota_manager.user_limits["user"]["tpm"] == 20000
        assert quota_module.quota_manager.has_user_quota(
            "user-42",
            role="user",
            tokens=20000,
        )
        status = quota_module.quota_manager.user_quota_status("user-42", role="user")
        assert status["tokens_limit"] == 20000
    finally:
        USER_LIMITS["user"]["tpd"] = original_tpd
        USER_LIMITS["user"]["tpm"] = original_tpm
        reload(quota_module)
