"""Pure audio sample helpers for capture mixing and dual-track output."""

from __future__ import annotations

import wave

import numpy as np

DEFAULT_MAX_LAG_MS = 80.0
DEFAULT_BLEED_EARLY_LAG_MS = 20.0
DEFAULT_BLEED_LATE_MIN_CORR = 0.45
DEFAULT_GATE_RATIO = 0.35  # legacy; kept for mix_gated
DEFAULT_LOCAL_MIX_GAIN = 1.0
DEFAULT_ENVELOPE_ATTACK_MS = 8.0
DEFAULT_ENVELOPE_RELEASE_MS = 160.0
DEFAULT_ENVELOPE_ECHO_RELEASE_MS = 20.0
DEFAULT_LIMITER_CEILING = 29000.0
DEFAULT_VOICE_POLISH_MS = 6.0
DEFAULT_VOICE_GATE_FLOOR = 350.0
DEFAULT_MIN_REMOTE_RMS = 500.0
DEFAULT_VOICE_OPEN_RMS = 420.0
DEFAULT_VOICE_FULL_RMS = 950.0
DEFAULT_ECHO_VOICE_MAX = 380.0
DEFAULT_REMOTE_LOUD = 900.0
DEFAULT_BLEED_ADAPT_CORR_MIN = 0.30
DEFAULT_BLEED_CLEAN_CORR_MIN = 0.20
DEFAULT_BLEED_ADAPT_GAIN_MIN = 0.10
DEFAULT_BLEED_PASSTHROUGH_GAIN = 0.10
DEFAULT_BLEED_DECAY = 0.5
DEFAULT_ECHO_MIC_REMOTE_RATIO = 0.85
DEFAULT_USER_DOMINANCE_RATIO = 1.15
# Real acoustic echo (recording on speakers) cannot be cancelled by our single-tap
# subtraction because the loopback reference and mic run on independent clocks with a
# large, drifting bulk delay (~45 ms) plus a reverberant, non-linear room path. When we
# detect that the mic is genuinely correlated with the remote (i.e. real echo is present),
# we stop trying to subtract it and instead hard-gate the mic while the remote is talking,
# so no re-captured remote can ever leak into the mono mix.
DEFAULT_ECHO_DETECT_CORR = 0.10
DEFAULT_ECHO_RATIO_MIN = 0.50
DEFAULT_ECHO_RATIO_CORR_FLOOR = 0.04
DEFAULT_SPEAKER_MUTE_REMOTE_RMS = 250.0
DEFAULT_SPEAKER_MUTE_SUB_MS = 3.0
DEFAULT_ECHO_DETECT_WINDOW_MS = 400.0
DEFAULT_GATE_WINDOW_MS = 30.0
DEFAULT_REMOTE_HANGOVER_MS = 300.0


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


def find_bleed_lag(
    lb: np.ndarray,
    mic: np.ndarray,
    *,
    max_lag_ms: float = DEFAULT_MAX_LAG_MS,
    sample_rate: int = 48000,
) -> tuple[int, float, float]:
    """Return lag (samples), correlation, and gain where mic[lag:] ~ gain * lb[:-lag]."""
    max_lag = max(0, int(max_lag_ms * sample_rate / 1000))
    early_max = max(0, int(DEFAULT_BLEED_EARLY_LAG_MS * sample_rate / 1000))
    lb_f = lb.astype(np.float64)
    mic_f = mic.astype(np.float64)
    min_len = 64

    def scan(lag_start: int, lag_end: int) -> tuple[int, float, float]:
        best_lag, best_corr, best_gain = 0, -1.0, 0.0
        for lag in range(lag_start, min(lag_end, max_lag) + 1):
            if len(lb_f) - lag < min_len:
                break
            ref = lb_f[: len(lb_f) - lag]
            sig = mic_f[lag : lag + len(ref)]
            energy = float(np.dot(ref, ref))
            if energy < 1e6:
                continue
            ref_norm = float(np.sqrt(energy))
            sig_norm = float(np.linalg.norm(sig))
            if sig_norm < 1e-3:
                continue
            corr = float(np.dot(ref, sig) / (ref_norm * sig_norm))
            gain = max(0.0, min(float(np.dot(sig, ref)) / energy, 1.35))
            if corr > best_corr + 1e-6:
                best_lag, best_corr, best_gain = lag, corr, gain
            elif corr >= best_corr - 1e-6 and lag < best_lag:
                best_lag, best_corr, best_gain = lag, corr, gain
        return best_lag, best_corr, best_gain

    early = scan(0, early_max)
    if early[1] >= DEFAULT_BLEED_ADAPT_CORR_MIN:
        return early

    late = scan(early_max + 1, max_lag)
    if (
        early[1] < DEFAULT_BLEED_ADAPT_CORR_MIN
        and late[1] >= DEFAULT_BLEED_LATE_MIN_CORR
        and late[2] >= DEFAULT_BLEED_ADAPT_GAIN_MIN
    ):
        return late
    return early


def estimate_bleed_gain(lb: np.ndarray, mic: np.ndarray, *, lag_samples: int = 0) -> float:
    """Least-squares gain with optional loopback delay alignment."""
    lag = max(0, int(lag_samples))
    lb_f = lb.astype(np.float64)
    mic_f = mic.astype(np.float64)
    if lag >= len(lb_f) - 8:
        return 0.0
    if lag > 0:
        lb_f = lb_f[: len(lb_f) - lag]
        mic_f = mic_f[lag : lag + len(lb_f)]
    energy = float(np.dot(lb_f, lb_f))
    if energy < 1e6:
        return 0.0
    gain = float(np.dot(mic_f, lb_f)) / energy
    return max(0.0, min(gain, 1.35))


class BleedCancelState:
    """Smoothed adaptive bleed gain and delay across capture chunks."""

    def __init__(
        self,
        initial: float = 0.0,
        *,
        sample_rate: int = 48000,
        max_lag_ms: float = DEFAULT_MAX_LAG_MS,
        initial_lag_ms: float = 3.0,
    ) -> None:
        self.gain = initial
        self.sample_rate = sample_rate
        self.max_lag_ms = max_lag_ms
        self.lag_samples = max(0, int(initial_lag_ms * sample_rate / 1000))
        self.last_corr = 0.0

    def update(self, lb: np.ndarray, mic: np.ndarray) -> tuple[float, int, float]:
        lag, corr, measured = find_bleed_lag(
            lb,
            mic,
            max_lag_ms=self.max_lag_ms,
            sample_rate=self.sample_rate,
        )
        self.last_corr = corr
        if corr > DEFAULT_BLEED_ADAPT_CORR_MIN and measured > DEFAULT_BLEED_ADAPT_GAIN_MIN:
            boosted = min(measured * (1.0 + 0.10 * min(corr, 1.0)), 1.35)
            self.gain = self.gain * 0.6 + boosted * 0.4
            self.lag_samples = int(round(self.lag_samples * 0.6 + lag * 0.4))
        else:
            self.gain *= DEFAULT_BLEED_DECAY
        return self.gain, self.lag_samples, corr


def cancel_speaker_bleed(mic: np.ndarray, lb: np.ndarray, *, factor: float) -> np.ndarray:
    """Remove speaker output re-captured by the mic before mixing (zero lag)."""
    return cancel_speaker_bleed_delayed(mic, lb, factor=factor, lag_samples=0)


def cancel_speaker_bleed_delayed(
    mic: np.ndarray,
    lb: np.ndarray,
    *,
    factor: float,
    lag_samples: int = 0,
) -> np.ndarray:
    """Remove delayed loopback bleed: mic[t] -= factor * lb[t - lag]."""
    if factor <= 0:
        return mic
    lag = max(0, int(lag_samples))
    if lag <= 0:
        cleaned = mic.astype(np.float32) - factor * lb.astype(np.float32)
        return np.clip(cleaned, -32768, 32767).astype(np.int16)

    n = min(len(mic), len(lb))
    if lag >= n:
        return mic
    out = mic.astype(np.float32).copy()
    aligned_len = n - lag
    out[lag:n] -= factor * lb[:aligned_len].astype(np.float32)
    return np.clip(out, -32768, 32767).astype(np.int16)


def refine_local_clean(
    mic: np.ndarray,
    lb: np.ndarray,
    *,
    gain: float,
    lag_samples: int,
    bleed_corr: float | None = None,
) -> np.ndarray:
    """Delay-aware AEC; pass mic through when echo is not confidently detected."""
    if not _aec_active(gain, bleed_corr):
        return mic.astype(np.int16) if mic.dtype != np.int16 else mic

    cleaned = cancel_speaker_bleed_delayed(mic, lb, factor=gain, lag_samples=lag_samples)
    lag = max(0, int(lag_samples))
    if lag > 4 and gain > 0.20:
        cleaned = cancel_speaker_bleed_delayed(
            cleaned.astype(np.int16),
            lb,
            factor=min(gain * 0.20, 0.35),
            lag_samples=max(0, lag // 2),
        )
    return cleaned


def _chunk_rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def _orthogonal_rms(remote: np.ndarray, voice: np.ndarray, *, lag_samples: int = 0) -> float:
    """RMS of voice after removing delay-aligned remote projection."""
    r = remote.astype(np.float64)
    v = voice.astype(np.float64)
    if _chunk_rms(r - np.mean(r)) < 200.0:
        return _chunk_rms(v)
    lag = max(0, int(lag_samples))
    if lag > 0 and lag < len(r):
        r_ref = r[: len(r) - lag]
        v_ref = v[lag:]
    else:
        r_ref, v_ref = r, v
    energy = float(np.dot(r_ref, r_ref))
    if energy < 1e6:
        return _chunk_rms(v)
    proj = max(0.0, float(np.dot(v_ref, r_ref)) / energy)
    ortho = v_ref - proj * r_ref
    return _chunk_rms(ortho)


def _aec_active(gain: float, bleed_corr: float | None) -> bool:
    if gain < DEFAULT_BLEED_PASSTHROUGH_GAIN:
        return False
    if bleed_corr is not None and bleed_corr < DEFAULT_BLEED_CLEAN_CORR_MIN:
        return False
    return True


def _gate_voice_rms(
    remote_rms: float,
    raw_rms: float,
    *,
    corr: float,
    ortho_rms: float,
    cleaned_rms: float,
    cleaned_ortho_rms: float,
    voice_open_rms: float,
) -> float:
    """Decide how much local energy may enter the mix while remote is loud."""
    del corr, cleaned_rms, voice_open_rms  # dominance rule supersedes correlation heuristics
    if remote_rms <= DEFAULT_REMOTE_LOUD:
        return raw_rms
    if raw_rms <= remote_rms * DEFAULT_USER_DOMINANCE_RATIO:
        return 0.0
    return max(cleaned_ortho_rms, ortho_rms)


def _window_mix_overlay(
    remote_chunk: np.ndarray,
    mic_chunk: np.ndarray,
    local_chunk: np.ndarray,
    *,
    sample_rate: int,
) -> tuple[float, np.ndarray]:
    """Return gate level driver and the per-window signal to blend into remote."""
    remote_rms = _chunk_rms(remote_chunk)
    raw_rms = _chunk_rms(mic_chunk)
    if remote_rms <= DEFAULT_REMOTE_LOUD:
        return raw_rms, local_chunk.astype(np.float64)

    lag, corr, gain = find_bleed_lag(
        remote_chunk.astype(np.int16),
        mic_chunk.astype(np.int16),
        max_lag_ms=DEFAULT_BLEED_EARLY_LAG_MS,
        sample_rate=sample_rate,
    )
    cleaned = cancel_speaker_bleed_delayed(
        mic_chunk.astype(np.int16),
        remote_chunk.astype(np.int16),
        factor=gain,
        lag_samples=lag,
    ).astype(np.float64)
    cleaned_rms = _chunk_rms(cleaned)
    ortho_rms = _orthogonal_rms(remote_chunk, mic_chunk, lag_samples=lag)
    cleaned_ortho_rms = _orthogonal_rms(remote_chunk, cleaned, lag_samples=lag)
    voice_rms = _gate_voice_rms(
        remote_rms,
        raw_rms,
        corr=corr,
        ortho_rms=ortho_rms,
        cleaned_rms=cleaned_rms,
        cleaned_ortho_rms=cleaned_ortho_rms,
        voice_open_rms=DEFAULT_VOICE_OPEN_RMS,
    )
    if voice_rms <= 0.0:
        return 0.0, np.zeros_like(cleaned)
    if raw_rms > remote_rms * DEFAULT_USER_DOMINANCE_RATIO:
        return voice_rms, local_chunk.astype(np.float64)
    if corr >= DEFAULT_BLEED_CLEAN_CORR_MIN:
        return voice_rms, cleaned
    return voice_rms, local_chunk.astype(np.float64)


def extract_voice_component(
    remote: np.ndarray,
    local: np.ndarray,
    *,
    lag_samples: int = 0,
    bleed_corr: float | None = None,
) -> np.ndarray:
    """Return the part of local that is not delay-aligned with remote."""
    if bleed_corr is not None and bleed_corr < DEFAULT_BLEED_ADAPT_CORR_MIN:
        return local.astype(np.int16)

    r = remote.astype(np.float64)
    l = local.astype(np.float64)
    lag = max(0, int(lag_samples))
    n = len(r)
    if n == 0:
        return local.astype(np.int16)

    voice = l.copy()
    if lag > 0 and lag < n:
        r_ref = r[: n - lag]
        l_ref = l[lag:n]
    else:
        r_ref, l_ref = r, l
        lag = 0

    energy = float(np.dot(r_ref, r_ref))
    if energy >= 1e6:
        proj = max(0.0, float(np.dot(l_ref, r_ref)) / energy)
        corrected = l_ref - proj * r_ref
        if lag > 0:
            fade = min(lag, 128)
            voice[lag:n] = corrected
            if fade > 1:
                ramp = np.linspace(0.0, 1.0, fade, dtype=np.float64)
                start = lag - fade
                voice[start:lag] = l[start:lag] * (1.0 - ramp) + corrected[:fade] * ramp
            voice[: max(0, lag - fade)] = 0.0
        else:
            voice = corrected

    return np.clip(voice, -32768, 32767).astype(np.int16)


def polish_voice_for_mix(voice: np.ndarray, *, sample_rate: int) -> np.ndarray:
    """Tame AEC grain before blending; leave clear speech untouched."""
    v = voice.astype(np.float64)
    n = v.size
    if n == 0:
        return v

    win = min(max(1, int(sample_rate * DEFAULT_VOICE_POLISH_MS / 1000)), n)
    kernel = np.ones(win, dtype=np.float64) / win
    v = np.convolve(v, kernel, mode="same")

    if _chunk_rms(v) > 650.0:
        return v

    knee = DEFAULT_VOICE_GATE_FLOOR
    abs_v = np.abs(v)
    gain = np.where(abs_v >= knee, 1.0, (abs_v / knee) ** 2)
    return v * gain


def _smooth_envelope(
    target: np.ndarray,
    *,
    attack: int,
    release: int,
    echo_release: int | None = None,
) -> np.ndarray:
    out = np.zeros(len(target), dtype=np.float64)
    level = 0.0
    attack = max(1, attack)
    release = max(1, release)
    echo_release = max(1, echo_release or release // 4)
    for i, goal in enumerate(target):
        if goal > level:
            rate = attack
        elif goal <= 0.0:
            rate = echo_release
        else:
            rate = release
        level += (goal - level) / rate
        out[i] = level
    return out


def voice_mix_envelope(
    remote: np.ndarray,
    local_voice: np.ndarray,
    *,
    sample_rate: int,
    gate_ratio: float = DEFAULT_GATE_RATIO,
    min_remote_rms: float = DEFAULT_MIN_REMOTE_RMS,
    voice_open_rms: float = DEFAULT_VOICE_OPEN_RMS,
    voice_full_rms: float = DEFAULT_VOICE_FULL_RMS,
    window_ms: float = 50.0,
    mic: np.ndarray | None = None,
) -> np.ndarray:
    """Open on absolute user speech level; ignore remote-relative floor when user is loud."""
    del gate_ratio, min_remote_rms  # absolute gate supersedes remote-relative mix gate
    n = len(remote)
    if n == 0:
        return np.zeros(0, dtype=np.float64)

    win = max(1, int(sample_rate * window_ms / 1000))
    target = np.zeros(n, dtype=np.float64)
    remote_f = remote.astype(np.float64)
    voice_f = local_voice.astype(np.float64)
    gate_f = mic.astype(np.float64) if mic is not None else voice_f
    span = max(voice_full_rms - voice_open_rms, 1.0)

    for start in range(0, n, win):
        end = min(start + win, n)
        remote_rms = _chunk_rms(remote_f[start:end])
        chunk = remote_f[start:end]
        gate_chunk = gate_f[start:end]
        raw_rms = _chunk_rms(gate_chunk)
        if remote_rms > DEFAULT_REMOTE_LOUD and mic is not None:
            lag, corr, _gain = find_bleed_lag(
                chunk.astype(np.int16),
                gate_chunk.astype(np.int16),
                max_lag_ms=DEFAULT_BLEED_EARLY_LAG_MS,
                sample_rate=sample_rate,
            )
            cleaned = cancel_speaker_bleed_delayed(
                gate_chunk.astype(np.int16),
                chunk.astype(np.int16),
                factor=_gain,
                lag_samples=lag,
            ).astype(np.float64)
            ortho_rms = _orthogonal_rms(chunk, gate_chunk, lag_samples=lag)
            voice_rms = _gate_voice_rms(
                remote_rms,
                raw_rms,
                corr=corr,
                ortho_rms=ortho_rms,
                cleaned_rms=_chunk_rms(cleaned),
                cleaned_ortho_rms=_orthogonal_rms(chunk, cleaned, lag_samples=lag),
                voice_open_rms=voice_open_rms,
            )
        else:
            voice_rms = raw_rms
        if voice_rms < voice_open_rms:
            level = 0.0
        elif remote_rms > DEFAULT_REMOTE_LOUD and voice_rms < DEFAULT_ECHO_VOICE_MAX:
            level = 0.0
        else:
            level = min(1.0, (voice_rms - voice_open_rms) / span)
        target[start:end] = level

    attack = max(1, int(sample_rate * DEFAULT_ENVELOPE_ATTACK_MS / 1000))
    release = max(1, int(sample_rate * DEFAULT_ENVELOPE_RELEASE_MS / 1000))
    echo_release = max(1, int(sample_rate * DEFAULT_ENVELOPE_ECHO_RELEASE_MS / 1000))
    return _smooth_envelope(
        target, attack=attack, release=release, echo_release=echo_release
    )


def soft_limit(samples: np.ndarray, *, ceiling: float = DEFAULT_LIMITER_CEILING) -> np.ndarray:
    """Gently compress peaks to reduce harsh clipping crackle."""
    x = samples.astype(np.float64)
    abs_x = np.abs(x)
    over = abs_x > ceiling
    if not np.any(over):
        return np.clip(x, -32768, 32767).astype(np.int16)
    compressed = ceiling + (abs_x - ceiling) * 0.25
    x = np.where(over, np.sign(x) * compressed, x)
    return np.clip(x, -32768, 32767).astype(np.int16)


def _remote_duck_envelope(
    remote: np.ndarray,
    local_voice: np.ndarray,
    *,
    sample_rate: int,
    window_ms: float = 50.0,
) -> np.ndarray:
    """Attenuate local overlay only when remote is loud and voice looks like echo residue."""
    n = len(remote)
    if n == 0:
        return np.zeros(0, dtype=np.float64)

    win = max(1, int(sample_rate * window_ms / 1000))
    echo_lag = max(0, int(sample_rate * 0.004))
    duck = np.ones(n, dtype=np.float64)
    remote_f = remote.astype(np.float64)
    voice_f = local_voice.astype(np.float64)

    for start in range(0, n, win):
        end = min(start + win, n)
        remote_rms = _chunk_rms(remote_f[start:end])
        if remote_rms > DEFAULT_REMOTE_LOUD:
            voice_rms = _orthogonal_rms(
                remote_f[start:end], voice_f[start:end], lag_samples=echo_lag
            )
        else:
            voice_rms = _chunk_rms(voice_f[start:end])
        if remote_rms > DEFAULT_REMOTE_LOUD and voice_rms < DEFAULT_ECHO_VOICE_MAX:
            ratio = remote_rms / max(voice_rms, 400.0)
            factor = 1.0 / (1.0 + max(ratio - 0.8, 0.0) ** 2)
            duck[start:end] = factor

    smooth_win = min(max(1, int(sample_rate * 20 / 1000)), n)
    if smooth_win > 1:
        kernel = np.ones(smooth_win, dtype=np.float64) / smooth_win
        duck = np.convolve(duck, kernel, mode="same")
    return duck


def _best_abs_xcorr(ref: np.ndarray, sig: np.ndarray, max_lag: int, step: int) -> float:
    """Peak absolute normalized cross-correlation of sig vs ref over lags [0, max_lag]."""
    n = len(ref)
    best = 0.0
    for lag in range(0, max_lag + 1, max(1, step)):
        if n - lag < 64:
            break
        r = ref[: n - lag]
        s = sig[lag : lag + len(r)]
        rn = float(np.linalg.norm(r))
        sn = float(np.linalg.norm(s))
        if rn < 1e-6 or sn < 1e-6:
            continue
        corr = abs(float(np.dot(r, s)) / (rn * sn))
        if corr > best:
            best = corr
    return best


def echo_presence_score(
    remote: np.ndarray,
    mic: np.ndarray,
    *,
    sample_rate: int = 48000,
) -> float:
    """How strongly the raw mic is explained by the remote (real acoustic echo present).

    Returns the 75th-percentile peak cross-correlation across loud-remote windows,
    boosted when the mic level tracks the remote even though lagged correlation is
    low (reverberant / call-app-processed speaker bleed). Near 0 for an independent
    mic (headphones); high when the mic re-captures speaker output. Used only to pick
    a mixing strategy, never to subtract — single-tap subtraction is useless on this
    echo path.
    """
    r = remote.astype(np.float64)
    m = mic.astype(np.float64)
    n = min(len(r), len(m))
    if n < 64:
        return 0.0
    r = r[:n]
    m = m[:n]
    win = min(int(sample_rate * DEFAULT_ECHO_DETECT_WINDOW_MS / 1000), max(64, n // 2))
    max_lag = min(int(sample_rate * DEFAULT_MAX_LAG_MS / 1000), max(1, n // 4))
    step = max(1, int(sample_rate * 0.001))
    xcorr_vals: list[float] = []
    ratio_vals: list[float] = []
    for start in range(0, n - win + 1, win):
        end = start + win
        remote_rms = _chunk_rms(r[start:end])
        if remote_rms < DEFAULT_REMOTE_LOUD:
            continue
        mic_rms = _chunk_rms(m[start:end])
        xcorr_vals.append(_best_abs_xcorr(r[start:end], m[start:end], max_lag, step))
        ratio_vals.append(mic_rms / remote_rms)
    if not xcorr_vals:
        return 0.0
    xcorr_p75 = float(np.percentile(np.array(xcorr_vals), 75))
    ratio_p75 = float(np.percentile(np.array(ratio_vals), 75)) if ratio_vals else 0.0
    if (
        xcorr_p75 >= DEFAULT_ECHO_RATIO_CORR_FLOOR
        and ratio_p75 >= DEFAULT_ECHO_RATIO_MIN
    ):
        return max(xcorr_p75, DEFAULT_ECHO_DETECT_CORR + 0.01)
    return xcorr_p75


def _remote_chunk_active(
    remote_chunk: np.ndarray,
    *,
    sample_rate: int,
    threshold: float = DEFAULT_SPEAKER_MUTE_REMOTE_RMS,
    sub_ms: float = DEFAULT_SPEAKER_MUTE_SUB_MS,
) -> bool:
    """True when any short slice of remote crosses the speaker-mute threshold."""
    remote_f = remote_chunk.astype(np.float64)
    if _chunk_rms(remote_f) >= threshold:
        return True
    sub = max(1, int(sample_rate * sub_ms / 1000))
    for start in range(0, len(remote_f), sub):
        end = min(start + sub, len(remote_f))
        if _chunk_rms(remote_f[start:end]) >= threshold:
            return True
    return False


def _remote_active_mask(
    remote: np.ndarray,
    *,
    sample_rate: int,
    hangover_ms: float = DEFAULT_REMOTE_HANGOVER_MS,
) -> np.ndarray:
    """Sample-level 1/0 mask marking where the remote is (or recently was) speaking."""
    n = len(remote)
    win = max(1, int(sample_rate * DEFAULT_GATE_WINDOW_MS / 1000))
    remote_f = remote.astype(np.float64)
    nwin = (n + win - 1) // win
    active = np.zeros(nwin, dtype=bool)
    for wi in range(nwin):
        start = wi * win
        end = min(start + win, n)
        if _chunk_rms(remote_f[start:end]) > DEFAULT_REMOTE_LOUD:
            active[wi] = True

    hang_win = max(0, int(round(hangover_ms / 1000.0 * sample_rate / win)))
    held = active.copy()
    hold = 0
    for wi in range(nwin):
        if active[wi]:
            hold = hang_win
        elif hold > 0:
            held[wi] = True
            hold -= 1

    mask = np.zeros(n, dtype=np.float64)
    for wi in range(nwin):
        if held[wi]:
            start = wi * win
            end = min(start + win, n)
            mask[start:end] = 1.0
    return mask


def _mix_speaker_hard_gate(
    remote: np.ndarray,
    local_voice: np.ndarray,
    mic: np.ndarray,
    *,
    sample_rate: int,
    local_gain: float,
) -> np.ndarray:
    """Speaker-mode mix: never add the mic while the remote is talking.

    Real re-captured echo is uncancellable from the recording, so the only way to keep
    the mono mix echo-free is to output remote-only during remote speech (plus a hangover
    for the reverb tail and inter-word gaps). When the remote is silent the local voice
    is added back with an absolute open-gate so the user's own turns are preserved.
    """
    n = len(remote)
    if n == 0:
        return remote.astype(np.int16)
    win = max(1, int(sample_rate * DEFAULT_GATE_WINDOW_MS / 1000))
    remote_f = remote.astype(np.float64)
    mic_f = mic.astype(np.float64)
    span = max(DEFAULT_VOICE_FULL_RMS - DEFAULT_VOICE_OPEN_RMS, 1.0)
    active = _remote_active_mask(remote, sample_rate=sample_rate)

    target = np.zeros(n, dtype=np.float64)
    mute = np.zeros(n, dtype=bool)
    nwin = (n + win - 1) // win
    for wi in range(nwin):
        start = wi * win
        end = min(start + win, n)
        chunk = remote_f[start:end]
        remote_now = (
            np.max(active[start:end]) > 0.0
            or _remote_chunk_active(chunk, sample_rate=sample_rate)
        )
        remote_soon = False
        if wi + 1 < nwin:
            nstart = (wi + 1) * win
            nend = min(nstart + win, n)
            remote_soon = _remote_chunk_active(
                remote_f[nstart:nend], sample_rate=sample_rate
            )
        if remote_now or remote_soon:
            mute[start:end] = True
            level = 0.0
        else:
            voice_rms = _chunk_rms(mic_f[start:end])
            if voice_rms < DEFAULT_VOICE_OPEN_RMS:
                level = 0.0
            else:
                level = min(1.0, (voice_rms - DEFAULT_VOICE_OPEN_RMS) / span)
        target[start:end] = level

    attack = max(1, int(sample_rate * DEFAULT_ENVELOPE_ATTACK_MS / 1000))
    release = max(1, int(sample_rate * DEFAULT_ENVELOPE_RELEASE_MS / 1000))
    echo_release = max(1, int(sample_rate * DEFAULT_ENVELOPE_ECHO_RELEASE_MS / 1000))
    env = _smooth_envelope(target, attack=attack, release=release, echo_release=echo_release)
    env = np.where(mute, 0.0, env)
    env = np.clip(env, 0.0, 1.0)
    overlay = local_voice.astype(np.float64)
    mixed = remote_f + env * local_gain * overlay
    return soft_limit(mixed)


def _mix_clean_mic(
    remote: np.ndarray,
    local_voice: np.ndarray,
    mic: np.ndarray,
    *,
    sample_rate: int,
    local_gain: float,
) -> np.ndarray:
    """Mix an already echo-free mic (native OS AEC) with the remote.

    Because the mic no longer contains re-captured remote, there is no echo to gate:
    the user's voice is added whenever they speak — including during double-talk while
    the remote is also talking — using only an absolute voice-activity gate. This is the
    path taken when capture-time VoiceProcessingIO AEC is confirmed active.
    """
    n = len(remote)
    if n == 0:
        return remote.astype(np.int16)
    win = max(1, int(sample_rate * DEFAULT_GATE_WINDOW_MS / 1000))
    mic_f = mic.astype(np.float64)
    span = max(DEFAULT_VOICE_FULL_RMS - DEFAULT_VOICE_OPEN_RMS, 1.0)

    target = np.zeros(n, dtype=np.float64)
    for start in range(0, n, win):
        end = min(start + win, n)
        voice_rms = _chunk_rms(mic_f[start:end])
        if voice_rms < DEFAULT_VOICE_OPEN_RMS:
            level = 0.0
        else:
            level = min(1.0, (voice_rms - DEFAULT_VOICE_OPEN_RMS) / span)
        target[start:end] = level

    attack = max(1, int(sample_rate * DEFAULT_ENVELOPE_ATTACK_MS / 1000))
    release = max(1, int(sample_rate * DEFAULT_ENVELOPE_RELEASE_MS / 1000))
    echo_release = max(1, int(sample_rate * DEFAULT_ENVELOPE_ECHO_RELEASE_MS / 1000))
    env = _smooth_envelope(target, attack=attack, release=release, echo_release=echo_release)
    env = np.clip(env, 0.0, 1.0)
    overlay = local_voice.astype(np.float64)
    mixed = remote.astype(np.float64) + env * local_gain * overlay
    return soft_limit(mixed)


def build_mixed_track(
    remote: np.ndarray,
    local_voice: np.ndarray,
    *,
    sample_rate: int,
    gate_ratio: float = DEFAULT_GATE_RATIO,
    local_gain: float = DEFAULT_LOCAL_MIX_GAIN,
    mic: np.ndarray | None = None,
    native_aec: bool = False,
) -> np.ndarray:
    """Remote-first mix with smoothed local voice overlay and soft limiting.

    When ``native_aec`` is True the mic was already echo-cancelled at capture time
    (macOS VoiceProcessingIO), so double-talk is preserved via ``_mix_clean_mic``.
    The echo-presence detector still runs first as a safety net: if real echo is
    somehow present (native AEC off/failed), we fall back to the hard-gate path.
    """
    if len(remote) == 0:
        return remote.astype(np.int16)

    if mic is not None and echo_presence_score(
        remote, mic, sample_rate=sample_rate
    ) >= DEFAULT_ECHO_DETECT_CORR:
        # Real speaker echo detected: it cannot be subtracted, so hard-gate the mic
        # whenever the remote is talking rather than leaking re-captured remote back in.
        # This also catches the case where native AEC was requested but failed.
        return _mix_speaker_hard_gate(
            remote, local_voice, mic, sample_rate=sample_rate, local_gain=local_gain
        )

    if mic is not None and native_aec:
        # Mic is confirmed echo-free at the source — keep the user's voice even during
        # double-talk (no hard gate needed, no risk of re-adding remote echo).
        return _mix_clean_mic(
            remote, local_voice, mic, sample_rate=sample_rate, local_gain=local_gain
        )

    n = len(remote)
    win = max(1, int(sample_rate * 50 / 1000))
    span = max(DEFAULT_VOICE_FULL_RMS - DEFAULT_VOICE_OPEN_RMS, 1.0)
    target = np.zeros(n, dtype=np.float64)
    overlay = local_voice.astype(np.float64).copy()

    if mic is not None:
        mic_f = mic.astype(np.float64)
        remote_f = remote.astype(np.float64)
        local_f = local_voice.astype(np.float64)
        for start in range(0, n, win):
            end = min(start + win, n)
            voice_rms, chunk_overlay = _window_mix_overlay(
                remote_f[start:end],
                mic_f[start:end],
                local_f[start:end],
                sample_rate=sample_rate,
            )
            overlay[start:end] = chunk_overlay
            remote_rms = _chunk_rms(remote_f[start:end])
            if voice_rms < DEFAULT_VOICE_OPEN_RMS:
                level = 0.0
            elif remote_rms > DEFAULT_REMOTE_LOUD and voice_rms < DEFAULT_ECHO_VOICE_MAX:
                level = 0.0
            else:
                level = min(1.0, (voice_rms - DEFAULT_VOICE_OPEN_RMS) / span)
            target[start:end] = level
        attack = max(1, int(sample_rate * DEFAULT_ENVELOPE_ATTACK_MS / 1000))
        release = max(1, int(sample_rate * DEFAULT_ENVELOPE_RELEASE_MS / 1000))
        echo_release = max(1, int(sample_rate * DEFAULT_ENVELOPE_ECHO_RELEASE_MS / 1000))
        env = _smooth_envelope(
            target, attack=attack, release=release, echo_release=echo_release
        )
    else:
        env = voice_mix_envelope(
            remote,
            local_voice,
            sample_rate=sample_rate,
            gate_ratio=gate_ratio,
        )

    env = np.clip(env, 0.0, 1.0) ** 0.85
    env *= _remote_duck_envelope(remote, overlay, sample_rate=sample_rate)

    mixed = remote.astype(np.float64) + env * local_gain * overlay
    return soft_limit(mixed)


def mix_speaker_tracks(
    remote: np.ndarray,
    local: np.ndarray,
    *,
    lag_samples: int = 0,
    gate_ratio: float = DEFAULT_GATE_RATIO,
    min_remote_rms: float = DEFAULT_MIN_REMOTE_RMS,
    sample_rate: int = 48000,
    bleed_corr: float | None = None,
) -> np.ndarray:
    """Chunk-level mix helper; prefer build_mixed_track for full-file export."""
    voice = extract_voice_component(
        remote, local, lag_samples=lag_samples, bleed_corr=bleed_corr
    )
    return build_mixed_track(
        remote,
        voice,
        sample_rate=sample_rate,
        gate_ratio=gate_ratio,
    )


def mix_mono(
    lb: np.ndarray,
    mic: np.ndarray,
    *,
    bleed_gain: float | None = None,
    bleed_cancel: float | None = None,
    lag_samples: int = 0,
    sample_rate: int = 48000,
    bleed_corr: float | None = None,
) -> np.ndarray:
    gain = bleed_gain if bleed_gain is not None else (bleed_cancel if bleed_cancel is not None else 0.0)
    mic_clean = refine_local_clean(
        mic, lb, gain=gain, lag_samples=lag_samples, bleed_corr=bleed_corr
    )
    voice = extract_voice_component(lb, mic_clean, lag_samples=lag_samples, bleed_corr=bleed_corr)
    return build_mixed_track(lb, voice, sample_rate=sample_rate, mic=mic)


def mix_gated(
    remote: np.ndarray,
    local: np.ndarray,
    *,
    gate_ratio: float = DEFAULT_GATE_RATIO,
    min_remote_rms: float = DEFAULT_MIN_REMOTE_RMS,
) -> np.ndarray:
    """When local is quiet relative to remote, return remote only to avoid double-counting echo."""
    remote_f = remote.astype(np.float64)
    local_f = local.astype(np.float64)
    remote_rms = float(np.sqrt(np.mean(remote_f**2))) if remote_f.size else 0.0
    local_rms = float(np.sqrt(np.mean(local_f**2))) if local_f.size else 0.0
    gate_floor = max(min_remote_rms, gate_ratio * max(remote_rms, min_remote_rms))
    if local_rms < gate_floor:
        return remote.astype(np.int16)
    return np.clip(
        remote.astype(np.int32) + local.astype(np.int32),
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


def write_mono_wav(path: str, samples: np.ndarray, rate: int) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(samples.astype(np.int16).tobytes())
