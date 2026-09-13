from dataclasses import dataclass
from typing import Optional


# ============================================================
# HOST ACCOUNT
# ============================================================
# IMPORTANT:
# Replace this with the actual email of the ODDI owner.
# Do NOT put the email in the user's prompt or let the AI
# decide whether someone is the owner.
# ============================================================

HOST_EMAIL = "vedansshrajsinha@gmail.com"


@dataclass(frozen=True)
class Identity:
    user_id: str
    email: str
    role: str
    is_host: bool


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_identity(
    user_id: str,
    email: str,
    role: Optional[str] = None,
) -> Identity:

    normalized_email = normalize_email(email)

    is_host = normalized_email == normalize_email(HOST_EMAIL)

    if is_host:
        resolved_role = "owner"
    else:
        resolved_role = role or "user"

    return Identity(
        user_id=user_id,
        email=normalized_email,
        role=resolved_role,
        is_host=is_host,
    )