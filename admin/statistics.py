from __future__ import annotations

from typing import Any, Dict, Optional

from quota.manager import QuotaManager
from reliability.manager import ReliabilityManager
from routing.engine import (
    DEFAULT_MODELS,
    GEMINI_CAPACITIES,
    GROQ_CAPACITIES,
    SINGLE_CAPACITIES,
    RoutingEngine,
    QUOTA_MANAGER,
    RELIABILITY_MANAGER,
)


class AdminStatistics:
    """
    Phase 9 � deterministic ODDI-AI administration/statistics.

    This module NEVER calls an AI provider.
    It only reads router, quota and reliability state.
    """

    def __init__(
        self,
        quota_manager: Optional[QuotaManager] = None,
        reliability_manager: Optional[ReliabilityManager] = None,
        routing_engine: Optional[RoutingEngine] = None,
    ):
        self.quota_manager = quota_manager or QUOTA_MANAGER
        self.reliability_manager = (
            reliability_manager or RELIABILITY_MANAGER
        )
        self.routing_engine = (
            routing_engine
            or RoutingEngine(
                quota_manager=self.quota_manager
            )
        )
    # ==========================================================
    # PHASE 9 COMMAND WRAPPERS
    # ==========================================================

    def accounts(self) -> Dict[str, Any]:
            """
            Return account-level statistics.

            Uses the existing application database.
            No AI/provider call.
            """
            try:
                from app.database import get_db

                conn = get_db("chat")

                try:
                    row = conn.execute(
                        "SELECT COUNT(*) AS total_accounts FROM users"
                    ).fetchone()

                    total_accounts = int(
                        row["total_accounts"]
                        if row is not None
                        else 0
                    )

                finally:
                    conn.close()

                return {
                    "status": "success",
                    "total_accounts": total_accounts,
                }

            except Exception as exc:
                return {
                    "status": "error",
                    "total_accounts": 0,
                    "error": str(exc),
                }

    def account_count(self) -> Dict[str, Any]:
            """
            Return only the total account count.
            """
            result = self.accounts()

            return {
                "status": result.get("status", "success"),
                "total_accounts": int(
                    result.get("total_accounts", 0)
                ),
            }

    def usage(self) -> Dict[str, Any]:
            """
            Aggregate runtime user AI usage from the quota manager.
            """
            tracked_users = 0
            total_requests = 0
            total_tokens = 0

            user_usage = getattr(
                self.quota_manager,
                "user_usage",
                {},
            )

            if isinstance(user_usage, dict):
                tracked_users = len(user_usage)

                for usage in user_usage.values():
                    if not isinstance(usage, dict):
                        continue

                    total_requests += int(
                        usage.get("requests", 0) or 0
                    )

                    total_tokens += int(
                        usage.get("tokens", 0) or 0
                    )

            return {
                "status": "success",
                "tracked_users": tracked_users,
                "total_requests": total_requests,
                "total_tokens": total_tokens,
            }
        # ==========================================================
    # PHASE 9 — ACCOUNT STATISTICS
    # ==========================================================

    def accounts(self) -> Dict[str, Any]:
        """
        Return account-level statistics.

        This is deterministic and never calls an AI provider.
        """
        total_accounts = 0

        try:
            from app.database import get_db

            # The authentication/user database may be supplied by
            # the application. If it is unavailable, fall back safely.
            for backend in ("auth", "chat"):
                try:
                    conn = get_db(backend)

                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) AS total_accounts "
                            "FROM users"
                        ).fetchone()

                        if row is not None:
                            try:
                                total_accounts = int(
                                    row["total_accounts"]
                                )
                            except (TypeError, KeyError):
                                total_accounts = int(row[0])

                            return {
                                "status": "success",
                                "total_accounts": total_accounts,
                            }

                    finally:
                        conn.close()

                except Exception:
                    continue

        except Exception:
            pass

        return {
            "status": "success",
            "total_accounts": total_accounts,
        }

    def account_count(self) -> Dict[str, Any]:
        """
        Return only the total account count.
        """
        result = self.accounts()

        return {
            "status": result.get("status", "success"),
            "total_accounts": int(
                result.get("total_accounts", 0)
            ),
        }

    # ==========================================================
    # PHASE 9 — AGGREGATED USAGE
    # ==========================================================

    def usage(self) -> Dict[str, Any]:
        """
        Return aggregate in-memory ODDI-AI user usage.

        No provider/API call is made.
        """
        total_users = 0
        total_requests = 0
        total_tokens = 0

        user_usage = getattr(
            self.quota_manager,
            "user_usage",
            {},
        )

        if isinstance(user_usage, dict):
            total_users = len(user_usage)

            for usage in user_usage.values():
                if not isinstance(usage, dict):
                    continue

                total_requests += int(
                    usage.get("requests", 0) or 0
                )

                total_tokens += int(
                    usage.get("tokens", 0) or 0
                )

        return {
            "status": "success",
            "tracked_users": total_users,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
        }
    # ==========================================================
    # PROVIDER STATISTICS
    # ==========================================================

    def provider_statistics(self) -> Dict[str, Any]:
        providers = {}

        for provider in DEFAULT_MODELS:
            capacities = self._capacities(provider)

            provider_data = {
                "provider": provider,
                "models": list(DEFAULT_MODELS.get(provider, [])),
                "capacities": {},
            }

            for capacity_id in capacities:
                quota = self._safe_quota_status(
                    provider,
                    capacity_id,
                )

                reliability = self._safe_reliability_state(
                    provider,
                    capacity_id,
                )

                state = self.routing_engine.get_provider_state(
                    provider,
                    capacity_id,
                )

                provider_data["capacities"][capacity_id] = {
                    "configured": state.get("configured", False),
                    "healthy": state.get("healthy", False),
                    "quota_available": state.get(
                        "quota_available",
                        False,
                    ),
                    "quota": quota,
                    "reliability": reliability,
                }

            providers[provider] = provider_data

        return {
            "status": "success",
            "providers": providers,
        }

    # ==========================================================
    # USER USAGE
    # ==========================================================

    def user_usage(
        self,
        user_id: str,
        role: Optional[str] = None,
        is_host: bool = False,
        quota_exempt: bool = False,
    ) -> Dict[str, Any]:

        if not user_id:
            return {
                "status": "failed",
                "reason": "user_id_required",
            }

        usage = self.quota_manager.get_user_usage(
            user_id
        )

        quota = self.quota_manager.user_quota_status(
            user_id=user_id,
            role=role,
            is_host=is_host,
            quota_exempt=quota_exempt,
        )

        return {
            "status": "success",
            "user_id": user_id,
            "usage": usage,
            "quota": quota,
        }

    # ==========================================================
    # ROUTER HEALTH
    # ==========================================================

    def router_health(self) -> Dict[str, Any]:
        result = {
            "status": "success",
            "providers": {},
            "healthy_capacities": 0,
            "unhealthy_capacities": 0,
            "configured_capacities": 0,
        }

        for provider in DEFAULT_MODELS:
            result["providers"][provider] = {}

            for capacity_id in self._capacities(provider):
                state = self.routing_engine.get_provider_state(
                    provider,
                    capacity_id,
                )

                result["providers"][provider][capacity_id] = {
                    "configured": state.get(
                        "configured",
                        False,
                    ),
                    "healthy": state.get(
                        "healthy",
                        False,
                    ),
                    "quota_available": state.get(
                        "quota_available",
                        False,
                    ),
                }

                if state.get("configured"):
                    result["configured_capacities"] += 1

                if state.get("healthy"):
                    result["healthy_capacities"] += 1
                else:
                    result["unhealthy_capacities"] += 1

        return result

    # ==========================================================
    # FAILURE STATISTICS
    # ==========================================================

    def failure_statistics(self) -> Dict[str, Any]:
        result = {
            "status": "success",
            "providers": {},
            "total_failures": 0,
            "total_successes": 0,
        }

        for provider in DEFAULT_MODELS:
            result["providers"][provider] = {}

            for capacity_id in self._capacities(provider):
                state = self._safe_reliability_state(
                    provider,
                    capacity_id,
                )

                failures = int(
                    state.get(
                        "total_failures",
                        0,
                    )
                    or 0
                )

                successes = int(
                    state.get(
                        "total_successes",
                        0,
                    )
                    or 0
                )

                result["total_failures"] += failures
                result["total_successes"] += successes

                result["providers"][provider][capacity_id] = {
                    "total_failures": failures,
                    "total_successes": successes,
                    "consecutive_failures": state.get(
                        "consecutive_failures",
                        0,
                    ),
                    "healthy": state.get(
                        "healthy",
                        True,
                    ),
                    "cooldown_remaining_seconds": state.get(
                        "cooldown_remaining_seconds",
                        0,
                    ),
                }

        return result

    # ==========================================================
    # QUOTA STATISTICS
    # ==========================================================

    def quota_statistics(self) -> Dict[str, Any]:
        result = {
            "status": "success",
            "providers": {},
        }

        for provider in DEFAULT_MODELS:
            result["providers"][provider] = {}

            for capacity_id in self._capacities(provider):
                result["providers"][provider][capacity_id] = (
                    self._safe_quota_status(
                        provider,
                        capacity_id,
                    )
                )

        return result

    # ==========================================================
    # HELP
    # ==========================================================

    @staticmethod
    def help() -> Dict[str, Any]:
        return {
            "status": "success",
            "commands": {
                "/help": "Show available host/admin commands",
                "/accounts": "Show available account information",
                "/count": "Show total account count",
                "/usage": "Show usage information",
                "/provider_statistics": (
                    "Show provider, capacity, quota and health statistics"
                ),
                "/quota": "Show provider quota statistics",
                "/health": "Show router/provider health",
                "/failures": "Show provider failure statistics",
            },
        }

    # ==========================================================
    # INTERNAL HELPERS
    # ==========================================================

    @staticmethod
    def _capacities(provider: str) -> Dict[str, Dict[str, Any]]:

        if provider == "gemini":
            return GEMINI_CAPACITIES

        if provider == "groq":
            return GROQ_CAPACITIES

        return {
            provider: SINGLE_CAPACITIES.get(
                provider,
                {
                    "provider": provider,
                    "api_key_number": None,
                    "env": None,
                },
            )
        }

    def _safe_quota_status(
        self,
        provider: str,
        capacity_id: str,
    ) -> Dict[str, Any]:

        try:
            result = self.quota_manager.quota_status(
                provider,
                capacity_id,
            )

            return (
                result
                if isinstance(result, dict)
                else {"status": "unknown"}
            )

        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    def _safe_reliability_state(
        self,
        provider: str,
        capacity_id: str,
    ) -> Dict[str, Any]:

        try:
            result = self.reliability_manager.get_state(
                provider,
                capacity_id,
            )

            return (
                result
                if isinstance(result, dict)
                else {"status": "unknown"}
            )

        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }
