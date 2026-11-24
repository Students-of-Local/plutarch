---
name: plutarch
description: Makes a finished MP4 documentary video (vertical, for X/Twitter) about a real person, built on real recordings of their own voice, with a narrator, music, captions and motion graphics. The scripts in this skill do the video, audio and timing work; you cannot do it by writing a script, outline or text file yourself. Use when asked to make a documentary, short film, profile, tribute, biopic, "clip doc" or any video about a real person, especially one with clips of them talking. Runs on local models, no paid API.
---

# Plutarch: clip documentaries

You make `out/final.mp4`: a 60-140 second vertical film about one real person. The person is heard in
real recordings. A narrator states facts. The scripts in this folder cut, time, mix and draw everything.

`SKILL_DIR` below means the folder that holds this SKILL.md. Use its absolute path.

## When to use

- The user asks for a documentary, profile, tribute, biopic or short film about a real person.
- The user wants a video of a person "in their own words" or "with clips of them talking".
- The user wants a video to post on X/Twitter about someone.

Not for: videos with no real person at the center, or editing a video file the user already has.

## Start here: the whole method is one loop

1. **Run** `python3 SKILL_DIR/scripts/next.py` in the folder the user named (or your working folder).
2. **Do exactly what it prints** under `DO:`. Copy its commands. Replace the example words (CAPITALS,
   `___`, "up to 7 words") with real ones for this film.
3. **Run next.py again** (it prints the command under `THEN:`). Repeat until it prints `DONE`.

That is the job. `next.py` reads the project and always knows the next step, including when to wait for a
long job. Never write your own video script, outline, shell script or placeholder file instead.

Each step has more detail in `SKILL_DIR/references/steps.md` (same step numbers). Read it when a step
fails twice.

## Rules that next.py cannot check for you

- **Change `film.json` and `story.md` only with `python3 scripts/film.py`.** Do not open them in an editor or
  write them with a heredoc. next.py prints the film.py command for each change. `film.py show` and
  `film.py scenes` print what is there now.

- **Every quote is real.** It must come from a recording in `src/` that you downloaded. Never from memory
  or an article.
- **Every fact needs two sources** in `story.md`. Use only facts you read in search results. Never invent a
  date, number or quote.
- **Never fake the person's voice.** No voice cloning, no text-to-speech in their name. The narrator is a stock voice.
- **No photos or video of the person.** The scripts draw original graphics only.
- **Narrator lines:** one fact each, at most 16 words, no praise words like "legendary", "iconic", "visionary".
- **Screen lines:** at most 7 words. Put each quote in the scene for the year it is about.
- **The person speaks last.** The final speaking item in the film is one of their clips.
- **Do not edit the scripts.** If a script prints `ERROR` or `FIX`, do what that line says.
- **Never print big files.** Do not `cat` anything in `tx/`, `clips/`, `narr/` or `out/*.json`. Use
  `python3 scripts/clip.py find` to search transcripts.
- **Long jobs run in the background** (transcribe, clip make, render). next.py gives the exact `nohup ... &`
  line and then tells you to wait. While it says `wait`, run `sleep 60` and then next.py. Do not start the job twice.
- If the same error comes back 3 times, stop and tell the user what it says.

## Done when

- `python3 scripts/next.py` prints `DONE` (that means `check.py` printed `ALL CHECKS PASSED` after your last change).
- Your last message gives the user: the path to `out/final.mp4`, its length, every audio source with its
  URL, the table in `out/check.txt`, and one honest sentence about what you could not check yourself.

Never say "done", "verified" or "synced" before next.py prints `DONE`.

## When something goes wrong

| what you see | do this |
|---|---|
| `STEP 0 ... install the tools` | Run the setup command it prints. If pip fails, make the virtualenv it names, then run it again. |
| `find_audio.py` finds no podcast | Try `find_audio.py archive "NAME"` and `find_audio.py web "NAME interview audio"`. YouTube is often blocked on servers; read `references/finding-audio.md`. |
| `clip.py find` shows nothing useful | Search other words: one strong word, a place, a year, a name. Try the other transcript. |
| A clip is `NOT VERIFIED` | Run the same `film.py clip KEY ...` again with the words from the `heard` column. |
| `film.py` prints `ERROR` | Read its `FIX:` line, change that one value, and run the command again. |
| `film.json is not valid JSON` | Someone edited it by hand. next.py prints the line and column; fix that spot once, then use film.py. |
| `plan.py` says `OVER by` | Remove one quote or one narrator line. Never speed up the narrator. |
| `check.py` has `FAIL` rows | next.py lists each `FIX` line. Do them, then run next.py. |

## Worked example

User: "Make a short documentary about Abraham Lincoln for X. Put it in ./films/lincoln."

```
$ python3 /home/me/skills/plutarch/scripts/next.py
STEP 1 of 12: make the film project
DO:
  python3 /home/me/skills/plutarch/scripts/setup.py --init ./films/SHORTNAME
  cd ./films/SHORTNAME
  python3 scripts/next.py
```
The agent runs `setup.py --init ./films/lincoln`, then `cd ./films/lincoln`, then `python3 scripts/next.py`:
```
STEP 2 of 12: write the subject's name into film.json
DO:
  python3 scripts/film.py set subject "FULL NAME"
```
The agent runs `python3 scripts/film.py set subject "Abraham Lincoln"` and runs next.py again. It keeps going
the same way: `film.py fact` for each fact it found, download two recordings, `film.py source`, transcribe,
`film.py clip` for each quote, `film.py scene add` for each scene,
narrate, plan, mix, render, until next.py prints `DONE: check.py passed for out/final.mp4 (118.4 s).`

## More reading (only when you need it)

- `references/steps.md`: every step in detail, with what each script prints.
- `references/craft.md`: the shape of the film, choosing quotes, writing lines.
- `references/film-json.md`: every field in film.json.
- `references/finding-audio.md`: where to find real recordings.
- `references/voices-music-sfx.md`: other narrator voices and music engines.
- `references/decisions.md`: why the kit works this way, and the mistakes it prevents.

## Harness notes

- Install this folder where your agent looks for skills: omp `~/.omp/agent/skills/plutarch/`,
  pi `~/.pi/agent/skills/plutarch/`, Claude Code `~/.claude/skills/plutarch/`, Codex `~/.agents/skills/plutarch/`.
- No GPU is needed. Agents without image input can trust the numeric tables the scripts print; say so in the hand-over.
