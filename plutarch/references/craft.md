# Craft — why these films work, and how to decide

Read this at step 1 (story) and step 5 (writing scenes). The scripts handle timing, sound and drawing.
**You** handle the four things below. A film that passes `check.py` but ignores this page is correct and dull.

## 1. The shape

One person. One risk. What it cost. One turn. Their own words at the end.

| # | beat | scene type | what it must do | seconds |
|---|---|---|---|---|
| 1 | Cold open | `arena` `reveal: hits`, or a `card` that starts with a short clip | Start inside the most alive moment. Real sound, no music, no explanation. | 3-7 |
| 2 | Title | `title` | 2-3 words that name the risk. | 3.4 |
| 3 | Origin | `card` `bg: glow` | Where and when it began. Small and human (a place, a date, a number of people). | 8-10 |
| 4 | The bet | `card` + short clip `big: true` | The moment it could all have ended, in the subject's own words. | 10-16 |
| 5 | The rise | `chart` | One real number growing. Stamps on the milestones. Few words. | 12-22 |
| 6 | The cost | `stack` + one longer clip | The price paid, in the subject's words. Big words land as they are spoken. | 12-24 |
| 7 | The question | `card` + short clip | A short, surprising answer that makes the viewer lean in. | 8-12 |
| 8 | The setback | `card` `bg: pulse` | The turn. Date + plain fact. Then a gap of silence. | 10-20 |
| 9 | The resolution | `arena` `reveal: rise` with `peak` | The payoff line. The room fills with light and erupts on it. | 15-26 |
| 10 | End card | `end` | The title again, plus a second line that answers it. | 6.5 |

The reference film: 11 scenes (two charts), 158.6 s, made for a Premium account. For the normal 140 s limit
use 9-10 scenes and the low end of each range.

**If the subject's life does not fit:** keep 1, 2, 4, 6, 9 and 10. Drop or swap the others. No public setback?
Make beat 8 the hardest decision instead. No crowd recording? Open on a `card` whose only item is the strongest
2-4 s quote (`"music": false`), and end on an `arena` with no `under`. No number worth charting? Replace the
chart with a `card`. Never invent an event to fill a beat.

## 2. Story rules

1. Write the film in one sentence first (`story.md`). If you cannot, you do not have a film yet.
2. **The narrator says facts. The subject says feelings.** Narrator lines carry dates, numbers, names and what
   happened. Anything about fear, doubt, pride or pain must be a real quote. Never have the narrator praise
   the subject ("legendary", "visionary", "changed the world" are banned words).
3. The subject has the last spoken word. Nothing is said after the payoff line.
4. The title comes back on the end card with a second line that changes its meaning. Decide both at step 1.
5. Every fact (date, number, name) has two sources in `story.md`. If two sources disagree, leave the fact out.
6. **A quote goes under the time it is about**, not the time it was recorded. That is what `year` and `about`
   are for. A 2023 quote about a 1997 decision belongs in the 1997 scene, never on a card with a different year.
7. Do not join two quotes to make a sentence that was never said. One clip = one continuous piece of speech.
8. At least half of all speaking time is the subject's real voice (reference: 70 s of real voice, 43 s of narrator).

## 3. Choosing quotes

Search the transcripts with `clip.py find`. Keep a quote only if it passes all of these:

- 1-9 seconds (one longer quote of up to ~20 s is allowed for beat 6).
- Makes sense alone. No "that", "it" or "he" that needs the question before it.
- Has a picture, a number or a feeling in it. "We had six months of cash" beats "it was a difficult period".
- Starts and ends on a clean sentence edge.
- Only this person could have said it.

Aim for 6-10 quotes from 2-4 sources. More than 10 and none of them lands.

## 4. Writing narrator lines and screen text

- Narrator: max 16 words, one fact per line, present or simple past tense, no questions, no adjectives of praise.
  Good: "By the end of that year, they had six months of cash left." Bad: "Little did he know, everything was about to change."
- A scene has at most two narrator lines. A scene with a long quote has none.
- Screen `lines`: max 3 per scene, max 7 words each. They repeat the key fact, they do not add new ones.
- `heading`: a date, a year, or 2-4 capital words.
- `stack` `words`: 3-6 words copied exactly from the clip, in the order spoken. `accent_word` = the heaviest, usually the last.
- Chart: 5-12 real points, `label` says what the number is, `source` says where it is from. Round and say "(APPROX.)".
- One `accent` color for the whole film, chosen for the subject. Everything else stays black, white and grey.

## 5. Sound choices you make (the mixer does the work)

- Cold open: `"music": false` on a card opening; an `arena` opening has no music by default. Real sound first.
- Music enters on the title impact. Leave `energy` alone unless a scene feels wrong:
  low (0.2) under a long emotional quote, high (0.9-1.0) at the end of the rise and at the resolution.
- Put `{"gap": 1.0}` after the setback line and before/after the payoff line. Silence is what makes them land.
- `"under"` + `"drums": true` on the cold open makes drum hits follow the crowd's own rhythm.

## 6. Reading the preview sheet (step 9)

For every scene ask: Can I read the heading in one second? Is any text cut off or touching the edge? Is any
frame empty? Does the accent color appear only where it should? If you cannot view images, trust the table that
`render.py --sheet` prints: no row may say `EMPTY` or `CUT OFF AT EDGE`.

## 7. Posting on X

- 1080x1920, 30 fps, under 140 s (512 MB) for normal accounts. The kit enforces this.
- Captions are always on: most people watch muted. The kit times every word.
- The first frame is the thumbnail. `check.py` fails a black first frame.
- The post text is the user's job. Offer one plain line if asked; do not write slogans.
