"""Prompt cooldown tracking (dismiss + post-stop)."""

import time


class CooldownManager:
    def __init__(self, dismiss_seconds: float, post_stop_seconds: float):
        self._dismiss_seconds = dismiss_seconds
        self._post_stop_seconds = post_stop_seconds
        self._dismiss_until: dict[str, float] = {}
        self._post_stop_until: dict[str, float] = {}

    def can_prompt(self, context_key: str) -> bool:
        now = time.time()
        if self._dismiss_until.get(context_key, 0) > now:
            return False
        if self._post_stop_until.get(context_key, 0) > now:
            return False
        return True

    def record_dismiss(self, context_key: str) -> None:
        self._dismiss_until[context_key] = time.time() + self._dismiss_seconds

    def record_post_stop(self, context_key: str) -> None:
        self._post_stop_until[context_key] = time.time() + self._post_stop_seconds
