from __future__ import annotations

from typing import Any, Dict

from admin.statistics import AdminStatistics


class AdminCommandService:
    """
    Deterministic host/admin command layer.

    No AI provider calls.
    Authorization is supplied by the trusted identity layer.
    """

    ADMIN_COMMANDS = {
        "/help",
        "/accounts",
        "/count",
        "/usage",
        "/provider_statistics",
    }

    def __init__(self, statistics: AdminStatistics | None = None):
        self.statistics = statistics or AdminStatistics()

    def execute(
        self,
        message: str,
        is_host: bool = False,
        user_id: str | None = None,
        role: str | None = None,
    ) -> Dict[str, Any]:

        command = (message or "").strip().lower()

        # ------------------------------------------------------
        # Authorization
        # ------------------------------------------------------

        authorized = bool(
            is_host or role in {"owner", "admin"}
        )

        if not authorized:
            return {
                "status": "forbidden",
                "success": False,
                "command": command,
                "message": (
                    "This command is available to administrators only."
                ),
            }

        # ------------------------------------------------------
        # /help
        # ------------------------------------------------------

        if command == "/help":
            return {
                "status": "success",
                "success": True,
                "command": "/help",
                "commands": [
                    "/help",
                    "/accounts",
                    "/count",
                    "/usage",
                    "/provider_statistics",
                ],
                "message": (
                    "ODDI-AI Host/Admin Commands\n"
                    "/help — show this help\n"
                    "/accounts — account information\n"
                    "/count — total account count\n"
                    "/usage — AI usage statistics\n"
                    "/provider_statistics — provider statistics"
                ),
            }

        # ------------------------------------------------------
        # /accounts
        # ------------------------------------------------------

        if command == "/accounts":
            result = self.statistics.accounts()

            return {
                "status": "success",
                "success": True,
                "command": "/accounts",
                "data": result,
                "message": self._format_accounts(result),
            }

        # ------------------------------------------------------
        # /count
        # ------------------------------------------------------

        if command == "/count":
            result = self.statistics.account_count()

            return {
                "status": "success",
                "success": True,
                "command": "/count",
                "data": result,
                "message": (
                    f"Total accounts: "
                    f"{result.get('total_accounts', 0)}"
                ),
            }

        # ------------------------------------------------------
        # /usage
        # ------------------------------------------------------

        if command == "/usage":
            result = self.statistics.usage()

            return {
                "status": "success",
                "success": True,
                "command": "/usage",
                "data": result,
                "message": self._format_usage(result),
            }

        # ------------------------------------------------------
        # /provider_statistics
        # ------------------------------------------------------

        if command == "/provider_statistics":
            result = self.statistics.provider_statistics()

            return {
                "status": "success",
                "success": True,
                "command": "/provider_statistics",
                "data": result,
                "message": self._format_provider_statistics(result),
            }

        # ------------------------------------------------------
        # Unknown command
        # ------------------------------------------------------

        return {
            "status": "unknown_command",
            "success": False,
            "command": command,
        }

    @staticmethod
    def _format_accounts(data: Dict[str, Any]) -> str:
        return (
            "Account Statistics\n"
            f"Total accounts: {data.get('total_accounts', 0)}"
        )

    @staticmethod
    def _format_usage(data: Dict[str, Any]) -> str:
        return (
            "AI Usage Statistics\n"
            f"Tracked users: {data.get('tracked_users', 0)}\n"
            f"Total requests: {data.get('total_requests', 0)}\n"
            f"Total tokens: {data.get('total_tokens', 0)}"
        )

    @staticmethod
    def _format_provider_statistics(
        data: Dict[str, Any],
    ) -> str:

        providers = data.get("providers", {})

        lines = ["Provider Statistics"]

        for provider, stats in providers.items():
            lines.append(
                f"{provider}: "
                f"requests={stats.get('requests', 0)}, "
                f"tokens={stats.get('tokens', 0)}, "
                f"failures={stats.get('failures', 0)}"
            )

        return "\n".join(lines)