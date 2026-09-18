from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Dict, Optional

@dataclass
class ReliabilityState:
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    open_until: float = 0.0
    healthy: bool = True

class ReliabilityManager:
    RETRYABLE_FAILURES = ("timeout", "timed out", "connection", "network", "429", "500", "502", "503", "504", "temporarily unavailable", "service unavailable", "rate limit", "too many requests")
    RATE_LIMIT_FAILURES = ("429", "rate limit", "rate limited", "too many requests", "resource exhausted")
    TIMEOUT_FAILURES = ("timeout", "timed out", "deadline exceeded")
    QUOTA_FAILURES = ("quota exceeded", "quota_exceeded", "daily limit", "requests per day", "tokens per day")
    AUTH_FAILURES = ("401", "403", "missing required environment variable", "invalid api key", "invalid api_key", "authentication", "unauthorized", "forbidden")
    PERMANENT_FAILURES = ("401", "403", "404", "missing required environment variable", "invalid api key", "invalid api_key", "authentication", "unauthorized", "forbidden", "no adapter available", "invalid request", "malformed request", "unsupported model")

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be greater than 0")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = float(cooldown_seconds)
        self._states: Dict[str, ReliabilityState] = {}
        self._lock = Lock()

    @staticmethod
    def _key(provider: str, capacity_id: Optional[str] = None) -> str:
        provider = provider.strip().lower()
        return f"{provider}:{capacity_id.strip().lower()}" if capacity_id else provider

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _classify_failure(error: Any) -> str:
        retryable = getattr(error, "retryable", None)
        if isinstance(retryable, bool):
            return "retryable" if retryable else "permanent"
        text = str(error).lower()
        for marker in ReliabilityManager.RATE_LIMIT_FAILURES:
            if marker in text: return "rate_limited"
        for marker in ReliabilityManager.TIMEOUT_FAILURES:
            if marker in text: return "timeout"
        for marker in ReliabilityManager.QUOTA_FAILURES:
            if marker in text: return "quota_exceeded"
        for marker in ReliabilityManager.AUTH_FAILURES:
            if marker in text: return "authentication"
        for marker in ReliabilityManager.PERMANENT_FAILURES:
            if marker in text: return "permanent"
        for marker in ReliabilityManager.RETRYABLE_FAILURES:
            if marker in text: return "retryable"
        return "retryable"

    def _get_state(self, provider: str, capacity_id: Optional[str] = None) -> ReliabilityState:
        key = self._key(provider, capacity_id)
        if key not in self._states:
            self._states[key] = ReliabilityState()
        return self._states[key]

    def is_healthy(self, provider: str, capacity_id: Optional[str] = None) -> bool:
        with self._lock:
            return self.is_healthy_unlocked(self._get_state(provider, capacity_id))

    def record_success(self, provider: str, capacity_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            state = self._get_state(provider, capacity_id)
            state.consecutive_failures = 0
            state.total_successes += 1
            state.last_success_at = self._now()
            state.healthy = True
            state.open_until = 0.0
            return self.get_state_unlocked(provider, capacity_id)

    def record_failure(self, provider: str, error: Any, capacity_id: Optional[str] = None) -> Dict[str, Any]:
        failure_type = self._classify_failure(error)
        with self._lock:
            state = self._get_state(provider, capacity_id)
            state.total_failures += 1
            state.last_failure_at = self._now()
            if failure_type in {"permanent", "authentication"}:
                state.consecutive_failures = self.failure_threshold
                state.healthy = False
                state.open_until = monotonic() + self.cooldown_seconds
            else:
                state.consecutive_failures += 1
                if state.consecutive_failures >= self.failure_threshold:
                    state.healthy = False
                    state.open_until = monotonic() + self.cooldown_seconds
            result = self.get_state_unlocked(provider, capacity_id)
            result["failure_type"] = failure_type
            result["error"] = str(error)
            return result

    def get_state(self, provider: str, capacity_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            return self.get_state_unlocked(provider, capacity_id)

    def get_state_unlocked(self, provider: str, capacity_id: Optional[str] = None) -> Dict[str, Any]:
        state = self._get_state(provider, capacity_id)
        healthy = self.is_healthy_unlocked(state)
        remaining = max(0.0, state.open_until - monotonic())
        return {"provider": provider.strip().lower(), "capacity_id": capacity_id, "healthy": healthy, "consecutive_failures": state.consecutive_failures, "total_failures": state.total_failures, "total_successes": state.total_successes, "last_failure_at": state.last_failure_at.isoformat() if state.last_failure_at else None, "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None, "cooldown_remaining_seconds": round(remaining, 3)}

    @staticmethod
    def is_healthy_unlocked(state: ReliabilityState) -> bool:
        if state.healthy: return True
        if monotonic() >= state.open_until:
            state.healthy = True
            state.consecutive_failures = 0
            state.open_until = 0.0
            return True
        return False

    def reset(self, provider: str, capacity_id: Optional[str] = None) -> None:
        with self._lock:
            self._states[self._key(provider, capacity_id)] = ReliabilityState()

    def reset_all(self) -> None:
        with self._lock:
            self._states.clear()

RELIABILITY_MANAGER = ReliabilityManager()
