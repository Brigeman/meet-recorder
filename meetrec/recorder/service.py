"""Recorder service — JSONL commands on stdin, events on stdout."""

import logging
import sys
import threading
import time
import uuid

from meetrec.config import load_config
from meetrec.ipc.protocol import iter_jsonl, write_jsonl_line
from meetrec.logging_util import log_event, setup_process_logging
from meetrec.recorder.capture import AudioCapture

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
        meeting_hint = cmd.get("meeting_hint")
        try:
            path = self._capture.start(self._session_id, app, matched, meeting_hint=meeting_hint)
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
        session_id = self._session_id
        export_pending = bool(
            self._capture.current_file and self._capture.metadata.get("speaker_separation")
        )
        try:
            meta = self._capture.stop(defer_export=export_pending)
        except Exception as e:
            log.error("capture stop failed: %s", e)
            meta = self._capture.metadata
            audio_file = meta.get("audio_file") or self._capture.current_file
            write_jsonl_line(
                {
                    "type": "recording_failed",
                    "session_id": session_id,
                    "message": str(e),
                    "file_path": audio_file,
                    "metadata": meta,
                    "timestamp": time.time(),
                }
            )
            return

        audio_file = meta.get("audio_file")
        try:
            write_jsonl_line(
                {
                    "type": "recording_stopped",
                    "session_id": session_id,
                    "file_path": audio_file,
                    "metadata": meta,
                    "export_pending": export_pending,
                    "timestamp": time.time(),
                }
            )
            log_event("recording_stopped", session_id=session_id)
        except Exception as e:
            log.error("recording_stopped event failed: %s", e)
            write_jsonl_line(
                {
                    "type": "recording_stopped",
                    "session_id": session_id,
                    "file_path": audio_file,
                    "metadata": {},
                    "partial": True,
                    "timestamp": time.time(),
                }
            )
            return

        if export_pending and audio_file:
            threading.Thread(
                target=self._finalize_export,
                args=(session_id,),
                daemon=True,
                name="recorder-export",
            ).start()

    def _finalize_export(self, session_id: str | None) -> None:
        try:
            self._capture.finalize_export()
            meta = self._capture.metadata
            write_jsonl_line(
                {
                    "type": "recording_exported",
                    "session_id": session_id,
                    "file_path": meta.get("audio_file"),
                    "metadata": meta,
                    "timestamp": time.time(),
                }
            )
            log_event("recording_exported", session_id=session_id)
        except Exception as e:
            log.error("background export failed: %s", e)
            write_jsonl_line(
                {
                    "type": "recording_export_failed",
                    "session_id": session_id,
                    "message": str(e),
                    "metadata": self._capture.metadata,
                    "timestamp": time.time(),
                }
            )


def main() -> None:
    from meetrec.ipc.worker_guard import start_parent_watchdog

    start_parent_watchdog()
    try:
        RecorderService().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
