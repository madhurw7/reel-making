"""Project paths, config.toml loading and small shared helpers."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("REEL_ROOT") or Path(__file__).resolve().parent.parent)
IDEAS = ROOT / "ideas"
REELS = ROOT / "reels"
ASSETS = ROOT / "assets"
TEMPLATES = ROOT / "templates"
STAGES = ["script", "voice", "sound", "compose", "render"]


def load_config() -> dict:
    with open(ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def slugify(text: str, limit: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].strip("-") or "untitled"


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cmd: list, cwd: Path | None = None, env: dict | None = None, log: Path | None = None) -> str:
    """Run a command, return stdout; raise with the tail of stderr on failure."""
    full_env = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1", **(env or {})}
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, env=full_env, capture_output=True, text=True)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n$ {' '.join(str(c) for c in cmd)}\n{p.stdout}\n{p.stderr}\n")
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(str(c) for c in cmd[:4])} ...\n"
                           f"{(p.stderr or p.stdout)[-1500:]}")
    return p.stdout


def reel_dir(name: str) -> Path:
    """Resolve a reel by folder name, unique prefix/substring, or path."""
    p = Path(name)
    if p.is_dir() and (p / "reel.json").exists():
        return p.resolve()
    if (REELS / name / "reel.json").exists():
        return REELS / name
    hits = sorted(d for d in REELS.glob("*") if d.is_dir() and name in d.name and (d / "reel.json").exists())
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"no reel matching '{name}' in {REELS}")
    raise SystemExit(f"'{name}' matches several reels: {', '.join(d.name for d in hits)}")


class Manifest:
    """reel.json: what was built, when, with which settings."""

    def __init__(self, rdir: Path):
        self.path = rdir / "reel.json"
        self.data = read_json(self.path) if self.path.exists() else {"stages": {}}

    def done(self, stage: str, **info) -> None:
        self.data.setdefault("stages", {})[stage] = {"status": "done", "at": now(), **info}
        for later in STAGES[STAGES.index(stage) + 1:]:      # anything downstream is now out of date
            if self.data["stages"].get(later, {}).get("status") == "done":
                self.data["stages"][later]["status"] = "stale"
        self.save()

    def status(self, stage: str) -> str:
        return self.data.get("stages", {}).get(stage, {}).get("status", "pending")

    def save(self) -> None:
        self.data["updated_at"] = now()
        write_json(self.path, self.data)
