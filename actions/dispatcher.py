from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from providers.adapters import execute_route


class ActionDispatcher:
    """
    Phase 8 — Action Layer.

    Responsibility:
        Request Analyzer
            ↓
        Routing Engine
            ↓
        Action Dispatcher
            ↓
        Provider execution / platform action

    This layer does NOT decide which provider/model to use.
    Routing Engine remains responsible for routing.
    """

    def __init__(
        self,
        action_handlers: Optional[Dict[str, Callable[..., Dict[str, Any]]]] = None,
    ):
        self._handlers: Dict[str, Callable[..., Dict[str, Any]]] = (
            action_handlers or {}
        )

    def register(
        self,
        action: str,
        handler: Callable[..., Dict[str, Any]],
    ) -> None:
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string")

        if not callable(handler):
            raise TypeError("handler must be callable")

        self._handlers[action.strip().lower()] = handler

    def dispatch(
        self,
        request: Dict[str, Any],
        route: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(request, dict):
            return self._error(
                "invalid_request",
                "request must be a dictionary",
            )

        action = self._resolve_action(request)

        # Standard AI response action.
        if action in {
            "answer",
            "question_answering",
            "chat",
            "general",
        }:
            return self._execute_ai_route(
                request=request,
                route=route,
                prompt=prompt,
                action=action,
            )

        # Registered application/platform actions.
        handler = self._handlers.get(action)

        if handler is not None:
            try:
                result = handler(
                    request=request,
                    route=route,
                    prompt=prompt,
                )

                if not isinstance(result, dict):
                    return self._error(
                        "invalid_action_result",
                        f"Action handler '{action}' must return a dictionary",
                        action=action,
                    )

                return {
                    "status": "success",
                    "success": True,
                    "action": action,
                    "result": result,
                }

            except Exception as exc:
                return self._error(
                    "action_execution_failed",
                    str(exc),
                    action=action,
                )

        # Action recognized but not yet connected to an application handler.
        return {
            "status": "unsupported",
            "success": False,
            "action": action,
            "result": None,
            "reason": "action_handler_not_registered",
        }

    def _execute_ai_route(
        self,
        request: Dict[str, Any],
        route: Optional[Dict[str, Any]],
        prompt: Optional[str],
        action: str,
    ) -> Dict[str, Any]:

        if route is None:
            return self._error(
                "route_required",
                "A routed candidate is required before AI execution",
                action=action,
            )

        execution_prompt = prompt

        if execution_prompt is None:
            execution_prompt = request.get("prompt")

        if execution_prompt is None:
            execution_prompt = request.get("message")

        if not isinstance(execution_prompt, str) or not execution_prompt.strip():
            return self._error(
                "prompt_required",
                "A non-empty prompt is required for AI execution",
                action=action,
            )

        try:
            result = execute_route(
                route=route,
                prompt=execution_prompt,
            )

        except Exception as exc:
            return self._error(
                "execution_failed",
                str(exc),
                action=action,
            )

        if not isinstance(result, dict):
            return self._error(
                "invalid_execution_result",
                "Provider execution returned an invalid result",
                action=action,
            )

        # Preserve adapter response while adding Action Layer identity.
        response = dict(result)
        response["action"] = action

        return response

    @staticmethod
    def _resolve_action(request: Dict[str, Any]) -> str:
        """
        Resolve the action from the analyzer output.

        Priority:
            explicit action
            actions list
            intent
            default answer
        """

        action = request.get("action")

        if isinstance(action, str) and action.strip():
            return action.strip().lower()

        actions = request.get("actions")

        if isinstance(actions, (list, tuple)):
            for candidate in actions:
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip().lower()

        intent = request.get("intent")

        if isinstance(intent, str) and intent.strip():
            return intent.strip().lower()

        return "answer"

    @staticmethod
    def _error(
        reason: str,
        message: str,
        action: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "status": "failed",
            "success": False,
            "action": action,
            "result": None,
            "reason": reason,
            "error": message,
        }


_DEFAULT_DISPATCHER = ActionDispatcher()


def dispatch_action(
    request: Dict[str, Any],
    route: Optional[Dict[str, Any]] = None,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience API for the rest of ODDI-AI.
    """
    return _DEFAULT_DISPATCHER.dispatch(
        request=request,
        route=route,
        prompt=prompt,
    )


def register_action(
    action: str,
    handler: Callable[..., Dict[str, Any]],
) -> None:
    """
    Register an application/platform action globally.
    """
    _DEFAULT_DISPATCHER.register(action, handler)