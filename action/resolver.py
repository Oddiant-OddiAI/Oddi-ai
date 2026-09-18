from __future__ import annotations

from typing import Any, Dict, List, Optional

from action.registry import has_action


# Analyzer domain/intent -> registered executable action.
#
# Only actions that actually exist in ACTION_REGISTRY belong here.
ACTION_MAP = {
    "memory.remember": "memory.remember",
    "memory.recall": "memory.recall",
    "memory.delete": "memory.delete",
    "memory.clear": "memory.clear",

    "conversation.create": "conversation.create",
    "conversation.update": "conversation.update",
    "conversation.delete": "conversation.delete",
    "conversation.metadata": "conversation.metadata",

    "file.register": "file.register",
    "file.update": "file.update",
}


def resolve_action(
    action_id: str,
) -> Optional[str]:
    """
    Resolve one requested action to a registered executable action.

    Returns None when the action is not currently executable.
    """

    resolved = ACTION_MAP.get(action_id)

    if resolved is None:
        return None

    if not has_action(resolved):
        return None

    return resolved


def resolve_actions(
    action_ids: List[str],
) -> List[str]:
    """
    Resolve a list of requested action IDs.

    Unknown or currently unsupported actions are excluded.
    """

    resolved = []

    for action_id in action_ids:
        action = resolve_action(action_id)

        if action and action not in resolved:
            resolved.append(action)

    return resolved


def resolve_analyzer_result(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add controlled executable actions to an analyzer result.

    Existing analyzer fields remain unchanged.
    """

    result = dict(analysis)

    requested_actions = result.get(
        "actions",
        [],
    )

    executable_actions = resolve_actions(
        requested_actions
    )

    result["executable_actions"] = executable_actions

    result["has_executable_action"] = bool(
        executable_actions
    )

    return result