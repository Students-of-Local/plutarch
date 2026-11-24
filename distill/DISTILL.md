# skill-distill run: plutarch — teacher handoff

This folder is the teacher's half of a `skill-distill` run (sybil-solutions/skill-distill, method at commit 4c3b307).
The skill itself is `../plutarch/`. Before a run, put the original request in `prompt.md` here
(it is git-ignored: prompts and `runs/` stay private).

## Where the run stands

| distill step | status |
|---|---|
| 0 settle inputs | **student not named yet** (harness + model). Everything else settled: prompt = `prompt.md`, base = `empty` |
| 1 check the student answers | not done (needs the student) |
| 2 create the run | not done here: `distill.py init` writes machine paths, so run it on the machine that hosts the student |
| 3 what "as good" means | **done**: `acceptance.md` (9 items), `checks.sh` (the skill's own `check.py` plus 5 task checks) |
| 3 checks pass on the reference | **done**: all pass on the reference film; they fail on the earlier flawed cut (black first frame, a line 1.2 s off plan) and on a deliberately thin test film (too few quotes, narrator-heavy) |
| 4 first student skill | **done**: `../plutarch/` (SKILL.md 229 lines + 4 reference pages + 11 scripts) |
| 5-7 run student, judge, fix | not done |
| 8 owner pass/fail | not done |
| 9 "Tested with" line | placeholder at the end of SKILL.md; replace after step 8 |

## Run it (on the machine with the student)

```
# once per machine: one Python environment for the kit (the student and the checks both use it)
python3 -m venv ~/.venvs/clipdoc && . ~/.venvs/clipdoc/bin/activate
python3 <this folder>/../plutarch/scripts/setup.py --install      # must end with: SETUP OK.

cd <skill-distill>/skills/skill-distill
# step 1: prove the student answers, e.g. for omp
omp -p --no-session --model <provider/id> "Create hello.txt containing hi, then reply DONE."

# step 2
python3 scripts/distill.py init runs/plutarch \
  --prompt <this folder>/prompt.md --student <harness>:<provider/model> --base empty --name plutarch \
  --timeout-min 240 --env "PATH=$HOME/.venvs/clipdoc/bin:$PATH"
rm -rf runs/plutarch/skill && cp -r <this folder>/../plutarch runs/plutarch/skill
cp <this folder>/acceptance.md <this folder>/checks.sh runs/plutarch/

# step 5: three trials (keep the venv active in this shell: evidence runs checks.sh with it)
python3 scripts/distill.py trial runs/plutarch -k 3
python3 scripts/distill.py wait runs/plutarch --timeout 540     # repeat until all exit
python3 scripts/distill.py evidence runs/plutarch               # runs checks.sh per trial
```
`--setup` is not used: `distill.py` runs it before the skill is copied into the workspace, and a venv
activated there would not reach the student. First model downloads (speech recognition, voice separation,
Kokoro, alignment: about 1.5 GB) happen on first use; run one film by hand first or allow for it in the timeout.

The reference film is not in this folder. To re-run "checks pass on the reference" on your machine you need the
teacher session's reference project; otherwise rely on the result recorded above.

## What the kit decides and what the student decides

The scripts are large on purpose (about 1,900 lines): timing, word alignment, mixing, mastering and drawing
are the mechanical steps a weak model fumbles, so they are scripts ("scripts beat prose"). They are general
tools: they contain no part of the reference film, no quote, no source, no fact. `templates/film.json` is all
placeholders and the scripts refuse to run until every placeholder is replaced.

The student still does everything that makes a film good or bad: research and fact sourcing, finding the
recordings, choosing 6-10 quotes, writing narrator lines and screen text, ordering the beats, and reacting to
the checks. That is what the trials measure.

## Where I expect the first divergences (watch these in the traces)

1. **Finding audio.** Open models stall on YouTube bot-blocks or grab someone else's re-edit. The skill routes
   to podcasts and X posts first; see if the student follows it.
2. **Quote choice.** Expect quotes that need context, or too few. `plan.py` prints `FIX:` lines and `check.py`
   fails on "enough real quotes" / "real voice is half the talking", but taste is not scripted.
3. **Leaving `<<placeholders>>` or typing the template's sample chart numbers.** Guarded for placeholders and
   for a missing chart `source`; made-up chart points with a made-up source are not caught by a script.
4. **Quote under the wrong date.** Only `year`/`about` nudge this. It is acceptance item 7 (teacher).
5. **Stopping before `check.py`**, or reporting success with FAIL rows. The skill says this three times.
6. **Printing transcripts into context.** The skill forbids `cat` on `tx/`; watch for it anyway.
7. **Long commands in the foreground** timing out the tool call (transcribe, clip make, render).

## What was actually run while building this (teacher side)

- All 11 scripts, end to end, on four test films with the default local engines (Kokoro voice, built-in score).
  The last one started from a fresh `setup.py --init` project and used only the commands in SKILL.md.
- A film with no crowd recording (opens on a quote card): passes.
- `find_audio.py`: `web`, `podcast`, `episodes`, `archive`, `yt` (search) and `get` (podcast mp3, a section of
  one, posts on X) ran for real. `subs` and YouTube downloads were bot-blocked on the build machine: the code
  path printed its hint; the caption parser was only tested on synthetic data.
- Narrator engines: `kokoro`, `piper`, `cmd` ran for real; `openai` ran against a mock server; `elevenlabs`
  (REST) was not run. Chatterbox and Qwen3-TTS snippets are from their READMEs, not run.
- `score.py acestep` ran against a mock of the documented ACE-Step 1.5 API, not a real server.
- No GPU was used anywhere.

## Known limits of this version

- Word timing on noisy clips is cross-checked by two methods and marked `unverified` when they disagree; it can
  still be wrong when both are wrong the same way. Acceptance item 3 asks the teacher to watch the noisiest clip.
- Speech recognition can miss the first word of a clip that starts at the very beginning of a file; the kit
  says so (`NOT IN THE CUT`) and cuts to what it heard.
- The built-in score is plain. A generated track is the single biggest quality upgrade.
- Scene types are fixed (title, card, arena, stack, chart, end). A project `custom.py` can draw one more, but
  that is beyond what a weak student should attempt.
