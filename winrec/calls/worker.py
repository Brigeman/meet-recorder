"""Background worker for upload queue and heartbeat."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from winrec.calls.client import (
    build_call_title,
    compute_duration_sec,
    heartbeat,
    upload_call,
)
from winrec.calls.queue import list_pending_jobs, pending_count, process_job

log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SEC = 300
DRAIN_INTERVAL_SEC = 15
MAX_BACKOFF_SEC = 300


class CallsUploadWorker:
    def __init__(
        self,
        get_config: Callable[[], dict],
        on_upload_result: Callable[[str, bool, str | None], None] | None = None,
        on_pending_changed: Callable[[int, bool], None] | None = None,
    ):
        self._get_config = get_config
        self._on_upload_result = on_upload_result
        self._on_pending_changed = on_pending_changed
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_heartbeat = 0.0
        self._drain_lock = threading.Lock()
        self._next_drain_at = 0.0
        self._backoff_sec = DRAIN_INTERVAL_SEC
        self._network_waiting = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._next_drain_at = 0.0
        self._thread = threading.Thread(target=self._run, name="calls-upload-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def enqueue_now(self) -> None:
        self._next_drain_at = 0.0
        self._drain_once()

    @property
    def network_waiting(self) -> bool:
        return self._network_waiting

    def _run(self) -> None:
        while not self._stop.is_set():
            cfg = self._get_config()
            token = cfg.get("calls_device_token") or ""
            if cfg.get("calls_setup_completed") and token:
                if self._maybe_heartbeat(cfg):
                    self._next_drain_at = 0.0
                    self._backoff_sec = DRAIN_INTERVAL_SEC

            now = time.time()
            if now >= self._next_drain_at:
                network_issue = self._drain_once()
                if network_issue:
                    self._backoff_sec = min(max(self._backoff_sec * 2, DRAIN_INTERVAL_SEC), MAX_BACKOFF_SEC)
                    self._network_waiting = True
                else:
                    self._backoff_sec = DRAIN_INTERVAL_SEC
                    self._network_waiting = False
                self._next_drain_at = time.time() + self._backoff_sec
                self._notify_pending(self._network_waiting)

            wait = max(1.0, self._next_drain_at - time.time())
            if self._stop.wait(wait):
                break

    def _notify_pending(self, waiting_for_network: bool) -> None:
        if not self._on_pending_changed:
            return
        try:
            self._on_pending_changed(pending_count(), waiting_for_network)
        except Exception:
            pass

    def _maybe_heartbeat(self, cfg: dict[str, Any]) -> bool:
        now = time.time()
        if now - self._last_heartbeat < HEARTBEAT_INTERVAL_SEC:
            return False
        token = cfg.get("calls_device_token") or ""
        api_base = cfg.get("calls_api_base_url") or ""
        if not token or not api_base:
            return False
        try:
            heartbeat(api_base, token)
            self._last_heartbeat = now
            log.debug("heartbeat_ok")
            return True
        except Exception as exc:
            log.warning("heartbeat_failed error=%s", exc)
            return False

    def _drain_once(self) -> bool:
        with self._drain_lock:
            return self._drain_once_locked()

    def _drain_once_locked(self) -> bool:
        cfg = self._get_config()
        if not cfg.get("calls_setup_completed"):
            return False
        token = cfg.get("calls_device_token") or ""
        if not token:
            return False

        network_issue = False
        for job in list_pending_jobs():
            if self._stop.is_set():
                break
            result = process_job(
                job,
                token=token,
                upload_fn=upload_call,
                build_title_fn=build_call_title,
                duration_fn=compute_duration_sec,
            )
            if result == "busy":
                continue
            if result in ("retry_network", "retry"):
                network_issue = network_issue or result == "retry_network"
            if self._on_upload_result and result in ("success", "failed"):
                self._on_upload_result(
                    str(job.get("job_id", "")),
                    result == "success",
                    job.get("last_error"),
                )
        return network_issue
