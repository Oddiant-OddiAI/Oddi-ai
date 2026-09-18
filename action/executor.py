from __future__ import annotations

from typing import Any, Dict

from identity.identity import Identity

from action.permissions import authorize_action


class ActionExecutionError(Exception):
    """Raised when a registered action cannot be executed."""


def _validate_parameters(
    action,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate parameters against the action registry.

    Returns a cleaned copy containing only declared parameters.
    """

    if not isinstance(parameters, dict):
        raise ActionExecutionError(
            "Action parameters must be an object."
        )

    allowed = set(action.required_parameters) | set(
        action.optional_parameters
    )

    provided = set(parameters.keys())

    missing = (
        set(action.required_parameters) - provided
    )

    if missing:
        raise ActionExecutionError(
            "Missing required parameters: "
            + ", ".join(sorted(missing))
        )

    unexpected = provided - allowed

    if unexpected:
        raise ActionExecutionError(
            "Unexpected parameters: "
            + ", ".join(sorted(unexpected))
        )

    return {
        key: parameters[key]
        for key in allowed
        if key in parameters
    }


def _execute_memory_action(
    action_id: str,
    user_id: str,
    parameters: Dict[str, Any],
):
    from app.database import (
        clear_memory,
        delete_memory,
        get_memory,
        save_memory,
    )

    if action_id == "memory.remember":
        save_memory(
            user_id,
            parameters["key"],
            parameters["value"],
        )
        return {
            "ok": True,
            "action": action_id,
        }

    if action_id == "memory.recall":
        value = get_memory(
            user_id,
            parameters["key"],
        )
        return {
            "ok": True,
            "action": action_id,
            "value": value,
        }

    if action_id == "memory.delete":
        delete_memory(
            user_id,
            parameters["key"],
        )
        return {
            "ok": True,
            "action": action_id,
        }

    if action_id == "memory.clear":
        clear_memory(user_id)
        return {
            "ok": True,
            "action": action_id,
        }

    raise ActionExecutionError(
        f"Unsupported memory action: {action_id}"
    )


def _execute_conversation_action(
    action_id: str,
    user_id: str,
    parameters: Dict[str, Any],
):
    from app.database import (
        create_conversation,
        delete_conversation,
        update_conversation,
        update_conversation_metadata,
    )

    if action_id == "conversation.create":
        conversation = create_conversation(
            user_id,
            parameters["title"],
        )

        return {
            "ok": True,
            "action": action_id,
            "conversation": conversation,
        }

    if action_id == "conversation.update":
        result = update_conversation(
            parameters["conversation_id"],
            user_id,
            parameters["title"],
            parameters["messages"],
            parameters.get("expected_revision"),
        )

        return {
            "ok": bool(result.get("ok")),
            "action": action_id,
            **result,
        }

    if action_id == "conversation.delete":
        deleted = delete_conversation(
            parameters["conversation_id"],
            user_id,
        )

        return {
            "ok": bool(deleted),
            "action": action_id,
            "deleted": bool(deleted),
        }

    if action_id == "conversation.metadata":
        conversation = update_conversation_metadata(
            parameters["conversation_id"],
            user_id,
            pinned=parameters.get("pinned"),
            archived=parameters.get("archived"),
            deleted=parameters.get("deleted"),
        )

        return {
            "ok": conversation is not None,
            "action": action_id,
            "conversation": conversation,
        }

    raise ActionExecutionError(
        f"Unsupported conversation action: {action_id}"
    )


def _execute_file_action(
    action_id: str,
    user_id: str,
    parameters: Dict[str, Any],
):
    from app.database import (
        register_file,
        update_file_record,
    )

    if action_id == "file.register":
        file_id = register_file(
            user_id=user_id,
            filename=parameters["filename"],
            mime_type=parameters["mime_type"],
            size_bytes=parameters["size_bytes"],
            conversation_id=parameters.get(
                "conversation_id"
            ),
            storage_backend=parameters.get(
                "storage_backend",
                "metadata-only",
            ),
            storage_key=parameters.get("storage_key"),
            external_file_id=parameters.get(
                "external_file_id"
            ),
            status=parameters.get(
                "status",
                "received",
            ),
        )

        return {
            "ok": True,
            "action": action_id,
            "file_id": file_id,
        }

    if action_id == "file.update":
        patch = {
            key: value
            for key, value in parameters.items()
            if key != "file_id"
        }

        updated = update_file_record(
            parameters["file_id"],
            user_id,
            **patch,
        )

        return {
            "ok": bool(updated),
            "action": action_id,
            "updated": bool(updated),
        }

    raise ActionExecutionError(
        f"Unsupported file action: {action_id}"
    )


def execute_action(
    identity: Identity,
    action_id: str,
    parameters: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Authorize, validate, and execute one registered ODDI action.

    The authenticated identity is the sole source of user_id.
    """

    action = authorize_action(
        identity,
        action_id,
    )

    parameters = parameters or {}

    cleaned_parameters = _validate_parameters(
        action,
        parameters,
    )

    user_id = identity.user_id

    if action_id.startswith("memory."):
        result = _execute_memory_action(
            action_id,
            user_id,
            cleaned_parameters,
        )

    elif action_id.startswith("conversation."):
        result = _execute_conversation_action(
            action_id,
            user_id,
            cleaned_parameters,
        )

    elif action_id.startswith("file."):
        result = _execute_file_action(
            action_id,
            user_id,
            cleaned_parameters,
        )

    else:
        raise ActionExecutionError(
            f"No executor available for action: {action_id}"
        )

    return {
        "status": "success" if result.get("ok") else "failed",
        "user_id": user_id,
        **result,
    }