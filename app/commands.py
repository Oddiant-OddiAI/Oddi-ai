from app.help_menu import show_help
from app.stats import show_stats


ADMIN_COMMANDS = {
    "/accounts",
    "/count",
    "/usage",
    "/provider_statistics",
}


def handle_command(message, identity=None):
    if not message:
        return None

    command = message.strip().lower()

    # ----------------------------------------------------------
    # PHASE 9 — ADMIN COMMAND ROUTING
    # ----------------------------------------------------------
    #
    # Send recognized admin commands through the authorization
    # layer regardless of who sent them.
    #
    # AdminCommandService itself decides whether the identity
    # is authorized.
    #
    if command in ADMIN_COMMANDS:
        from admin.commands import AdminCommandService

        is_host = bool(
            getattr(identity, "is_host", False)
        ) if identity is not None else False

        role = (
            getattr(identity, "role", None)
            if identity is not None
            else None
        )

        return AdminCommandService().execute(
            message=command,
            is_host=is_host,
            user_id=(
                getattr(identity, "user_id", None)
                if identity is not None
                else None
            ),
            role=role,
        )

    # ----------------------------------------------------------
    # HELP
    # ----------------------------------------------------------

    if command == "/help":

        # Host/admin gets admin help.
        if identity is not None:
            is_host = bool(
                getattr(identity, "is_host", False)
            )

            role = (
                getattr(identity, "role", "")
                or ""
            ).lower()

            if is_host or role in {"owner", "admin"}:
                from admin.commands import AdminCommandService

                return AdminCommandService().execute(
                    message="/help",
                    is_host=is_host,
                    user_id=getattr(
                        identity,
                        "user_id",
                        None,
                    ),
                    role=role,
                )

        # Normal users get normal help only.
        return show_help()

    # ----------------------------------------------------------
    # EXISTING COMMANDS
    # ----------------------------------------------------------

    if command == "/stats":
        return show_stats()

    return None