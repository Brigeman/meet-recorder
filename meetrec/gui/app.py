"""Main GUI process — tray, prompt, panel, IPC."""

import logging
import os
import queue
import sys
import threading
import time
import uuid

import customtkinter as ctk
import pystray

from meetrec import autostart
from meetrec.calls.queue import enqueue_upload, pending_count
from meetrec.calls.worker import CallsUploadWorker
from meetrec.config import APP_NAME, load_config, save_config
from meetrec.gui.cooldown import CooldownManager
from meetrec.gui.icons import app_ico_path, make_tray_icon
from meetrec.gui.panel_factory import create_meeting_prompt, create_recording_panel
from meetrec.gui.settings import SettingsWindow
from meetrec.calls.projects import apply_session_project, default_project_id
from meetrec.gui.project_picker import ProjectPickerDialog
from meetrec.gui.setup_wizard import SetupWizard
from meetrec.ipc.process_cleanup import reap_stale_workers
from meetrec.ipc.single_instance import acquire_single_instance, release_single_instance
from meetrec.ipc.supervisor import ProcessSupervisor
from meetrec.logging_util import log_event, setup_process_logging
from meetrec.platform import frozen_module_cmd, open_path, set_app_user_model_id, show_message
log = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _module_cmd(module: str) -> list[str]:
    return frozen_module_cmd(module)


class WinRecApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        set_app_user_model_id("meetrec.desktop.meeting")

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
        self._stop_pending = False
        self._session_project_id: str | None = None
        self._pending_record: dict | None = None
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()

        self._cooldown = CooldownManager(
            self._cfg.get("dismiss_cooldown_seconds", 90),
            self._cfg.get("post_stop_cooldown_seconds", 120),
        )

        self._prompt = create_meeting_prompt(self, self._on_record, self._on_dismiss)
        self._panel = create_recording_panel(self, self._stop_recording, self._start_manual)
        self.withdraw()

        self._recorder_sup = ProcessSupervisor(
            _module_cmd("meetrec.recorder.service"),
            on_line=self._on_recorder_line,
            name="recorder",
        )
        self._detector_sup = ProcessSupervisor(
            _module_cmd("meetrec.detector.service"),
            on_line=self._on_detector_line,
            name="detector",
        )

        self._recorder_sup.start()
        self._detector_sup.start()
        self._upload_worker = CallsUploadWorker(
            get_config=lambda: self._cfg,
            on_upload_result=self._on_upload_result,
            on_pending_changed=self._on_pending_changed,
        )
        self._upload_worker.start()
        self._create_tray()
        self._apply_autostart_policy()
        self._maybe_show_setup_wizard()
        self.after(50, self._pump_ui_queue)
        if sys.platform == "darwin":
            self.after(50, self._pump_cocoa_events)
        log_event("app_start", recordings_dir=self._cfg.get("recordings_dir"))

    def _pump_cocoa_events(self) -> None:
        """Keep NSStatusItem responsive while Tk owns the main loop."""
        if sys.platform != "darwin":
            return
        try:
            from AppKit import NSApp, NSDefaultRunLoopMode, NSDate, NSEventMaskAny

            app = NSApp()
            if app is not None:
                until = NSDate.dateWithTimeIntervalSinceNow_(0)
                while True:
                    event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                        NSEventMaskAny, until, NSDefaultRunLoopMode, True
                    )
                    if event is None:
                        break
                    app.sendEvent_(event)
        except Exception:
            log.debug("cocoa_event_pump_failed", exc_info=True)
        try:
            if self.winfo_exists():
                self.after(200, self._pump_cocoa_events)
        except Exception:
            pass

    def _post_to_ui(self, fn, /, *args, **kwargs) -> None:
        self._ui_queue.put((fn, args, kwargs))

    def _pump_ui_queue(self) -> None:
        while True:
            try:
                fn, args, kwargs = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args, **kwargs)
            except Exception:
                log.exception("ui_queue handler failed")
        try:
            if self.winfo_exists():
                self.after(50, self._pump_ui_queue)
        except Exception:
            pass

    def _create_tray(self):
        try:
            if sys.platform == "darwin":
                from meetrec.gui.tray_macos import MacOSTray

                self._tray_icon = MacOSTray(
                    self,
                    APP_NAME,
                    make_tray_icon(self._state, size=18),
                    on_toggle_record=self._tray_toggle_record,
                    on_open_folder=self._tray_open_folder,
                    on_settings=self._tray_settings,
                    on_quit=self._tray_quit,
                    recording=self._recording,
                )
                log_event("tray_created", platform="macos")
            else:
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
            show_message(
                "Не удалось создать значок в трее. Окно показано напрямую.",
                APP_NAME,
                0x30,
            )

    def _update_tray_icon(self):
        if not self._tray_icon:
            return
        if sys.platform == "darwin" and hasattr(self._tray_icon, "set_recording"):
            self._tray_icon.set_recording(self._recording)
            return
        state = "recording" if self._recording else "monitoring"
        icon_size = 18 if sys.platform == "darwin" else 64
        self._tray_icon.icon = make_tray_icon(state, size=icon_size)

    def _notify_tray(self, title: str, message: str) -> None:
        if not self._tray_icon:
            return
        try:
            self._tray_icon.notify(title, message)
        except Exception:
            pass

    def _maybe_show_setup_wizard(self, *, force: bool = False) -> None:
        if not force:
            if self._cfg.get("calls_setup_completed"):
                return
            if self._cfg.get("calls_setup_skipped"):
                return
            # Menu-bar app on macOS: modal Tk wizard on startup can terminate the GUI
            # process silently (no app_exit). Offer setup from tray → Settings instead.
            if sys.platform == "darwin":
                # Notification only — do not open Tk SetupWizard on startup (crashes GUI).
                log.info("calls_setup_pending use tray Settings to connect Calls")
                return

        def _open():
            try:
                SetupWizard(self, self._cfg, self._on_setup_complete)
            except Exception:
                log.exception("setup_wizard_open_failed")

        self.after(500, _open)

    def _on_setup_complete(self, cfg: dict) -> None:
        self._cfg = cfg
        if cfg.get("calls_setup_completed"):
            self._notify_tray("Calls подключён", "Записи будут загружаться автоматически")
            log_event("calls_setup_completed")
            self._upload_worker.enqueue_now()

    def _on_pending_changed(self, count: int, waiting_for_network: bool) -> None:
        self._post_to_ui(self._notify_pending_changed, count, waiting_for_network)

    def _notify_pending_changed(self, count: int, waiting_for_network: bool) -> None:
        if count <= 0:
            return
        if waiting_for_network:
            self._notify_tray(
                "Ожидает VPN/сети",
                f"{count} записей ждут подключения к Calls",
            )
        else:
            self._notify_tray("Загрузка", f"Отправка {count} записей в Calls…")

    def _on_upload_result(self, job_id: str, success: bool, error: str | None) -> None:
        self._post_to_ui(self._notify_upload_result, job_id, success, error)

    def _notify_upload_result(self, job_id: str, success: bool, error: str | None) -> None:
        if success:
            self._notify_tray("Загрузка завершена", "Звонок отправлен в Calls")
            log_event("upload_success", job_id=job_id)
        else:
            self._notify_tray(
                "Ошибка загрузки",
                "Запись сохранена локально; повторите позже или обратитесь в поддержку",
            )
            log_event("upload_failed", job_id=job_id, error=error)
        remaining = pending_count()
        if remaining > 0:
            self._notify_pending_changed(remaining, self._upload_worker.network_waiting)

    def _resolve_audio_path(self, metadata: dict, file_path: str | None) -> str | None:
        candidates: list[str] = []
        for value in (
            (metadata or {}).get("mixed_file"),
            (metadata or {}).get("audio_file"),
            (metadata or {}).get("wav_backup"),
            file_path,
        ):
            if value and value not in candidates:
                candidates.append(str(value))

        for candidate in list(candidates):
            sidecar = candidate.rsplit(".", 1)[0] + ".json"
            if sidecar not in candidates:
                candidates.append(sidecar)

        for candidate in candidates:
            if candidate.endswith(".json") and os.path.isfile(candidate):
                try:
                    import json

                    with open(candidate, encoding="utf-8") as f:
                        meta = json.load(f)
                    audio = meta.get("mixed_file") or meta.get("audio_file") or meta.get("wav_backup")
                    if audio and os.path.isfile(audio) and os.path.getsize(audio) > 0:
                        return audio
                except (OSError, json.JSONDecodeError, TypeError):
                    continue
            elif os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                return candidate
        return None

    def _should_auto_upload(self) -> bool:
        return bool(self._cfg.get("calls_auto_upload", True))

    def _maybe_enqueue_recording(self, metadata: dict, file_path: str | None) -> None:
        if not self._should_auto_upload():
            return
        self._enqueue_upload(metadata, file_path)

    def _enqueue_upload(self, metadata: dict, file_path: str | None) -> None:
        audio_path = self._resolve_audio_path(metadata or {}, file_path)
        if not audio_path:
            log.warning("upload_skipped reason=missing_audio")
            return
        try:
            project_id = self._session_project_id
            if project_id is None:
                project_id = default_project_id(self._cfg)
            enqueue_upload(
                audio_path=audio_path,
                metadata=metadata or {},
                project_id=project_id,
                api_base=self._cfg.get("calls_api_base_url", "https://calls.o2consult.ai"),
            )
            if project_id:
                self._cfg = apply_session_project(self._cfg, project_id)
                save_config(self._cfg)
            if self._cfg.get("calls_device_token"):
                self._notify_tray("Загрузка", "Отправка записи в Calls…")
            else:
                self._notify_tray(
                    "Запись сохранена",
                    "Будет отправлена в Calls после подключения",
                )
            self._upload_worker.enqueue_now()
            log_event("upload_enqueued", audio_path=audio_path, project_id=project_id)
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
        self._post_to_ui(self._handle_detector_event, obj)

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
        self._post_to_ui(self._handle_recorder_event, obj)

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
            self._stop_pending = False
            self._recording = True
            self._session_id = obj.get("session_id")
            self._panel.show_recording()
            self._update_tray_icon()
            log_event("recording_started", file_path=obj.get("file_path"))
        elif etype == "recording_stopped":
            self._stop_pending = False
            self._recording = False
            self._panel.hide_panel()
            if self._last_context:
                self._cooldown.record_post_stop(self._last_context, app=self._last_app or None)
            self._update_tray_icon()
            metadata = obj.get("metadata") or {}
            file_path = obj.get("file_path")
            log_event("recording_stopped", file_path=file_path)
            if not obj.get("export_pending"):
                self._maybe_enqueue_recording(metadata, file_path)
        elif etype == "recording_exported":
            metadata = obj.get("metadata") or {}
            file_path = obj.get("file_path")
            log_event("recording_exported", file_path=file_path)
            self._maybe_enqueue_recording(metadata, file_path)
        elif etype == "recording_export_failed":
            log.error("recording_export_failed: %s", obj.get("message"))
            metadata = obj.get("metadata") or {}
            file_path = obj.get("file_path")
            self._maybe_enqueue_recording(metadata, file_path)
        elif etype == "recording_failed":
            self._stop_pending = False
            log.error("recording_failed: %s", obj.get("message"))
            self._recording = False
            self._panel.hide_panel()
            self._update_tray_icon()
            metadata = obj.get("metadata") or {}
            file_path = obj.get("file_path")
            self._maybe_enqueue_recording(metadata, file_path)

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
        self._pending_record = {
            "app": app,
            "matched": cand.get("matched", []),
            "meeting_hint": meeting_hint,
        }
        self._show_project_picker(self._begin_pending_record)

    def _start_manual(self):
        self._pending_record = {"app": "Manual", "matched": [], "meeting_hint": "Manual"}
        self._show_project_picker(self._begin_pending_record)

    def _show_project_picker(self, on_confirm):
        if not self._cfg.get("calls_setup_completed") or not self._cfg.get("calls_device_token"):
            on_confirm(default_project_id(self._cfg))
            return

        def _confirmed(project_id: str | None):
            self._session_project_id = project_id
            on_confirm(project_id)

        def _cancelled():
            self._pending_record = None

        ProjectPickerDialog(self, self._cfg, _confirmed, on_cancel=_cancelled)

    def _begin_pending_record(self, project_id: str | None):
        pending = self._pending_record
        self._pending_record = None
        if not pending:
            return
        self._session_project_id = project_id
        self._start_recording(
            pending["app"],
            pending.get("matched"),
            meeting_hint=pending.get("meeting_hint"),
        )

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
        # Optimistic tray label — user may stop before recorder confirms.
        if sys.platform == "darwin" and self._tray_icon and hasattr(self._tray_icon, "set_recording"):
            self._tray_icon.set_recording(True)

    def _stop_recording(self):
        if self._stop_pending:
            return
        if not self._recording and not getattr(self._panel, "_recording", False):
            log_event("stop_recording_ignored", reason="not_recording")
            return
        self._stop_pending = True
        self._panel.show_stopping()
        self._recording = False
        self._update_tray_icon()
        if sys.platform == "darwin" and self._tray_icon and hasattr(self._tray_icon, "set_recording"):
            self._tray_icon.set_recording(False)
        log.info("stop_recording requested")
        sent = self._recorder_sup.send_stdin({"command": "stop_recording"})
        log_event("stop_recording_requested", sent=bool(sent))
        if not sent:
            self._stop_pending = False
            log.error("stop_recording: failed to send command to recorder")

    def _tray_toggle_record(self, icon=None, item=None):
        if self._recording:
            self._stop_recording()
        else:
            self._panel.show_idle_ready()
            self._start_manual()

    def _tray_open_folder(self, icon=None, item=None):
        path = self._cfg.get("recordings_dir", "")
        if os.path.exists(path):
            open_path(path)

    def _tray_settings(self, icon=None, item=None):
        SettingsWindow(
            self,
            self._cfg,
            self._on_config_saved,
            on_reset_pairing=self._on_reset_pairing,
            on_pairing_complete=self._on_pairing_complete,
        )

    def _on_pairing_complete(self, cfg: dict) -> None:
        self._cfg = cfg
        self._notify_tray("Calls подключён", "Записи будут загружаться автоматически")
        log_event("calls_setup_completed")
        self._upload_worker.enqueue_now()

    def _on_reset_pairing(self, *, reopen_settings: bool = False) -> None:
        self._cfg["calls_setup_completed"] = False
        self._cfg["calls_setup_skipped"] = False
        self._cfg["calls_device_token"] = ""
        self._cfg["calls_device_id"] = ""
        self._cfg["calls_default_project_id"] = None
        save_config(self._cfg)
        if sys.platform == "darwin":
            self._notify_tray(
                "Calls отключён",
                "Вставьте новый код в Настройках",
            )
            if reopen_settings:
                self.after(200, self._tray_settings)
            return
        self._maybe_show_setup_wizard(force=True)

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
        release_single_instance()
        self._post_to_ui(self.quit)

    def run(self):
        try:
            self.mainloop()
        finally:
            if self._tray_icon:
                try:
                    self._tray_icon.stop()
                except Exception:
                    pass
                self._tray_icon = None
            self._upload_worker.stop()
            self._detector_sup.stop()
            self._recorder_sup.stop()
            try:
                self.destroy()
            except Exception:
                pass


def run_gui() -> int:
    import faulthandler

    faulthandler.enable()
    log_path = setup_process_logging("gui")
    logging.getLogger(__name__).info("gui_log_file=%s", log_path)
    if not acquire_single_instance():
        log_event("single_instance_duplicate")
        log.warning("Another instance is already running")
        # Exit 0: a duplicate launch is a benign no-op, not a failure. Returning
        # non-zero makes the macOS LaunchAgent (KeepAlive: SuccessfulExit=False)
        # relaunch us forever, spamming the "already running" prompt.
        if sys.platform == "win32":
            show_message("Desktop Meeting Recorder уже запущен.", APP_NAME, 0x40)
        return 0
    log_event("single_instance_acquired")
    reap_stale_workers()
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
        log_event("app_exit")
        release_single_instance()
    return 0
