"""Data shapes: the captured idea and the generated script. JSON Schemas are exported to schemas/."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

Format = Literal["educational", "story", "trivia"]
Language = Literal["english", "hinglish"]
Scene = Literal["hook", "statement", "bullets", "stat", "compare", "quiz", "answer", "story", "outro"]
SCENES = ("hook", "statement", "bullets", "stat", "compare", "quiz", "answer", "story", "outro")


# ---------------------------------------------------------------- idea

class Audience(BaseModel):
    who: str = Field(description="Who this reel is for, concretely. e.g. 'college students curious about space'")
    knowledge_level: Literal["beginner", "intermediate", "expert"] = "beginner"
    why_they_care: str = Field("", description="The itch this scratches for them: curiosity, usefulness, emotion")


class Source(BaseModel):
    type: str = Field("manual", description="Where the idea came from: manual, hackernews, url, book, video, ...")
    ref: str = Field("", description="Link, title or pointer to the source (for Hacker News: the discussion page)")
    url: str = Field("", description="The article or page the idea is based on")
    title: str = Field("", description="Title of the source as published")
    material: str = Field("", description="Folder holding the downloaded source: article text, comments, digest")
    raw: str = Field("", description="Original snippet as captured, before it was shaped into an idea")
    captured_at: str = ""
    meta: dict = Field(default_factory=dict, description="Source-specific extras, e.g. HN id, points, comment count")


class GlossaryItem(BaseModel):
    term: str
    meaning: str = Field(description="One plain sentence a non-technical viewer understands")


class SourceDigest(BaseModel):
    """Everything worth keeping from the source, so the idea can be reworked without re-reading the article."""
    summary: str = Field("", description="What the article says, in 4-8 plain sentences")
    facts: list[str] = Field(default_factory=list, description="Every checkable claim the article makes, one per line")
    numbers: list[str] = Field(default_factory=list, description="Figures with their unit and what they measure")
    entities: list[str] = Field(default_factory=list, description="People, companies, products, places: 'Name: who/what'")
    glossary: list[GlossaryItem] = Field(default_factory=list, description="Jargon the viewer will not know")
    truncated: bool = Field(False, description="True if the article was longer than what was processed")


class Perspective(BaseModel):
    """A point from the discussion around the source (e.g. a Hacker News comment) that adds something."""
    point: str = Field(description="The point, paraphrased in plain language")
    kind: Literal["explains", "new_angle", "counterpoint", "experience", "correction", "context"] = "new_angle"
    origin: str = Field("", description="Where it came from, e.g. 'HN comment 4123456 by someuser'")
    verified: bool = Field(False, description="True only if the article itself (or a cited source) supports it; "
                                              "unverified points are opinions and must be presented as such")


class Review(BaseModel):
    """Editor pass over a machine-drafted idea."""
    by: str = Field("", description="Who reviewed: model name or person")
    at: str = ""
    style_guide_version: str = ""
    changes: list[str] = Field(default_factory=list, description="What was changed and why, one line each")
    concerns: list[str] = Field(default_factory=list, description="Open doubts a human should settle before production")


class Idea(BaseModel):
    """One reel idea. Every capture source produces this same structure."""
    id: str = Field(description="Slug, unique among ideas")
    title: str = Field(description="Working title")
    essence: str = Field(description="The core of the reel in 1-2 sentences: the single thing a viewer walks away with")
    format: Format = Field(description="educational = teaches one concept; story = narrative with a turn; "
                                       "trivia = question(s) the viewer tries to answer")
    language: Language = "hinglish"
    audience: Audience
    hook: str = Field("", description="Opening angle: the question, surprise or stake that stops the scroll")
    angle: str = Field("", description="The take that makes this reel ours: the quirky, relatable way into the topic")
    background: str = Field("", description="What the viewer must know first, assuming no prior knowledge")
    analogies: list[str] = Field(default_factory=list,
                                 description="Everyday comparisons that make the idea click (chai stall, cricket, ...)")
    so_what: str = Field("", description="Why this matters to the viewer's own life, money, job or phone")
    share_line: str = Field("", description="The one line the viewer can repeat to a friend to sound in the loop")
    key_points: list[str] = Field(default_factory=list,
                                  description="Facts to teach / plot beats in order / trivia questions with answers. "
                                              "The script may only use facts listed here or in essence")
    tone: str = Field("curious", description="e.g. curious, playful, dramatic, calm, funny")
    target_duration_s: int = Field(35, ge=12, le=90)
    cta: str = Field("", description="Closing call to action; empty = a generic follow line")
    visual_notes: str = Field("", description="Optional hints for the visuals")
    references: list[str] = Field(default_factory=list, description="Links for fact-checking")
    perspectives: list[Perspective] = Field(default_factory=list,
                                            description="Points from the discussion that teach or add a new view")
    digest: SourceDigest | None = Field(None, description="Everything captured from the source article")
    review: Review | None = None
    tags: list[str] = Field(default_factory=list)
    source: Source = Field(default_factory=Source)
    status: Literal["draft", "reviewed", "captured", "approved", "in_production", "published", "rejected"] = "captured"
    notes: str = ""
    created_at: str = ""


# ---------------------------------------------------------------- script

class LLMBeat(BaseModel):
    """What the script model writes for each beat. All fields are required so small models stay on rails."""
    scene: Scene
    narration: str
    heading: str
    emoji: str
    items: list[str]
    value: str
    answer_index: int


class LLMScript(BaseModel):
    title: str
    beats: list[LLMBeat]
    caption: str
    hashtags: list[str]


class Beat(BaseModel):
    id: int
    scene: Scene
    narration: str = Field(description="Spoken line in the on-screen script (Roman letters); drives captions")
    tts: str = Field("", description="The same line as sent to Maya (Devanagari for Hinglish)")
    heading: str = Field("", description="Short on-screen text")
    emoji: str = ""
    items: list[str] = Field(default_factory=list, description="bullets: 2-4 points; compare: 2 sides; quiz: options")
    value: str = Field("", description="stat scene: the big number, e.g. '8 minute', '70%'")
    answer_index: int = Field(-1, description="quiz scene: index of the correct option")


class Script(BaseModel):
    title: str
    language: Language
    format: Format
    beats: list[Beat]
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    model: str = ""
    generated_at: str = ""

    def words(self) -> int:
        return sum(len(b.narration.split()) for b in self.beats)


DEFAULT_EMOJI = {"hook": "🤯", "statement": "💡", "bullets": "📌", "stat": "📊", "compare": "⚖️",
                 "quiz": "❓", "answer": "✅", "story": "📖", "outro": "🔔"}
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿⌀-⏿]"
                       "[️‍\U0001F3FB-\U0001F3FF\U0001F000-\U0001FAFF☀-➿]*")


def first_emoji(text: str, fallback: str) -> str:
    m = _EMOJI_RE.search(text or "")
    return m.group(0) if m else fallback


def clean_beats(raw: list[LLMBeat]) -> list[Beat]:
    """Make the model's beats safe for the scene templates: every scene gets the fields it needs, or is downgraded."""
    beats: list[Beat] = []
    seen_quiz = False
    for i, b in enumerate(raw, 1):
        scene = b.scene
        items = [re.sub(r"^\s*(?:[A-Da-d1-4][).:]|[-•*])\s*", "", s).strip() for s in b.items if s and s.strip()][:4]
        value = b.value.strip()
        answer = b.answer_index
        if scene == "bullets" and len(items) < 2:
            scene = "statement"
        if scene == "compare":
            items = items[:2]
            if len(items) < 2:
                scene = "statement"
        if scene == "quiz":
            if len(items) < 2 or not 0 <= answer < len(items):
                scene = "statement"
            else:
                seen_quiz = True
                if "?" not in b.heading and "?" in b.narration and len(b.narration) <= 64:
                    b = b.model_copy(update={"heading": b.narration})       # the screen shows the question itself
        if scene == "answer" and not seen_quiz:
            scene = "statement"
        if scene == "stat" and not value:
            scene = "statement"
        if scene not in ("bullets", "compare", "quiz"):
            items = []
        beats.append(Beat(
            id=i, scene=scene, narration=" ".join(b.narration.split()),
            heading=" ".join(b.heading.split())[:70],
            emoji=first_emoji(b.emoji, DEFAULT_EMOJI[scene]),
            items=[s[:60] for s in items],
            value=value[:18] if scene == "stat" else "",
            answer_index=answer if scene == "quiz" else -1,
        ))
    if beats and beats[0].scene not in ("hook", "quiz"):
        beats[0].scene = "hook"
        beats[0].items, beats[0].value = [], ""
    return beats
