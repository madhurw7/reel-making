"""Stage 2: script.json -> one WAV per beat via the local Maya 2 model, then voice.wav + timeline.json."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from . import llm, timeline
from .config import read_json, write_json
from .models import Script

SR = 24000


def _key(text: str, voice: str, lang: str, seed: int) -> str:
    return hashlib.sha1(f"{voice}|{lang}|{seed}|{text}".encode()).hexdigest()[:8]


def run(rdir: Path, cfg: dict, log=print) -> dict:
    script = Script.model_validate(read_json(rdir / "script.json"))
    vcfg = cfg["voice"]
    who = vcfg[script.language]
    beats_dir = rdir / "audio" / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)

    files, todo = {}, []
    for b in script.beats:
        text = b.tts or b.narration
        path = beats_dir / f"{b.id:02d}-{_key(text, who['voice'], who['lang'], vcfg['seed'])}.wav"
        files[b.id] = path
        if not path.exists():                       # unchanged lines are reused; only edited lines are re-spoken
            todo.append({"id": b.id, "text": text, "out": str(path)})
    for old in beats_dir.glob("*.wav"):
        if old not in files.values():
            old.unlink()

    info = {"voice": who["voice"], "lang": who["lang"], "generated": len(todo), "reused": len(files) - len(todo)}
    if todo:
        llm.unload(cfg["script"])                   # Maya needs ~6 GB; never keep the script model loaded beside it
        swap = llm.swap_used_mb()
        if swap > 6000:
            log(f"  ! swap is {swap:.0f} MB used. Maya runs up to 15x slower when memory is full "
                f"(healthy: ~2x real time). Close heavy apps if this crawls.")
        job = {"maya_dir": cfg["paths"]["maya_dir"], "voice": who["voice"], "lang": who["lang"], "seed": vcfg["seed"],
               "retries": vcfg["retries"], "items": todo, "result": str(rdir / "audio" / "maya_result.json")}
        write_json(rdir / "audio" / "maya_job.json", job)
        worker = Path(__file__).with_name("maya_worker.py")
        logf = rdir / "logs" / "voice.log"
        logf.parent.mkdir(exist_ok=True)
        env = {**os.environ, "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1"}     # weights are cached: stay offline
        with open(logf, "a", encoding="utf-8") as lf:
            p = subprocess.Popen([cfg["paths"]["maya_python"], str(worker), str(rdir / "audio" / "maya_job.json")],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            for line in p.stdout:
                lf.write(line)
                lf.flush()
                if line.startswith("[maya]"):
                    log("  " + line.rstrip())
            if p.wait() != 0:
                raise RuntimeError(f"Maya worker failed; see {logf}")
        res = read_json(rdir / "audio" / "maya_result.json")
        info["gen_s"] = round(sum(i["gen_s"] for i in res["items"]), 1)
        info["unclean_beats"] = [i["id"] for i in res["items"] if not i["clean"]]

    waves = {bid: sf.read(str(p), dtype="float32")[0] for bid, p in files.items()}
    durations = {bid: len(w) / SR for bid, w in waves.items()}
    tl = timeline.build(script, durations, vcfg, captions=cfg["video"]["captions"] != "off")
    voice = np.zeros(int(tl["duration"] * SR) + 1, np.float32)
    for s in tl["scenes"]:
        w = waves[s["beat"]]
        at = int(s["voice_start"] * SR)
        voice[at: at + len(w)] += w[: len(voice) - at]
    sf.write(str(rdir / "audio" / "voice.wav"), voice, SR, subtype="PCM_16")
    write_json(rdir / "audio" / "timeline.json", tl)
    info.update(duration_s=tl["duration"], speech_s=round(sum(durations.values()), 2))
    return info


if __name__ == "__main__":
    sys.exit("use: reel voice <reel>")
