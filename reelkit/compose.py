"""Stage 4: script.json + timeline.json -> a HyperFrames project in <reel>/video (index.html + assets).

Every timed element is written into the HTML with its own id, so the result is editable by hand, in the
HyperFrames Studio preview, or by Claude. Scene looks live in templates/reel.css, motion in templates/reel.js.
"""
from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path

from .config import ROOT, TEMPLATES, now, read_json, write_json
from .models import Script

HF_VERSION = "0.9.56"
FONT_WEIGHTS = (500, 600, 700, 800, 900)


STAGE_W = 840            # usable width of a scene in px (see templates/reel.css)


def fit(text: str, steps: list[tuple[int, int]], floor: int, width: int = STAGE_W) -> int:
    """Font size for a text: the first (max_chars, px) step that fits, shrunk so the longest word fits `width`."""
    px = next((size for chars, size in steps if len(text) <= chars), floor)
    longest = max((len(w) for w in text.split()), default=1)
    return min(px, int(width / (0.64 * longest)))


def spans(text: str, highlight_last: bool = False) -> str:
    """One <span class="w"> per word so words can animate in one by one."""
    ws = text.split()
    out = []
    for i, w in enumerate(ws):
        cls = "w hl" if highlight_last and i == len(ws) - 1 and len(ws) > 1 else "w"
        out.append(f'<span class="{cls}">{escape(w)}{" " if i < len(ws) - 1 else ""}</span>')
    return "".join(out)


def emoji(e: str, small: bool = False) -> str:
    return f'<div class="emoji{" sm" if small else ""}"><span>{escape(e)}</span></div>'


def items_html(beat, at: list[float], letters: bool, cls=lambda i: "") -> str:
    longest = max(beat.items, key=len)
    grid = letters and len(beat.items) == 4 and len(longest) <= 10        # short quiz options: 2 x 2
    size = 40 if grid else fit(longest, [(18, 48), (28, 42), (40, 36)], 32, width=600)
    kind = " grid" if grid else (" tight" if len(beat.items) == 4 else "")
    rows = []
    for i, text in enumerate(beat.items):
        label = "ABCD"[i] if letters else str(i + 1)
        when = f' data-at="{at[i]}"' if i < len(at) else ""
        mark = '<span class="mark">✅</span>' if "correct" in cls(i) else ""
        rows.append(f'<li class="item{cls(i)}"{when} style="font-size:{size}px"><b class="idx">{label}</b>'
                    f'<span class="txt">{escape(text)}</span>{mark}</li>')
    return f'<ul class="list{kind}">' + "".join(rows) + "</ul>"


def split_value(value: str):
    """'8 minute' -> ('', 8.0, 0, ' minute'); '70%' -> ('', 70.0, 0, '%'); text without a number -> None."""
    m = re.match(r"^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$", value.strip())
    if not m:
        return None
    digits = m.group(2).replace(",", "")
    dec = len(digits.split(".")[1]) if "." in digits else 0
    return m.group(1), float(digits), dec, m.group(3)


def scene_html(beat, sc: dict, quiz, handle: str) -> tuple[str, str]:
    """-> (inner HTML of the scene's stage, extra data attributes for the <section>)."""
    h, kind, attrs = beat.heading, beat.scene, ""
    if kind == "hook":
        size = fit(h, [(16, 124), (28, 104), (42, 88)], 74)
        body = emoji(beat.emoji) + f'<h1 class="headline" style="font-size:{size}px">{spans(h, True)}</h1>'
        return f'<div class="stage">{body}</div>', attrs
    if kind == "bullets":
        size = fit(h, [(18, 78), (30, 66)], 56)
        body = (f'<h2 class="title" style="font-size:{size}px">{spans(h)}</h2>'
                + items_html(beat, sc["items_at"], letters=False))
        return f'<div class="stage top">{body}</div>', attrs
    if kind == "stat":
        parts = split_value(beat.value)
        size = fit(beat.value, [(4, 250), (7, 190), (10, 140)], 108)
        if parts:
            pre, to, dec, unit = parts
            shown = f"{to:,.{dec}f}"
            big = (f'{escape(pre)}<span class="num" data-to="{to}" data-dec="{dec}">{shown}</span>'
                   f'<span class="unit">{escape(unit.strip())}</span>')
        else:
            big = escape(beat.value)
        tsize = fit(h, [(22, 72), (36, 60)], 52)
        body = (emoji(beat.emoji, small=True) + f'<div class="big" style="font-size:{size}px">{big}</div>'
                + f'<h2 class="title" style="font-size:{tsize}px">{spans(h)}</h2>')
        return f'<div class="stage">{body}</div>', f' data-count-end="{sc["count_end"]}"'
    if kind == "compare":
        size = fit(max(beat.items, key=len), [(14, 68), (24, 56), (36, 48)], 40, width=740)
        tsize = fit(h, [(18, 78), (30, 66)], 56)
        l, r = beat.items
        body = (f'<h2 class="title" style="font-size:{tsize}px">{spans(h)}</h2><div class="versus">'
                f'<div class="side left" data-at="{sc["items_at"][0]}" style="font-size:{size}px">{escape(l)}</div>'
                f'<div class="vs">VS</div>'
                f'<div class="side right" data-at="{sc["items_at"][1]}" style="font-size:{size}px">{escape(r)}</div></div>')
        return f'<div class="stage">{body}</div>', attrs
    if kind == "quiz":
        size = fit(h, [(24, 62), (44, 52), (64, 44)], 40)
        timer = (f'<div class="timer" data-hold-start="{sc["hold_start"]}" data-hold="{round(sc["hold"] - 0.1, 3)}">'
                 '<svg viewBox="0 0 190 190"><circle class="ring-bg" cx="95" cy="95" r="80"/>'
                 '<circle class="ring" cx="95" cy="95" r="80" transform="rotate(-90 95 95)"/></svg>'
                 '<div class="count"><span>3</span><span>2</span><span>1</span></div></div>')
        body = (f'<div class="qhead"><div class="chip">{escape(beat.emoji)} QUIZ</div>{timer}</div>'
                f'<h2 class="title" style="font-size:{size}px">{spans(h)}</h2>'
                + items_html(beat, sc["items_at"], letters=True))
        return f'<div class="stage top">{body}</div>', attrs
    if kind == "answer" and quiz is not None:
        size = fit(h, [(22, 72), (38, 60)], 50)
        body = ('<div class="chip">✅ ANSWER</div>'
                + items_html(quiz, [], letters=True,
                             cls=lambda i: " correct" if i == quiz.answer_index else " wrong")
                + f'<h2 class="title" style="font-size:{size}px">{spans(h, True)}</h2>')
        return f'<div class="stage top">{body}</div>', f' data-reveal-at="{sc["reveal_at"]}"'
    if kind == "story":
        size = fit(h, [(18, 88), (32, 74), (48, 62)], 54)
        body = (f'<div class="spot">{emoji(beat.emoji)}</div>'
                f'<h2 class="title" style="font-size:{size}px">{spans(h)}</h2>')
        return f'<div class="stage">{body}</div>', attrs
    if kind == "outro":
        size = fit(h, [(14, 104), (24, 86)], 72)
        body = (emoji(beat.emoji) + f'<h1 class="headline" style="font-size:{size}px">{spans(h)}</h1>'
                '<div class="follow">+ Follow</div>'
                + (f'<div class="handle">{escape(handle)}</div>' if handle else ""))
        return f'<div class="stage">{body}</div>', attrs
    size = fit(h, [(18, 100), (32, 84), (48, 70)], 58)                     # statement (also the fallback)
    body = (emoji(beat.emoji) + f'<h2 class="title" style="font-size:{size}px">{spans(h)}</h2><div class="rule"></div>')
    return f'<div class="stage">{body}</div>', attrs


def build_html(script: Script, tl: dict, theme: dict, vcfg: dict, title: str) -> str:
    css = (TEMPLATES / "reel.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "reel.js").read_text(encoding="utf-8")
    dur = tl["duration"]
    parts, quiz = [], None
    for beat, sc in zip(script.beats, tl["scenes"]):
        if beat.scene == "quiz":
            quiz = beat
        inner, attrs = scene_html(beat, sc, quiz, vcfg.get("handle", ""))
        kind = beat.scene if not (beat.scene == "answer" and quiz is None) else "statement"
        parts.append(
            f'      <section id="scene-{beat.id}" class="clip scene" data-scene="{kind}" data-start="{sc["start"]}" '
            f'data-duration="{sc["duration"]}" data-track-index="1" data-track-kind="graphics"{attrs}>\n'
            f'        {inner}\n      </section>')
    caps = [f'        <div id="cap-{i}" class="clip cap" data-start="{c["start"]}" data-duration="{c["duration"]}" '
            f'data-track-index="2"><span class="cap-text">{escape(c["text"])}</span></div>'
            for i, c in enumerate(tl["captions"], 1)]
    brand = (f'\n      <div class="brand" data-layout-allow-safe-zone>{escape(vcfg["handle"])}</div>'
             if vcfg.get("handle") else "")
    root_vars = (f':root {{ --bg: {theme["bg"]}; --a: {theme["a"]}; --b: {theme["b"]}; '
                 f'--accent: {theme["accent"]}; }}')
    return f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>{escape(title)}</title>
    <!-- Generated by reelkit ({now()}). Safe to edit: text and timing are plain HTML attributes.
         Re-running `reel compose` overwrites this file; `reel render` alone keeps your edits. -->
    <script src="assets/gsap.min.js"></script>
    <style>
      {root_vars}
{css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dur}" data-width="1080" data-height="1920" data-fps="{vcfg['fps']}">
      <div class="bg" data-layout-allow-overflow><div class="glow g1" data-layout-allow-overflow></div><div class="glow g2" data-layout-allow-overflow></div><div class="glow g3" data-layout-allow-overflow></div><div class="ring-deco r1" data-layout-allow-overflow></div><div class="ring-deco r2" data-layout-allow-overflow></div><div class="ring-deco r3"></div><div class="dots"></div><div class="shade"></div></div>
      <div class="progress"><div id="progress-fill"></div></div>{brand}

{chr(10).join(parts)}

      <div id="captions" data-track-kind="captions">
{chr(10).join(caps)}
      </div>

      <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{dur}" data-track-index="3" data-volume="1"></audio>
    </div>
    <script>
{js}
    </script>
  </body>
</html>
"""


def run(rdir: Path, cfg: dict) -> dict:
    script = Script.model_validate(read_json(rdir / "script.json"))
    tl = read_json(rdir / "audio" / "timeline.json")
    video = rdir / "video"
    assets = video / "assets"
    (assets / "fonts").mkdir(parents=True, exist_ok=True)

    nm = ROOT / "node_modules"
    shutil.copyfile(nm / "gsap" / "dist" / "gsap.min.js", assets / "gsap.min.js")
    for wgt in FONT_WEIGHTS:
        name = f"poppins-latin-{wgt}-normal.woff2"
        shutil.copyfile(nm / "@fontsource" / "poppins" / "files" / name, assets / "fonts" / name)
    shutil.copyfile(rdir / "audio" / "mix.wav", assets / "mix.wav")

    theme = cfg["themes"][script.format]
    (video / "index.html").write_text(build_html(script, tl, theme, cfg["video"], script.title), encoding="utf-8")
    if not (video / "hyperframes.json").exists():
        write_json(video / "hyperframes.json", {
            "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
            "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}})
        write_json(video / "meta.json", {"id": rdir.name, "name": script.title, "createdAt": now()})
        write_json(video / "package.json", {
            "name": rdir.name, "private": True, "type": "module",
            "scripts": {"dev": f"npx --yes hyperframes@{HF_VERSION} preview",
                        "check": f"npx --yes hyperframes@{HF_VERSION} check",
                        "render": f"npx --yes hyperframes@{HF_VERSION} render"}})
    return {"scenes": len(tl["scenes"]), "captions": len(tl["captions"]), "duration_s": tl["duration"],
            "theme": script.format}
