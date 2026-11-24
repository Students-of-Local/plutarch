# film.json: every field

You write scenes **in order**. You never write timestamps: `plan.py` works them out from the real length of
each clip and narrator line. Start from `templates/film.json`.

## Top level

| key | meaning |
|---|---|
| `title` | 2-3 words, ends with a period: `"LAST CHANCE."` The period is drawn in the accent color. |
| `subject` | Full name. Used in the small source tag under every quote. |
| `accent` | One hex color for the whole film (the dot, the chart line, the end card). Pick one that fits the subject. |
| `max_seconds` | 140 for a normal X account. Only raise it if the user says they have X Premium. |
| `narrator` | Voice engine. See `scripts/narrate.py` header and `voices-music-sfx.md`. |
| `music` | `{"synth": true}` or `{"file": "music/track.mp3"}`. |
| `sources` | `id -> {"file", "credit", "url"}`. `credit` is shown on screen and on the end card: `"Show Name (2023)"`. |
| `clips` | `id -> clip` (below). |
| `scenes` | list of scenes (below). |

## A clip (one real quote)

```json
"bet": {"src": "interview", "in": 560.0, "out": 562.5, "text": "We had one try left.", "year": 2009, "about": "the last product they could afford to build"}
```

| key | meaning |
|---|---|
| `src` | id from `sources` |
| `in`, `out` | seconds in the source file. **Rough is fine** (within 1.5 s): `clip.py make` snaps to the word edges. |
| `text` | the exact words you want, as spoken. `make` finds them. If it says it heard something else, the source wins: fix `text`. |
| `year`, `about` | when the thing he is talking about happened, and what he was talking about. Required. Stops you putting a quote under the wrong date. |
| `live` | `true` for noisy field recordings (crowd, phone video). Needs `text`. The voice is separated and the timing is checked against voice pitch. |
| `isolate` | `true` when there is music under the voice (someone else's edit). The cleaned voice is used in the film. |
| `lines` | optional: your own caption line breaks/punctuation. Must have the same number of words as were heard. |
| `speaker` | only if someone other than the subject is speaking: `"an employee"`. |

## Scenes

Every scene has `type`, and may have `id` (used in messages and `render.py --scene`), `heading`, `lines`, and `items`.

`items` is what you HEAR, in order:

```json
"items": [{"say": "Narrator line."}, {"clip": "bet"}, {"gap": 1.0}]
```

- `{"say": "..."}` narrator line. Max 16 words. A fact, never an opinion. Spell out odd names.
- `{"clip": "id"}` a quote. Add `"big": true` to show a very short quote in large type.
- `{"gap": seconds}` silence (music keeps playing). Use it to let a moment breathe.

`lines` is what you READ under the heading. Each line appears while the narrator speaks. To tie a line to a
narrator word: `{"text": "The factory closes.", "at": "closes"}`. Max 3 lines, max 7 words each.

| type | what you see | extra keys |
|---|---|---|
| `arena` | a crowd of lights on curved balconies around one accent-colored figure | `reveal`: `"hits"` = cold open, camera pulls back on each drum hit; `"rise"` = the room fills with light and erupts at the peak. `under`: crowd sound bed `{"src", "in", "out", "gain", "drums": true}`. `peak`: clip id where it erupts (for `rise`). `chant`: a word drawn faintly behind (`"NAME"`). |
| `title` | the title slams in | `text`, `sub`: up to 2 small lines |
| `card` | heading + lines on black. As scene 1 with a clip as its first item, the quote is on screen from the first frame. | `bg`: `"glow"` (warm light, for the origin), `"pulse"` (heartbeat line + heartbeat sound, for the setback). `ghost`: huge faint text behind (`"1993"`). |
| `stack` | big words slam in exactly when he says them | `words`: 3-6 words that occur in the clip, in spoken order. `accent_word`. Needs one clip item. |
| `chart` | a line chart that draws itself; the scale grows with it | `points`: `[[x, value], ...]` real data. `source`: where the numbers come from (required). `unit` (1e9 if values are billions), `prefix` (`"$"`), `label`, `stamps`: `[[x, "BIG TEXT", "small text"], ...]` shown when the line reaches x. |
| `end` | title again + second line in accent + credits | `text`, `accent_text` |

Other keys any scene can take: `impact` (flash + boom at the start; on by default for `title` and `end`),
`music: false` (no music in this scene; default for a cold-open arena), `energy: [start, end]` (0-1, how
intense the music should be), `pre` / `post` (seconds of air before/after the items), `min` (minimum length).

## The files the scripts make

| file | made by | what |
|---|---|---|
| `src/*`, `tx/*.json` | find_audio.py, transcribe.py | sources and searchable transcripts |
| `clips/<id>.wav/.json` | clip.py make | the exact cut + a start time for every word |
| `narr/<id>.wav/.json` | narrate.py | narrator lines |
| `out/plan.json` | plan.py | every scene, sound and caption with its exact time |
| `out/mix.wav`, `out/stem_*.wav`, `out/sync.json` | mix.py | mastered sound, stems, beat/hit times for the picture |
| `out/sheet.jpg`, `out/final.mp4` | render.py | preview frames, the film |
