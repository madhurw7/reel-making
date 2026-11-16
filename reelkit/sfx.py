"""Sound effects synthesised in code (no downloads, no licences): whoosh, pop, tick, ding, thud, sparkle.

`reel assets sfx` writes them to assets/sfx/*.wav (48 kHz mono). Replace any file with your own sound of the
same name and the mixer will use it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.abs(x).max()
    return (x * (peak / m)).astype(np.float32) if m else x.astype(np.float32)


def _fade(x: np.ndarray, a: float = 0.002, r: float = 0.01) -> np.ndarray:
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    x = x.copy()
    x[:na] *= np.linspace(0, 1, na)
    x[-nr:] *= np.linspace(1, 0, nr)
    return x


def _bandpass_sweep(noise: np.ndarray, f0: np.ndarray, q: float = 1.4) -> np.ndarray:
    """State-variable band-pass whose centre frequency follows f0 (per sample)."""
    low = band = 0.0
    out = np.empty_like(noise)
    f = 2 * np.sin(np.pi * np.clip(f0, 30, SR / 6) / SR)
    damp = 1 / q
    for i in range(len(noise)):
        low += f[i] * band
        high = noise[i] - low - damp * band
        band += f[i] * high
        out[i] = band
    return out


def pop() -> np.ndarray:
    t = _t(0.11)
    freq = 190 + 520 * np.exp(-t * 55)
    x = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 38)
    return _norm(_fade(x))


def tick() -> np.ndarray:
    t = _t(0.06)
    x = np.sin(2 * np.pi * 1150 * t) * np.exp(-t * 95) + 0.35 * np.sin(2 * np.pi * 2300 * t) * np.exp(-t * 140)
    return _norm(_fade(x, 0.0005))


def ding() -> np.ndarray:
    t = _t(0.9)
    f = 1318.5                                                   # E6
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t * 6)
         + 0.45 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 9)
         + 0.22 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 14))
    return _norm(_fade(x, 0.003, 0.08), 0.8)


def sparkle() -> np.ndarray:
    notes = [1046.5, 1318.5, 1568.0, 2093.0]                     # C6 E6 G6 C7
    out = np.zeros(int(0.95 * SR))
    for k, f in enumerate(notes):
        t = _t(0.55)
        n = np.sin(2 * np.pi * f * t) * np.exp(-t * 9) + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 14)
        at = int(k * 0.085 * SR)
        out[at: at + len(n)] += _fade(n, 0.003, 0.05)
    return _norm(out, 0.75)


def thud() -> np.ndarray:
    t = _t(0.38)
    freq = 48 + 70 * np.exp(-t * 16)
    x = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 11)
    return _norm(_fade(x, 0.003, 0.05))


def whoosh() -> np.ndarray:
    rng = np.random.default_rng(7)
    t = _t(0.5)
    u = t / t[-1]
    centre = 350 + 3200 * np.sin(np.pi * u) ** 2                 # rises then falls
    x = _bandpass_sweep(rng.standard_normal(len(t)), centre) * np.sin(np.pi * u) ** 1.6
    return _norm(x, 0.8)


ALL = {"pop": pop, "tick": tick, "ding": ding, "sparkle": sparkle, "thud": thud, "whoosh": whoosh}


def build(out_dir: Path, overwrite: bool = False) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for name, fn in ALL.items():
        p = out_dir / f"{name}.wav"
        if overwrite or not p.exists():
            sf.write(str(p), fn(), SR, subtype="PCM_16")
            made.append(name)
    return made
