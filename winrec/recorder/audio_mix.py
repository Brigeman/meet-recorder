"""Pure audio sample helpers for capture mixing and dual-track output."""

from __future__ import annotations

import numpy as np


def to_mono(arr: np.ndarray, channels: int) -> np.ndarray:
    if channels <= 1:
        return arr
    return arr.reshape(-1, channels).mean(axis=1).astype(np.int16)


def resample(arr: np.ndarray, target_len: int) -> np.ndarray:
    if target_len <= 0:
        return np.zeros(0, dtype=np.int16)
    if len(arr) == target_len:
        return arr
    if len(arr) == 0:
        return np.zeros(target_len, dtype=np.int16)
    return np.interp(
        np.linspace(0, len(arr) - 1, target_len),
        np.arange(len(arr)),
        arr.astype(np.float64),
    ).astype(np.int16)


def mix_mono(lb: np.ndarray, mic: np.ndarray) -> np.ndarray:
    return np.clip(
        lb.astype(np.int32) + mic.astype(np.int32),
        -32768,
        32767,
    ).astype(np.int16)


def interleave_stereo(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    n = min(len(left), len(right))
    if n == 0:
        return np.zeros(0, dtype=np.int16)
    stereo = np.empty(n * 2, dtype=np.int16)
    stereo[0::2] = left[:n]
    stereo[1::2] = right[:n]
    return stereo


def peak_level(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.abs(samples.astype(np.float32)).max()) / 32768.0
