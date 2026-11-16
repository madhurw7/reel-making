"""Compare script models: same ideas, same prompts, one report. Speed and rule-following are measured here;
writing quality still needs a reader, so every script is saved next to the numbers."""
from __future__ import annotations

import time
from datetime import datetime

from . import llm, script as scriptgen
from .config import IDEAS, ROOT, read_json, write_json
from .models import Idea


def run(models: list[str], idea_ids: list[str] | None, cfg: dict, say=print) -> None:
    paths = [IDEAS / f"{i}.json" for i in idea_ids] if idea_ids else sorted(IDEAS.glob("*.json"))
    ideas = [Idea.model_validate(read_json(p)) for p in paths]
    out = ROOT / "eval" / datetime.now().strftime("%Y%m%d-%H%M%S")
    rows = []
    for model in models:
        llm.unload(cfg["script"])                               # one model in memory at a time
        for idea in ideas:
            say(f"[eval] {model} · {idea.id} ...")
            t0 = time.perf_counter()
            try:
                s, rep = scriptgen.generate(idea, cfg["script"], model, cfg["voice"][idea.language]["words_per_second"])
            except Exception as e:                              # a model that cannot follow the schema is a result too
                rows.append({"model": model, "idea": idea.id, "error": str(e)[:200]})
                say(f"  failed: {e}")
                continue
            d = out / model.replace(":", "_").replace("/", "_")
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{idea.id}.md").write_text(scriptgen.to_markdown(s), encoding="utf-8")
            write_json(d / f"{idea.id}.json", s.model_dump())
            scenes = sorted({b.scene for b in s.beats})
            rows.append({"model": model, "idea": idea.id, "language": idea.language, "format": idea.format,
                         "total_s": round(time.perf_counter() - t0, 1), "tokens_per_s": rep["tokens_per_s"],
                         "llm_calls": rep["llm_calls"], "words": rep["words"], "word_budget": rep["word_budget"],
                         "beats": rep["beats"], "scene_types": len(scenes), "scenes": ",".join(scenes),
                         "warnings": len(rep["warnings"]), "warning_text": rep["warnings"]})
            say(f"  {rows[-1]['total_s']}s, {rep['words']}/{rep['word_budget']} words, {rep['beats']} beats, "
                f"{len(rep['warnings'])} warnings")
    llm.unload(cfg["script"])
    write_json(out / "results.json", rows)
    lines = ["# Script model comparison", "",
             "| model | idea | lang | time s | tok/s | calls | words/budget | beats | scene types | warnings |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['model']} | {r['idea']} | | | | | | | | FAILED: {r['error']} |")
        else:
            lines.append(f"| {r['model']} | {r['idea']} | {r['language']} | {r['total_s']} | {r['tokens_per_s']} | "
                         f"{r['llm_calls']} | {r['words']}/{r['word_budget']} | {r['beats']} | {r['scene_types']} | "
                         f"{r['warnings']} |")
    lines += ["", "Scripts are in the per-model folders beside this file. Read them: the table cannot judge writing."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"\nreport: {out / 'report.md'}")
