"""`reel` command: capture ideas and run the pipeline stage by stage."""
from __future__ import annotations

import argparse
import hashlib
import re
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path

from . import compose, llm, render, script as scriptgen, sfx, sound, voice
from .config import ASSETS, IDEAS, REELS, ROOT, STAGES, Manifest, load_config, now, read_json, reel_dir, slugify, write_json
from .models import Audience, Idea, Script, Source


def say(msg: str = "") -> None:
    print(msg, flush=True)


def sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


# ------------------------------------------------------------------ ideas

def cmd_idea_new(a) -> None:
    if a.file:
        data = read_json(Path(a.file))
        data.setdefault("id", slugify(data.get("title", "")))
        idea = Idea.model_validate(data)
    else:
        missing = [k for k in ("title", "essence", "format", "audience") if not getattr(a, k)]
        if missing:
            raise SystemExit("missing: " + ", ".join("--" + m for m in missing) + " (or pass --file idea.json)")
        idea = Idea(
            id=slugify(a.title), title=a.title, essence=a.essence, format=a.format, language=a.language,
            audience=Audience(who=a.audience, knowledge_level=a.level, why_they_care=a.why or ""),
            hook=a.hook or "", key_points=a.point or [], tone=a.tone, target_duration_s=a.duration, cta=a.cta or "",
            visual_notes=a.visual or "", references=a.ref or [], tags=a.tag or [],
            source=Source(type=a.source_type, ref=a.source_ref or ""), notes=a.notes or "")
    idea.created_at = idea.created_at or now()
    idea.source.captured_at = idea.source.captured_at or idea.created_at
    path = IDEAS / f"{idea.id}.json"
    if path.exists() and not a.force:
        raise SystemExit(f"{path} already exists (use --force to overwrite)")
    write_json(path, idea.model_dump())
    say(f"idea saved: {path}")


def cmd_idea_validate(a) -> None:
    path = Path(a.idea) if Path(a.idea).exists() else IDEAS / f"{a.idea}.json"
    if not path.exists():
        raise SystemExit(f"no such idea file: {a.idea}")
    try:
        idea = Idea.model_validate(read_json(path))
    except ValueError as e:
        raise SystemExit(f"INVALID {path}\n{e}")
    problems = []
    if path.parent.resolve() == IDEAS.resolve() and path.stem != idea.id:
        problems.append(f"file name '{path.stem}' does not match id '{idea.id}'")
    if len(idea.key_points) < 3:
        problems.append("fewer than 3 key_points")
    if idea.language == "hinglish" and re.search(r"[\u0900-\u097F]", idea.title + idea.hook + idea.share_line):
        problems.append("Devanagari in title/hook/share_line (on-screen text is Roman script)")
    if problems:
        raise SystemExit(f"INVALID {path}\n- " + "\n- ".join(problems))
    say(f"valid: {path}  [{idea.status}] {idea.format}/{idea.language}, {len(idea.key_points)} key points, "
        f"{len(idea.perspectives)} perspectives, digest {'yes' if idea.digest else 'no'}, "
        f"review {'yes' if idea.review else 'no'}")


def cmd_hn(a) -> None:
    from . import hn, ideate
    cfg = load_config()
    icfg = cfg.get("ideation", {})
    if a.hn_cmd == "ideate":
        src = Path(a.source).resolve()
        say(f"[hn] drafting from {src.name} with {icfg.get('model', cfg['script']['model'])} ...")
        say(f"[hn] draft idea: {ideate.draft_from_source(src, cfg, say)}")
        llm.unload(cfg["script"])
        return
    count = a.count or icfg.get("count", 3)
    say(f"[hn] reading the top {count} stories ...")
    done = []
    for story in hn.top_stories(count):
        src, new = hn.capture_story(story, icfg.get("top_comments", 12), icfg.get("replies", 1), force=a.force)
        info = read_json(src / "story.json")
        say(f"[hn] #{info['rank']} {info['title']}  ({info['points']} points)\n"
            f"     {'captured' if new else 'already captured'}: {src}\n"
            f"     article: {info['article']['status']}, {info['article']['chars']} chars via "
            f"{info['article']['method'] or 'n/a'}; {info['comments_saved']} comments saved")
        done.append((src, new))
    if a.hn_cmd == "fetch":
        return
    results = []
    for src, new in done:
        info = read_json(src / "story.json")
        existing = sorted(IDEAS.glob(f"hn-{info['id']}-*.json"))
        if existing and not a.force:
            say(f"[hn] idea already exists, left as is: {existing[0]}")
            results.append((existing[0], src, False))
            continue
        say(f"[hn] drafting '{info['title'][:60]}' with {icfg.get('model', cfg['script']['model'])} ...")
        try:
            results.append((ideate.draft_from_source(src, cfg, say), src, True))
        except (llm.LLMError, ValueError) as e:
            say(f"  ! draft failed: {e}")
    llm.unload(cfg["script"])
    say("\nDRAFTS (status 'draft': the local model's work, not yet edited)")
    for path, src, new in results:
        say(f"IDEA {path} | SOURCE {src} | {'new' if new else 'existing'}")


def cmd_idea_list(a) -> None:
    rows = [Idea.model_validate(read_json(p)) for p in sorted(IDEAS.glob("*.json"))]
    if not rows:
        say(f"no ideas yet in {IDEAS}")
    for i in rows:
        say(f"{i.id:<44} {i.format:<12} {i.language:<9} {i.target_duration_s:>3}s  {i.status:<14} {i.title}")


def start_reel(idea_id: str) -> Path:
    path = IDEAS / f"{idea_id}.json"
    if not path.exists():
        raise SystemExit(f"no idea '{idea_id}' in {IDEAS}")
    idea = Idea.model_validate(read_json(path))
    rdir = REELS / f"{date.today().isoformat()}-{idea.id}"
    if rdir.exists():
        raise SystemExit(f"{rdir} already exists")
    for sub in ("audio", "video", "final", "logs"):
        (rdir / sub).mkdir(parents=True)
    write_json(rdir / "idea.json", idea.model_dump())
    m = Manifest(rdir)
    m.data.update(id=rdir.name, idea_id=idea.id, title=idea.title, format=idea.format, language=idea.language,
                  created_at=now())
    m.save()
    idea.status = "in_production"
    write_json(path, idea.model_dump())
    say(f"reel folder: {rdir}")
    return rdir


def resolve(name: str) -> Path:
    """A reel name, or an idea id (which starts a new reel folder)."""
    if (IDEAS / f"{name}.json").exists() and not any(REELS.glob(f"*-{name}")):
        return start_reel(name)
    return reel_dir(name)


# ------------------------------------------------------------------ stages

def stage_script(rdir: Path, cfg: dict, model: str | None = None) -> None:
    idea = Idea.model_validate(read_json(rdir / "idea.json"))
    say(f"[script] writing with {model or cfg['script']['model']} ...")
    s, report = scriptgen.generate(idea, cfg["script"], model, cfg["voice"][idea.language]["words_per_second"])
    write_json(rdir / "script.json", s.model_dump())
    (rdir / "script.md").write_text(scriptgen.to_markdown(s), encoding="utf-8")
    Manifest(rdir).done("script", **report)
    say(f"[script] {report['beats']} beats, {report['words']} words (budget {report['word_budget']}), "
        f"~{report['est_duration_s']}s, {report['wall_s']}s at {report['tokens_per_s']} tok/s")
    for w in report["warnings"]:
        say(f"  ! {w}")


def stage_voice(rdir: Path, cfg: dict) -> None:
    (rdir / "script.md").write_text(
        scriptgen.to_markdown(Script.model_validate(read_json(rdir / "script.json"))), encoding="utf-8")
    say("[voice] speaking with Maya (loads in ~20 s, then roughly 2x real time) ...")
    info = voice.run(rdir, cfg, log=say)
    Manifest(rdir).done("voice", script_sha=sha(rdir / "script.json"), **info)
    say(f"[voice] {info['duration_s']}s timeline, {info['generated']} beats spoken, {info['reused']} reused")
    if info.get("unclean_beats"):
        say(f"  ! beats {info['unclean_beats']} hit Maya's length cap; listen to them in audio/beats/")


def stage_sound(rdir: Path, cfg: dict) -> None:
    info = sound.run(rdir, cfg, read_json(rdir / "idea.json")["format"], log=say)
    Manifest(rdir).done("sound", **info)
    music = info["music"]["title"] + " by " + info["music"]["artist"] if info["music"] else "none"
    say(f"[sound] music: {music}; {info['sfx']} sound effects; {info['input_lufs']} -> {info['target_lufs']} LUFS")


def stage_compose(rdir: Path, cfg: dict) -> None:
    info = compose.run(rdir, cfg)
    Manifest(rdir).done("compose", **info)
    say(f"[compose] {info['scenes']} scenes, {info['captions']} caption chunks -> {rdir / 'video' / 'index.html'}")


def stage_render(rdir: Path, cfg: dict, draft: bool = False) -> None:
    say("[render] rendering frames with HyperFrames ...")
    t0 = time.perf_counter()
    info = render.run(rdir, cfg, draft=draft)
    info["render_s"] = round(time.perf_counter() - t0, 1)
    if not draft:
        Manifest(rdir).done("render", **info)
    say(f"[render] {info['file']}  ({info['duration_s']}s, {info['video']}, audio {info['audio']}, "
        f"{info['size_mb']} MB, took {info['render_s']}s)")


RUNNERS = {"script": stage_script, "voice": stage_voice, "sound": stage_sound, "compose": stage_compose,
           "render": stage_render}


def cmd_stage(a) -> None:
    rdir, cfg = resolve(a.reel), load_config()
    if a.cmd == "script":
        stage_script(rdir, cfg, a.model)
    elif a.cmd == "render":
        stage_render(rdir, cfg, draft=a.draft)
    elif a.cmd == "sound":
        if a.music:
            cfg["sound"]["music"] = a.music
        stage_sound(rdir, cfg)
    else:
        RUNNERS[a.cmd](rdir, cfg)


def cmd_run(a) -> None:
    rdir, cfg = resolve(a.reel), load_config()
    m = Manifest(rdir)
    # A script edited by hand after the voice was recorded makes everything from voice onwards out of date.
    if m.status("voice") == "done" and m.data["stages"]["voice"].get("script_sha") != sha(rdir / "script.json"):
        for st in STAGES[1:]:
            if m.status(st) == "done":
                m.data["stages"][st]["status"] = "stale"
        m.save()
        say("script.json changed since the voice was recorded: redoing voice, sound, compose, render")
    first = a.start or next((s for s in STAGES if m.status(s) != "done"), None)
    if first is None:
        say(f"everything is up to date: {rdir / 'final' / 'reel.mp4'}  (use --from <stage> to redo)")
        return
    for st in STAGES[STAGES.index(first):]:
        if st == "script":
            stage_script(rdir, cfg, a.model)
            if not a.auto:
                say(f"\nReview the script: {rdir / 'script.md'}\nEdit {rdir / 'script.json'} if needed "
                    f"(`narration` = captions, `tts` = what Maya says), then run:\n  reel run {rdir.name}")
                return
        else:
            RUNNERS[st](rdir, cfg)
    say(f"\ndone: {rdir / 'final' / 'reel.mp4'}")


def cmd_status(a) -> None:
    dirs = [reel_dir(a.reel)] if a.reel else sorted(d for d in REELS.glob("*") if (d / "reel.json").exists())
    if not dirs:
        say(f"no reels yet in {REELS}")
    for d in dirs:
        m = Manifest(d)
        marks = " ".join(f"{s}:{m.status(s)}" for s in STAGES)
        say(f"{d.name}\n    {marks}")


def cmd_preview(a) -> None:
    rdir = reel_dir(a.reel)
    env = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1"}
    os.chdir(rdir / "video")
    os.execve(str(render.HF), [str(render.HF), "preview"], env)        # foreground; Ctrl-C to stop


def cmd_check(a) -> None:
    rdir = reel_dir(a.reel)
    res = render.check(rdir)
    say(f"check {'passed' if res['ok'] else 'found problems'}; details: {rdir / 'logs' / 'check.json'}")
    if a.at:
        say(f"snapshots: {render.snapshot(rdir, [float(x) for x in a.at.split(',')])}")


def cmd_assets(a) -> None:
    made = sfx.build(ASSETS / "sfx", overwrite=a.overwrite)
    say(f"sound effects in {ASSETS / 'sfx'}: wrote {made or 'nothing (all present)'}")


def cmd_schema(a) -> None:
    write_json(ROOT / "schemas" / "idea.schema.json", Idea.model_json_schema())
    write_json(ROOT / "schemas" / "script.schema.json", Script.model_json_schema())
    say(f"schemas written to {ROOT / 'schemas'}")


def cmd_eval(a) -> None:
    from . import evalmodels
    evalmodels.run(a.models, a.ideas, load_config(), say)


def cmd_unload(a) -> None:
    llm.unload(load_config()["script"])
    say("asked Ollama to unload all models")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="reel", description="Local pipeline for faceless animated reels.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    idea = sub.add_parser("idea", help="capture and list ideas").add_subparsers(dest="idea_cmd", required=True)
    n = idea.add_parser("new", help="save an idea to ideas/<id>.json")
    n.add_argument("--file", help="idea JSON to validate and import (instead of the flags below)")
    n.add_argument("--title")
    n.add_argument("--essence", help="the core of the reel in 1-2 sentences")
    n.add_argument("--format", choices=["educational", "story", "trivia"])
    n.add_argument("--language", choices=["hinglish", "english"], default="hinglish")
    n.add_argument("--audience", help="who it is for")
    n.add_argument("--level", choices=["beginner", "intermediate", "expert"], default="beginner")
    n.add_argument("--why", help="why they care")
    n.add_argument("--hook")
    n.add_argument("--point", action="append", help="key point / plot beat / question with answer (repeatable)")
    n.add_argument("--tone", default="curious")
    n.add_argument("--duration", type=int, default=35, help="target seconds")
    n.add_argument("--cta")
    n.add_argument("--visual", help="visual notes")
    n.add_argument("--ref", action="append", help="reference link (repeatable)")
    n.add_argument("--tag", action="append")
    n.add_argument("--source-type", default="manual")
    n.add_argument("--source-ref")
    n.add_argument("--notes")
    n.add_argument("--force", action="store_true")
    n.set_defaults(fn=cmd_idea_new)
    idea.add_parser("list", help="list captured ideas").set_defaults(fn=cmd_idea_list)
    v = idea.add_parser("validate", help="check an idea file against the idea structure")
    v.add_argument("idea", help="idea id or path to a JSON file")
    v.set_defaults(fn=cmd_idea_validate)

    hn = sub.add_parser("hn", help="capture Hacker News top stories as draft ideas").add_subparsers(dest="hn_cmd", required=True)
    for name, text in (("capture", "download the top stories and draft an idea for each with the local model"),
                       ("fetch", "only download articles and comments (no model)")):
        h = hn.add_parser(name, help=text)
        h.add_argument("--count", type=int, help="how many top stories (default: [ideation] count)")
        h.add_argument("--force", action="store_true", help="redo stories that were already captured")
        h.set_defaults(fn=cmd_hn)
    h = hn.add_parser("ideate", help="(re)draft the idea for one downloaded source folder")
    h.add_argument("source", help="path to sources/hackernews/<date>-<id>")
    h.set_defaults(fn=cmd_hn)

    p = sub.add_parser("run", help="run the pipeline for a reel (or start one from an idea id)")
    p.add_argument("reel")
    p.add_argument("--auto", action="store_true", help="do not stop for script review")
    p.add_argument("--from", dest="start", choices=STAGES, help="redo from this stage")
    p.add_argument("--model", help="script model override")
    p.set_defaults(fn=cmd_run)

    for st in STAGES:
        p = sub.add_parser(st, help=f"run only the {st} stage")
        p.add_argument("reel")
        if st == "script":
            p.add_argument("--model")
        if st == "sound":
            p.add_argument("--music", help='file in assets/music, "auto" or "none"')
        if st == "render":
            p.add_argument("--draft", action="store_true", help="fast low-quality render to final/reel_draft.mp4")
        p.set_defaults(fn=cmd_stage)

    p = sub.add_parser("status", help="stage status of one or all reels")
    p.add_argument("reel", nargs="?")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("preview", help="open the reel in the HyperFrames Studio preview (local editor)")
    p.add_argument("reel")
    p.set_defaults(fn=cmd_preview)
    p = sub.add_parser("check", help="lint + layout checks, optional snapshots")
    p.add_argument("reel")
    p.add_argument("--at", help="comma-separated seconds to snapshot as PNG")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("assets", help="(re)build the synthesised sound effects")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(fn=cmd_assets)
    sub.add_parser("schema", help="export JSON Schemas to schemas/").set_defaults(fn=cmd_schema)
    sub.add_parser("unload", help="unload Ollama models to free memory").set_defaults(fn=cmd_unload)
    p = sub.add_parser("eval-models", help="compare script models on the same ideas")
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--ideas", nargs="*", help="idea ids (default: all in ideas/)")
    p.set_defaults(fn=cmd_eval)

    a = ap.parse_args(argv)
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found (brew install ffmpeg)")
    try:
        a.fn(a)
    except (llm.LLMError, RuntimeError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
