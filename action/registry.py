from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ActionDefinition:
    """
    Defines one controlled ODDI backend action.

    The registry describes what an action is allowed to do.
    It does not execute the action.
    """

    action_id: str
    description: str
    permission: str
    required_parameters: tuple[str, ...] = ()
    optional_parameters: tuple[str, ...] = ()


ACTION_REGISTRY: Dict[str, ActionDefinition] = {}


def register_action(action: ActionDefinition) -> None:
    """
    Register a new action.
    """

    if not action.action_id.strip():
        raise ValueError("Action ID cannot be empty.")

    if action.action_id in ACTION_REGISTRY:
        raise ValueError(
            f"Action already registered: {action.action_id}"
        )

    ACTION_REGISTRY[action.action_id] = action


def get_action(action_id: str) -> ActionDefinition:
    """
    Return a registered action.
    """

    action = ACTION_REGISTRY.get(action_id)

    if action is None:
        raise KeyError(
            f"Unknown action: {action_id}"
        )

    return action


def has_action(action_id: str) -> bool:
    """
    Check whether an action exists.
    """

    return action_id in ACTION_REGISTRY


def list_actions() -> List[ActionDefinition]:
    """
    Return all registered actions.
    """

    return list(ACTION_REGISTRY.values())


# ============================================================
# MEMORY ACTIONS
# ============================================================

register_action(
    ActionDefinition(
        action_id="memory.remember",
        description="Save a piece of user memory.",
        permission="memory.write",
        required_parameters=("key", "value"),
    )
)

register_action(
    ActionDefinition(
        action_id="memory.recall",
        description="Read a piece of the user's memory.",
        permission="memory.read",
        required_parameters=("key",),
    )
)

register_action(
    ActionDefinition(
        action_id="memory.delete",
        description="Delete one piece of the user's memory.",
        permission="memory.write",
        required_parameters=("key",),
    )
)

register_action(
    ActionDefinition(
        action_id="memory.clear",
        description="Clear all memory belonging to the current user.",
        permission="memory.write",
    )
)


# ============================================================
# CONVERSATION ACTIONS
# ============================================================

register_action(
    ActionDefinition(
        action_id="conversation.create",
        description="Create a new conversation for the current user.",
        permission="conversation.write",
        required_parameters=("title",),
    )
)

register_action(
    ActionDefinition(
        action_id="conversation.update",
        description="Update an existing conversation.",
        permission="conversation.write",
        required_parameters=(
            "conversation_id",
            "title",
            "messages",
        ),
        optional_parameters=("expected_revision",),
    )
)

register_action(
    ActionDefinition(
        action_id="conversation.delete",
        description="Delete an existing conversation belonging to the current user.",
        permission="conversation.write",
        required_parameters=("conversation_id",),
    )
)

register_action(
    ActionDefinition(
        action_id="conversation.metadata",
        description="Update conversation metadata such as pin, archive, restore, or delete state.",
        permission="conversation.write",
        required_parameters=("conversation_id",),
        optional_parameters=(
            "pinned",
            "archived",
            "deleted",
        ),
    )
)


# ============================================================
# FILE ACTIONS
# ============================================================

register_action(
    ActionDefinition(
        action_id="file.register",
        description="Register a file belonging to the current user.",
        permission="file.write",
        required_parameters=(
            "filename",
            "mime_type",
            "size_bytes",
        ),
        optional_parameters=(
            "conversation_id",
            "storage_backend",
            "storage_key",
            "external_file_id",
            "status",
        ),
    )
)

register_action(
    ActionDefinition(
        action_id="file.update",
        description="Update metadata for a user's registered file.",
        permission="file.write",
        required_parameters=("file_id",),
        optional_parameters=(
            "filename",
            "mime_type",
            "size_bytes",
            "conversation_id",
            "storage_backend",
            "storage_key",
            "external_file_id",
            "status",
        ),
    )
)