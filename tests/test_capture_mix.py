"""Tests for audio sample mixing helpers."""

import numpy as np

from winrec.recorder.audio_mix import interleave_stereo, mix_mono, peak_level, resample, to_mono


def test_to_mono_stereo():
    arr = np.array([100, 200, 300, 400], dtype=np.int16)
    mono = to_mono(arr, 2)
    assert mono.tolist() == [150, 350]


def test_to_mono_mono_passthrough():
    arr = np.array([100, 200], dtype=np.int16)
    assert to_mono(arr, 1).tolist() == [100, 200]


def test_resample_same_length():
    arr = np.array([0, 1000, 2000], dtype=np.int16)
    assert resample(arr, 3).tolist() == [0, 1000, 2000]


def test_resample_longer():
    arr = np.array([0, 1000], dtype=np.int16)
    out = resample(arr, 4)
    assert len(out) == 4
    assert out[0] == 0
    assert out[-1] == 1000


def test_resample_empty():
    out = resample(np.array([], dtype=np.int16), 5)
    assert out.tolist() == [0, 0, 0, 0, 0]


def test_mix_mono_clips():
    lb = np.array([30000, -30000], dtype=np.int16)
    mic = np.array([10000, -10000], dtype=np.int16)
    mixed = mix_mono(lb, mic)
    assert mixed.tolist() == [32767, -32768]


def test_interleave_stereo():
    left = np.array([1, 2], dtype=np.int16)
    right = np.array([10, 20], dtype=np.int16)
    stereo = interleave_stereo(left, right)
    assert stereo.tolist() == [1, 10, 2, 20]


def test_peak_level():
    samples = np.array([0, 16384, -8192], dtype=np.int16)
    assert abs(peak_level(samples) - 0.5) < 0.01
