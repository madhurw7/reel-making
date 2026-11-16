"""Stage 5: render the HyperFrames project to MP4, then mux the final mix on top -> final/reel.mp4."""
from __future__ import annotations

import json
from pathlib import Path

from .config import ROOT, read_json, run as sh
from .models import Script

HF = ROOT / "node_modules" / ".bin" / "hyperframes"


def check(rdir: Path) -> dict:
    """HyperFrames lint + runtime + layout checks. Returns {'ok', 'errors', 'warnings', 'findings'}."""
    import os
    import subprocess
    env = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1"}
    p = subprocess.run([str(HF), "check", str(rdir / "video"), "--json"], capture_output=True, text=True, env=env)
    (rdir / "logs").mkdir(exist_ok=True)
    (rdir / "logs" / "check.json").write_text(p.stdout or p.stderr, encoding="utf-8")
    try:
        data = json.loads(p.stdout[p.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return {"ok": p.returncode == 0, "errors": None, "warnings": None, "raw": (p.stdout or p.stderr)[-800:]}
    return {"ok": p.returncode == 0, "data": data}


def snapshot(rdir: Path, at: list[float]) -> Path:
    """PNG frames at the given seconds, for looking at a reel before rendering it."""
    sh([HF, "snapshot", rdir / "video", "--at", ",".join(f"{t:.2f}" for t in at)], cwd=rdir / "video",
       log=rdir / "logs" / "render.log")
    runs = sorted((rdir / "video" / ".hyperframes" / "artifacts" / "snapshots").glob("*"), key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else rdir / "video"


def run(rdir: Path, cfg: dict, draft: bool = False) -> dict:
    vcfg = cfg["video"]
    video, final = rdir / "video", rdir / "final"
    final.mkdir(exist_ok=True)
    (video / "renders").mkdir(exist_ok=True)
    silent = video / "renders" / "render.mp4"
    log = rdir / "logs" / "render.log"
    sh([HF, "render", video, "-o", silent, "-f", vcfg["fps"], "-q", "draft" if draft else vcfg["quality"],
        "-w", vcfg["workers"], "--quiet"], cwd=video, log=log)

    out = final / ("reel_draft.mp4" if draft else "reel.mp4")
    # Picture from the render, sound from audio/mix.wav: the mix is the single source of truth for audio.
    sh(["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", silent, "-i", rdir / "audio" / "mix.wav",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", 48000,
        "-shortest", "-movflags", "+faststart", out], log=log)

    tl = read_json(rdir / "audio" / "timeline.json")
    sh(["ffmpeg", "-y", "-hide_banner", "-nostats", "-ss", f"{min(1.6, tl['duration'] / 3):.2f}", "-i", out,
        "-frames:v", 1, "-q:v", 2, final / "cover.jpg"], log=log)
    script = Script.model_validate(read_json(rdir / "script.json"))
    (final / "caption.txt").write_text(
        f"{script.caption}\n\n{' '.join('#' + h for h in script.hashtags)}\n", encoding="utf-8")

    probe = json.loads(sh(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
                           "-of", "json", out]))
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    return {"file": str(out), "duration_s": round(float(probe["format"]["duration"]), 2),
            "size_mb": round(int(probe["format"]["size"]) / 1e6, 2), "video": f'{v["codec_name"]} {v["width"]}x{v["height"]} @ {v["r_frame_rate"]}',
            "audio": a["codec_name"] if a else None, "expected_duration_s": tl["duration"]}
