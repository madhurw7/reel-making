# Reel pipeline

Makes faceless, animated Instagram Reels / YouTube Shorts (1080x1920) in English or Hinglish, entirely on this Mac.

```
idea.json ──► script ──► voice ──► sound ──► compose ──► render ──► final/reel.mp4
 (captured)   Ollama     Maya 2    music+SFX   HTML scenes  HyperFrames
              LLM        TTS       ducked mix  (templates)  + ffmpeg mux
```

Every reel lives in its own folder under `reels/` with all inputs, intermediate files and outputs.

## Quick start

```bash
cd /Users/madhurwadhwa/reel-making
source .venv/bin/activate            # gives you the `reel` command

reel idea new --file my_idea.json    # or --title/--essence/--format/... flags; see "Idea structure"
reel idea list
reel run <idea-id>                   # writes the script, then stops so you can review it
#   review reels/<date>-<idea-id>/script.md, edit script.json if needed
reel run <reel>                      # voice -> sound -> compose -> render
open reels/<reel>/final/reel.mp4
```

`reel run <idea-id> --auto` does everything without the review stop. `<reel>` can be any unique part of the folder
name. Other commands:

| Command | What it does |
|---|---|
| `reel script\|voice\|sound\|compose\|render <reel>` | Run one stage |
| `reel run <reel> --from sound` | Redo from a stage |
| `reel render <reel> --draft` | Fast low-quality render to `final/reel_draft.mp4` |
| `reel preview <reel>` | Open the reel in the HyperFrames Studio preview (local editor, Ctrl-C to stop) |
| `reel check <reel> --at 2,8,15` | Lint/layout checks plus PNG frames at those seconds |
| `reel sound <reel> --music new-shoes` | Re-mix with a specific track (`none` for no music) |
| `reel status` | Stage status of every reel |
| `reel hn capture` | Download the top 3 Hacker News stories and draft an idea for each with the local model |
| `reel hn fetch` / `reel hn ideate <folder>` | Only download / only (re)draft one downloaded story |
| `reel idea validate <id-or-file>` | Check an idea file against the idea structure |
| `reel eval-models --models a b` | Compare script models on the ideas in `ideas/` |
| `reel unload` | Unload Ollama models to free memory |

## Capturing ideas from Hacker News

In Claude Code, run `/hn-ideas` (skill in `.claude/skills/hn-ideas/`). It does three things:

1. **Download (no model).** The current top 3 stories, each article (plain HTTP, headless Chrome for JavaScript
   pages, PDFs via pypdf) and the top comments go to `sources/hackernews/<date>-<id>/`: `story.json`,
   `article.txt`, `comments.json`. Reader-comment sections on blog pages are trimmed off.
2. **Draft (local model).** `gemma4:12b` digests the article (facts, numbers, who is who, jargon), keeps only
   comments that teach something or add a different view, and writes `ideas/hn-<id>-<slug>.json` with
   `status: "draft"`. The untouched draft is also kept at `<source>/idea.local.json`.
3. **Edit (Claude Sonnet, xhigh effort).** One editor per draft reads `docs/claude-style-guide.md`, the article,
   the comments and the draft; checks every fact against the article; sharpens the hook, take, analogies and
   takeaway for our viewer; and sets `status: "reviewed"` with a `review` block listing changes and open concerns.

Steps 1 and 2 also run on their own from a terminal: `reel hn capture`. Settings (story count, comments read, the
audience description given to the local model) are under `[ideation]` in `config.toml`.

`docs/claude-style-guide.md` defines who the reels are for and what a good one looks like. It is meant to change:
tell Claude what you liked or disliked about an idea or reel and it updates the guide (with a changelog line).

## Idea structure

Whatever the capture source turns out to be, it must produce this structure (`ideas/<id>.json`; JSON Schema in
`schemas/idea.schema.json`; three samples in `ideas/`).

| Field | Meaning |
|---|---|
| `id` | Slug, unique among ideas |
| `title` | Working title |
| `essence` | The core of the reel in 1-2 sentences: the single thing a viewer walks away with |
| `format` | `educational` (teaches one concept), `story` (narrative with a turn) or `trivia` (questions the viewer tries to answer) |
| `language` | `hinglish` or `english` |
| `audience.who` | Who the reel is for, concretely |
| `audience.knowledge_level` | `beginner`, `intermediate` or `expert` |
| `audience.why_they_care` | The itch it scratches: curiosity, usefulness, emotion |
| `hook` | Opening angle: the question, surprise or stake that stops the scroll |
| `angle` | The take that makes the reel ours: the quirky, relatable way into the topic |
| `background` | What the viewer must know first, assuming no prior knowledge |
| `analogies` | Everyday comparisons that make the idea click |
| `so_what` | Why it matters to the viewer's own life, money, job or phone |
| `share_line` | The one line the viewer can repeat to a friend |
| `key_points` | Facts to teach / plot beats in order / questions with options and answers. The script may only use facts given here or in `essence`, so this is where accuracy is decided |
| `tone` | e.g. curious, playful, dramatic |
| `target_duration_s` | 12 to 90 |
| `cta` | Closing call to action (empty = generic follow line) |
| `visual_notes` | Optional hints for the visuals |
| `references` | Links for fact-checking |
| `perspectives` | Points from the discussion around the source (e.g. HN comments) that teach or add a view: `point`, `kind` (explains, context, correction, experience, counterpoint, new_angle), `origin`, `verified` (true only if the article supports it; otherwise it is an opinion) |
| `digest` | Everything captured from the source article: `summary`, `facts`, `numbers`, `entities`, `glossary`, `truncated` |
| `review` | The editor pass: `by`, `at`, `style_guide_version`, `changes`, `concerns` |
| `tags` | Free-form labels |
| `source` | `type` (manual, hackernews, url, ...), `ref`, `url`, `title`, `material` (folder with the downloaded source), `raw`, `captured_at`, `meta` |
| `status` | `draft` (local model) → `reviewed` (Claude editor) → `approved` (you) → `in_production` → `published`; or `captured` for hand-written ideas, `rejected` for skipped ones |
| `notes` | Anything else |

Only `id`, `title`, `essence`, `format` and `audience.who` are required; everything else has a default. The script
stage uses `hook`, `angle`, `background`, `key_points`, `analogies`, `so_what`, `share_line`, up to two
non-verified perspectives (as "some people say") and the glossary.

## Reel folder

```
reels/2026-11-16-aasman-neela-kyun-hai/
  reel.json            stage status, timings, model and settings used
  idea.json            copy of the idea as it was when the reel started
  script.json          the script: one beat = narration + on-screen content   (edit this)
  script.md            readable view of script.json                            (regenerated)
  audio/
    beats/NN-hash.wav  one Maya clip per beat (reused if the line did not change)
    voice.wav          all beats placed on the timeline
    timeline.json      scene windows, caption chunks, sound-effect cues (drives both mix and video)
    music_bed.wav      the music as mixed (ducked)       sfx.wav   the effects layer
    mix.wav            final audio: voice + music + effects, loudness-normalised
  video/               HyperFrames project: index.html + assets/ (open with `reel preview`)
  final/
    reel.mp4           the deliverable         cover.jpg   a frame for the thumbnail
    caption.txt        post caption and hashtags
  logs/
```

## Stages

**Script** (`reelkit/script.py`). Two passes with the local model: (1) write beats: scene type, spoken line,
on-screen heading/items/emoji; (2) for Hinglish, transliterate each spoken line to Devanagari for Maya, because Maya
pronounces Devanagari properly. So each beat has `narration` (Roman, shown as captions) and `tts` (what is spoken).
The stage warns about length, plain-English lines in a Hinglish reel, and voice text that drifted from the narration.
Read the script before recording: small models make grammar slips, and facts are only as good as `key_points`.

**Voice** (`reelkit/voice.py`, `reelkit/maya_worker.py`). Loads Maya once inside
`/Users/madhurwadhwa/local-audio/.venv-maya2` and speaks each beat separately. Knowing each beat's exact length is
what makes sync trivial. Voices are set per language in `config.toml` (Hinglish: Ritvik; English: Abhay).

**Sound** (`reelkit/sound.py`). Picks a music bed by format, sets it about 21 dB under the voice and a further 5 dB
down while the voice is speaking, adds effects at scene changes, list items, quiz countdown and reveals, then
normalises to -14 LUFS. All levels are in `config.toml` under `[sound]`.

**Compose** (`reelkit/compose.py`). Writes `video/index.html`: one `<section>` per beat with its start and duration,
caption chunks, and the mix as the audio track. Scene types: `hook`, `statement`, `bullets`, `stat`, `compare`,
`quiz` (with countdown), `answer`, `story`, `outro`. Colours per format are in `config.toml` under `[themes]`; set
`[video] handle` to show your channel name.

**Render** (`reelkit/render.py`). HyperFrames renders the frames; ffmpeg puts `audio/mix.wav` on top.

## Editing a reel

- Words or facts: edit `script.json`, then `reel run <reel>`. Only changed lines are re-spoken.
- Look, layout, motion of one reel: `reel preview <reel>` (Studio), or edit `video/index.html`, then
  `reel render <reel>`. Do not run `reel compose` afterwards; it regenerates the file.
- A bespoke pass by Claude Code: open this folder in Claude Code and ask it to polish `reels/<reel>/video`.
  `CLAUDE.md` holds the rules. Installing the HyperFrames skills first helps: `npx hyperframes skills update`.
- Look of every future reel: `templates/reel.css` and `templates/reel.js`.

## Music and sound effects

`assets/music/` holds nine CC0 (public domain) tracks from OpenGameArt by HoliznaCC0, Snabisch and omfgdude;
`assets/music/index.json` lists title, artist, source page and which formats each is used for. The format tags were
assigned from titles, not by ear: listen and retag. To add music, drop a file in and add an entry.
`assets/sfx/` holds six effects synthesised by `reelkit/sfx.py` (whoosh, pop, tick, ding, thud, sparkle). Replace any
of them with a file of the same name to use your own.

## Requirements already set up

Python venv `.venv` (reelkit), `node_modules` (hyperframes 0.9.56, gsap, Poppins font), ffmpeg, Ollama with the
script model, and the Maya setup in `/Users/madhurwadhwa/local-audio`. To rebuild: `uv venv .venv --python 3.12 &&
uv pip install --python .venv/bin/python -e . && npm install`.

## Script model: what was compared and what to use

Measured on this Mac (M2 Pro, 16 GB) with `reel eval-models` on the three sample ideas; the full scripts are in
`eval/20261116-200652/`.

| Model (Ollama tag) | Size | Speed | Hinglish | Follows the brief | Verdict |
|---|---|---|---|---|---|
| `gemma4:12b` | 7.7 GB | 13-24 tok/s, 70-96 s per script | Natural, correct grammar; transliteration to Devanagari is accurate | Uses the given facts, hits length, good scene choice; 0 warnings on both Hinglish ideas | **Default** |
| `qwen3:8b` | 5.2 GB | 25 tok/s, 50-78 s | Often falls back to plain English; grammar slips ("kar deta hai"); sometimes translates instead of transliterating | Scripts come out about 40% short; one run timed out | Fallback when memory is tight |
| `qwen3:4b` | 2.5 GB | 40 tok/s, 23-76 s | Broken | Invented facts ("300 million dollars") | Do not use |

Not tested, with reasons: Sarvam 30B (the only Indian-built open model) needs about 19 GB at 4-bit, so it does not
fit; `qwen3:14b` and `gemma4:26b` leave too little room on 16 GB. Worth trying next with the same command: any new
8-12B multilingual model, e.g. `reel eval-models --models gemma4:12b <new-tag>`.

Notes: `gemma4:12b` on Ollama cannot do schema-constrained output ("structured output is unavailable"), so
`reelkit/llm.py` falls back to putting the JSON Schema in the prompt and validating the reply. English scripts tend to
come out shorter than their word budget. The budget comes from each voice's measured speaking rate
(`words_per_second` under `[voice.hinglish]` / `[voice.english]`): Ritvik speaks Hinglish at 3.7 words/s, Abhay
speaks English at 2.1.

## Video: why HTML and not a video model

MiniMax H3 (open weights, about 42 GB, practical minimum a 24 GB NVIDIA card) does not run on this Mac, and the video
models that do run on Apple Silicon take on the order of an hour for a few seconds of footage. HyperFrames
(Apache-2.0, by HeyGen) renders HTML/CSS/GSAP to MP4 with headless Chrome and ffmpeg; a 31 s reel renders in 20-40 s
here. Its usage telemetry was switched off (`hyperframes telemetry disable`; re-enable with `... enable`).

`reel check` reports some warnings that are accepted on purpose: `nested_structure_needs_subcomposition` /
`timeline_track_too_dense` (one file per reel is easier to hand-edit than one file per scene) and TikTok / YouTube
right-edge safe-zone notes for centred titles in the upper half, above where those apps draw their buttons.

## Speed and memory on this machine

One model at a time. Maya holds about 11 GB while speaking, the script model 8 GB. The first reel measured:
script 114 s, voice 17 min for 28 s of speech (Maya ran 6x to 100x slower than real time because memory was full:
a virtual machine and Chrome were holding about 9 GB), sound 2 s, render 21-38 s. With memory free, the Maya runbook's
figure is about 2x real time, i.e. about a minute of voice work per reel.
Before a voice run: quit heavy apps (virtual machines, Chrome, IDEs), check with `top -o mem`, and run
`reel run ...` from your own terminal (it has no 10-minute limit).

## Known limits

- Caption timing inside a beat is estimated from text length (each beat's start is exact). Word-accurate captions
  would need forced alignment, e.g. `hyperframes transcribe`.
- Visuals are text, emoji, shapes and numbers. There are no illustrations or footage yet.
- Facts are not checked. The script may only use what the idea provides, so check `key_points` and read `script.md`.
- Music tags were not assigned by ear. Sound-effect and music levels are a starting point; tune `[sound]`.
