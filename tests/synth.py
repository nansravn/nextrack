"""Synthetic audio for tests: small, general helpers. Everything is float32 and mono unless
stated; `pan` makes stereo `(n, 2)`. No file I/O and no real audio."""
import numpy as np

SR = 22050


def _n(ms: float, sr: int) -> int:
    return int(round(ms * sr / 1000))


def silence(ms: float, sr: int = SR) -> np.ndarray:
    """`ms` of digital silence."""
    return np.zeros(_n(ms, sr), dtype=np.float32)


def tone(freq: float, ms: float, sr: int = SR, amp: float = 0.5) -> np.ndarray:
    """A sine of `freq` Hz and peak amplitude `amp` (0.5 is about -6 dBFS)."""
    t = np.arange(_n(ms, sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def noise_burst(ms: float, sr: int = SR, amp: float = 0.5, seed: int = 0,
                low_hz: float | None = None, high_hz: float | None = None) -> np.ndarray:
    """White noise of RMS `amp`, deterministic for a `seed`, optionally band-limited to
    [`low_hz`, `high_hz`] by an FFT mask (the RMS is rescaled to `amp`)."""
    x = np.random.default_rng(seed).standard_normal(_n(ms, sr))
    if low_hz is not None or high_hz is not None:
        spec = np.fft.rfft(x)
        f = np.fft.rfftfreq(len(x), 1 / sr)
        keep = (f >= (low_hz or 0)) & (f <= (high_hz or sr / 2))
        x = np.fft.irfft(spec * keep, n=len(x))
    rms = np.sqrt(np.mean(x ** 2)) or 1.0
    return (x * amp / rms).astype(np.float32)


def place(length_ms: float, events: list[tuple[float, np.ndarray]], sr: int = SR) -> np.ndarray:
    """A silent buffer of `length_ms` with each `(start_ms, signal)` added in (clipped at the end)."""
    out = np.zeros(_n(length_ms, sr), dtype=np.float32)
    for start, sig in events:
        a = _n(start, sr)
        b = min(a + len(sig), len(out))
        if a < len(out):
            out[a:b] += sig[: b - a]
    return out


def clicks(times_ms: list[float], length_ms: float, sr: int = SR, amp: float = 0.9,
           click_ms: float = 5) -> np.ndarray:
    """Short 1 kHz clicks at each time in `times_ms`, in a buffer of `length_ms`."""
    return place(length_ms, [(t, tone(1000, click_ms, sr, amp)) for t in times_ms], sr)


def clicks_on_beats(bpm: float, length_ms: float, first_ms: float = 0, sr: int = SR,
                    amp: float = 0.9) -> np.ndarray:
    """Clicks on every beat of a constant `bpm`, the first at `first_ms`."""
    step = 60000 / bpm
    return clicks(list(np.arange(first_ms, length_ms, step)), length_ms, sr, amp)


def pan(x: np.ndarray, left: float = 1.0, right: float = 1.0) -> np.ndarray:
    """A mono signal as `(n, 2)` with the given linear gain per channel (`pan(x, 1, 0)` is hard left)."""
    return np.stack([x * left, x * right], axis=1).astype(np.float32)


def db(gain_db: float) -> float:
    """A linear gain for `gain_db` decibels."""
    return 10 ** (gain_db / 20)


def glide(f0: float, f1: float, ms: float, sr: int = SR, amp: float = 0.5) -> np.ndarray:
    """A phase-continuous sine gliding exponentially from `f0` to `f1` Hz over `ms`."""
    t = np.arange(_n(ms, sr)) / sr
    k = np.log(f1 / f0) / (ms / 1000)
    phase = 2 * np.pi * f0 * (np.exp(k * t) - 1) / k
    return (amp * np.sin(phase)).astype(np.float32)
