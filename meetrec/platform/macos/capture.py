"""Dual-stream macOS capture: ScreenCaptureKit system audio + microphone."""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import imageio_ffmpeg
import numpy as np

from meetrec.recorder.audio_mix import interleave_stereo, mix_mono, peak_level, resample, to_mono

log = logging.getLogger(__name__)

CHUNK = 2048
QUEUE_MAX = 200
MAX_FILENAME = 180
DEVICE_CHECK_INTERVAL = 1.0
FILE_RATE = 48000

_FFMPEG_ARGS = {
    "mp3": ["-b:a", "192k"],
    "flac": ["-c:a", "flac"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "aac": ["-c:a", "aac", "-b:a", "192k"],
    "wma": ["-c:a", "wmav2", "-b:a", "192k"],
}


@dataclass
class StreamBundle:
    helper_proc: subprocess.Popen | None
    mic_stream: Any | None
    mic_rate: int
    mic_ch: int
    mic_name: str | None
    system_available: bool
    lb_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=QUEUE_MAX))
    mic_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=QUEUE_MAX))
    helper_error: threading.Event = field(default_factory=threading.Event)
    mic_error: threading.Event = field(default_factory=threading.Event)


def _helper_path() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / "MeetRecSystemAudio",
                exe_dir.parent / "Resources" / "MeetRecSystemAudio",
                exe_dir.parent / "MacOS" / "MeetRecSystemAudio",
            ]
        )
    candidates.append(Path(__file__).resolve().parent / "helper" / "MeetRecSystemAudio")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class AudioCapture:
    def __init__(self, settings: dict):
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._file_closed = threading.Event()
        self._output_path: str | None = None
        self._metadata: dict = {}
        self._peak = 0.0
        self._peak_lock = threading.Lock()
        self._on_peak = None

    def update_settings(self, settings: dict) -> None:
        self._settings = settings

    @property
    def is_recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def current_file(self) -> str | None:
        return self._output_path

    @property
    def metadata(self) -> dict:
        return dict(self._metadata)

    @property
    def peak(self) -> float:
        with self._peak_lock:
            return self._peak

    def set_peak_callback(self, cb) -> None:
        self._on_peak = cb

    def build_output_path(self, app: str, session_id: str) -> str:
        now = datetime.now()
        base_dir = self._settings.get("recordings_dir", "")
        os.makedirs(base_dir, exist_ok=True)
        safe_app = "".join(c if c.isalnum() or c in "-_" else "_" for c in app)[:40]
        tag = f"{now.strftime('%Y-%m-%d_%H-%M')}_{safe_app}_call"
        if len(tag) > MAX_FILENAME:
            tag = tag[:MAX_FILENAME]
        return os.path.join(base_dir, f"{tag}.wav")

    def start(
        self,
        session_id: str,
        app: str,
        matched: list[str] | None = None,
        meeting_hint: str | None = None,
    ) -> str:
        if self.is_recording:
            return self._output_path or ""

        self._output_path = self.build_output_path(app, session_id)
        self._metadata = {
            "session_id": session_id,
            "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "app": app,
            "detected_by": matched or [],
            "meeting_hint": (meeting_hint or "").strip() or None,
            "user_confirmed": True,
            "audio_file": self._output_path,
            "dual_track": bool(self._settings.get("dual_track_recording", False)),
            "devices_used": [],
            "device_switches": [],
        }
        self._stop_event.clear()
        self._file_closed.clear()
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        log.info("Recording started -> %s", self._output_path)
        return self._output_path

    def stop(self) -> dict:
        if not self.is_recording:
            return self.metadata
        self._stop_event.set()
        self._file_closed.wait(timeout=10)
        self._thread.join(timeout=5)
        self._thread = None
        self._metadata["ended_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._write_metadata_json()

        fmt = self._settings.get("audio_format", "wav")
        if fmt != "wav":
            self._convert(fmt)
        log.info("Recording stopped -> %s", self._output_path)
        return self.metadata

    def _write_metadata_json(self) -> None:
        if not self._output_path:
            return
        meta_path = self._output_path.rsplit(".", 1)[0] + ".json"
        import json

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, indent=2, ensure_ascii=False)

    def _convert(self, fmt: str) -> None:
        wav_path = self._output_path
        if not wav_path:
            return
        out_path = wav_path.rsplit(".", 1)[0] + f".{fmt}"
        args = _FFMPEG_ARGS.get(fmt, [])
        try:
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run(
                [ffmpeg_bin, "-y", "-i", wav_path] + args + [out_path],
                capture_output=True,
                check=True,
            )
            self._output_path = out_path
            self._metadata["audio_file"] = out_path
            self._metadata["wav_backup"] = wav_path
            self._write_metadata_json()
        except Exception as e:
            log.error("ffmpeg error: %s", e)

    def _update_peak(self, samples: np.ndarray) -> None:
        if samples.size == 0:
            return
        peak = peak_level(samples)
        with self._peak_lock:
            self._peak = self._peak * 0.6 + peak * 0.4
        if self._on_peak:
            try:
                self._on_peak(self._peak)
            except Exception:
                pass

    def _open_streams(self) -> StreamBundle:
        import sounddevice as sd

        lb_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        mic_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        helper_error = threading.Event()
        mic_error = threading.Event()

        helper_proc = None
        system_available = False
        helper = _helper_path()
        if helper is not None:
            try:
                helper_proc = subprocess.Popen(
                    [str(helper)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                system_available = True
                threading.Thread(
                    target=self._drain_helper_stdout,
                    args=(helper_proc, lb_queue, helper_error),
                    daemon=True,
                ).start()
                threading.Thread(
                    target=self._drain_helper_stderr,
                    args=(helper_proc,),
                    daemon=True,
                ).start()
            except OSError as exc:
                log.warning("system audio helper failed to start: %s", exc)
                helper_proc = None
                system_available = False
        else:
            log.warning("MeetRecSystemAudio helper not found; recording microphone only")

        mic_info = sd.query_devices(kind="input")
        mic_rate = int(mic_info.get("default_samplerate", FILE_RATE))
        mic_ch = max(1, int(mic_info.get("max_input_channels", 1)))
        mic_name = str(mic_info.get("name", ""))

        def _mic_callback(indata, frames, time_info, status):
            if status:
                mic_error.set()
            try:
                mic_queue.put_nowait(indata.copy())
            except queue.Full:
                pass

        mic_stream = sd.InputStream(
            samplerate=mic_rate,
            channels=mic_ch,
            dtype="int16",
            blocksize=CHUNK,
            callback=_mic_callback,
        )
        mic_stream.start()

        return StreamBundle(
            helper_proc=helper_proc,
            mic_stream=mic_stream,
            mic_rate=mic_rate,
            mic_ch=mic_ch,
            mic_name=mic_name,
            system_available=system_available,
            lb_queue=lb_queue,
            mic_queue=mic_queue,
            helper_error=helper_error,
            mic_error=mic_error,
        )

    def _drain_helper_stdout(
        self,
        proc: subprocess.Popen,
        lb_queue: queue.Queue,
        helper_error: threading.Event,
    ) -> None:
        assert proc.stdout is not None
        frame_bytes = CHUNK * 2 * 2
        buf = bytearray()
        try:
            while not self._stop_event.is_set():
                data = proc.stdout.read(frame_bytes)
                if not data:
                    break
                buf.extend(data)
                while len(buf) >= frame_bytes:
                    frame = bytes(buf[:frame_bytes])
                    del buf[:frame_bytes]
                    try:
                        lb_queue.put_nowait(frame)
                    except queue.Full:
                        pass
        except Exception as exc:
            log.warning("helper stdout drain failed: %s", exc)
            helper_error.set()

    def _drain_helper_stderr(self, proc: subprocess.Popen) -> None:
        if not proc.stderr:
            return
        for line in proc.stderr:
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                log.warning("system audio helper: %s", text)

    def _close_bundle(self, bundle: StreamBundle | None) -> None:
        if not bundle:
            return
        if bundle.mic_stream is not None:
            try:
                bundle.mic_stream.stop()
                bundle.mic_stream.close()
            except Exception:
                pass
        if bundle.helper_proc is not None:
            try:
                bundle.helper_proc.terminate()
                bundle.helper_proc.wait(timeout=2)
            except Exception:
                try:
                    bundle.helper_proc.kill()
                except Exception:
                    pass

    def _record_device(self, bundle: StreamBundle) -> None:
        self._metadata["devices_used"].append(
            {
                "loopback": "ScreenCaptureKit" if bundle.system_available else None,
                "microphone": bundle.mic_name,
                "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        )

    def _process_chunk(
        self,
        bundle: StreamBundle,
        lb_data: bytes | None,
        mic_data: np.ndarray | None,
        dual_track: bool,
    ) -> np.ndarray:
        target_len = CHUNK
        if lb_data:
            lb_arr = to_mono(np.frombuffer(lb_data, dtype=np.int16), 2)
            if len(lb_arr) != target_len:
                lb_arr = resample(lb_arr, target_len)
        else:
            lb_arr = np.zeros(target_len, dtype=np.int16)

        if mic_data is not None:
            mic_arr = to_mono(mic_data.reshape(-1).astype(np.int16), bundle.mic_ch)
            if bundle.mic_rate != FILE_RATE:
                mic_arr = resample(
                    mic_arr,
                    max(1, int(len(mic_arr) * FILE_RATE / bundle.mic_rate)),
                )
            mic_arr = resample(mic_arr, target_len)
        else:
            mic_arr = np.zeros(target_len, dtype=np.int16)

        if dual_track:
            out = interleave_stereo(lb_arr, mic_arr)
        else:
            out = mix_mono(lb_arr, mic_arr)
        self._update_peak(out)
        return out

    def _record_loop(self) -> None:
        wf = None
        bundle: StreamBundle | None = None
        dual_track = bool(self._settings.get("dual_track_recording", False))

        try:
            bundle = self._open_streams()
            self._record_device(bundle)

            wf = wave.open(self._output_path, "wb")
            wf.setnchannels(2 if dual_track else 1)
            wf.setsampwidth(2)
            wf.setframerate(FILE_RATE)

            while not self._stop_event.is_set():
                lb_data = None
                if bundle.system_available:
                    try:
                        lb_data = bundle.lb_queue.get(timeout=0.1)
                    except queue.Empty:
                        pass

                mic_data = None
                try:
                    mic_data = bundle.mic_queue.get(timeout=0.05)
                except queue.Empty:
                    pass

                if lb_data is None and mic_data is None:
                    continue

                samples = self._process_chunk(bundle, lb_data, mic_data, dual_track)
                wf.writeframes(samples.tobytes())
        except Exception as e:
            log.error("Recording error: %s", e)
            raise
        finally:
            self._close_bundle(bundle)
            if wf is not None:
                try:
                    wf.close()
                except Exception:
                    pass
            self._file_closed.set()
