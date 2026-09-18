from identity.identity import Identity
from identity.permissions import has_permission

from action.registry import ActionDefinition, get_action


class ActionPermissionError(PermissionError):
    """Raised when an identity is not allowed to perform an action."""


def check_action_permission(
    identity: Identity,
    action: ActionDefinition,
) -> bool:
    """
    Check whether the identity has permission
    required by the action.
    """

    return has_permission(
        identity,
        action.permission,
    )


def authorize_action(
    identity: Identity,
    action_id: str,
) -> ActionDefinition:
    """
    Resolve an action and verify that the identity
    is allowed to execute it.

    Returns the ActionDefinition when authorized.
    Raises:
        KeyError: if the action does not exist.
        ActionPermissionError: if permission is denied.
    """

    action = get_action(action_id)

    if not check_action_permission(identity, action):
        raise ActionPermissionError(
            f"Permission denied for action: {action_id}"
        )

    return action