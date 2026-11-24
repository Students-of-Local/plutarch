---
name: plutarch
description: Make a short vertical documentary about a real person for X (Twitter) built on real audio clips of their own voice, with a narrator, music, word-timed captions and motion graphics. Use when asked for a documentary, profile, tribute or "clip doc" video about a person. Works with local models only (no paid API needed).
---

# Plutarch — clip documentaries

## Goal

A 60-140 second vertical film (`out/final.mp4`) about one real person. The person is heard in **real
recordings**. A narrator gives the facts. Music, captions and graphics are made by the scripts in this skill.

## Done means

1. `python3 scripts/check.py` prints `ALL CHECKS PASSED`. Nothing else counts as done.
2. `story.md` has two sources for every fact the narrator or the screen states.
3. Your final message lists: the file path, the length, every audio source with its URL, and the full
   `check.py` table. If something is unchecked, say so.

## Before you start (rules for the whole job)

- **Not sure what is next?** Run `python3 scripts/next.py` in the project (before a project exists:
  `python3 <skill>/scripts/next.py`). It reads the folder and prints the one next step with the exact command.
- **You never type a timestamp into the film.** You write scenes in order; `plan.py` computes every time.
  The only numbers you type are rough `in`/`out` seconds copied from `clip.py find`.
- **Do not edit the scripts. Do not edit audio or video by hand.** If a script prints `ERROR` or `FIX`, do what
  that line says. If the same error comes back 3 times, stop and tell the user what it says.
- **Never print big files.** Do not `cat` anything in `tx/`, `clips/`, `narr/` or `out/*.json`. Use
  `clip.py find` and `clip.py show`. Add `| tail -20` to long commands.
- **Long commands run in the background** (transcribe, clip make, render):
  `nohup python3 scripts/render.py > out/render.log 2>&1 &` then `tail -3 out/render.log` every 30-60 s
  until you see `OK` or `ERROR`.
- After you change `film.json`, run again from `plan.py` down (table in "After a change").
- `<skill>` below = the folder this file is in.

## Steps

### 0. Set up (once)

```
python3 <skill>/scripts/setup.py
```
Expect the last line `SETUP OK.` If it says `SETUP NOT READY`, run the install command it prints, then again.

```
python3 <skill>/scripts/setup.py --init ~/films/<short-name>
cd ~/films/<short-name>
```
Expect `PROJECT READY: ...`. From now on you are inside the project and every command is `python3 scripts/<name>.py`.

### 1. Story first

Read `<skill>/references/craft.md` sections 1-4. Then fill in `story.md`: the film in one sentence, the title
and its end-card echo, and the facts (two source URLs each). Use your web search tool, or
`python3 scripts/find_audio.py web "<query>"`.
Done when: the one sentence is written and you have at least 5 facts with two sources each.

### 2. Find the subject's real voice

Read `<skill>/references/finding-audio.md`. Get 2-4 sources into `src/`: one long clean interview, and one
live moment if it exists.
```
python3 scripts/find_audio.py podcast "<show name>"
python3 scripts/find_audio.py episodes "<feed url>" --grep "<guest name>"
python3 scripts/find_audio.py get "<audio or video url>" --name interview
```
Expect `OK src/interview.mp3 ...` and an `Add to film.json:` line. Put each source into `film.json` → `sources`
(file, credit, url), replacing the template entries.

### 3. Transcribe

```
nohup python3 scripts/transcribe.py src/interview.mp3 > out/tx.log 2>&1 &
```
A 90-minute interview takes 5-15 minutes on a CPU. Done when the log ends with
`OK wrote tx/interview.json and tx/interview.txt (N lines).` Do this for every source.

### 4. Pick 6-10 quotes and cut them

Search for words and ideas from your story sheet:
```
python3 scripts/clip.py find tx/interview.json "back against the wall"
```
Expect blocks like this (the numbers are what you copy):
```
#1  match 97%   "in": 560.9, "out": 562.3
     before: ...
     >>>     <the sentence that was said>
     after:  ...
```
Choose with craft.md section 3. In `film.json` → `clips`, replace the template entries with yours: one per
quote, with `src`, `in`, `out`, `text` (the exact words), `year` and `about`. Add `"live": true` if it is a noisy
recording (crowd, phone). Leave `scenes` for step 5. Then:
```
nohup python3 scripts/clip.py make > out/clips.log 2>&1 &
```
Done when the log ends with `OK: N/N clips verified.` and the `verified` column says `asr` or `pitch` on every row.

| the log says | do this |
|---|---|
| `heard` is different from your `text` | The recording wins. Change `text` to the heard words, or pick another quote. |
| `NOT IN THE CUT: "word"` | A word of your `text` was not found. If the quote still makes sense without it, change `text` to the heard words. If not, move `in` 1 s earlier (or `out` 1 s later) and run `clip.py make <id>` again, or pick another quote. |
| `ERROR: clip 'x': could not find all of "..."` | Read the `Heard there:` line. Either `in`/`out` are off (run `clip.py find` again and copy the numbers) or your `text` is not what was said (fix `text`). |
| `there is music or noise under this voice` | Add `"isolate": true` to that clip and run `clip.py make <id>` again. |
| `NOT VERIFIED` (the row says `unverified`) | Do exactly what that note says. Crowd or phone recording: add `"live": true`. Already `live`: remove it if the recording is clean, or set `in`/`out` tightly around the sentence. Still unverified after two tries: drop the quote. |

Use `"live": true` **only** for crowd or phone recordings. On a clean interview it makes timing worse.

### 5. Write the scenes

Open `film.json`. Replace **every** `<<...>>`. Keep the scene order of the template unless craft.md section 1
tells you to drop or swap a beat. Field list: `<skill>/references/film-json.md`. Rules that matter most:
narrator lines are facts and at most 16 words; screen lines at most 7 words; the subject's voice gets the
last word; every quote sits in the scene for the year it is **about**.

### 6. Narrator and timing

```
python3 scripts/narrate.py
python3 scripts/plan.py
```
`narrate.py`: every row must say `ok` (`MISREAD` → respell the hard word the way it sounds, run again).
`plan.py`: expect a scene table, then `TOTAL 131.2 s (limit 140 s). OK.` and a `REAL VOICE ... NARRATOR ... QUOTES` line.
If it says `OVER by`, remove a quote or a scene (do not speed up the narrator). If it prints a `FIX:` line, do it
(usually: add a quote or cut a narrator line). Then run both again. Other voices: `<skill>/references/voices-music-sfx.md`.

### 7. Music

Default, works everywhere:
```
python3 scripts/score.py synth
```
Expect `OK music/synth.wav (...)`. Better, if a music generator is available: `python3 scripts/score.py acestep`
(local ACE-Step server), or `python3 scripts/score.py prompt` → generate 2-3 tracks → `python3 scripts/score.py pick music/*.mp3`
→ put the winner in `film.json` `"music": {"file": "music/<name>"}`. Details: voices-music-sfx.md.

### 8. Mix

```
python3 scripts/mix.py
```
Expect a table where **every row ends in `ok`**, then
`OK: out/mix.wav  131.2 s  loudness -14.4 LUFS (target -14)  peak -1.6 dB (must be below -1).`
A row that says `COVERED`: something loud sits under that voice. Add `"isolate": true` to that clip (crowd or phone
recording: `"live": true`), then `clip.py make <id>`, `plan.py`, `mix.py`.

### 9. Preview frames (seconds, not minutes)

```
python3 scripts/render.py --sheet
```
Expect a table with no `EMPTY` and no `CUT OFF AT EDGE`, then `OK: out/sheet.jpg (N frames)`. If you can view
images, open `out/sheet.jpg` and check it with craft.md section 6. `CUT OFF AT EDGE`: shorten that scene's
heading or lines. `EMPTY`: that scene has no heading, lines or clip: give it one. Then `plan.py`, `mix.py`,
`render.py --sheet` again.

### 10. Render and check

```
nohup python3 scripts/render.py > out/render.log 2>&1 &
```
About 4 minutes per minute of film on a CPU. Done when the log ends with `OK out/final.mp4 (131.2 s). Next: python3 scripts/check.py`. Then:
```
python3 scripts/check.py
```
Expect 18 `PASS` rows and `ALL CHECKS PASSED  (out/final.mp4)`. For every `FAIL`, do its `FIX` line, then run
`check.py` again. Do not stop at `NOT DONE`.

### 11. Hand over

Give the user: `out/final.mp4`, the length, the list of audio sources with URLs, the `check.py` table, and one
honest sentence about anything you could not check (for example: "I cannot view images; the frame table was all ok").

## After a change, run again from here

| you changed | run, in order |
|---|---|
| a clip's `in`/`out`/`text`/`live`/`isolate` | `clip.py make <id>` → `plan.py` → `mix.py` → `render.py` → `check.py` |
| a narrator line, or the voice | `narrate.py` → `plan.py` → `mix.py` → `render.py` → `check.py` |
| scene order, items, gaps | `plan.py` → `mix.py` → `render.py` → `check.py` |
| only text on screen (heading, lines, colors) in one scene | `plan.py` → `render.py --scene <id>` → `check.py` |
| only music or sound effects | `mix.py` → `render.py --mux` (seconds) → `check.py` |

## Decisions (and why)

- **Sound first, picture second.** Every picture event is timed from the finished sound. That is why captions
  and impacts land exactly: `plan.py` and `mix.py` run before any frame is drawn.
- **Real voice for feeling, narrator for facts.** A synthetic voice saying emotional lines sounds fake; a real
  person saying them is the whole reason people watch.
- **No photos or video of the person.** Original motion graphics only: no image-rights problems, and the film
  looks like one designed piece instead of a slideshow.
- **Word-by-word captions on every quote.** Most viewers watch muted, and a word that appears as it is spoken
  proves the quote is real.
- **Vertical 1080x1920, at most 140 s, about -14 LUFS.** That is what X plays best for normal accounts.
- **Cold open on real sound, music enters at the title.** The first two seconds decide whether anyone stays.
- **Local, free tools by default** (Kokoro voice, built-in score). Better engines are a swap in `film.json`,
  never a reason to stall.

## Don't

- Don't trust a quote from memory or from an article. If it is not in a recording in `src/`, it is not in the film.
- Don't put a quote under a date it is not about. (A line about one year once played over a card for another.)
- Don't make the subject "say" anything with a voice model, and don't feed any real person's voice to a
  cloning model. Narrator = stock voice.
- Don't type caption or scene times, and don't trust word times in a noisy clip without `"live": true`.
  (A caption once ran 4 seconds early because speech was hidden in crowd noise.)
- Don't keep another creator's music under a quote: use `"isolate": true`.
- Don't let the narrator praise or summarize feelings. No "legendary", "visionary", "iconic".
- Don't add a closing line the facts don't support. (An end-card line about "investigations" had to be removed.)
- Don't start on a black frame. Scene 1 is an `arena` with `reveal: hits`, or a card that starts with a clip.
- Don't run a full render to change only sound: `mix.py` then `render.py --mux`.
- Don't raise `max_seconds` above 140 unless the user says the account has Premium.
- Don't say "done", "verified" or "synced" unless `check.py` printed `ALL CHECKS PASSED` after your last change.

## Verify before you say you're done

Run `python3 scripts/check.py` **after your last change** and paste its table. It measures the finished file:
format, length, loudness, peak, dead air, black first frame, empty scenes, every line's position against the
plan (to 0.1 s), spoken words against caption words, voice over music, credits, that every quote is
verified with a year and context, that real voice is at least half of the talking, and that the subject
speaks last. Then read `story.md` once more: every fact on screen has two sources.

## Harness notes

- Install this folder where your agent looks for skills: omp `~/.omp/agent/skills/plutarch/`,
  pi `~/.pi/agent/skills/plutarch/`, Claude Code `~/.claude/skills/plutarch/`,
  Codex `~/.agents/skills/plutarch/`.
- No GPU is needed: every script runs on the CPU. A GPU only matters for optional bigger voice or music models.
- Agents without image input: steps 9 and 10 print numeric tables. Trust them and say so in the hand-over.
- YouTube often blocks servers ("confirm you're not a bot"). Use the podcast or X route in finding-audio.md.

---
Tested with: no student model yet. Teacher-side only: the checks pass on the reference film and fail on a
known-bad cut; the scripts were run end to end on four test films with the default local engines.
