"""Dual-stream WASAPI capture with peak metering."""

import logging
import os
import queue
import subprocess
import threading
import wave
from datetime import datetime, timezone

import imageio_ffmpeg
import numpy as np
import pyaudiowpatch as pyaudio

from winrec.recorder.devices import find_loopback_device, find_mic_device

log = logging.getLogger(__name__)

CHUNK = 2048
FORMAT = pyaudio.paInt16
QUEUE_MAX = 200
MAX_FILENAME = 180

_FFMPEG_ARGS = {
    "mp3": ["-b:a", "192k"],
    "flac": ["-c:a", "flac"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "aac": ["-c:a", "aac", "-b:a", "192k"],
    "wma": ["-c:a", "wmav2", "-b:a", "192k"],
}


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

    def start(self, session_id: str, app: str, matched: list[str] | None = None, meeting_hint: str | None = None) -> str:
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
            os.remove(wav_path)
            self._output_path = out_path
            self._metadata["audio_file"] = out_path
            self._write_metadata_json()
        except Exception as e:
            log.error("ffmpeg error: %s", e)

    def _update_peak(self, samples: np.ndarray) -> None:
        if samples.size == 0:
            return
        peak = float(np.abs(samples.astype(np.float32)).max()) / 32768.0
        with self._peak_lock:
            self._peak = self._peak * 0.6 + peak * 0.4
        if self._on_peak:
            try:
                self._on_peak(self._peak)
            except Exception:
                pass

    def _record_loop(self) -> None:
        p = pyaudio.PyAudio()
        wf = None
        lb_stream = None
        mic_stream = None
        try:
            loopback = find_loopback_device(p)
            mic = find_mic_device(p)
            lb_rate = int(loopback["defaultSampleRate"])
            lb_ch = loopback["maxInputChannels"]
            mic_rate = int(mic["defaultSampleRate"])
            mic_ch = mic["maxInputChannels"]

            lb_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
            mic_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)

            def _lb_callback(in_data, frame_count, time_info, status):
                try:
                    lb_queue.put_nowait(in_data)
                except queue.Full:
                    pass
                return (None, pyaudio.paContinue)

            def _mic_callback(in_data, frame_count, time_info, status):
                try:
                    mic_queue.put_nowait(in_data)
                except queue.Full:
                    pass
                return (None, pyaudio.paContinue)

            wf = wave.open(self._output_path, "wb")
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(lb_rate)

            mic_chunk = max(1, int(CHUNK * mic_rate / lb_rate))
            lb_stream = p.open(
                format=FORMAT,
                channels=lb_ch,
                rate=lb_rate,
                input=True,
                input_device_index=loopback["index"],
                frames_per_buffer=CHUNK,
                stream_callback=_lb_callback,
            )
            mic_stream = p.open(
                format=FORMAT,
                channels=mic_ch,
                rate=mic_rate,
                input=True,
                input_device_index=mic["index"],
                frames_per_buffer=mic_chunk,
                stream_callback=_mic_callback,
            )
            lb_stream.start_stream()
            mic_stream.start_stream()

            while not self._stop_event.is_set():
                try:
                    lb_data = lb_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    mic_data = mic_queue.get(timeout=0.05)
                except queue.Empty:
                    mic_data = None

                lb_arr = np.frombuffer(lb_data, dtype=np.int16)
                if lb_ch > 1:
                    lb_arr = lb_arr.reshape(-1, lb_ch).mean(axis=1).astype(np.int16)
                target_len = len(lb_arr)

                if mic_data is not None:
                    mic_arr = np.frombuffer(mic_data, dtype=np.int16)
                    if mic_ch > 1:
                        mic_arr = mic_arr.reshape(-1, mic_ch).mean(axis=1).astype(np.int16)
                    if len(mic_arr) != target_len:
                        mic_arr = np.interp(
                            np.linspace(0, len(mic_arr) - 1, target_len),
                            np.arange(len(mic_arr)),
                            mic_arr.astype(np.float64),
                        ).astype(np.int16)
                else:
                    mic_arr = np.zeros(target_len, dtype=np.int16)

                mixed = np.clip(
                    lb_arr.astype(np.int32) + mic_arr.astype(np.int32),
                    -32768,
                    32767,
                ).astype(np.int16)
                self._update_peak(mixed)
                wf.writeframes(mixed.tobytes())
        except Exception as e:
            log.error("Recording error: %s", e)
            raise
        finally:
            for stream in (lb_stream, mic_stream):
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
            if wf is not None:
                try:
                    wf.close()
                except Exception:
                    pass
            self._file_closed.set()
            p.terminate()
