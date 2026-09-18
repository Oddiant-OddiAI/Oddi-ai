from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, Optional


from config.limits import PROVIDER_LIMITS


@dataclass
class UsageEvent:
    """One request event used for rolling one-minute quota checks."""
    timestamp: datetime
    tokens: int = 0
    custom_usage: Dict[str, float] = field(default_factory=dict)


@dataclass
class ProviderUsage:
    """Runtime usage counters for one provider or capacity pool."""

    requests: int = 0
    tokens: int = 0

    custom_usage: Dict[str, float] = field(
        default_factory=dict
    )

    last_request_at: Optional[datetime] = None

    # Rolling one-minute events.
    events: Deque[UsageEvent] = field(
        default_factory=deque
    )


@dataclass
class UserUsage:
    """Runtime usage counters for one ODDI user."""

    requests: int = 0
    tokens: int = 0

    # UTC calendar day used for the daily user allowance.
    usage_date: str = ""

    last_request_at: Optional[datetime] = None

    # Rolling one-minute events for fair-use protection.
    events: Deque[UsageEvent] = field(
        default_factory=deque
    )


class QuotaManager:
    """
    Provider/capacity-aware runtime quota manager.

    Supports:

    - RPM
    - RPD
    - TPM
    - TPD
    - provider-specific custom quotas
    - capacity-specific quotas
    - rolling one-minute usage
    - projected quota checks
    - thread-safe accounting
    - per-user daily limits
    - per-user rolling fair-use limits
    - role/priority-aware user limits
    - automatic user daily rollover
    - user-level quota status and reset

    This class does NOT:

    - make provider API calls
    - perform provider authentication
    - resolve authentication or identity
    - read Memory directly
    """

    WINDOW_SECONDS = 60

    def __init__(
        self,
        limits: Optional[Dict[str, Dict[str, Any]]] = None,
        user_limits: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.limits = (
            limits
            if limits is not None
            else PROVIDER_LIMITS
        )

        # User-level limits are deliberately separate from provider
        # quotas. Provider quotas describe external AI capacity;
        # user limits describe ODDI product/fair-use policy.
        self.user_limits = (
            user_limits
            if user_limits is not None
            else {
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
        )

        self.usage: Dict[str, ProviderUsage] = {}

        # User usage is isolated by user_id.
        self.user_usage: Dict[str, UserUsage] = {}

        self._lock = Lock()

    # ======================================================
    # NORMALIZATION
    # ======================================================

    @staticmethod
    def _normalize_provider(
        provider: str,
    ) -> str:
        provider = provider.strip().lower()

        if not provider:
            raise ValueError(
                "provider cannot be empty"
            )

        return provider

    @staticmethod
    def _normalize_capacity(
        capacity_id: Optional[str],
    ) -> Optional[str]:

        if capacity_id is None:
            return None

        capacity_id = capacity_id.strip().lower()

        if not capacity_id:
            raise ValueError(
                "capacity_id cannot be empty"
            )

        return capacity_id

    # ======================================================
    # USAGE KEYS
    # ======================================================

    @staticmethod
    def _usage_key(
        provider: str,
        capacity_id: Optional[str] = None,
    ) -> str:

        provider = provider.strip().lower()

        if capacity_id:
            return (
                f"{provider}:"
                f"{capacity_id.strip().lower()}"
            )

        return provider

    # ======================================================
    # INTERNAL USAGE
    # ======================================================

    def _get_usage(
        self,
        provider: str,
        capacity_id: Optional[str] = None,
    ) -> ProviderUsage:

        key = self._usage_key(
            provider,
            capacity_id,
        )

        if key not in self.usage:
            self.usage[key] = ProviderUsage()

        return self.usage[key]

    # ======================================================
    # LIMIT LOOKUP
    # ======================================================

    def _get_config(
        self,
        provider: str,
        capacity_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        provider_config = (
            self.limits.get(provider, {})
            or {}
        )

        if capacity_id:

            pools = (
                provider_config.get(
                    "capacity_pools",
                    {},
                )
                or {}
            )

            # Single-capacity providers are represented by the
            # provider itself as their capacity_id.
            #
            # Example:
            #   provider="mistral"
            #   capacity_id="mistral"
            #
            # There is no capacity_pools["mistral"], so the
            # provider-level configuration is the correct quota
            # configuration.
            if not pools:
                if capacity_id == provider:
                    return provider_config

                return {}

            return (
                pools.get(capacity_id, {})
                or {}
            )

        return provider_config
    def _get_limit(
        self,
        provider: str,
        key: str,
        capacity_id: Optional[str] = None,
    ) -> Optional[float]:

        config = self._get_config(
            provider,
            capacity_id,
        )

        value = config.get(key)

        if value is None:
            return None

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

    def _get_custom_limits(
        self,
        provider: str,
        capacity_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        config = self._get_config(
            provider,
            capacity_id,
        )

        return (
            config.get("custom", {})
            or {}
        )

    # ======================================================
    # CAPACITY VALIDATION
    # ======================================================

    def _validate_capacity(
        self,
        provider: str,
        capacity_id: Optional[str],
    ) -> None:

        if capacity_id is None:
            return

        provider_config = (
            self.limits.get(provider, {})
            or {}
        )

        pools = (
            provider_config.get(
                "capacity_pools",
                {},
            )
            or {}
        )

        # Single-capacity provider.
        #
        # The router represents the provider itself as the
        # capacity ID:
        #
        #   mistral -> mistral
        #   cloudflare -> cloudflare
        #   openrouter -> openrouter
        #
        # These providers do not need a capacity_pools section.
        if not pools:
            if capacity_id == provider:
                return

            raise ValueError(
                f"Unknown capacity "
                f"'{capacity_id}' "
                f"for provider "
                f"'{provider}'"
            )

        # Multi-capacity provider.
        if capacity_id not in pools:
            raise ValueError(
                f"Unknown capacity pool "
                f"'{capacity_id}' "
                f"for provider "
                f"'{provider}'"
            )

    # ======================================================
    # TIME
    # ======================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # ======================================================
    # ROLLING WINDOW
    # ======================================================

    def _prune_events(
        self,
        usage: ProviderUsage,
        now: datetime,
    ) -> None:

        cutoff = (
            now.timestamp()
            - self.WINDOW_SECONDS
        )

        while usage.events:

            first = usage.events[0]

            if (
                first.timestamp.timestamp()
                >= cutoff
            ):
                break

            usage.events.popleft()

    def _rolling_usage(
        self,
        usage: ProviderUsage,
        now: datetime,
    ):
        self._prune_events(
            usage,
            now,
        )

        requests = len(
            usage.events
        )

        tokens = sum(
            event.tokens
            for event in usage.events
        )

        custom: Dict[
            str,
            float,
        ] = {}

        for event in usage.events:

            for (
                key,
                value,
            ) in event.custom_usage.items():

                custom[key] = (
                    custom.get(key, 0)
                    + value
                )

        return (
            requests,
            tokens,
            custom,
        )

    # ======================================================
    # GET USAGE
    # ======================================================

    def get_usage(
        self,
        provider: str,
        capacity_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        provider = self._normalize_provider(
            provider
        )

        capacity_id = (
            self._normalize_capacity(
                capacity_id
            )
        )

        with self._lock:

            usage = self._get_usage(
                provider,
                capacity_id,
            )

            now = self._now()

            (
                rolling_requests,
                rolling_tokens,
                rolling_custom,
            ) = self._rolling_usage(
                usage,
                now,
            )

            return {
                "provider": provider,
                "capacity_id": capacity_id,

                "requests": usage.requests,
                "tokens": usage.tokens,

                "custom_usage": dict(
                    usage.custom_usage
                ),

                "rolling_1m_requests":
                    rolling_requests,

                "rolling_1m_tokens":
                    rolling_tokens,

                "rolling_1m_custom_usage":
                    rolling_custom,

                "last_request_at": (
                    usage.last_request_at.isoformat()
                    if usage.last_request_at
                    else None
                ),
            }

    # ======================================================
    # RECORD REQUEST
    # ======================================================

    def record_request(
        self,
        provider: str,
        tokens: int = 0,
        custom_usage:
            Optional[
                Dict[str, float]
            ] = None,
        capacity_id:
            Optional[str] = None,
    ) -> Dict[str, Any]:

        provider = self._normalize_provider(
            provider
        )

        capacity_id = (
            self._normalize_capacity(
                capacity_id
            )
        )

        if tokens < 0:
            raise ValueError(
                "tokens cannot be negative"
            )

        custom_usage = (
            custom_usage
            if custom_usage is not None
            else {}
        )

        for (
            key,
            value,
        ) in custom_usage.items():

            if value < 0:
                raise ValueError(
                    f"custom usage cannot "
                    f"be negative: {key}"
                )

        with self._lock:

            self._validate_capacity(
                provider,
                capacity_id,
            )

            usage = self._get_usage(
                provider,
                capacity_id,
            )

            now = self._now()

            # ------------------------------------------
            # CUMULATIVE USAGE
            # ------------------------------------------

            usage.requests += 1

            usage.tokens += tokens

            usage.last_request_at = now

            # ------------------------------------------
            # ROLLING WINDOW EVENT
            # ------------------------------------------

            usage.events.append(
                UsageEvent(
                    timestamp=now,
                    tokens=tokens,
                    custom_usage=dict(
                        custom_usage
                    ),
                )
            )

            # ------------------------------------------
            # CUSTOM USAGE
            # ------------------------------------------

            for (
                key,
                value,
            ) in custom_usage.items():

                usage.custom_usage[key] = (
                    usage.custom_usage.get(
                        key,
                        0,
                    )
                    + value
                )

            self._prune_events(
                usage,
                now,
            )

            return {
                "provider": provider,
                "capacity_id": capacity_id,

                "requests":
                    usage.requests,

                "tokens":
                    usage.tokens,

                "custom_usage":
                    dict(
                        usage.custom_usage
                    ),

                "last_request_at":
                    now.isoformat(),
            }

    # ======================================================
    # QUOTA STATUS
    # ======================================================

    def quota_status(
        self,
        provider: str,
        capacity_id:
            Optional[str] = None,
    ) -> Dict[str, Any]:

        provider = self._normalize_provider(
            provider
        )

        capacity_id = (
            self._normalize_capacity(
                capacity_id
            )
        )

        with self._lock:

            self._validate_capacity(
                provider,
                capacity_id,
            )

            usage = self._get_usage(
                provider,
                capacity_id,
            )

            now = self._now()

            (
                rolling_requests,
                rolling_tokens,
                rolling_custom,
            ) = self._rolling_usage(
                usage,
                now,
            )

            # ------------------------------------------
            # LIMITS
            # ------------------------------------------

            rpm_limit = self._get_limit(
                provider,
                "rpm",
                capacity_id,
            )

            rpd_limit = self._get_limit(
                provider,
                "rpd",
                capacity_id,
            )

            tpm_limit = self._get_limit(
                provider,
                "tpm",
                capacity_id,
            )

            tpd_limit = self._get_limit(
                provider,
                "tpd",
                capacity_id,
            )

            # ------------------------------------------
            # REMAINING
            # ------------------------------------------

            rpm_remaining = (
                None
                if rpm_limit is None
                else max(
                    0,
                    rpm_limit
                    - rolling_requests,
                )
            )

            rpd_remaining = (
                None
                if rpd_limit is None
                else max(
                    0,
                    rpd_limit
                    - usage.requests,
                )
            )

            tpm_remaining = (
                None
                if tpm_limit is None
                else max(
                    0,
                    tpm_limit
                    - rolling_tokens,
                )
            )

            tpd_remaining = (
                None
                if tpd_limit is None
                else max(
                    0,
                    tpd_limit
                    - usage.tokens,
                )
            )

            # ------------------------------------------
            # CUSTOM LIMITS
            # ------------------------------------------

            custom_limits = (
                self._get_custom_limits(
                    provider,
                    capacity_id,
                )
            )

            custom_status: Dict[
                str,
                Any,
            ] = {}

            for (
                key,
                limit,
            ) in custom_limits.items():

                # Metadata, not a quota.
                if (
                    key == "source"
                    or limit is None
                ):
                    continue

                try:
                    numeric_limit = float(
                        limit
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                daily_used = (
                    usage.custom_usage.get(
                        key,
                        0,
                    )
                )

                rolling_used = (
                    rolling_custom.get(
                        key,
                        0,
                    )
                )

                custom_status[key] = {
                    "used": daily_used,
                    "limit": numeric_limit,
                    "remaining": max(
                        0,
                        numeric_limit
                        - daily_used,
                    ),
                    "rolling_1m_used":
                        rolling_used,
                }

            # ------------------------------------------
            # EXHAUSTED DIMENSIONS
            # ------------------------------------------

            exhausted_dimensions = []

            dimensions = {
                "rpm": rpm_remaining,
                "rpd": rpd_remaining,
                "tpm": tpm_remaining,
                "tpd": tpd_remaining,
            }

            for (
                name,
                remaining,
            ) in dimensions.items():

                if (
                    remaining is not None
                    and remaining <= 0
                ):
                    exhausted_dimensions.append(
                        name
                    )

            for (
                key,
                item,
            ) in custom_status.items():

                if item["remaining"] <= 0:
                    exhausted_dimensions.append(
                        f"custom:{key}"
                    )

            return {
                "provider": provider,
                "capacity_id": capacity_id,

                "quota_available":
                    not exhausted_dimensions,

                "exhausted_dimensions":
                    exhausted_dimensions,

                "requests_used":
                    usage.requests,

                "requests_limit":
                    rpd_limit,

                "requests_remaining":
                    rpd_remaining,

                "tokens_used":
                    usage.tokens,

                "tokens_limit":
                    tpd_limit,

                "tokens_remaining":
                    tpd_remaining,

                "rpm_used":
                    rolling_requests,

                "rpm_limit":
                    rpm_limit,

                "rpm_remaining":
                    rpm_remaining,

                "tpm_used":
                    rolling_tokens,

                "tpm_limit":
                    tpm_limit,

                "tpm_remaining":
                    tpm_remaining,

                "custom":
                    custom_status,
            }

    # ======================================================
    # PROJECTED QUOTA CHECK
    # ======================================================

    def has_quota(
        self,
        provider: str,
        capacity_id:
            Optional[str] = None,
        *,
        tokens: int = 0,
        custom_usage:
            Optional[
                Dict[str, float]
            ] = None,
    ) -> bool:

        provider = self._normalize_provider(
            provider
        )

        capacity_id = (
            self._normalize_capacity(
                capacity_id
            )
        )

        if tokens < 0:
            raise ValueError(
                "tokens cannot be negative"
            )

        custom_usage = (
            custom_usage
            if custom_usage is not None
            else {}
        )

        with self._lock:

            self._validate_capacity(
                provider,
                capacity_id,
            )

            usage = self._get_usage(
                provider,
                capacity_id,
            )

            now = self._now()

            (
                rolling_requests,
                rolling_tokens,
                rolling_custom,
            ) = self._rolling_usage(
                usage,
                now,
            )

            # ------------------------------------------
            # REQUEST LIMITS
            # ------------------------------------------

            rpd_limit = self._get_limit(
                provider,
                "rpd",
                capacity_id,
            )

            rpm_limit = self._get_limit(
                provider,
                "rpm",
                capacity_id,
            )

            # ------------------------------------------
            # TOKEN LIMITS
            # ------------------------------------------

            tpd_limit = self._get_limit(
                provider,
                "tpd",
                capacity_id,
            )

            tpm_limit = self._get_limit(
                provider,
                "tpm",
                capacity_id,
            )

            # ------------------------------------------
            # PROJECTED REQUEST
            # ------------------------------------------

            projected_requests = (
                usage.requests + 1
            )

            projected_rolling_requests = (
                rolling_requests + 1
            )

            projected_tokens = (
                usage.tokens + tokens
            )

            projected_rolling_tokens = (
                rolling_tokens + tokens
            )

            # ------------------------------------------
            # CHECK DAILY REQUESTS
            # ------------------------------------------

            if (
                rpd_limit is not None
                and projected_requests
                > rpd_limit
            ):
                return False

            # ------------------------------------------
            # CHECK RPM
            # ------------------------------------------

            if (
                rpm_limit is not None
                and projected_rolling_requests
                > rpm_limit
            ):
                return False

            # ------------------------------------------
            # CHECK DAILY TOKENS
            # ------------------------------------------

            if (
                tpd_limit is not None
                and projected_tokens
                > tpd_limit
            ):
                return False

            # ------------------------------------------
            # CHECK TPM
            # ------------------------------------------

            if (
                tpm_limit is not None
                and projected_rolling_tokens
                > tpm_limit
            ):
                return False

            # ------------------------------------------
            # CUSTOM LIMITS
            # ------------------------------------------

            custom_limits = (
                self._get_custom_limits(
                    provider,
                    capacity_id,
                )
            )

            for (
                key,
                value,
            ) in custom_usage.items():

                if value < 0:
                    raise ValueError(
                        f"custom usage cannot "
                        f"be negative: {key}"
                    )

                limit = custom_limits.get(
                    key
                )

                if limit is None:
                    continue

                try:
                    numeric_limit = float(
                        limit
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                projected = (
                    usage.custom_usage.get(
                        key,
                        0,
                    )
                    + value
                )

                if projected > numeric_limit:
                    return False

            # ------------------------------------------
            # ALREADY EXHAUSTED CUSTOM LIMIT
            # ------------------------------------------

            for (
                key,
                limit,
            ) in custom_limits.items():

                if (
                    key == "source"
                    or limit is None
                ):
                    continue

                try:
                    numeric_limit = float(
                        limit
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if (
                    usage.custom_usage.get(
                        key,
                        0,
                    )
                    >= numeric_limit
                ):
                    return False

            return True

    # ======================================================
    # USER LIMITS / FAIR USE
    # ======================================================

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        """Normalize and validate an ODDI user identifier."""

        if user_id is None:
            raise ValueError("user_id cannot be None")

        user_id = str(user_id).strip()

        if not user_id:
            raise ValueError("user_id cannot be empty")

        return user_id

    @staticmethod
    def _normalize_role(role: Optional[str]) -> str:
        """Normalize a role supplied by the trusted identity layer."""

        if role is None:
            return "user"

        role = str(role).strip().lower()

        return role or "user"

    @staticmethod
    def _normalize_priority(priority: Any) -> Any:
        """
        Preserve the priority value supplied by the identity/memory
        layer without making QuotaManager responsible for resolving it.
        """

        return priority

    def _get_user_usage(
        self,
        user_id: str,
    ) -> UserUsage:
        """Return isolated runtime usage for one user."""

        if user_id not in self.user_usage:
            self.user_usage[user_id] = UserUsage(
                usage_date=self._today_key()
            )

        return self.user_usage[user_id]

    @staticmethod
    def _today_key() -> str:
        """Return the current UTC calendar-day key."""

        return date.today().isoformat()

    def _ensure_user_day(
        self,
        usage: UserUsage,
        today: Optional[str] = None,
    ) -> None:
        """
        Automatically roll a user's daily counters into a new
        calendar day.

        Rolling events are also cleared because they cannot belong to
        the new daily bucket.
        """

        today = today or self._today_key()

        if usage.usage_date == today:
            return

        usage.requests = 0
        usage.tokens = 0
        usage.last_request_at = None
        usage.events.clear()
        usage.usage_date = today

    def _get_user_limit(
        self,
        role: str,
        key: str,
    ) -> Optional[float]:
        """
        Resolve one user limit.

        Unknown roles inherit the normal user policy. This keeps a new
        application role from accidentally receiving an unlimited quota.
        """

        role_config = self.user_limits.get(role)

        if role_config is None:
            role_config = self.user_limits.get("user", {})

        value = role_config.get(key)

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_user_exempt(
        role: str,
        is_host: bool = False,
        quota_exempt: bool = False,
    ) -> bool:
        """
        Determine whether normal user quota limits are bypassed.

        Host/owner/admin exemption is explicit and does not depend on
        email matching inside the quota layer.
        """

        if quota_exempt:
            return True

        if is_host:
            return True

        return role in {"owner", "admin"}

    def get_user_usage(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Return current usage for one isolated ODDI user."""

        user_id = self._normalize_user_id(user_id)

        with self._lock:

            usage = self._get_user_usage(user_id)

            self._ensure_user_day(usage)

            now = self._now()

            (
                rolling_requests,
                rolling_tokens,
                _rolling_custom,
            ) = self._rolling_usage(
                usage,
                now,
            )

            return {
                "user_id": user_id,
                "usage_date": usage.usage_date,
                "requests": usage.requests,
                "tokens": usage.tokens,
                "rolling_1m_requests": rolling_requests,
                "rolling_1m_tokens": rolling_tokens,
                "last_request_at": (
                    usage.last_request_at.isoformat()
                    if usage.last_request_at
                    else None
                ),
            }

    def user_quota_status(
        self,
        user_id: str,
        role: Optional[str] = None,
        priority: Any = None,
        is_host: bool = False,
        quota_exempt: bool = False,
    ) -> Dict[str, Any]:
        """
        Return complete user quota state.

        The role/priority/is_host values should come from the trusted
        identity/permissions layer. QuotaManager does not authenticate
        the user or read Memory itself.
        """

        user_id = self._normalize_user_id(user_id)
        role = self._normalize_role(role)
        priority = self._normalize_priority(priority)

        with self._lock:

            usage = self._get_user_usage(user_id)

            self._ensure_user_day(usage)

            now = self._now()

            (
                rolling_requests,
                rolling_tokens,
                _rolling_custom,
            ) = self._rolling_usage(
                usage,
                now,
            )

            exempt = self._is_user_exempt(
                role=role,
                is_host=is_host,
                quota_exempt=quota_exempt,
            )

            rpd_limit = self._get_user_limit(
                role,
                "rpd",
            )

            tpd_limit = self._get_user_limit(
                role,
                "tpd",
            )

            rpm_limit = self._get_user_limit(
                role,
                "rpm",
            )

            tpm_limit = self._get_user_limit(
                role,
                "tpm",
            )

            if exempt:
                rpd_remaining = None
                tpd_remaining = None
                rpm_remaining = None
                tpm_remaining = None
                exhausted_dimensions = []
                quota_available = True
            else:
                rpd_remaining = (
                    None
                    if rpd_limit is None
                    else max(
                        0,
                        rpd_limit - usage.requests,
                    )
                )

                tpd_remaining = (
                    None
                    if tpd_limit is None
                    else max(
                        0,
                        tpd_limit - usage.tokens,
                    )
                )

                rpm_remaining = (
                    None
                    if rpm_limit is None
                    else max(
                        0,
                        rpm_limit - rolling_requests,
                    )
                )

                tpm_remaining = (
                    None
                    if tpm_limit is None
                    else max(
                        0,
                        tpm_limit - rolling_tokens,
                    )
                )

                exhausted_dimensions = []

                dimensions = {
                    "rpd": rpd_remaining,
                    "tpd": tpd_remaining,
                    "rpm": rpm_remaining,
                    "tpm": tpm_remaining,
                }

                for (
                    name,
                    remaining,
                ) in dimensions.items():

                    if (
                        remaining is not None
                        and remaining <= 0
                    ):
                        exhausted_dimensions.append(name)

                quota_available = not exhausted_dimensions

            return {
                "user_id": user_id,
                "role": role,
                "priority": priority,
                "is_host": bool(is_host),
                "quota_exempt": bool(quota_exempt),
                "exempt": exempt,
                "usage_date": usage.usage_date,
                "quota_available": quota_available,
                "exhausted_dimensions": exhausted_dimensions,
                "requests_used": usage.requests,
                "requests_limit": rpd_limit,
                "requests_remaining": rpd_remaining,
                "tokens_used": usage.tokens,
                "tokens_limit": tpd_limit,
                "tokens_remaining": tpd_remaining,
                "rpm_used": rolling_requests,
                "rpm_limit": rpm_limit,
                "rpm_remaining": rpm_remaining,
                "tpm_used": rolling_tokens,
                "tpm_limit": tpm_limit,
                "tpm_remaining": tpm_remaining,
            }

    def has_user_quota(
        self,
        user_id: str,
        role: Optional[str] = None,
        priority: Any = None,
        is_host: bool = False,
        quota_exempt: bool = False,
        *,
        requests: int = 1,
        tokens: int = 0,
    ) -> bool:
        """
        Project whether one user can perform another request.

        This is intended to be called BEFORE provider routing.

        `requests` is normally 1. `tokens` should be the estimated
        request/response token cost available to the caller. If the
        exact token cost is unknown, zero can be supplied and the final
        usage should still be recorded after successful execution.
        """

        user_id = self._normalize_user_id(user_id)
        role = self._normalize_role(role)
        self._normalize_priority(priority)

        if requests < 0:
            raise ValueError("requests cannot be negative")

        if tokens < 0:
            raise ValueError("tokens cannot be negative")

        with self._lock:

            usage = self._get_user_usage(user_id)

            self._ensure_user_day(usage)

            if self._is_user_exempt(
                role=role,
                is_host=is_host,
                quota_exempt=quota_exempt,
            ):
                return True

            now = self._now()

            (
                rolling_requests,
                rolling_tokens,
                _rolling_custom,
            ) = self._rolling_usage(
                usage,
                now,
            )

            rpd_limit = self._get_user_limit(
                role,
                "rpd",
            )

            tpd_limit = self._get_user_limit(
                role,
                "tpd",
            )

            rpm_limit = self._get_user_limit(
                role,
                "rpm",
            )

            tpm_limit = self._get_user_limit(
                role,
                "tpm",
            )

            projected_requests = (
                usage.requests + requests
            )

            projected_tokens = (
                usage.tokens + tokens
            )

            projected_rolling_requests = (
                rolling_requests + requests
            )

            projected_rolling_tokens = (
                rolling_tokens + tokens
            )

            if (
                rpd_limit is not None
                and projected_requests > rpd_limit
            ):
                return False

            if (
                tpd_limit is not None
                and projected_tokens > tpd_limit
            ):
                return False

            if (
                rpm_limit is not None
                and projected_rolling_requests > rpm_limit
            ):
                return False

            if (
                tpm_limit is not None
                and projected_rolling_tokens > tpm_limit
            ):
                return False

            return True

    def record_user_request(
        self,
        user_id: str,
        tokens: int = 0,
        role: Optional[str] = None,
        priority: Any = None,
        is_host: bool = False,
        quota_exempt: bool = False,
    ) -> Dict[str, Any]:
        """
        Record one successfully completed ODDI user request.

        This method intentionally records usage AFTER successful
        provider execution. It does not consume a user's daily
        allowance merely because routing was attempted.
        """

        user_id = self._normalize_user_id(user_id)
        role = self._normalize_role(role)
        priority = self._normalize_priority(priority)

        if tokens < 0:
            raise ValueError("tokens cannot be negative")

        with self._lock:

            usage = self._get_user_usage(user_id)

            self._ensure_user_day(usage)

            now = self._now()

            usage.requests += 1
            usage.tokens += tokens
            usage.last_request_at = now

            usage.events.append(
                UsageEvent(
                    timestamp=now,
                    tokens=tokens,
                )
            )

            self._prune_events(
                usage,
                now,
            )

            return {
                "user_id": user_id,
                "role": role,
                "priority": priority,
                "is_host": bool(is_host),
                "quota_exempt": bool(quota_exempt),
                "usage_date": usage.usage_date,
                "requests": usage.requests,
                "tokens": usage.tokens,
                "last_request_at": now.isoformat(),
            }

    def reset_user(
        self,
        user_id: str,
    ) -> None:
        """Reset one user's daily and rolling usage."""

        user_id = self._normalize_user_id(user_id)

        with self._lock:

            self.user_usage[user_id] = UserUsage(
                usage_date=self._today_key()
            )

    def reset_all_users(self) -> None:
        """Reset all tracked user usage."""

        with self._lock:
            self.user_usage.clear()

    # ======================================================
    # RESET ONE PROVIDER / CAPACITY
    # ======================================================

    def reset_provider(
        self,
        provider: str,
        capacity_id:
            Optional[str] = None,
    ) -> None:

        provider = self._normalize_provider(
            provider
        )

        capacity_id = (
            self._normalize_capacity(
                capacity_id
            )
        )

        with self._lock:

            self._validate_capacity(
                provider,
                capacity_id,
            )

            key = self._usage_key(
                provider,
                capacity_id,
            )

            self.usage[key] = ProviderUsage()

    # ======================================================
    # RESET EVERYTHING
    # ======================================================

    def reset_all(self) -> None:

        with self._lock:
            self.usage.clear()


# ==========================================================
# DEFAULT USER LIMIT POLICY
# ==========================================================

DEFAULT_USER_LIMITS = {
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


# ==========================================================
# SHARED QUOTA MANAGER
# ==========================================================

quota_manager = QuotaManager()


# ==========================================================
# MODULE TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("ODDI-AI QUOTA MANAGER")
    print("=" * 60)

    print(
        "Configured providers:",
        ", ".join(
            sorted(
                PROVIDER_LIMITS.keys()
            )
        ),
    )

    print(
        "Status: initialized"
    )

    print("=" * 60)