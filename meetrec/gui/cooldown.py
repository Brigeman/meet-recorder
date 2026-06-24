"""Prompt cooldown tracking (dismiss + post-stop)."""

import time


class CooldownManager:
    def __init__(self, dismiss_seconds: float, post_stop_seconds: float):
        self._dismiss_seconds = dismiss_seconds
        self._post_stop_seconds = post_stop_seconds
        self._dismiss_until: dict[str, float] = {}
        self._post_stop_until: dict[str, float] = {}
        self._app_dismiss_until: dict[str, float] = {}
        self._app_post_stop_until: dict[str, float] = {}

    def can_prompt(self, context_key: str, app: str | None = None) -> bool:
        now = time.time()
        if self._dismiss_until.get(context_key, 0) > now:
            return False
        if self._post_stop_until.get(context_key, 0) > now:
            return False
        if app and self._app_dismiss_until.get(app, 0) > now:
            return False
        if app and self._app_post_stop_until.get(app, 0) > now:
            return False
        return True

    def record_dismiss(self, context_key: str, app: str | None = None) -> None:
        until = time.time() + self._dismiss_seconds
        self._dismiss_until[context_key] = until
        if app:
            self._app_dismiss_until[app] = until

    def record_post_stop(self, context_key: str, app: str | None = None) -> None:
        until = time.time() + self._post_stop_seconds
        self._post_stop_until[context_key] = until
        if app:
            self._app_post_stop_until[app] = until
