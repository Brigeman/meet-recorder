"""Recorder service — JSONL commands on stdin, events on stdout."""

import logging
import sys
import threading
import time
import uuid

from winrec.config import load_config
from winrec.ipc.protocol import iter_jsonl, write_jsonl_line
from winrec.logging_util import log_event, setup_process_logging
from winrec.recorder.capture import AudioCapture

log = logging.getLogger(__name__)

LEVEL_INTERVAL_SEC = 0.15


class RecorderService:
    def __init__(self):
        self._cfg = load_config()
        self._capture = AudioCapture(self._cfg)
        self._session_id: str | None = None
        self._level_thread: threading.Thread | None = None
        self._running = True

    def run(self) -> None:
        log_path = setup_process_logging("recorder")
        log.info("recorder_log_file=%s", log_path)
        log_event("recorder_started")
        write_jsonl_line({"type": "recorder_ready", "timestamp": time.time()})

        self._capture.set_peak_callback(self._emit_level)
        self._level_thread = threading.Thread(target=self._level_loop, daemon=True)
        self._level_thread.start()

        for cmd in iter_jsonl(sys.stdin):
            if not self._running:
                break
            self._handle_command(cmd)

    def _level_loop(self) -> None:
        while self._running:
            if self._capture.is_recording:
                write_jsonl_line(
                    {"type": "level", "peak": round(self._capture.peak, 4), "timestamp": time.time()}
                )
            time.sleep(LEVEL_INTERVAL_SEC)

    def _emit_level(self, peak: float) -> None:
        pass

    def _handle_command(self, cmd: dict) -> None:
        command = cmd.get("command")
        if command == "start_recording":
            self._start(cmd)
        elif command == "stop_recording":
            self._stop()
        elif command == "update_config":
            self._cfg = load_config()
            self._capture.update_settings(self._cfg)
        elif command == "shutdown":
            self._running = False
            if self._capture.is_recording:
                self._stop()
        else:
            write_jsonl_line(
                {"type": "error", "message": f"unknown command: {command}", "timestamp": time.time()}
            )

    def _start(self, cmd: dict) -> None:
        if self._capture.is_recording:
            write_jsonl_line(
                {
                    "type": "recording_started",
                    "session_id": self._session_id,
                    "file_path": self._capture.current_file,
                    "timestamp": time.time(),
                }
            )
            return
        self._session_id = cmd.get("session_id") or str(uuid.uuid4())
        app = cmd.get("app", "Manual")
        matched = cmd.get("matched", [])
        try:
            path = self._capture.start(self._session_id, app, matched)
            write_jsonl_line(
                {
                    "type": "recording_started",
                    "session_id": self._session_id,
                    "file_path": path,
                    "timestamp": time.time(),
                }
            )
            log_event("recording_started", session_id=self._session_id, file_path=path)
        except Exception as e:
            log.error("start failed: %s", e)
            write_jsonl_line(
                {
                    "type": "recording_failed",
                    "session_id": self._session_id,
                    "message": str(e),
                    "timestamp": time.time(),
                }
            )

    def _stop(self) -> None:
        if not self._capture.is_recording:
            return
        try:
            meta = self._capture.stop()
            write_jsonl_line(
                {
                    "type": "recording_stopped",
                    "session_id": self._session_id,
                    "file_path": meta.get("audio_file"),
                    "metadata": meta,
                    "timestamp": time.time(),
                }
            )
            log_event("recording_stopped", session_id=self._session_id)
        except Exception as e:
            write_jsonl_line(
                {
                    "type": "recording_failed",
                    "message": str(e),
                    "timestamp": time.time(),
                }
            )


def main() -> None:
    try:
        RecorderService().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
