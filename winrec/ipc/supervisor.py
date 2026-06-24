import logging
import os
import subprocess
import sys
import threading
import time
from typing import Callable

from winrec.ipc.protocol import iter_jsonl

log = logging.getLogger(__name__)


class ProcessSupervisor:
    """Spawn and restart a child process; read JSONL from stdout."""

    def __init__(
        self,
        args: list[str],
        on_line: Callable[[dict], None],
        restart_cooldown: float = 8.0,
        name: str = "worker",
    ):
        self._args = args
        self._on_line = on_line
        self._restart_cooldown = restart_cooldown
        self._name = name
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._running = False
        self._stop = threading.Event()

    @property
    def process(self) -> subprocess.Popen | None:
        return self._proc

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop.clear()
        threading.Thread(target=self._supervise_loop, daemon=True, name=f"{self._name}-sup").start()

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._terminate()

    def send_stdin(self, obj: dict) -> bool:
        if not self._proc or not self._proc.stdin:
            return False
        import json

        try:
            self._proc.stdin.write(json.dumps(obj, ensure_ascii=True) + "\n")
            self._proc.stdin.flush()
            return True
        except OSError as e:
            log.error("%s stdin write failed: %s", self._name, e)
            return False

    def _supervise_loop(self) -> None:
        while self._running and not self._stop.is_set():
            try:
                self._spawn()
                if self._proc and self._proc.stdout:
                    self._reader = threading.Thread(
                        target=self._read_stdout, daemon=True, name=f"{self._name}-read"
                    )
                    self._reader.start()
                    code = self._proc.wait()
                    log.warning("%s exited with code %s", self._name, code)
            except Exception as e:
                log.error("%s spawn error: %s", self._name, e)
            finally:
                self._proc = None

            if not self._running or self._stop.is_set():
                break
            log.info("Restarting %s in %.0fs", self._name, self._restart_cooldown)
            self._stop.wait(self._restart_cooldown)

    def _spawn(self) -> None:
        log.info("subprocess_start name=%s cmd=%s", self._name, " ".join(self._args))
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self._proc = subprocess.Popen(
            self._args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            env=env,
        )
        threading.Thread(target=self._drain_stderr, daemon=True, name=f"{self._name}-err").start()

    def _drain_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        for line in self._proc.stderr:
            line = line.strip()
            if line:
                level = log.error if "Error" in line or "Traceback" in line else log.warning
                level("%s stderr: %s", self._name, line)

    def _read_stdout(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            for obj in iter_jsonl(self._proc.stdout):
                if self._stop.is_set():
                    break
                try:
                    self._on_line(obj)
                except Exception as e:
                    log.error("%s on_line error: %s", self._name, e)
        except Exception as e:
            log.error("%s stdout read error: %s", self._name, e)

    def _terminate(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
