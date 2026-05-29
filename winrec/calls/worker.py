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
from winrec.calls.queue import list_pending_jobs, process_job

log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SEC = 300
DRAIN_INTERVAL_SEC = 15


class CallsUploadWorker:
    def __init__(
        self,
        get_config: Callable[[], dict],
        on_upload_result: Callable[[str, bool, str | None], None] | None = None,
    ):
        self._get_config = get_config
        self._on_upload_result = on_upload_result
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_heartbeat = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="calls-upload-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def enqueue_now(self) -> None:
        self._drain_once()

    def _run(self) -> None:
        while not self._stop.is_set():
            cfg = self._get_config()
            if cfg.get("calls_setup_completed") and cfg.get("calls_device_token"):
                self._maybe_heartbeat(cfg)
                self._drain_once()
            if self._stop.wait(DRAIN_INTERVAL_SEC):
                break

    def _maybe_heartbeat(self, cfg: dict[str, Any]) -> None:
        now = time.time()
        if now - self._last_heartbeat < HEARTBEAT_INTERVAL_SEC:
            return
        token = cfg.get("calls_device_token") or ""
        api_base = cfg.get("calls_api_base_url") or ""
        if not token or not api_base:
            return
        try:
            heartbeat(api_base, token)
            self._last_heartbeat = now
            log.debug("heartbeat_ok")
        except Exception as exc:
            log.warning("heartbeat_failed error=%s", exc)

    def _drain_once(self) -> None:
        cfg = self._get_config()
        if not cfg.get("calls_setup_completed"):
            return
        token = cfg.get("calls_device_token") or ""
        if not token:
            return

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
            if self._on_upload_result and result in ("success", "abandoned"):
                self._on_upload_result(
                    str(job.get("job_id", "")),
                    result == "success",
                    job.get("last_error"),
                )
