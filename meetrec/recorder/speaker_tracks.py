"""Source-based speaker separation from dual-track meeting recordings."""

from __future__ import annotations

import logging
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from meetrec.recorder.audio_mix import (
    BleedCancelState,
    DEFAULT_BLEED_CLEAN_CORR_MIN,
    build_mixed_track,
    extract_voice_component,
    find_bleed_lag,
    refine_local_clean,
    write_mono_wav,
)

log = logging.getLogger(__name__)

CHUNK = 4096


@dataclass
class SpeakerExport:
    remote_path: str
    local_path: str
    mixed_path: str
    speakers: list[dict]


def export_speaker_tracks(
    stereo_wav_path: str, *, native_aec: bool = False
) -> SpeakerExport | None:
    """Split L=remote / R=raw mic stereo WAV; AEC local track + smoothed remote-first mix.

    When ``native_aec`` is True the R channel was already echo-cancelled at capture time
    (macOS VoiceProcessingIO), so the export-time single-tap AEC is skipped entirely
    (no double processing) — the mic is passed through as the local voice, and the mono
    mix keeps the user's voice even during double-talk.
    """
    path = Path(stereo_wav_path)
    if not path.is_file():
        return None

    with wave.open(str(path), "rb") as wf:
        if wf.getnchannels() != 2:
            return None
        rate = wf.getframerate()
        width = wf.getsampwidth()
        if width != 2:
            return None
        frames = wf.readframes(wf.getnframes())

    stereo = np.frombuffer(frames, dtype=np.int16)
    remote = stereo[0::2].copy()
    mic_raw = stereo[1::2].copy()
    if len(remote) == 0:
        return None

    if native_aec:
        # Mic already clean — do not run the (useless-on-real-echo) single-tap AEC.
        local_voice = mic_raw.copy()
    else:
        state = BleedCancelState(sample_rate=rate)
        local_voice = np.empty_like(mic_raw)
        for start in range(0, len(remote), CHUNK):
            end = min(start + CHUNK, len(remote))
            lb = remote[start:end]
            mic = mic_raw[start:end]
            gain, lag, corr = state.update(lb, mic)
            chunk_lag, chunk_corr, chunk_gain = find_bleed_lag(lb, mic, sample_rate=rate)
            if chunk_corr >= DEFAULT_BLEED_CLEAN_CORR_MIN:
                gain, lag, corr = chunk_gain, chunk_lag, chunk_corr
            cleaned = refine_local_clean(mic, lb, gain=gain, lag_samples=lag, bleed_corr=corr)
            if chunk_corr >= DEFAULT_BLEED_CLEAN_CORR_MIN:
                voice = cleaned
            else:
                voice = extract_voice_component(lb, cleaned, lag_samples=lag, bleed_corr=corr)
            local_voice[start:end] = voice

    mixed = build_mixed_track(
        remote, local_voice, sample_rate=rate, mic=mic_raw, native_aec=native_aec
    )

    base = path.with_suffix("")
    remote_path = str(base.with_name(base.name + "_remote").with_suffix(".wav"))
    local_path = str(base.with_name(base.name + "_local").with_suffix(".wav"))
    mixed_path = str(base.with_name(base.name + "_mixed").with_suffix(".wav"))

    write_mono_wav(remote_path, remote, rate)
    write_mono_wav(local_path, local_voice, rate)
    write_mono_wav(mixed_path, mixed, rate)

    speakers = [
        {
            "id": "remote",
            "label": "Meeting",
            "channel": "left",
            "file": remote_path,
        },
        {
            "id": "local",
            "label": "You",
            "channel": "right",
            "file": local_path,
        },
    ]
    log.info(
        "speaker_tracks_exported remote=%s local=%s mixed=%s native_aec=%s",
        remote_path,
        local_path,
        mixed_path,
        native_aec,
    )
    return SpeakerExport(
        remote_path=remote_path,
        local_path=local_path,
        mixed_path=mixed_path,
        speakers=speakers,
    )


def promote_mixed_as_primary(wav_path: str, mixed_path: str) -> str:
    """Replace the main .wav with mono mixed; preserve raw stereo as *_stereo.wav."""
    path = Path(wav_path)
    mixed = Path(mixed_path)
    if not path.is_file() or not mixed.is_file():
        return wav_path
    stereo_backup = path.with_name(path.stem + "_stereo").with_suffix(".wav")
    if path.resolve() != mixed.resolve():
        if not stereo_backup.exists():
            shutil.move(str(path), str(stereo_backup))
        shutil.copy2(str(mixed), str(path))
    return str(stereo_backup if stereo_backup.is_file() else path)


def finalize_recording_metadata(metadata: dict, wav_path: str, *, enabled: bool) -> None:
    if not enabled or not wav_path:
        return
    native_aec = bool(metadata.get("mic_os_aec_active"))
    export = export_speaker_tracks(wav_path, native_aec=native_aec)
    if export is None:
        return
    stereo_path = promote_mixed_as_primary(wav_path, export.mixed_path)
    metadata["stereo_file"] = stereo_path
    metadata["mixed_file"] = export.mixed_path
    metadata["speaker_tracks"] = export.speakers
    metadata["audio_file"] = wav_path
    log.info(
        "primary_audio_promoted mixed=%s stereo_backup=%s primary=%s native_aec=%s",
        export.mixed_path,
        stereo_path,
        wav_path,
        native_aec,
    )
