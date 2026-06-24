"""Main GUI process — tray, prompt, panel, IPC."""

import ctypes
import logging
import os
import sys
import threading
import time
import uuid

import customtkinter as ctk
import pystray

from winrec import autostart
from winrec.calls.queue import enqueue_upload
from winrec.calls.worker import CallsUploadWorker
from winrec.config import APP_NAME, load_config, save_config
from winrec.gui.cooldown import CooldownManager
from winrec.gui.icons import app_ico_path, make_tray_icon
from winrec.gui.panel import FloatingPanel
from winrec.gui.prompt import MeetingPrompt
from winrec.gui.settings import SettingsWindow
from winrec.gui.setup_wizard import SetupWizard
from winrec.ipc.single_instance import acquire_single_instance, release_single_instance
from winrec.ipc.supervisor import ProcessSupervisor
from winrec.logging_util import log_event, setup_process_logging
log = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _python_exe() -> str:
    return sys.executable


def _module_cmd(module: str) -> list[str]:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        if module.endswith("detector.service"):
            return [os.path.join(base, "WinRec.Detector.exe")]
        if module.endswith("recorder.service"):
            return [os.path.join(base, "WinRec.Recorder.exe")]
    return [_python_exe(), "-m", module]


class WinRecApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("winrec.desktop.meeting")

        self.title(APP_NAME)
        self.geometry("1x1+0+0")
        self.overrideredirect(True)
        self.withdraw()

        self._cfg = load_config()
        self._state = "monitoring"
        self._tray_icon = None
        self._recording = False
        self._session_id: str | None = None
        self._pending_candidate: dict | None = None
        self._prompt_visible = False
        self._last_context: str = ""
        self._last_app: str = ""
        self._last_level_ts = 0.0

        self._cooldown = CooldownManager(
            self._cfg.get("dismiss_cooldown_seconds", 90),
            self._cfg.get("post_stop_cooldown_seconds", 120),
        )

        self._prompt = MeetingPrompt(self, self._on_record, self._on_dismiss)
        self._panel = FloatingPanel(self, self._stop_recording, self._start_manual)
        self.withdraw()

        self._recorder_sup = ProcessSupervisor(
            _module_cmd("winrec.recorder.service"),
            on_line=self._on_recorder_line,
            name="recorder",
        )
        self._detector_sup = ProcessSupervisor(
            _module_cmd("winrec.detector.service"),
            on_line=self._on_detector_line,
            name="detector",
        )

        self._recorder_sup.start()
        self._detector_sup.start()
        self._upload_worker = CallsUploadWorker(
            get_config=lambda: self._cfg,
            on_upload_result=self._on_upload_result,
        )
        self._upload_worker.start()
        self._create_tray()
        self._apply_autostart_policy()
        self._maybe_show_setup_wizard()
        log_event("app_start", recordings_dir=self._cfg.get("recordings_dir"))

    def _create_tray(self):
        try:
            menu = pystray.Menu(
                pystray.MenuItem(
                    lambda _: "Stop recording" if self._recording else "Start recording",
                    self._tray_toggle_record,
                    default=True,
                ),
                pystray.MenuItem("Open recordings folder", self._tray_open_folder),
                pystray.MenuItem("Settings", self._tray_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._tray_quit),
            )
            self._tray_icon = pystray.Icon(
                APP_NAME,
                make_tray_icon(self._state),
                APP_NAME,
                menu,
            )
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except Exception as exc:
            self._tray_icon = None
            log_event("tray_create_failed", error=str(exc))
            log.exception("tray_create_failed: %s", exc)
            self._show_without_tray()

    def _show_without_tray(self):
        try:
            self.overrideredirect(False)
            self.geometry("360x120+120+120")
            self.deiconify()
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "Не удалось создать значок в трее. Окно показано напрямую.",
                    APP_NAME,
                    0x30,
                )
            except Exception:
                pass

    def _update_tray_icon(self):
        if self._tray_icon:
            state = "recording" if self._recording else "monitoring"
            self._tray_icon.icon = make_tray_icon(state)

    def _notify_tray(self, title: str, message: str) -> None:
        if not self._tray_icon:
            return
        try:
            self._tray_icon.notify(title, message)
        except Exception:
            pass

    def _maybe_show_setup_wizard(self) -> None:
        if self._cfg.get("calls_setup_completed"):
            return
        if self._cfg.get("calls_setup_skipped"):
            return

        def _open():
            SetupWizard(self, self._cfg, self._on_setup_complete)

        self.after(500, _open)

    def _on_setup_complete(self, cfg: dict) -> None:
        self._cfg = cfg
        if cfg.get("calls_setup_completed"):
            self._notify_tray("Calls подключён", "Записи будут загружаться автоматически")
            log_event("calls_setup_completed")

    def _on_upload_result(self, job_id: str, success: bool, error: str | None) -> None:
        def _notify():
            if success:
                self._notify_tray("Загрузка завершена", "Звонок отправлен в Calls")
                log_event("upload_success", job_id=job_id)
            else:
                self._notify_tray("Ошибка загрузки", "Не удалось отправить запись в Calls")
                log_event("upload_failed", job_id=job_id, error=error)

        self.after(0, _notify)

    def _enqueue_upload(self, metadata: dict, file_path: str | None) -> None:
        audio_path = (metadata or {}).get("audio_file") or file_path
        if not audio_path or not os.path.isfile(audio_path):
            log.warning("upload_skipped reason=missing_audio")
            return
        try:
            enqueue_upload(
                audio_path=audio_path,
                metadata=metadata or {},
                project_id=self._cfg.get("calls_default_project_id"),
                api_base=self._cfg.get("calls_api_base_url", "https://calls.o2consult.ai"),
            )
            self._notify_tray("Загрузка", "Отправка записи в Calls…")
            self._upload_worker.enqueue_now()
            log_event("upload_enqueued", audio_path=audio_path)
        except Exception as exc:
            log.error("upload_enqueue_failed: %s", exc)
            self._notify_tray("Ошибка загрузки", "Не удалось поставить запись в очередь")

    def _apply_autostart_policy(self):
        if not autostart.is_supported():
            return
        desired = self._cfg.get("start_with_windows", True)
        first_run = not self._cfg.get("first_run_completed", False)

        if first_run and desired:
            if autostart.enable(autostart.current_executable_path()):
                log_event("autostart_enabled_first_run")
            self._cfg["first_run_completed"] = True
            save_config(self._cfg)
            self._notify_first_run()
            return

        if desired and not autostart.is_enabled():
            autostart.enable(autostart.current_executable_path())
            return
        if not desired and autostart.is_enabled():
            autostart.disable()

    def _notify_first_run(self):
        if not self._tray_icon:
            return
        try:
            self._tray_icon.notify(
                "Desktop Meeting Recorder работает в трее",
                "Готов записывать звонки",
            )
        except Exception:
            pass

    def _on_detector_line(self, obj: dict):
        self.after(0, self._handle_detector_event, obj)

    def _handle_detector_event(self, obj: dict):
        etype = obj.get("type")
        if etype == "call_candidate":
            ctx = obj.get("context_key", "")
            app = obj.get("app", "Unknown")
            score = obj.get("score")
            matched = obj.get("matched", [])
            if self._recording:
                log.info("prompt_skipped reason=already_recording app=%s score=%s", app, score)
                return
            if self._prompt_visible:
                log.info("prompt_skipped reason=prompt_already_visible app=%s", app)
                return
            if not self._cooldown.can_prompt(ctx, app=app):
                log.info("prompt_skipped reason=cooldown context_key=%s app=%s", ctx, app)
                return
            self._pending_candidate = obj
            self._prompt_visible = True
            log_event("prompt_shown", app=app, score=score, matched=matched, context_key=ctx)
            self._prompt.show_for_candidate(app)
        elif etype == "no_call":
            log.debug(
                "detector_no_call score=%s matched=%s",
                obj.get("score"),
                obj.get("matched"),
            )
        elif etype == "error":
            log.error("detector_error message=%s", obj.get("message"))
        elif etype == "heartbeat":
            log.info("detector_heartbeat")

    def _on_recorder_line(self, obj: dict):
        self.after(0, self._handle_recorder_event, obj)

    def _handle_recorder_event(self, obj: dict):
        etype = obj.get("type")
        if etype == "level":
            if not self._recording or not self._panel.is_visible:
                return
            now = time.time()
            if now - self._last_level_ts < 0.12:
                return
            self._last_level_ts = now
            self._panel.set_peak(float(obj.get("peak", 0)))
        elif etype == "recording_started":
            self._recording = True
            self._session_id = obj.get("session_id")
            self._panel.show_recording()
            self._update_tray_icon()
            log_event("recording_started", file_path=obj.get("file_path"))
        elif etype == "recording_stopped":
            self._recording = False
            self._panel.hide_panel()
            if self._last_context:
                self._cooldown.record_post_stop(self._last_context, app=self._last_app or None)
            self._update_tray_icon()
            metadata = obj.get("metadata") or {}
            file_path = obj.get("file_path")
            log_event("recording_stopped", file_path=file_path)
            if (
                self._cfg.get("calls_setup_completed")
                and self._cfg.get("calls_auto_upload")
                and self._cfg.get("calls_device_token")
            ):
                self._enqueue_upload(metadata, file_path)
        elif etype == "recording_failed":
            log.error("recording_failed: %s", obj.get("message"))
            self._recording = False
            self._panel.hide_panel()
            self._update_tray_icon()
            metadata = obj.get("metadata") or {}
            file_path = obj.get("file_path")
            if (
                self._cfg.get("calls_setup_completed")
                and self._cfg.get("calls_auto_upload")
                and self._cfg.get("calls_device_token")
            ):
                self._enqueue_upload(metadata, file_path)

    def _on_dismiss(self, app: str):
        self._prompt_visible = False
        if self._pending_candidate:
            ctx = self._pending_candidate.get("context_key", app)
            self._cooldown.record_dismiss(ctx, app=app)
            log_event("prompt_dismissed", app=app)
        self._pending_candidate = None

    def _on_record(self, app: str):
        self._prompt_visible = False
        cand = self._pending_candidate or {}
        self._last_context = cand.get("context_key", app)
        self._last_app = app
        meeting_hint = cand.get("context_key") or cand.get("window_title") or app
        self._pending_candidate = None
        self._start_recording(app, cand.get("matched", []), meeting_hint=meeting_hint)

    def _start_recording(self, app: str, matched: list | None = None, meeting_hint: str | None = None):
        if self._recording:
            return
        self._session_id = str(uuid.uuid4())
        self._recorder_sup.send_stdin(
            {
                "command": "start_recording",
                "session_id": self._session_id,
                "app": app,
                "matched": matched or [],
                "meeting_hint": meeting_hint,
            }
        )

    def _stop_recording(self):
        if not self._recording:
            return
        self._recorder_sup.send_stdin({"command": "stop_recording"})

    def _start_manual(self):
        self._start_recording("Manual", [])

    def _tray_toggle_record(self, icon=None, item=None):
        if self._recording:
            self.after(0, self._stop_recording)
        else:
            self.after(0, lambda: (self._panel.show_idle_ready(), self._start_manual()))

    def _tray_open_folder(self, icon=None, item=None):
        path = self._cfg.get("recordings_dir", "")
        if os.path.exists(path):
            os.startfile(path)

    def _tray_settings(self, icon=None, item=None):
        def _open():
            SettingsWindow(self, self._cfg, self._on_config_saved)

        self.after(0, _open)

    def _on_config_saved(self, cfg: dict):
        self._cfg = cfg
        self._apply_autostart_policy()
        self._cooldown = CooldownManager(
            cfg.get("dismiss_cooldown_seconds", 90),
            cfg.get("post_stop_cooldown_seconds", 120),
        )
        self._recorder_sup.send_stdin({"command": "update_config"})

    def _tray_quit(self, icon=None, item=None):
        log_event("app_exit")
        self._upload_worker.stop()
        self._detector_sup.stop()
        self._recorder_sup.send_stdin({"command": "shutdown"})
        self._recorder_sup.stop()
        if self._tray_icon:
            self._tray_icon.stop()
        release_single_instance()
        self.after(0, self.destroy)

    def run(self):
        try:
            self.mainloop()
        finally:
            self._upload_worker.stop()
            self._detector_sup.stop()
            self._recorder_sup.stop()


def run_gui() -> int:
    log_path = setup_process_logging("gui")
    logging.getLogger(__name__).info("gui_log_file=%s", log_path)
    if not acquire_single_instance():
        log_event("single_instance_duplicate")
        log.warning("Another instance is already running")
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "Desktop Meeting Recorder уже запущен.",
                    APP_NAME,
                    0x40,
                )
            except Exception:
                pass
        return 1
    log_event("single_instance_acquired")
    try:
        app = WinRecApp()
        try:
            app.iconbitmap(app_ico_path())
        except Exception:
            pass
        app.run()
    except Exception as e:
        log.exception("GUI fatal: %s", e)
        return 1
    finally:
        release_single_instance()
    return 0
