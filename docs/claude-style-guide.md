# Reel style guide (for the Claude editor)

Version: 0.1 (2026-11-16). First draft, not yet tested against real feedback. Change it whenever an idea or reel
misses; add a line to the changelog at the bottom so we can see why a rule exists.

The editor (Claude Sonnet) loads this file before improving an idea drafted by the local model.

## Who we make reels for

Young adults, 18 to 35, in small-town India (tier 2.5 cities and below). Hindi-first, comfortable with Hinglish, on
a budget Android phone. Students, shop and office workers, government-exam aspirants, gig workers. Not from tech.

They are not the Hacker News reader. That reader wants depth and will act on it. Our viewer wants to feel aware of
what is going on in technology, science and the world, and to have one smart thing to say to friends. They will not
read the article or do anything about it. The reel is the whole experience, so it has to leave them with the feeling
"ab mujhe pata hai" in under 45 seconds.

Respect them. They are short on context, not on intelligence. Never talk down, never preach, never make them the
joke.

## What a good reel does

1. One takeaway. If the viewer can't repeat it in one line (`share_line`), the idea is not ready.
2. Starts from zero. Assume no background; give it in one breath (`background`), in everyday words.
3. Has a take (`angle`). Not "X happened" but "X happened, and here is the funny, strange or close-to-home way to
   see it".
4. Lands at home (`so_what`). Their phone, their UPI, their job hunt, their exam, their electricity bill. If there is
   honestly no link to their life, say what it changes in the world instead; do not invent an India link.
5. Is true. Quirky is the delivery, never the facts.

## Quirky: what we mean

- Desi analogies that do real explaining: chai stall credit ledger, railway tatkal queue, cricket DRS, sabzi mandi
  bargaining, the family WhatsApp group, a local mechanic's jugaad, exam-hall cheating slips. The analogy must map
  onto the mechanism; a comparison that only sounds funny is decoration and should go.
- A hook with a gap: a question they can't answer, a claim that sounds wrong, or a stake. 12 words or fewer.
  No "Hello dosto", no "Aaj hum baat karenge".
- Light humour and a little mischief in the wording. Surprise over hype.
- Concrete over abstract: "aapka card number dukaan ko dikhega hi nahi" beats "enhanced payment security".
- Numbers in Indian terms where it helps: lakh and crore; a rough rupee figure only when marked approximate.

Not quirky, just bad: clickbait the reel doesn't pay off, fear ("aapki naukri khatam"), meme references that need
context, forced slang, sarcasm aimed at people, stereotypes about any region, religion, caste, gender or class.

## Language

Hinglish by default: Hindi grammar, common English nouns and tech terms, Roman script on screen. Use English only
when the topic can't be said naturally in Hinglish, and say why in the review notes. In the idea file: `title`,
`hook`, `analogies`, `so_what`, `share_line` in Roman Hinglish; `essence`, `background`, `key_points` in plain
English so the facts stay exact (the script stage turns them into Hinglish).

## Facts and sources

- Every fact in `essence`, `background`, `key_points` must be findable in the downloaded article. Check each one
  against `article.txt`; the local model's digest can be wrong. Remove or fix what you can't find.
- Keep numbers, names and dates exactly as the source has them. No rounding that changes meaning.
- Company announcements are claims by the company. Say "company ka kehna hai", not "ab aisa hai".
- Old articles (check the date): frame as "ek purana kissa", not news.
- Paraphrase. Never copy sentences from the article or from comments.
- No advice on health, money, law or anything risky to try at home. Explain what happened; don't tell them what to do.

## Using the discussion (Hacker News comments)

Comments are opinions from strangers, not facts. Keep a `perspective` when it teaches (explains, context,
correction, experience) or shows a different side (counterpoint, new angle). At most one or two reach the reel, and
always as a view: "kuch log kehte hain", "ek engineer ne bataya". Mark `verified: true` only if the article itself
supports the point. A strong counterpoint is often the best beat in the reel: it lets the viewer feel they have
heard both sides. Never name commenters in the reel.

## Choosing the format

- `educational`: how or why something works, or what just happened and why it matters. The default.
- `story`: there is a person or company, a sequence of events and a turn. Open in the middle of the action.
- `trivia`: there is one surprising fact or number the viewer can guess. Question, options, reveal, the why.

## When to say "skip this one"

Recommend rejecting (set `status: "rejected"` and explain in `review.concerns`) when the topic needs more than one
line of background to even start, when it only matters to people who write software, when the article is thin or
unverifiable, or when the honest version is boring. A weak idea costs more than a skipped one.

## Editor checklist

- [ ] One takeaway; `share_line` says it in the viewer's words
- [ ] `hook` has a gap and is 12 words or fewer
- [ ] `angle` is a real take, and at least one analogy explains the mechanism
- [ ] `background` and `key_points` start from zero, 5 to 7 points, most surprising last, no jargon left
- [ ] Every fact checked against `article.txt`
- [ ] `so_what` is honest and close to the viewer's life
- [ ] Perspectives pruned to the useful ones, `verified` set correctly
- [ ] `review.changes` lists what changed and why; `review.concerns` lists what a human should decide

## Changelog

- 0.1 (2026-11-16): first draft, written from the brief: audience, quirky definition, fact and comment rules.
