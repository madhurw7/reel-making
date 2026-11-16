"""The single source of timing: voice durations -> scene windows, caption chunks and sound-effect cues.

Both the audio mix and the HTML composition are built from this file's output (audio/timeline.json),
which is why picture and sound stay in sync without any alignment step.
"""
from __future__ import annotations

import re

from .models import Script

PUNCT_END = re.compile(r"[,.;:?!।]$")


def caption_chunks(text: str, start: float, end: float, max_words: int = 4, max_chars: int = 22) -> list[dict]:
    """Split a spoken line into short caption chunks, timed in proportion to their length."""
    words = text.split()
    if not words or end <= start:
        return []
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if PUNCT_END.search(w) and len(cur) >= 2:
            chunks.append(cur)
            cur = []
    if cur:
        if chunks and len(cur) == 1 and len(" ".join(chunks[-1] + cur)) <= max_chars + 6:
            chunks[-1] += cur                                   # no single-word orphan at the end
        else:
            chunks.append(cur)
    weight = lambda ws: sum(len(w) + 1 + (3 if PUNCT_END.search(w) else 0) for w in ws)
    total = sum(weight(c) for c in chunks)
    out, t = [], start
    for c in chunks:
        d = (end - start) * weight(c) / total
        out.append({"start": round(t, 3), "duration": round(d, 3), "text": " ".join(c)})
        t += d
    out[-1]["duration"] = round(out[-1]["duration"] + 0.12, 3)
    return out


def build(script: Script, durations: dict[int, float], vcfg: dict, captions: bool = True) -> dict:
    lead, gap, tail, quiz_hold = vcfg["lead_in_s"], vcfg["beat_gap_s"], vcfg["tail_s"], vcfg["quiz_hold_s"]
    scenes, t = [], lead
    for b in script.beats:
        d = durations[b.id]
        hold = quiz_hold if b.scene == "quiz" else 0.0
        scenes.append({"beat": b.id, "scene": b.scene, "voice_start": round(t, 3), "voice_end": round(t + d, 3),
                       "hold": hold})
        t += d + hold + gap
    for i, s in enumerate(scenes):
        s["start"] = 0.0 if i == 0 else round(s["voice_start"] - min(0.15, gap / 2), 3)
    for i, s in enumerate(scenes):
        end = scenes[i + 1]["start"] if i + 1 < len(scenes) else s["voice_end"] + s["hold"] + tail
        s["duration"] = round(end - s["start"], 3)
    total = round(scenes[-1]["start"] + scenes[-1]["duration"], 3)

    caps, sfx = [], []
    for i, (b, s) in enumerate(zip(script.beats, scenes)):
        vs, vd = s["voice_start"], s["voice_end"] - s["voice_start"]
        n = len(b.items)
        s["items_at"] = []
        if captions:
            caps += caption_chunks(b.narration, vs, s["voice_end"])
        if i == 0:
            sfx += [{"t": 0.0, "name": "whoosh", "db": -3}, {"t": 0.28, "name": "thud", "db": 0}]
        else:
            sfx.append({"t": max(0.0, s["start"] - 0.08), "name": "whoosh", "db": -7})
        if b.scene == "bullets":
            s["items_at"] = [round(vs + vd * (0.12 + 0.76 * k / n), 3) for k in range(n)]
            sfx += [{"t": at, "name": "pop", "db": -2} for at in s["items_at"]]
        elif b.scene == "compare":
            s["items_at"] = [round(vs + vd * 0.12, 3), round(vs + vd * 0.5, 3)]
            sfx += [{"t": at, "name": "pop", "db": -2} for at in s["items_at"]]
        elif b.scene == "quiz":
            s["items_at"] = [round(s["start"] + 0.55 + 0.16 * k, 3) for k in range(n)]
            s["hold_start"] = round(s["voice_end"] + 0.1, 3)
            step = (s["hold"] - 0.1) / 3
            sfx += [{"t": round(s["hold_start"] + k * step, 3), "name": "tick", "db": -1} for k in range(3)]
        elif b.scene == "answer":
            s["reveal_at"] = round(s["start"] + 0.45, 3)
            sfx.append({"t": s["reveal_at"], "name": "ding", "db": 0})
        elif b.scene == "stat":
            s["count_end"] = round(vs + min(1.1, vd * 0.6), 3)
            sfx.append({"t": s["count_end"], "name": "ding", "db": -4})
        elif b.scene == "outro":
            sfx.append({"t": round(s["start"] + 0.35, 3), "name": "sparkle", "db": -2})
    return {"duration": total, "scenes": scenes, "captions": caps, "sfx": sorted(sfx, key=lambda e: e["t"])}
