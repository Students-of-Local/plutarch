# Steps in detail

`scripts/next.py` prints the step you are on. Use this page when you want to know more about that step.
`SKILL_DIR` = the folder that holds SKILL.md.


### 0. Set up (once)

```
python3 SKILL_DIR/scripts/setup.py
```
Expect the last line `SETUP OK.` If it says `SETUP NOT READY`, run the install command it prints, then again.

```
python3 SKILL_DIR/scripts/setup.py --init ~/films/SHORTNAME
cd ~/films/SHORTNAME
```
Expect `PROJECT READY: ...`. From now on you are inside the project and every command is `python3 scripts/<name>.py`.

### 1. Story first

Read `SKILL_DIR/references/craft.md` sections 1-4. Search with your web search tool, or `python3 scripts/find_audio.py web "<query>"`. Then write the story into
`story.md` with `python3 scripts/film.py sentence "<the whole film in one sentence>"` and, once per fact,
`python3 scripts/film.py fact "<fact with its date>" <url 1> <url 2>`.
film.py opens both pages and refuses a fact that is not on them. Wikipedia and news stories open; some sites block scripts.
Done when: the one sentence is written and you have at least 5 facts with two sources each.

### 2. Find the subject's real voice

Read `SKILL_DIR/references/finding-audio.md`. Get 2-4 sources into `src/`: one long clean interview, and one
live moment if it exists.
```
python3 scripts/find_audio.py podcast "<full name>"
```
It lists podcast episodes with the person, episodes of 5-90 minutes first, each with a ready `find_audio.py get` line.
Run the get line of one where they are the guest. For any other link: `find_audio.py get "<url>" --name interview`.
Expect `OK src/<name>.mp3 ...` and a `film.py source` command. Run it (if it still says `SHOW (YEAR)`,
write the show or event name and year there first); the first source replaces the template entries.

### 3. Transcribe

Run the `nohup python3 scripts/transcribe.py ...` line that next.py prints. It names every recording that
still needs a transcript and does them one after the other. A 90-minute interview takes 5-15 minutes on a
CPU. Done when the log ends with `OK: N file(s) transcribed.`

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
Choose with craft.md section 3. Add one clip per quote (the first one replaces the template clips):
```
python3 scripts/film.py clip <key> <source key> <in> <out> "<the exact words>" <year said> "<what it was about>"
```
Add `--live` if it is a noisy recording (crowd, phone). Leave the scenes for step 5. Then:
```
nohup python3 scripts/clip.py make > out/clips.log 2>&1 &
```
Done when the log ends with `OK: N/N clips verified.` and the `verified` column says `asr` or `pitch` on every row.

| the log says | do this |
|---|---|
| `heard` is different from your `text` | The recording wins. Run the same `film.py clip` again with the heard words, or pick another quote. |
| `NOT IN THE CUT: "word"` | A word of your `text` was not found. If the quote still makes sense without it, change `text` to the heard words. If not, move `in` 1 s earlier (or `out` 1 s later) and run `clip.py make <id>` again, or pick another quote. |
| `ERROR: clip 'x': could not find all of "..."` | Read the `Heard there:` line. Either `in`/`out` are off (run `clip.py find` again and copy the numbers) or your `text` is not what was said (fix `text`). |
| `there is music or noise under this voice` | Run `film.py clip <key> --isolate`, then `clip.py make <id>`. |
| `NOT VERIFIED` (the row says `unverified`) | Do exactly what that note says. Crowd or phone recording: `film.py clip <key> --live`. Already live: leave it off if the recording is clean, or set in and out tightly around the sentence. Still unverified after two tries: `film.py drop clip <key>`. |

Use `--live` **only** for crowd or phone recordings. On a clean interview it makes timing worse.

### 5. Write the scenes

Remove the template scenes, then add yours in order. next.py prints a starting list built from your clips.
```
python3 scripts/film.py set title "<TWO WORDS.>"
python3 scripts/film.py set accent "#C8102E"
python3 scripts/film.py scenes clear
python3 scripts/film.py scene add title
python3 scripts/film.py scene add card --heading "<DATE>" --line "<max 7 words>" --say "<one fact>" --clip <key>
python3 scripts/film.py scene add stack --heading "THE COST" --words "<3-6 words he says>" --clip <key>
python3 scripts/film.py scene add end --accent-text "<2-3 WORDS.>"
python3 scripts/film.py scenes
```
Items play in the order you give `--say`, `--clip` and `--gap`. New scenes go before the end card. Charts,
crowd sound under a scene and timed lines are edited in `film.json` by hand: `SKILL_DIR/references/film-json.md`.
Keep the beat order of craft.md section 1. Rules that matter most:
narrator lines are facts and at most 16 words; screen lines at most 7 words; the subject's voice gets the
last word; every quote sits in the scene for the year it is **about**.

### 6. Narrator and timing

```
python3 scripts/narrate.py
python3 scripts/plan.py
```
`narrate.py`: every row must say `ok` (`MISREAD`: run the `film.py reword` line it prints with the hard word respelled the way it sounds, then run it again).
`plan.py`: expect a scene table, then `TOTAL 131.2 s (limit 140 s). OK.` and a `REAL VOICE ... NARRATOR ... QUOTES` line.
If it says `OVER by`, remove a quote or a scene (do not speed up the narrator). If it prints a `FIX:` line, do it
(usually: add a quote or cut a narrator line). Then run both again. Other voices: `SKILL_DIR/references/voices-music-sfx.md`.

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
A row that says `COVERED`: something loud sits under that voice. Run `film.py clip <key> --isolate` (crowd or phone
recording: `film.py clip <key> --live`), then `clip.py make <id>`, `plan.py`, `mix.py`.

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

