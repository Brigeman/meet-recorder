import numpy as np

from meetrec.recorder.audio_mix import (
    BleedCancelState,
    build_mixed_track,
    cancel_speaker_bleed_delayed,
    extract_voice_component,
    find_bleed_lag,
    mix_gated,
    mix_mono,
    polish_voice_for_mix,
    refine_local_clean,
    soft_limit,
)
from meetrec.recorder.speaker_tracks import CHUNK


def test_no_echo_headphones_local_passthrough_and_mixed_has_user():
    """Independent mic (headphones) must not inject phantom remote into local/mixed."""
    n = 4800
    rate = 48000
    remote = (np.sin(np.linspace(0, 50 * np.pi, n)) * 4000).astype(np.int16)
    mic = (np.random.default_rng(42).standard_normal(n) * 3500).astype(np.int16)

    state = BleedCancelState(sample_rate=rate)
    local = np.empty_like(mic, dtype=np.int16)
    for start in range(0, n, CHUNK):
        end = min(start + CHUNK, n)
        gain, lag, corr = state.update(remote[start:end], mic[start:end])
        cleaned = refine_local_clean(
            mic[start:end], remote[start:end], gain=gain, lag_samples=lag, bleed_corr=corr
        )
        local[start:end] = extract_voice_component(
            remote[start:end], cleaned, lag_samples=lag, bleed_corr=corr
        )

    diff = local.astype(np.float64) - mic.astype(np.float64)
    assert float(np.sqrt(np.mean(diff**2))) < 500.0
    phantom = float(np.dot(local.astype(np.float64), remote.astype(np.float64))) / (
        np.linalg.norm(local) * np.linalg.norm(remote) + 1e-9
    )
    assert abs(phantom) < 0.20

    mixed = build_mixed_track(remote, local, sample_rate=rate, mic=mic)
    residual = mixed.astype(np.float64) - remote.astype(np.float64)
    assert float(np.sqrt(np.mean(residual**2))) > 800.0


def test_echo_adapts_and_suppresses_bleed():
    lag = 48
    n = 4096
    lb = (np.sin(np.linspace(0, 30 * np.pi, n)) * 10000).astype(np.int16)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (lb[:-lag].astype(np.float64) * 0.75).astype(np.int16)

    state = BleedCancelState(sample_rate=48000)
    for _ in range(8):
        for start in range(0, n, CHUNK):
            end = min(start + CHUNK, n)
            gain, lag_s, corr = state.update(lb[start:end], mic[start:end])

    assert gain > 0.20
    assert corr > 0.30
    cleaned = refine_local_clean(mic, lb, gain=gain, lag_samples=lag_s, bleed_corr=corr)
    echo_rms = float(np.sqrt(np.mean(cleaned[lag:].astype(np.float64) ** 2)))
    mic_rms = float(np.sqrt(np.mean(mic[lag:].astype(np.float64) ** 2)))
    assert echo_rms < mic_rms * 0.45


def test_gate_voice_rms_mutes_echo_keeps_user_dominance():
    from meetrec.recorder.audio_mix import _gate_voice_rms, DEFAULT_VOICE_OPEN_RMS

    # speaker echo: mic picks up remote at ~80% level
    assert _gate_voice_rms(
        4000, 2800, corr=0.04, ortho_rms=2800, cleaned_rms=2800,
        cleaned_ortho_rms=2800, voice_open_rms=DEFAULT_VOICE_OPEN_RMS,
    ) == 0.0
    # mic ≈ remote while remote plays — still echo, not user
    assert _gate_voice_rms(
        2964, 3040, corr=0.80, ortho_rms=1200, cleaned_rms=1100,
        cleaned_ortho_rms=900, voice_open_rms=DEFAULT_VOICE_OPEN_RMS,
    ) == 0.0
    # user clearly louder than remote
    assert (
        _gate_voice_rms(
            3574, 7056, corr=0.17, ortho_rms=6500, cleaned_rms=6800,
            cleaned_ortho_rms=6400, voice_open_rms=DEFAULT_VOICE_OPEN_RMS,
        )
        == 6500
    )


def test_find_bleed_lag_prefers_early_acoustic_echo():
    """Speech periodicity must not steal lag to ~50 ms when echo is at ~3 ms."""
    lag = 144  # 3 ms at 48 kHz
    n = 2400
    rate = 48000
    lb = (np.sin(np.linspace(0, 80 * np.pi, n)) * 10000).astype(np.int16)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (lb[:-lag].astype(np.float64) * 0.70).astype(np.int16)

    found_lag, corr, gain = find_bleed_lag(lb, mic, sample_rate=rate)
    assert found_lag <= int(0.008 * rate)
    assert corr > 0.55
    assert gain > 0.50


def test_build_mixed_track_keeps_user_voice_with_loud_remote():
    remote = np.full(4800, 4000, dtype=np.int16)
    voice = np.full(4800, 1500, dtype=np.int16)
    out = build_mixed_track(remote, voice, sample_rate=48000)
    residual = out.astype(np.float64) - remote.astype(np.float64)
    assert float(np.sqrt(np.mean(residual**2))) > 400.0


def test_build_mixed_track_adds_voice_when_remote_silent():
    remote = np.zeros(4800, dtype=np.int16)
    voice = np.full(4800, 5000, dtype=np.int16)
    out = build_mixed_track(remote, voice, sample_rate=48000, gate_ratio=0.15)
    assert float(np.sqrt(np.mean(out.astype(np.float64) ** 2))) > 2000.0


def test_cancel_speaker_bleed_removes_duplicate():
    lb = np.array([8000, 4000, -2000], dtype=np.int16)
    mic = np.array([5600, 2800, -1400], dtype=np.int16)  # ~70% bleed
    cleaned = cancel_speaker_bleed_delayed(mic, lb, factor=0.7, lag_samples=0)
    assert np.max(np.abs(cleaned)) < 800


def test_mix_with_bleed_cancel_reduces_echo():
    lb = np.array([10000, 5000, -5000], dtype=np.int16)
    mic = np.array([7000, 3500, -3500], dtype=np.int16)

    def remote_bleed(mixed, remote):
        energy = float(np.dot(remote.astype(np.float64), remote.astype(np.float64)))
        return float(np.dot(mixed.astype(np.float64), remote.astype(np.float64))) / energy

    raw = mix_mono(lb, mic, bleed_cancel=0.0)
    fixed = mix_mono(lb, mic, bleed_cancel=0.7)
    assert remote_bleed(raw, lb) >= remote_bleed(fixed, lb) - 0.05
    assert np.max(np.abs(fixed)) <= np.max(np.abs(raw))


def test_delayed_bleed_cancellation():
    lag = 48  # 1 ms at 48 kHz
    n = 512
    lb = (np.sin(np.linspace(0, 30 * np.pi, n)) * 10000).astype(np.int16)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (lb[:-lag].astype(np.float64) * 0.8).astype(np.int16)

    found_lag, corr, gain = find_bleed_lag(lb, mic, max_lag_ms=5, sample_rate=48000)
    assert found_lag == lag
    assert corr > 0.9
    assert 0.7 <= gain <= 0.9

    cleaned = cancel_speaker_bleed_delayed(mic, lb, factor=gain, lag_samples=found_lag)
    assert float(np.sqrt(np.mean(cleaned[lag:].astype(np.float64) ** 2))) < 500


def test_mix_gated_uses_remote_when_local_quiet():
    remote = np.full(1000, 5000, dtype=np.int16)
    local = np.full(1000, 200, dtype=np.int16)
    out = mix_gated(remote, local, gate_ratio=0.25)
    assert np.array_equal(out, remote)


def test_mix_gated_sums_when_local_active():
    remote = np.full(1000, 3000, dtype=np.int16)
    local = np.full(1000, 4000, dtype=np.int16)
    out = mix_gated(remote, local, gate_ratio=0.25)
    assert np.max(np.abs(out)) > 5000


def test_build_mixed_track_stays_close_to_remote_when_local_silent():
    remote = (np.sin(np.linspace(0, 40 * np.pi, 4800)) * 8000).astype(np.int16)
    local = np.zeros(4800, dtype=np.int16)
    out = build_mixed_track(remote, local, sample_rate=48000)
    corr = float(
        np.dot(out.astype(np.float64), remote.astype(np.float64))
        / (np.linalg.norm(out) * np.linalg.norm(remote) + 1e-9)
    )
    assert corr > 0.99


def test_soft_limit_reduces_peak():
    x = np.array([0, 30000, -32000, 1000], dtype=np.int16)
    out = soft_limit(x.astype(np.float64))
    assert np.max(np.abs(out)) <= 30500


def test_echo_presence_score_detects_speaker_vs_headphones():
    from meetrec.recorder.audio_mix import echo_presence_score, DEFAULT_ECHO_DETECT_CORR

    n = 9600
    rate = 48000
    remote = (np.sin(np.linspace(0, 120 * np.pi, n)) * 8000).astype(np.int16)

    # headphones: mic is independent noise -> no correlation -> low score
    mic_hp = (np.random.default_rng(1).standard_normal(n) * 4000).astype(np.int16)
    assert echo_presence_score(remote, mic_hp, sample_rate=rate) < DEFAULT_ECHO_DETECT_CORR

    # speakers: mic re-captures remote at ~45 ms with room-ish level -> high score
    lag = int(0.045 * rate)
    mic_echo = np.zeros(n, dtype=np.int16)
    mic_echo[lag:] = (remote[:-lag].astype(np.float64) * 0.6).astype(np.int16)
    assert echo_presence_score(remote, mic_echo, sample_rate=rate) >= DEFAULT_ECHO_DETECT_CORR


def test_echo_presence_score_detects_low_corr_reverberant_bleed():
    """Teams/processed speaker bleed can track remote level without high lagged xcorr."""
    from meetrec.recorder.audio_mix import echo_presence_score, DEFAULT_ECHO_DETECT_CORR

    rate = 48000
    n = rate * 4
    remote = np.zeros(n, dtype=np.int16)
    mic = np.zeros(n, dtype=np.int16)
    win = int(rate * 0.4)
    rng = np.random.default_rng(9)
    for start in range(0, n - win, win):
        tone = (np.sin(np.linspace(0, 80 * np.pi, win)) * 8000).astype(np.int16)
        remote[start : start + win] = tone
        # short-lag diffuse bleed + unrelated grain (corr stays low, level tracks remote)
        bleed = np.zeros(win, dtype=np.float64)
        for lag_ms, gain in ((0.6, 0.35), (4.0, 0.20), (12.0, 0.12)):
            lag = max(1, int(lag_ms * rate / 1000))
            bleed[lag:] += tone[:-lag].astype(np.float64) * gain
        bleed += rng.standard_normal(win) * 900
        mic[start : start + win] = bleed.astype(np.int16)

    assert echo_presence_score(remote, mic, sample_rate=rate) >= DEFAULT_ECHO_DETECT_CORR


def test_speaker_echo_mixed_has_no_remote_leak_when_remote_only():
    """On speakers with no user speech, the mono mix must equal remote (zero echo added)."""
    n = 9600
    rate = 48000
    remote = (np.sin(np.linspace(0, 120 * np.pi, n)) * 8000).astype(np.int16)
    lag = int(0.045 * rate)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (remote[:-lag].astype(np.float64) * 0.6).astype(np.int16)  # pure echo

    # local_voice as produced by the (useless) single-tap AEC still contains echo
    local_voice = mic.copy()
    mixed = build_mixed_track(remote, local_voice, sample_rate=rate, mic=mic)

    residual = mixed.astype(np.float64) - remote.astype(np.float64)
    remote_rms = float(np.sqrt(np.mean(remote.astype(np.float64) ** 2)))
    residual_rms = float(np.sqrt(np.mean(residual**2)))
    assert residual_rms < 0.02 * remote_rms


def test_speaker_hard_gate_mutes_on_remote_onset_inside_window():
    """Remote speech starting mid-window must not leak mic bleed through the gate."""
    from meetrec.recorder.audio_mix import _mix_speaker_hard_gate

    rate = 48000
    win = max(1, int(rate * 30 / 1000))
    n = win * 3
    remote = np.zeros(n, dtype=np.int16)
    # silent first half-window, loud second half — onset inside one gate window
    remote[win // 2 :] = 8000
    lag = max(1, int(0.004 * rate))
    mic = np.zeros(n, dtype=np.int16)
    mic[win // 2 + lag :] = 5000  # echo once remote starts
    local = mic.copy()

    mixed = _mix_speaker_hard_gate(remote, local, mic, sample_rate=rate, local_gain=1.0)
    residual = mixed.astype(np.float64) - remote.astype(np.float64)
    assert float(np.sqrt(np.mean(residual[win : 2 * win] ** 2))) < 200.0


def test_speaker_mode_keeps_user_voice_when_remote_silent():
    """User's solo turns (remote quiet) must still be mixed in, even in speaker mode."""
    rate = 48000
    n = rate * 2  # 2 s so the user segment comfortably exceeds the 300 ms hangover
    remote = np.zeros(n, dtype=np.int16)
    # remote talks (with echo) in first half, silent in second half
    half = n // 2
    remote[:half] = (np.sin(np.linspace(0, 400 * np.pi, half)) * 8000).astype(np.int16)
    lag = int(0.045 * rate)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:half] = (remote[: half - lag].astype(np.float64) * 0.6).astype(np.int16)
    # user speaks loudly in second half (remote silent) -> real independent voice
    mic[half:] = (np.random.default_rng(3).standard_normal(n - half) * 5000).astype(np.int16)
    local_voice = mic.copy()

    mixed = build_mixed_track(remote, local_voice, sample_rate=rate, mic=mic)
    settle = half + int(rate * 0.4)  # skip envelope ramp + hangover after remote goes silent
    second_half_rms = float(np.sqrt(np.mean(mixed[settle:].astype(np.float64) ** 2)))
    assert second_half_rms > 2000.0  # user voice preserved when remote is silent


def test_native_aec_clean_mic_keeps_user_during_doubletalk():
    """With native AEC (clean mic), user voice is kept even while the remote is loud."""
    rate = 48000
    n = rate  # 1 s, remote loud the whole time
    remote = (np.sin(np.linspace(0, 400 * np.pi, n)) * 8000).astype(np.int16)
    # echo-free mic: independent user speech, uncorrelated with remote
    mic = (np.random.default_rng(7).standard_normal(n) * 5000).astype(np.int16)
    local_voice = mic.copy()

    mixed = build_mixed_track(
        remote, local_voice, sample_rate=rate, mic=mic, native_aec=True
    )
    residual = mixed.astype(np.float64) - remote.astype(np.float64)
    assert float(np.sqrt(np.mean(residual**2))) > 800.0  # user preserved during double-talk


def test_native_flag_but_real_echo_falls_back_to_hard_gate():
    """Safety net: if the mic still correlates with remote (native AEC failed),
    the echo detector forces the hard-gate path regardless of the native flag."""
    rate = 48000
    n = 9600
    remote = (np.sin(np.linspace(0, 120 * np.pi, n)) * 8000).astype(np.int16)
    lag = int(0.045 * rate)
    mic = np.zeros(n, dtype=np.int16)
    mic[lag:] = (remote[:-lag].astype(np.float64) * 0.6).astype(np.int16)  # real echo
    local_voice = mic.copy()

    mixed = build_mixed_track(
        remote, local_voice, sample_rate=rate, mic=mic, native_aec=True
    )
    residual = mixed.astype(np.float64) - remote.astype(np.float64)
    remote_rms = float(np.sqrt(np.mean(remote.astype(np.float64) ** 2)))
    assert float(np.sqrt(np.mean(residual**2))) < 0.02 * remote_rms  # echo gated out


def test_polish_voice_for_mix_softens_quiet_grain():
    voice = np.array([50, -80, 120, -60] * 500, dtype=np.int16)
    out = polish_voice_for_mix(voice, sample_rate=48000)
    assert float(np.sqrt(np.mean(out**2))) < float(np.sqrt(np.mean(voice.astype(np.float64) ** 2)))
