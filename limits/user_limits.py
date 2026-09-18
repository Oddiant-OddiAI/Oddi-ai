from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional


DEFAULT_DAILY_TOKEN_LIMIT = 5000


@dataclass
class UserUsage:
    """Runtime usage counters for one user."""

    tokens: int = 0
    requests: int = 0
    custom_usage: Dict[str, float] = field(default_factory=dict)
    last_request_at: Optional[datetime] = None


class UserLimitManager:
    """
    Per-user daily usage and fair-use manager.

    This layer is independent from provider quotas.

    Provider quota:
        "Can Gemini/Mistral/Cloudflare handle this request?"

    User quota:
        "Is this user allowed to consume more today?"
    """

    def __init__(
        self,
        daily_token_limit: int = DEFAULT_DAILY_TOKEN_LIMIT,
    ):
        if daily_token_limit < 0:
            raise ValueError(
                "daily_token_limit cannot be negative"
            )

        self.daily_token_limit = daily_token_limit
        self.usage: Dict[str, UserUsage] = {}
        self._lock = Lock()

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        if not isinstance(user_id, str):
            raise TypeError("user_id must be a string")

        user_id = user_id.strip()

        if not user_id:
            raise ValueError("user_id cannot be empty")

        return user_id

    def _get_usage(self, user_id: str) -> UserUsage:
        if user_id not in self.usage:
            self.usage[user_id] = UserUsage()

        return self.usage[user_id]

    def get_usage(self, user_id: str) -> Dict[str, Any]:
        """Return the current usage information for one user."""

        user_id = self._normalize_user_id(user_id)

        with self._lock:
            usage = self._get_usage(user_id)

            return {
                "user_id": user_id,
                "requests": usage.requests,
                "tokens": usage.tokens,
                "daily_token_limit": self.daily_token_limit,
                "tokens_remaining": max(
                    0,
                    self.daily_token_limit - usage.tokens,
                ),
                "custom_usage": dict(usage.custom_usage),
                "last_request_at": (
                    usage.last_request_at.isoformat()
                    if usage.last_request_at
                    else None
                ),
            }

    def quota_status(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Return the user's current daily quota status."""

        user_id = self._normalize_user_id(user_id)

        with self._lock:
            usage = self._get_usage(user_id)

            remaining = max(
                0,
                self.daily_token_limit - usage.tokens,
            )

            return {
                "user_id": user_id,
                "quota_available": (
                    usage.tokens < self.daily_token_limit
                ),
                "tokens_used": usage.tokens,
                "tokens_limit": self.daily_token_limit,
                "tokens_remaining": remaining,
                "requests_used": usage.requests,
            }

    def can_consume(
        self,
        user_id: str,
        estimated_tokens: int,
    ) -> bool:
        """
        Check whether the user can consume the estimated tokens
        without exceeding the daily limit.
        """

        user_id = self._normalize_user_id(user_id)

        if estimated_tokens < 0:
            raise ValueError(
                "estimated_tokens cannot be negative"
            )

        with self._lock:
            usage = self._get_usage(user_id)

            return (
                usage.tokens + estimated_tokens
                <= self.daily_token_limit
            )

    def has_quota(self, user_id: str) -> bool:
        """Return True when the user still has daily quota."""

        return self.quota_status(
            user_id
        )["quota_available"]

    def record_usage(
        self,
        user_id: str,
        tokens: int = 0,
        custom_usage: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Record successful AI usage for one user.

        This method records actual/estimated token usage supplied
        by the caller.
        """

        user_id = self._normalize_user_id(user_id)

        if tokens < 0:
            raise ValueError(
                "tokens cannot be negative"
            )

        if custom_usage:
            for key, value in custom_usage.items():
                if value < 0:
                    raise ValueError(
                        f"custom usage cannot be negative: {key}"
                    )

        with self._lock:
            usage = self._get_usage(user_id)

            usage.requests += 1
            usage.tokens += tokens
            usage.last_request_at = datetime.now(
                timezone.utc
            )

            if custom_usage:
                for key, value in custom_usage.items():
                    usage.custom_usage[key] = (
                        usage.custom_usage.get(key, 0)
                        + value
                    )

            return {
                "user_id": user_id,
                "requests": usage.requests,
                "tokens": usage.tokens,
                "daily_token_limit": self.daily_token_limit,
                "tokens_remaining": max(
                    0,
                    self.daily_token_limit - usage.tokens,
                ),
                "custom_usage": dict(
                    usage.custom_usage
                ),
                "last_request_at": (
                    usage.last_request_at.isoformat()
                ),
            }

    def reset_user(self, user_id: str) -> None:
        """Reset runtime usage for one user."""

        user_id = self._normalize_user_id(user_id)

        with self._lock:
            self.usage[user_id] = UserUsage()

    def reset_all(self) -> None:
        """Reset runtime usage for all users."""

        with self._lock:
            self.usage.clear()