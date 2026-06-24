"""Dual-stream WASAPI capture with peak metering and device hot-swap."""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import imageio_ffmpeg
import numpy as np
import pyaudiowpatch as pyaudio

from winrec.recorder.audio_mix import interleave_stereo, mix_mono, peak_level, resample, to_mono
from winrec.recorder.devices import (
    default_input_key,
    default_output_key,
    find_loopback_device,
    find_mic_device,
)

log = logging.getLogger(__name__)

CHUNK = 2048
FORMAT = pyaudio.paInt16
QUEUE_MAX = 200
MAX_FILENAME = 180
DEVICE_CHECK_INTERVAL = 1.0

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
    p: pyaudio.PyAudio
    lb_stream: Any
    mic_stream: Any | None
    lb_rate: int
    lb_ch: int
    mic_rate: int
    mic_ch: int
    mic_chunk: int
    lb_name: str
    mic_name: str | None
    output_key: tuple[int, str] | None
    input_key: tuple[int, str] | None
    lb_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=QUEUE_MAX))
    mic_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=QUEUE_MAX))
    lb_error: threading.Event = field(default_factory=threading.Event)
    mic_error: threading.Event = field(default_factory=threading.Event)


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
            os.remove(wav_path)
            self._output_path = out_path
            self._metadata["audio_file"] = out_path
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

    def _record_device(self, bundle: StreamBundle, *, switched: bool = False) -> None:
        entry = {
            "loopback": bundle.lb_name,
            "microphone": bundle.mic_name,
            "output_index": bundle.output_key[0] if bundle.output_key else None,
            "input_index": bundle.input_key[0] if bundle.input_key else None,
            "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self._metadata["devices_used"].append(entry)
        if switched:
            self._metadata["device_switches"].append(entry)
            log.info(
                "device_switched loopback=%s mic=%s",
                bundle.lb_name,
                bundle.mic_name,
            )

    def _open_streams(self, p: pyaudio.PyAudio, file_rate: int) -> StreamBundle:
        loopback = find_loopback_device(p)
        mic = find_mic_device(p)
        lb_rate = int(loopback["defaultSampleRate"])
        lb_ch = int(loopback["maxInputChannels"])
        mic_rate = int(mic["defaultSampleRate"]) if mic else file_rate
        mic_ch = int(mic["maxInputChannels"]) if mic else 1
        mic_chunk = max(1, int(CHUNK * mic_rate / lb_rate)) if mic else CHUNK

        lb_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        mic_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        lb_error = threading.Event()
        mic_error = threading.Event()

        def _lb_callback(in_data, frame_count, time_info, status):
            if status:
                lb_error.set()
            try:
                lb_queue.put_nowait(in_data)
            except queue.Full:
                pass
            return (None, pyaudio.paContinue)

        def _mic_callback(in_data, frame_count, time_info, status):
            if status:
                mic_error.set()
            try:
                mic_queue.put_nowait(in_data)
            except queue.Full:
                pass
            return (None, pyaudio.paContinue)

        lb_stream = p.open(
            format=FORMAT,
            channels=lb_ch,
            rate=lb_rate,
            input=True,
            input_device_index=loopback["index"],
            frames_per_buffer=CHUNK,
            stream_callback=_lb_callback,
        )
        mic_stream = None
        if mic:
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
        if mic_stream:
            mic_stream.start_stream()

        return StreamBundle(
            p=p,
            lb_stream=lb_stream,
            mic_stream=mic_stream,
            lb_rate=lb_rate,
            lb_ch=lb_ch,
            mic_rate=mic_rate,
            mic_ch=mic_ch,
            mic_chunk=mic_chunk,
            lb_name=str(loopback.get("name", "")),
            mic_name=str(mic.get("name", "")) if mic else None,
            output_key=default_output_key(p),
            input_key=default_input_key(p),
            lb_queue=lb_queue,
            mic_queue=mic_queue,
            lb_error=lb_error,
            mic_error=mic_error,
        )

    def _close_bundle(self, bundle: StreamBundle | None) -> None:
        if not bundle:
            return
        for stream in (bundle.lb_stream, bundle.mic_stream):
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
        try:
            bundle.p.terminate()
        except Exception:
            pass

    def _devices_changed(self, p: pyaudio.PyAudio, bundle: StreamBundle) -> bool:
        return (
            default_output_key(p) != bundle.output_key
            or default_input_key(p) != bundle.input_key
        )

    def _process_chunk(
        self,
        bundle: StreamBundle,
        lb_data: bytes,
        mic_data: bytes | None,
        file_rate: int,
        dual_track: bool,
    ) -> np.ndarray:
        lb_arr = to_mono(np.frombuffer(lb_data, dtype=np.int16), bundle.lb_ch)
        if bundle.lb_rate != file_rate:
            lb_arr = resample(lb_arr, max(1, int(len(lb_arr) * file_rate / bundle.lb_rate)))
        target_len = len(lb_arr)

        if mic_data is not None:
            mic_arr = to_mono(np.frombuffer(mic_data, dtype=np.int16), bundle.mic_ch)
            if bundle.mic_rate != file_rate:
                mic_arr = resample(
                    mic_arr,
                    max(1, int(len(mic_arr) * file_rate / bundle.mic_rate)),
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
        last_device_check = 0.0
        dual_track = bool(self._settings.get("dual_track_recording", False))
        file_rate = 48000

        try:
            p = pyaudio.PyAudio()
            bundle = self._open_streams(p, file_rate)
            file_rate = bundle.lb_rate
            self._record_device(bundle, switched=False)

            wf = wave.open(self._output_path, "wb")
            wf.setnchannels(2 if dual_track else 1)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(file_rate)

            while not self._stop_event.is_set():
                now = time.monotonic()
                if now - last_device_check >= DEVICE_CHECK_INTERVAL:
                    last_device_check = now
                    if self._devices_changed(bundle.p, bundle):
                        log.info("default audio device changed, reopening streams")
                        old_bundle = bundle
                        bundle = None
                        self._close_bundle(old_bundle)
                        p = pyaudio.PyAudio()
                        bundle = self._open_streams(p, file_rate)
                        self._record_device(bundle, switched=True)

                if bundle.lb_error.is_set() or bundle.mic_error.is_set():
                    log.warning("stream error detected, reopening streams")
                    bundle.lb_error.clear()
                    bundle.mic_error.clear()
                    old_bundle = bundle
                    bundle = None
                    self._close_bundle(old_bundle)
                    p = pyaudio.PyAudio()
                    bundle = self._open_streams(p, file_rate)
                    self._record_device(bundle, switched=True)

                try:
                    lb_data = bundle.lb_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                mic_data = None
                try:
                    mic_data = bundle.mic_queue.get(timeout=0.05)
                except queue.Empty:
                    pass

                samples = self._process_chunk(
                    bundle, lb_data, mic_data, file_rate, dual_track
                )
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
