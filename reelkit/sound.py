"""Stage 3: voice.wav + a quiet music bed (ducked under speech) + mild sound effects -> audio/mix.wav."""
from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

import numpy as np
import soundfile as sf

from . import sfx as sfxlib
from .config import ASSETS, read_json, run as sh

SR = 48000


def db(x: float) -> float:
    return 10 ** (x / 20)


def pick_music(setting: str, fmt: str, reel_id: str) -> dict | None:
    if setting == "none":
        return None
    tracks = read_json(ASSETS / "music" / "index.json")["tracks"]
    tracks = [t for t in tracks if (ASSETS / "music" / t["file"]).exists()]
    if setting != "auto":
        hit = [t for t in tracks if t["file"] == setting or Path(t["file"]).stem == setting]
        if not hit:
            raise SystemExit(f"music '{setting}' is not listed in assets/music/index.json")
        return hit[0]
    pool = [t for t in tracks if fmt in t.get("formats", [])] or tracks
    return pool[zlib.crc32(reel_id.encode()) % len(pool)] if pool else None     # stable per reel, varied across reels


def _speech_activity(voice: np.ndarray, attack_s: float = 0.06, release_s: float = 0.35) -> np.ndarray:
    """0..1 envelope: 1 while the voice is speaking, easing back to 0 in pauses."""
    win = SR // 100
    n = len(voice) // win
    rms = np.sqrt((voice[: n * win].reshape(n, win) ** 2).mean(1))
    active = (rms > 0.015).astype(np.float32)
    up, down = 1 - np.exp(-0.01 / attack_s), 1 - np.exp(-0.01 / release_s)
    env, level = np.empty(n, np.float32), 0.0
    for i, a in enumerate(active):
        level += (a - level) * (up if a > level else down)
        env[i] = level
    return np.interp(np.arange(len(voice)), (np.arange(n) + 0.5) * win, env).astype(np.float32)


def _loudnorm(src: Path, dst: Path, lufs: float, log: Path) -> dict:
    """Two-pass EBU R128 normalisation with ffmpeg (measure, then apply linearly)."""
    base = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
    import subprocess
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", base + ":print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        raise RuntimeError("loudnorm measurement failed:\n" + p.stderr[-600:])
    meas = json.loads(m.group(0))
    af = (f"{base}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
          f":measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true")
    sh(["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", src, "-af", af, "-ar", SR, "-ac", 2, "-c:a", "pcm_s16le",
        dst], log=log)
    return {"input_lufs": float(meas["input_i"]), "target_lufs": lufs}


def run(rdir: Path, cfg: dict, fmt: str, log=print) -> dict:
    scfg = cfg["sound"]
    audio = rdir / "audio"
    logf = rdir / "logs" / "sound.log"
    tl = read_json(audio / "timeline.json")
    n = int(tl["duration"] * SR) + 1

    sh(["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", audio / "voice.wav", "-ar", SR, "-ac", 1,
        audio / "voice_48k.wav"], log=logf)
    voice = sf.read(str(audio / "voice_48k.wav"), dtype="float32")[0]
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    (audio / "voice_48k.wav").unlink()
    loud = np.abs(voice) > 0.02
    v_rms = float(np.sqrt((voice[loud] ** 2).mean())) if loud.any() else 0.1
    v_peak = float(np.abs(voice).max()) or 1.0
    activity = _speech_activity(voice)

    mix = np.repeat(voice[:, None], 2, axis=1)
    info = {"music": None, "sfx": len(tl["sfx"])}

    track = pick_music(scfg["music"], fmt, rdir.name)
    if track:
        sh(["ffmpeg", "-y", "-hide_banner", "-nostats", "-stream_loop", "-1", "-ss", track.get("offset_s", 0),
            "-i", ASSETS / "music" / track["file"], "-t", f"{tl['duration'] + 0.1:.3f}", "-ar", SR, "-ac", 2,
            audio / "music_src.wav"], log=logf)
        music = sf.read(str(audio / "music_src.wav"), dtype="float32", always_2d=True)[0]
        music = np.pad(music, ((0, max(0, n - len(music))), (0, 0)))[:n]
        (audio / "music_src.wav").unlink()
        m_rms = float(np.sqrt((music ** 2).mean())) or 1.0
        gain = v_rms * db(scfg["music_db"]) / m_rms
        duck = db(scfg["duck_db"]) ** activity                       # 1.0 in pauses -> duck_db while speaking
        fade = np.ones(n, np.float32)
        fi, fo = int(0.5 * SR), int(min(1.4, tl["duration"] / 4) * SR)
        fade[:fi] = np.linspace(0, 1, fi)
        fade[-fo:] = np.linspace(1, 0, fo)
        bed = music * (gain * duck * fade)[:, None]
        sf.write(str(audio / "music_bed.wav"), bed, SR, subtype="PCM_16")
        mix += bed
        info["music"] = {k: track[k] for k in ("file", "title", "artist", "license", "source")}

    sfxlib.build(ASSETS / "sfx")                                     # creates any missing effect
    layer = np.zeros(n, np.float32)
    cache = {}
    for ev in tl["sfx"]:
        if ev["name"] not in cache:
            w = sf.read(str(ASSETS / "sfx" / f"{ev['name']}.wav"), dtype="float32", always_2d=True)[0].mean(1)
            cache[ev["name"]] = w / (np.abs(w).max() or 1.0)
        w = cache[ev["name"]] * v_peak * db(scfg["sfx_db"] + ev.get("db", 0))
        at = int(ev["t"] * SR)
        if at < n:
            layer[at: at + len(w)] += w[: n - at]
    sf.write(str(audio / "sfx.wav"), layer, SR, subtype="PCM_16")
    mix += layer[:, None]

    peak = float(np.abs(mix).max())
    if peak > 0.97:
        mix *= 0.97 / peak
    sf.write(str(audio / "mix_raw.wav"), mix, SR, subtype="PCM_16")
    info.update(_loudnorm(audio / "mix_raw.wav", audio / "mix.wav", scfg["target_lufs"], logf))
    (audio / "mix_raw.wav").unlink()
    info["duration_s"] = tl["duration"]
    return info
