"""Stage 1: idea.json -> script.json with a local model (two passes: write the beats, then Devanagari for Maya)."""
from __future__ import annotations

import re

from . import llm
from .config import now
from .models import Idea, LLMScript, Script, clean_beats

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")

LANG_RULES = {
    "hinglish": (
        "LANGUAGE: Hinglish. That means natural spoken Hindi mixed with everyday English words, the way young urban "
        "Indians talk, written ONLY in Roman (Latin) letters. Never use Devanagari letters.\n"
        "The idea below is written in English. Do NOT copy its English sentences. Say the same facts in Hinglish: "
        "Hindi grammar and connecting words (hai, ka, ki, ko, mein, se, aur, lekin, kyunki, toh), with English kept "
        "for nouns and technical terms.\n"
        "Examples of turning an English fact into Hinglish narration:\n"
        '- "Sunlight looks white but is a mix of all colours." -> "Sunlight white dikhti hai, lekin asal mein ye '
        'saare colours ka mix hai."\n'
        '- "Venus takes 243 Earth days to spin once." -> "Venus ko ek baar ghoomne mein 243 Earth days lagte hain."\n'
        '- "He escaped with the money." -> "Aur woh saara paisa lekar faraar ho gaya."\n'
        "On-screen text (heading, items) is short Roman Hinglish or simple English."
    ),
    "english": (
        "LANGUAGE: English. Simple, clear, friendly spoken English that an Indian audience follows easily. "
        "No Hindi words."
    ),
}

FORMAT_RULES = {
    "educational": (
        "FORMAT: educational. Teach ONE idea. Shape: hook -> the idea explained in 3 to 5 small steps "
        "(use statement, bullets, stat or compare scenes) -> one-line takeaway -> outro."
    ),
    "story": (
        "FORMAT: story. Tell it as a narrative. Shape: hook that opens in the middle of the action -> story scenes that "
        "build tension, one event per beat -> the turn or reveal -> what it means in one line -> outro."
    ),
    "trivia": (
        "FORMAT: trivia. Shape: hook that challenges the viewer -> a quiz scene (the narration reads the question; "
        "items are the options) -> an answer scene (the narration gives the answer and one surprising reason) -> "
        "repeat quiz + answer if there are more questions -> outro."
    ),
}

SYSTEM = """You write scripts for short vertical videos (Instagram Reels, YouTube Shorts).
The video has no presenter. It is animated motion graphics with a voice-over.
You answer with JSON only.

A script is a list of beats. One beat = one or two short spoken sentences ("narration") plus what the screen shows.

{lang}

{fmt}

NARRATION RULES
- Spoken and conversational. Short sentences. At most 20 words per beat.
- Whole script: about {words} words of narration ({lo} to {hi}), in {beats_lo} to {beats_hi} beats.
- Beat 1 is the hook: a question, a surprising claim or a stake, in 12 words or fewer. No greeting, no "in this video".
- Use only the facts given in the idea. Do not invent numbers, names or dates.
- Narration is plain text for a voice: no emojis, no hashtags, no brackets, no stage directions.
- The last beat is the outro: one short line asking the viewer to follow.

SCENES. Pick the one that matches what the narration is saying. Vary them: use statement at most twice, and
prefer bullets when the line lists things, stat when it gives a number, compare when it contrasts two things:
- hook: big headline. heading = 3 to 6 punchy words.
- statement: one idea. heading = the idea in 3 to 8 words.
- bullets: a list. heading = list title; items = 2 to 4 points of 2 to 5 words each.
- stat: one big number. value = the number with its unit (e.g. "8 minute", "70%"); heading = what the number means.
- compare: two things side by side. heading = the contrast; items = exactly 2 short labels.
- quiz: a question for the viewer. heading = the question; items = 2 to 4 options; answer_index = position of the
  correct option, counting from 0.
- answer: reveals the quiz answer. heading = the correct answer in a few words.
- story: a story moment. heading = the moment in 3 to 7 words.
- outro: the closing line. heading = 2 to 4 words like "Follow for more".

FIELDS in every beat
- scene, narration, heading as above.
- emoji: exactly one emoji that pictures this beat.
- items: [] unless the scene is bullets, compare or quiz.
- value: "" unless the scene is stat.
- answer_index: -1 unless the scene is quiz.

Also return: title (short), caption (1 to 2 sentences for the post, same language), hashtags (4 to 6, without #)."""

TTS_SYSTEM = """You rewrite Roman-script Hinglish lines in Devanagari script for a Hindi text-to-speech engine.
This is TRANSLITERATION, not translation: the voice must say exactly the same words, only the letters change.

Rules:
- Keep every word and the word order. Never replace an English word with a Hindi word.
  If the line says "light", write "लाइट", never "प्रकाश" or "रोशनी". If it says "sky", write "स्काई", never "आकाश".
- Hindi words: correct Devanagari spelling (kyun -> क्यों, nahin -> नहीं, hai -> है, zyada -> ज़्यादा).
- English words: write how they sound (internet -> इंटरनेट, science -> साइंस, follow -> फॉलो, scatter -> स्कैटर).
- Numbers and symbols: write them out as Hindi words (10 -> दस, 25 -> पच्चीस, 70% -> सत्तर प्रतिशत, 1925 -> उन्नीस सौ पच्चीस).
- The output has no Latin letters and no digits. Keep punctuation (? , !) and end sentences with । or ?
- Do not number the lines.

Examples:
"Sunlight white dikhti hai, lekin ye saare colours ka mix hai." -> "सनलाइट व्हाइट दिखती है, लेकिन ये सारे कलर्स का मिक्स है।"
"Blue light 10 guna zyada scatter hoti hai." -> "ब्लू लाइट दस गुना ज़्यादा स्कैटर होती है।"
"Follow karo, aise hi aur science facts ke liye!" -> "फॉलो करो, ऐसे ही और साइंस फैक्ट्स के लिए!"

Return JSON: {"lines": [...]} with exactly the same number of lines, in the same order."""


# Hindi function words that are not also English words ("is", "to", "the", "me", "us" are left out on purpose).
HINDI_WORDS = set("""hai hain tha thi hota hoti hote ka ki ke ko mein aur lekin kyun kyunki toh bhi nahi nahin kya
ye yeh woh iska iske iski uska uske uski ek aap tum jab kaise kitna kitne liye wala wali karo karte karta raha rahi
rahe gaya gayi diya liya bahut zyada phir sirf apna apne apni yahan wahan hota hua hui hue tak agar kuch""".split())


def is_hinglish(line: str) -> bool:
    """True when a Roman-script line has Hindi function words in it (i.e. it is not plain English)."""
    words = re.findall(r"[a-z]+", line.lower())
    return sum(w in HINDI_WORDS for w in words) >= max(1, len(words) // 8)


def budget(idea: Idea, wps: float) -> dict:
    words = int(round(idea.target_duration_s * wps * 0.9))          # ~10% of the runtime is pauses
    beats = max(4, round(idea.target_duration_s / 5))
    return {"words": words, "lo": int(words * 0.8), "hi": int(words * 1.15),
            "beats_lo": max(4, beats - 1), "beats_hi": beats + 2}


def idea_brief(idea: Idea) -> str:
    lines = [
        f"TITLE: {idea.title}",
        f"ESSENCE (the one thing the viewer must walk away with): {idea.essence}",
        f"AUDIENCE: {idea.audience.who} (level: {idea.audience.knowledge_level})",
    ]
    if idea.audience.why_they_care:
        lines.append(f"WHY THEY CARE: {idea.audience.why_they_care}")
    if idea.hook:
        lines.append(f"HOOK ANGLE: {idea.hook}")
    if idea.angle:
        lines.append(f"OUR TAKE (the flavour of the whole reel): {idea.angle}")
    if idea.background:
        lines.append(f"BACKGROUND THE VIEWER NEEDS FIRST: {idea.background}")
    if idea.key_points:
        lines.append("KEY POINTS (use these facts, in this order):\n" + "\n".join(f"- {p}" for p in idea.key_points))
    if idea.analogies:
        lines.append("ANALOGIES (use at least one, in your own words):\n" + "\n".join(f"- {a}" for a in idea.analogies))
    if idea.so_what:
        lines.append(f"WHY IT MATTERS TO THE VIEWER (say this near the end): {idea.so_what}")
    if idea.share_line:
        lines.append(f"LINE THE VIEWER SHOULD REMEMBER: {idea.share_line}")
    views = [p for p in idea.perspectives if p.kind in ("counterpoint", "new_angle", "experience", "correction")][:2]
    if views:
        lines.append("OTHER VIEWS (optional, at most one beat; these are opinions, so say 'kuch log kehte hain' / "
                     "'some people argue'):\n" + "\n".join(f"- {p.point}" for p in views))
    if idea.digest and idea.digest.glossary:
        lines.append("PLAIN MEANINGS (use these instead of jargon):\n" +
                     "\n".join(f"- {g.term}: {g.meaning}" for g in idea.digest.glossary[:6]))
    lines.append(f"TONE: {idea.tone}")
    lines.append(f"CALL TO ACTION: {idea.cta or 'ask them to follow for more like this'}")
    if idea.visual_notes:
        lines.append(f"VISUAL NOTES: {idea.visual_notes}")
    return "\n".join(lines)


def _problems(script: LLMScript, idea: Idea, b: dict) -> list[str]:
    out = []
    words = sum(len(x.narration.split()) for x in script.beats)
    if words < b["lo"] * 0.9:
        out.append(f"The narration has {words} words. It must have about {b['words']}. Add detail from the key points.")
    if words > b["hi"] * 1.05:
        out.append(f"The narration has {words} words. It must have about {b['words']}. Cut it down.")
    if len(script.beats) < 3:
        out.append("There are too few beats.")
    if idea.language == "hinglish":
        if any(DEVANAGARI.search(x.narration + x.heading) for x in script.beats):
            out.append("Some text uses Devanagari letters. Write everything in Roman letters only.")
        english = [i for i, x in enumerate(script.beats, 1) if not is_hinglish(x.narration)]
        if english:
            out.append(f"The narration of beats {english} is plain English. Rewrite those lines in Hinglish "
                       f"(Hindi sentence structure with words like hai, ka, mein, aur, lekin; English only for key terms).")
    long = [i for i, x in enumerate(script.beats, 1) if len(x.narration.split()) > 28]
    if long:
        out.append(f"Beats {long} are too long. Split them or shorten to 20 words.")
    return out


def write_beats(idea: Idea, cfg: dict, model: str, wps: float):
    b = budget(idea, wps)
    system = SYSTEM.format(lang=LANG_RULES[idea.language], fmt=FORMAT_RULES[idea.format], **b)
    user = "Write the script for this idea.\n\n" + idea_brief(idea)
    schema = LLMScript.model_json_schema()
    stats, best, best_issues = [], None, None
    for attempt in range(2):
        data, st = llm.chat_json(cfg, model, system, user, schema)
        stats.append(st)
        try:
            cand = LLMScript.model_validate(data)
        except ValueError as e:                              # only possible when the model ignores the schema
            if attempt == 1 and best is None:
                raise llm.LLMError(f"{model} did not return a valid script: {str(e)[:300]}") from e
            continue
        issues = _problems(cand, idea, b)
        off = lambda c: abs(sum(len(x.narration.split()) for x in c.beats) - b["words"])
        if best is None or (len(issues), off(cand)) < (len(best_issues), off(best)):   # fewer problems, then closer length
            best, best_issues = cand, issues
        if not issues:
            break
        user = ("Write the script for this idea.\n\n" + idea_brief(idea) +
                "\n\nYour previous attempt had these problems. Fix them:\n" + "\n".join(f"- {i}" for i in issues))
    return best, best_issues, stats, b


def _strip_no(line: str) -> str:
    return re.sub(r"^\s*\d+[.)]\s*", "", line).strip().strip('"')


def _tts_ok(line: str, src: str = "") -> bool:
    if not DEVANAGARI.search(line) or LATIN.search(line) or re.search(r"\d", line):
        return False
    if src and not re.search(r"\d", src):                 # same words in, same words out (numbers may expand)
        a, b = len(src.split()), len(line.split())
        return abs(a - b) <= max(2, round(a * 0.3))
    return True


def to_devanagari(lines: list[str], cfg: dict, model: str):
    """Roman Hinglish -> Devanagari, validated line by line; bad lines are retried on their own."""
    schema = {"type": "object", "required": ["lines"],
              "properties": {"lines": {"type": "array", "items": {"type": "string"},
                                       "minItems": len(lines), "maxItems": len(lines)}}}
    user = "Convert these lines:\n" + "\n".join(f'"{s}"' for s in lines)
    data, st = llm.chat_json(cfg, model, TTS_SYSTEM, user, schema, temperature=0.1)
    stats = [st]
    out = [_strip_no(s) for s in data.get("lines", [])]
    out = (out + [""] * len(lines))[: len(lines)]
    one = {"type": "object", "required": ["lines"],
           "properties": {"lines": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 1}}}
    bad = []
    for i, src in enumerate(lines):
        for _ in range(2):
            if _tts_ok(out[i], src):
                break
            data, st = llm.chat_json(cfg, model, TTS_SYSTEM, f'Convert this one line:\n"{src}"', one, temperature=0.2)
            stats.append(st)
            out[i] = _strip_no((data.get("lines") or [""])[0])
        if not _tts_ok(out[i], src):
            bad.append(i + 1)
    return out, bad, stats


def generate(idea: Idea, cfg: dict, model: str | None = None, wps: float = 3.0):
    """-> (Script, report). The report lists anything a human should look at before recording the voice.
    `wps` is the voice's speaking rate in words per second for this language (config: [voice.<language>])."""
    model = model or cfg["model"]
    raw, issues, stats, b = write_beats(idea, cfg, model, wps)
    beats = clean_beats(raw.beats)
    warnings = list(issues)
    if idea.language == "hinglish":
        lines, bad, st2 = to_devanagari([x.narration for x in beats], cfg, model)
        stats += st2
        for beat, line in zip(beats, lines):
            beat.tts = line
        if bad:
            warnings.append(f"Beats {bad}: check the Devanagari voice text (`tts`): Latin letters, digits, or words that differ from the narration.")
    else:
        for beat in beats:
            beat.tts = beat.narration
    script = Script(title=raw.title.strip() or idea.title, language=idea.language, format=idea.format, beats=beats,
                    caption=raw.caption.strip(), hashtags=[h.lstrip("#").strip() for h in raw.hashtags if h.strip()][:8],
                    model=model, generated_at=now())
    report = {
        "model": model, "words": script.words(), "word_budget": b["words"], "beats": len(beats),
        "est_duration_s": round(script.words() / wps / 0.9, 1),
        "llm_calls": len(stats), "wall_s": round(sum(s["wall_s"] for s in stats), 1),
        "tokens_per_s": round(sum(s["tokens_per_s"] for s in stats) / len(stats), 1),
        "warnings": warnings,
    }
    return script, report


def to_markdown(script: Script) -> str:
    """Human-readable view of script.json for review."""
    out = [f"# {script.title}", "",
           f"{script.format} · {script.language} · {len(script.beats)} beats · {script.words()} words · model {script.model}",
           ""]
    for b in script.beats:
        out.append(f"## {b.id}. {b.scene} {b.emoji}")
        out.append(f"**On screen:** {b.heading}" + (f" · **{b.value}**" if b.value else ""))
        for i, item in enumerate(b.items):
            out.append(f"- {item}" + ("  ✔" if i == b.answer_index else ""))
        out.append(f"\n**Says:** {b.narration}")
        if b.tts and b.tts != b.narration:
            out.append(f"\n**Voice text:** {b.tts}")
        out.append("")
    out += ["---", f"**Caption:** {script.caption}", "", " ".join("#" + h for h in script.hashtags), ""]
    return "\n".join(out)
