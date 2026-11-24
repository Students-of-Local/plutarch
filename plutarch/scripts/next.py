#!/usr/bin/env python3
"""Tell the agent the ONE next thing to do. Run it, do exactly what it prints, run it again.

  python3 <skill folder>/scripts/next.py      # before a project exists: says how to start
  python3 scripts/next.py                      # inside the project folder: the next step
  python3 scripts/next.py --wait               # while a long job runs: waits up to 100 s, then says what is next

It only reads files and lists processes. It never changes the film. Finishes with DONE when check.py passed."""
import os, sys, re, json, glob, hashlib, subprocess, importlib.util, time, shlex
WAIT = "--wait" in sys.argv

KIT = os.path.dirname(os.path.realpath(__file__))
QKIT = shlex.quote(KIT)
TOTAL = 12

def say(step, title, do, why=None, then="python3 scripts/next.py"):
    print(f"STEP {step} of {TOTAL}: {title}")
    if why: print(f"WHY: {why}")
    print("DO:")
    for line in do: print("  " + line)
    if then: print(f"THEN: {then}")
    sys.exit(0)

def load(p):
    try:
        with open(p, encoding="utf8") as f: return json.load(f)
    except FileNotFoundError: return None
    except json.JSONDecodeError as e:
        say("-", f"fix {p}: it is not valid JSON",
            [f"{p} line {e.lineno}, column {e.colno}: {e.msg}",
             "Open the file, fix that spot (a missing comma, quote or bracket is the usual cause), save it."])

def mtime(p): return os.path.getmtime(p) if os.path.exists(p) else 0.0

def holders(x, path=""):
    """Every string that still contains a <<template placeholder>>, with where it is."""
    out = []
    if isinstance(x, dict):
        for k, v in x.items(): out += holders(v, f"{path}.{k}" if path else k)
    elif isinstance(x, list):
        for i, v in enumerate(x): out += holders(v, f"{path}[{i}]")
    elif isinstance(x, str) and ("<<" in x or re.search(r"<[A-Za-z][^<>]*>", x)): out.append(f"{path}: {x[:70]}")
    return out

def spec(c):
    keep = {k: c.get(k) for k in ("src", "in", "out", "text", "lines", "live", "isolate")}
    return hashlib.md5(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:10]

def say_id(text): return "n" + hashlib.md5(text.strip().encode("utf8")).hexdigest()[:9]

def running(proj):
    """Kit scripts still running in this project folder (transcribe, clip make, render ...)."""
    found = []
    for d in glob.glob("/proc/[0-9]*"):
        try:
            cmd = open(d + "/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
            if "scripts/" not in cmd or "next.py" in cmd or "python" not in cmd: continue
            if os.path.realpath(os.readlink(d + "/cwd")) == os.path.realpath(proj):
                found.append(cmd.strip())
        except OSError: continue
    if not found and sys.platform == "darwin":
        r = subprocess.run(["pgrep", "-fl", "scripts/(transcribe|clip|render|mix|narrate|find_audio)"], capture_output=True, text=True)
        found = [l for l in r.stdout.splitlines() if l.strip()]
    return found

def log_tail(name):
    p = f"out/{name}"
    if not os.path.exists(p): return ""
    noise = ("warning", "fontconfig", "  warnings.warn", "userwarning", "futurewarning")
    lines = [l.rstrip() for l in open(p, encoding="utf8", errors="replace") if l.strip()]
    lines = [l for l in lines if not l.strip().lower().startswith(noise) and "Warning:" not in l]
    return lines[-1][:150] if lines else ""

def failed(log, done_file):
    """The job's log shows a crash and its output is missing: return the error line."""
    p = f"out/{log}"
    if not os.path.exists(p) or (done_file and os.path.exists(done_file) and mtime(done_file) >= mtime(p)): return None
    txt = open(p, encoding="utf8", errors="replace").read()
    if "Traceback" not in txt and not re.search(r"^ERROR", txt, re.M): return None
    errs = [l.strip() for l in txt.splitlines() if l.startswith("ERROR") or re.match(r"^\w*(Error|Exception)\b", l)]
    return (errs[-1] if errs else txt.strip().splitlines()[-1])[:200]

# ---- 0. tools installed? ----
need = ["numpy", "scipy", "soundfile", "pyloudnorm", "librosa", "skia", "PIL", "faster_whisper", "yt_dlp", "kokoro_onnx"]
missing = [m for m in need if importlib.util.find_spec(m) is None]
if missing:
    say(0, "install the tools (once per machine)",
        [f"python3 {QKIT}/setup.py --install",
         "If it says pip failed: python3 -m venv ~/.venvs/plutarch && . ~/.venvs/plutarch/bin/activate   then run the line above again."],
        why="missing Python packages: " + ", ".join(missing))

# ---- 1. inside a project? ----
if not (os.path.exists("film.json") and os.path.isdir("scripts")):
    make = [f"python3 {QKIT}/setup.py --init ./films/SHORTNAME      # SHORTNAME = the person's last name, lowercase, e.g. lincoln",
            "cd ./films/SHORTNAME", "python3 scripts/next.py"]
    found = sorted(glob.glob("films/*/film.json") + glob.glob("*/film.json"))
    if found:
        rows = []
        for f in found[:8]:
            try: who_f = json.load(open(f, encoding="utf8")).get("subject", "?")
            except Exception: who_f = "?"
            rows.append(f"  {os.path.dirname(f)}   subject: {who_f}")
        say(1, "go into the project for THIS film, or make a new one",
            ["Film projects already here:"] + rows +
            ["If one of them is about the person the user asked for now: cd into it, then python3 scripts/next.py",
             "Otherwise make a new project:"] + ["  " + m for m in make], then=None)
    say(1, "make the film project", make, then=None,
        why="there is no film.json here. If the user named a folder, use that folder instead of ./films/SHORTNAME.")

proj = os.getcwd()
film = load("film.json")
subject = film.get("subject", "")
who = subject if subject and "<<" not in subject else "FULL NAME"

jobs = running(proj)
if jobs and WAIT:
    t0 = time.time()
    while jobs and time.time() - t0 < 100:
        time.sleep(10); jobs = running(proj)
if jobs:
    name = re.search(r"scripts/(\w+)\.py", jobs[0]); name = name.group(1) if name else "a script"
    logs = {"transcribe": "tx.log", "clip": "clips.log", "render": "render.log"}
    last = log_tail(logs.get(name, "")) if name in logs else ""
    say("-", f"wait: {name}.py is still running",
        ["python3 scripts/next.py --wait      # waits up to 100 s, then tells you what is next"] + ([f"progress: {last}"] if last else []),
        why="a long job is working in the background. Do not start it again and do not start the next step yet.", then=None)

for log, out, what in (("tx.log", None, "transcribe.py"), ("clips.log", None, "clip.py make"), ("render.log", "out/final.mp4", "render.py")):
    err = failed(log, out)
    if err and (log != "tx.log" or not all(os.path.exists("tx/" + os.path.splitext(os.path.basename(v.get("file", "")))[0] + ".json")
                                             for v in (film.get("sources") or {}).values() if isinstance(v, dict))):
        hint = {"tx.log": "If it mentions CUDA, cublas or cudnn: run it again with  PLUTARCH_DEVICE=cpu  in front of the command.",
                "clips.log": "Read the ERROR line: usually a clip's in/out or text is wrong. Fix film.json \"clips\".",
                "render.log": "Read the ERROR line and fix what it names; then start the render again."}[log]
        say("-", f"{what} crashed", [f"out/{log} says: {err}", hint, f"Then delete out/{log} and run python3 scripts/next.py"],
            why="the job stopped with an error, so its output is missing.")

# ---- 2. story: one sentence + 5 facts with two sources ----
story = open("story.md", encoding="utf8").read() if os.path.exists("story.md") else ""
facts = [l for l in story.splitlines() if l.startswith("|") and len(re.findall(r"https?://", l)) >= 2]
sentence = re.search(r"## The film in one sentence\s*\n(.*)", story)
sentence_ok = bool(sentence) and "____" not in sentence.group(1) and len(sentence.group(1).strip()) > 20
if who == "FULL NAME":
    say(2, "write the subject's name into film.json",
        ['Open film.json. Set "subject" to the person\'s full name, e.g. "subject": "Abraham Lincoln". Save.'])
if len(facts) < 5 or not sentence_ok:
    search_ok = importlib.util.find_spec("ddgs") or os.environ.get("SEARXNG_URL") or os.environ.get("BRAVE_API_KEY")
    do = ([] if search_ok else ["find_audio.py web needs a search engine. Run: python3 -m pip install ddgs   (or use your own web search tool for the next two lines)"]) + [f'python3 scripts/find_audio.py web "{who} biography"',
          f'python3 scripts/find_audio.py web "{who} career timeline"',
          "Open story.md and fill it in. Replace the ____ under 'The film in one sentence' with one sentence.",
          "Add at least 5 fact rows to the Facts table. Each row has the fact and TWO different source URLs:",
          "  | 1 | Born March 3, 1960 in Ohio | https://first-source... | https://second-source... |",
          "Use only facts you found in the search results. Copy the URLs exactly.",
          "If a search prints ERROR: web search failed, run it again or change the words."]
    say(2, "story first: one sentence and 5 facts with two sources each", do,
        why=f"story.md has {len(facts)} fact rows with two URLs (need 5)" + ("" if sentence_ok else " and no one-sentence summary yet"))

# ---- 3. audio sources ----
AUD = (".mp3", ".m4a", ".wav", ".flac", ".mp4", ".webm", ".mkv", ".opus", ".ogg", ".aac", ".mov")
srcfiles = sorted(f for f in glob.glob("src/*") if f.lower().endswith(AUD))
sources = film.get("sources", {})
if not srcfiles:
    say(3, "get a real recording of the subject's voice into src/",
        [f'python3 scripts/find_audio.py podcast "{who}"',
         "  -> pick a show that interviewed them; copy its feed URL",
         f'python3 scripts/find_audio.py episodes "FEED_URL" --grep "{who.split()[-1]}"',
         "  -> copy the audio URL of the episode with them in it",
         'python3 scripts/find_audio.py get "AUDIO_URL" --name interview',
         "It prints an 'Add to film.json:' line. Copy that entry into film.json \"sources\"."],
        why="src/ has no audio yet. Read references/finding-audio.md if podcasts find nothing. YouTube is often blocked; prefer podcasts.")
bad_src = [k for k, v in sources.items() if holders(v) or not os.path.exists(v.get("file", ""))]
if bad_src or not sources:
    files = ", ".join(srcfiles)
    say(3, "list your recordings in film.json \"sources\"",
        [f"Files in src/: {files}",
         "Open film.json. In \"sources\", keep one entry per file you have and DELETE template entries you do not use.",
         'Each entry: "interview": {"file": "src/interview.mp3", "credit": "Show Name (2019)", "url": "https://where-you-got-it"}',
         "The 'Add to film.json:' line that find_audio.py get printed has the right values."],
        why=("these sources are template text or point to a missing file: " + ", ".join(bad_src)) if bad_src else "film.json \"sources\" is empty.")
if len(sources) < 2:
    say(3, "get a second recording (a different interview, speech or event)",
        [f'python3 scripts/find_audio.py podcast "{who}"',
         f'python3 scripts/find_audio.py archive "{who}"',
         'python3 scripts/find_audio.py get "AUDIO_URL" --name SECOND_NAME',
         "Add it to film.json \"sources\" like the first one."],
        why="the film needs real voice from at least 2 sources (check.py and the acceptance checks require it).")

# ---- 4. transcripts ----
for k, v in sources.items():
    stem = os.path.splitext(os.path.basename(v["file"]))[0]
    if mtime(f"tx/{stem}.json") < mtime(v["file"]):
        say(4, f"transcribe {v['file']}",
            [f"nohup python3 scripts/transcribe.py {shlex.quote(v['file'])} > out/tx.log 2>&1 &",
             "python3 scripts/next.py --wait      # waits while transcribe runs"], then=None,
            why="you search the transcript for quotes. A 1-hour file takes about 5-10 minutes.")

# ---- 5. quotes ----
clips = film.get("clips", {})
real = {k: c for k, c in clips.items() if not holders(c) and c.get("out", 0) > c.get("in", 0)}
tx = sorted(glob.glob("tx/*.json"))
if holders(clips) or len(real) < 6:
    say(5, "choose 6-10 quotes and put them in film.json \"clips\"",
        [f'python3 scripts/clip.py find {tx[0] if tx else "tx/interview.json"} "a few words or an idea"',
         "  -> each result shows   \"in\": 560.9, \"out\": 562.3   and the sentence that was said",
         "Search for ideas from story.md: the start, the risk, the cost, the turn, the comeback.",
         "Add one entry per quote to film.json \"clips\" and DELETE every template entry that still has << >>:",
         '  "start": {"src": "interview", "in": 560.9, "out": 562.3, "text": "the exact words said", "year": 2010, "about": "what he was talking about"}',
         '"src" is a key from "sources". Copy in/out from the result. "text" = the sentence shown after >>>.',
         "Use quotes from at least 2 different sources."],
        why=f"film.json has {len(real)} finished clips (need 6 or more)" + (" and template entries still in \"clips\"" if holders(clips) else ""))
srcs_used = {c["src"] for c in real.values()}
if len(srcs_used) < 2:
    say(5, "add a quote from your second recording",
        [f"python3 scripts/clip.py find tx/SECOND.json \"words\"      # transcripts: {', '.join(tx)}",
         "Add it to film.json \"clips\" with \"src\" set to the second source's key."],
        why="all clips come from one source; the film needs real voice from 2 or more.")
def cut_is_stale(k, c):
    d = load(f"clips/{k}.json")
    if not d: return True
    if "spec" in d: return d["spec"] != spec(c)
    want = c.get("text") or " ".join(c.get("lines") or [])          # cut by an older kit: compare what it stored
    return (d.get("wanted") != want or bool(d.get("live")) != bool(c.get("live")) or "isolate" in c
            or abs(d.get("in_exact", -99) - c["in"]) > 2.0 or abs(d.get("out_exact", -99) - c["out"]) > 2.0)
stale = [k for k, c in real.items() if cut_is_stale(k, c)]
if stale:
    say(6, "cut and verify the quotes",
        ["nohup python3 scripts/clip.py make > out/clips.log 2>&1 &",
         "python3 scripts/next.py --wait      # waits while clips are cut"], then=None,
        why="clips not cut yet (or changed since): " + ", ".join(stale))
unver = [k for k in real if (load(f"clips/{k}.json") or {}).get("verified") == "unverified"]
if unver:
    say(6, "fix the clips that are NOT VERIFIED",
        ["grep -A2 -E '^\\s*\\[(" + "|".join(unver) + ")\\]' out/clips.log | head -30",
         "Do what each note says. The usual fixes, in order:",
         "  1. Change \"text\" to the exact words in the 'heard' column.",
         "  2. Crowd or phone recording: add \"live\": true. Music under the voice: add \"isolate\": true.",
         "  3. Still unverified after two tries: delete that clip from film.json \"clips\" and from scenes."],
        why="unverified: " + ", ".join(unver))

# ---- 7. scenes ----
left = holders({k: film[k] for k in film if k not in ("_readme", "sources", "clips")})
used = {it.get("clip") for s in film.get("scenes", []) for it in s.get("items", []) if isinstance(it, dict)}
dangling = sorted(x for x in used if x and x not in clips)
unders = sorted({s["under"].get("src") for s in film.get("scenes", []) if isinstance(s.get("under"), dict)} - set(sources) - {None})
if left or dangling or unders:
    do = ["Open film.json. Replace every <<...>> below with real text. Rules:",
          "  title: 2-3 words, CAPITALS, ends with a period. accent: one color like #C8102E.",
          "  narrator \"say\" lines: one fact from story.md, at most 16 words, no praise words.",
          "  \"lines\" on screen: at most 7 words each. \"heading\": a date or 2-4 words.",
          "  Each {\"clip\": \"...\"} item must name a key in \"clips\". Put each quote in the scene for the year it is about.",
          "  The last clip item in the film must be the subject speaking (the payoff).",
          "  Delete a whole scene (or the chart) if you have no real facts for it. Never invent numbers.",
          "Still to replace:"] + ["  " + x for x in left[:12]] + (["  ... and %d more" % (len(left) - 12)] if len(left) > 12 else [])
    if unders: do.append("Scenes play sound \"under\" from sources that do not exist: " + ", ".join(unders) +
                         " -> set \"src\" to one of your sources, or delete the \"under\" key. No crowd recording? Make scene 1 a card whose first item is a clip.")
    if dangling: do.append("Scenes use clips that do not exist in \"clips\": " + ", ".join(dangling) + " -> change them to your clip keys.")
    say(7, "write the scenes", do, why=f"{len(left)} placeholder(s) left outside clips/sources")

# ---- 8. narrator ----
says = [it["say"] for s in film.get("scenes", []) for it in s.get("items", []) if isinstance(it, dict) and it.get("say")]
if any(not os.path.exists(f"narr/{say_id(t)}.json") for t in says):
    say(8, "record the narrator", ["python3 scripts/narrate.py"],
        why="every row must say ok. MISREAD: respell that word the way it sounds, then run narrate.py again.")

# ---- 9. timing ----
deps = ["film.json"] + glob.glob("clips/*.json") + glob.glob("narr/*.json")
plan = load("out/plan.json")
if not plan or mtime("out/plan.json") < max(mtime(p) for p in deps):
    say(9, "compute the timing", ["python3 scripts/plan.py"],
        why="if it prints OVER by or a FIX: line, do that first (remove a scene or quote; never speed up the narrator).")
limit = film.get("max_seconds", 140)
if plan.get("dur", 0) > limit:
    say(9, f"the film is too long ({plan['dur']:.0f} s, limit {limit} s)",
        ["Remove one quote item or one narrator line from a scene in film.json (do not change max_seconds).",
         "python3 scripts/plan.py"], why="X plays at most 140 s for normal accounts.")

sp = sorted([q for q in plan.get("audio", []) if q.get("role") in ("narr", "voice", "live")], key=lambda q: q["at"])
rs = sum(q["dur"] for q in sp if q["role"] != "narr"); ns = sum(q["dur"] for q in sp if q["role"] == "narr")
nq = len({q.get("id") for q in sp if q["role"] != "narr"}); wantq = max(3, round(plan.get("dur", 0) / 25))
if rs < 0.5 * (rs + ns):
    say(9, "let the subject talk more than the narrator",
        [f"Now: real voice {rs:.0f} s, narrator {ns:.0f} s. Real voice must be at least half.",
         "In film.json: add a quote item to a scene, make a clip longer, or delete a narrator \"say\" line.",
         "python3 scripts/next.py"], why="check.py fails a film where the narrator talks more than the subject.", then=None)
if nq < wantq:
    say(9, "add more quotes to the scenes", [f"The scenes use {nq} quotes; this length needs {wantq}. Add {{\"clip\": \"KEY\"}} items for clips you made but did not use, or make new clips (step 5)."],
        why="check.py counts the quotes the film plays.")
if sp and sp[-1]["role"] == "narr":
    say(9, "give the subject the last word", ["In the last scene that talks, put a {\"clip\": \"KEY\"} item after the last \"say\" item."],
        why="the film must end on the subject's own voice.")

# ---- 10. music + mix ----
mus = (film.get("music") or {}).get("file") or "music/synth.wav"
if mus != "music/synth.wav" and not os.path.exists(mus):
    say(10, f"music file {mus} is missing", [f"Put the track at {mus}, or set film.json \"music\" back to {{\"synth\": true}}."],
        why="film.json \"music\" names a file that does not exist.")
if not os.path.exists(mus) or (mus == "music/synth.wav" and mtime(mus) < mtime("out/plan.json")):
    say(10, "make the music", ["python3 scripts/score.py synth"])
if mtime("out/mix.wav") < max(mtime("out/plan.json"), mtime(mus)):
    say(10, "mix the sound", ["python3 scripts/mix.py"],
        why="every row must end in ok. COVERED: add \"isolate\": true to that clip (crowd/phone: \"live\": true), then python3 scripts/next.py")

# ---- 11. pictures ----
if mtime("out/sheet.jpg") < mtime("out/mix.wav"):
    say(11, "preview the frames (fast)", ["python3 scripts/render.py --sheet"],
        why="EMPTY: give that scene a heading, lines or a clip. CUT OFF AT EDGE: shorten that scene's heading or lines. If you can view images, open out/sheet.jpg.")
if mtime("out/final.mp4") < max(mtime("out/mix.wav"), mtime("out/plan.json")):
    say(11, "render the film",
        ["nohup python3 scripts/render.py > out/render.log 2>&1 &",
         "python3 scripts/next.py --wait      # waits while the film renders: about 4 minutes per minute of film"], then=None)

# ---- 12. check ----
if mtime("out/check.txt") < max(mtime("out/final.mp4"), mtime("film.json"), mtime("story.md")):
    r = subprocess.run([sys.executable, os.path.join(KIT, "check.py")], capture_output=True, text=True)
    with open("out/check.txt", "w", encoding="utf8") as f: f.write(r.stdout + r.stderr)
res = open("out/check.txt", encoding="utf8").read()
if "ALL CHECKS PASSED" in res:
    print(f"DONE: check.py passed for out/final.mp4 ({plan['dur']:.1f} s).")
    print("Hand over now. Your last message gives the user:")
    print(f"  1. the file: {os.path.join(proj, 'out/final.mp4')}   and its length")
    print("  2. every audio source with its URL (film.json \"sources\")")
    print("  3. the check table:  cat out/check.txt")
    print("  4. one honest sentence about anything you could not check yourself (for example, you cannot watch video).")
    sys.exit(0)
fails = [l for l in res.splitlines() if l.lstrip().startswith(("FAIL", "FIX", "ERROR")) or "  FIX" in l]
if not fails:
    say(12, "check.py crashed", ["out/check.txt ends with:"] + ["  " + l[:160] for l in res.strip().splitlines()[-4:]] +
        ["Fix what the last line names (a missing file: rerun the step that makes it), then: rm out/check.txt"],
        why="check.py stopped before it could measure the film.")
say(12, "fix what check.py failed",
    ["These lines are from out/check.txt:"] + ["  " + l.strip()[:160] for l in fails[:14]] +
    ["Do each FIX line. After any change, python3 scripts/next.py tells you what to rerun."],
    why="not done until check.py prints ALL CHECKS PASSED.")
