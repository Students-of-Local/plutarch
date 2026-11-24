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

CD = ""   # "cd PROJECT && " once inside a project: many agent shells do not keep cd between commands

def here(line):
    return CD + line if CD and line.startswith(("python3 scripts/", "nohup python3 scripts/", "grep ")) else line

def say(step, title, do, why=None, then="python3 scripts/next.py"):
    print(f"STEP {step} of {TOTAL}: {title}")
    if why: print(f"WHY: {why}")
    print("DO:")
    for line in do: print("  " + here(line))
    if then: print(f"THEN: {here(then)}")
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

# ---- 0. kit intact? ----
broken = []
for p in sorted(glob.glob(os.path.join(KIT, "*.py"))):
    try: compile(open(p, encoding="utf8").read(), p, "exec")
    except (SyntaxError, ValueError, UnicodeDecodeError): broken.append(os.path.basename(p))
if broken:
    say(0, "the skill is damaged",
        [f"Someone changed {', '.join(broken)} in {KIT}, and it no longer runs. Never edit, overwrite or replace a file in the skill folder.",
         "Reinstall the skill: copy a fresh plutarch/ folder from https://github.com/baney75/plutarch over the old one,",
         "or ask the user to. Your film project folder is safe: do not delete it."],
        why="a kit script does not compile.", then=f"python3 {QKIT}/next.py")

# ---- 0. tools installed? ----
need = ["numpy", "scipy", "soundfile", "pyloudnorm", "librosa", "skia", "PIL", "faster_whisper", "yt_dlp", "kokoro_onnx"]
missing = [m for m in need if importlib.util.find_spec(m) is None]
if missing:
    say(0, "install the tools (once per machine)",
        [f"python3 {QKIT}/setup.py --install",
         "If it says pip failed: python3 -m venv ~/.venvs/plutarch && . ~/.venvs/plutarch/bin/activate   then run the line above again."],
        why="missing Python packages: " + ", ".join(missing))

# ---- 1. inside a project? ----
SKILL = os.path.dirname(KIT)
if (os.path.realpath(os.getcwd()) + os.sep).startswith(os.path.realpath(SKILL) + os.sep):
    say(1, "leave the skill folder",
        [f"You are in {os.getcwd()}, inside the skill. Never make or edit a film here.",
         "Go back to the folder the user asked you to work in (where your shell starts) and run:",
         f"python3 {QKIT}/next.py"], then=None,
        why="the skill folder holds the kit. The film goes in the user's folder, e.g. ./films/lincoln there.")
if not (os.path.exists("film.json") and os.path.isdir("scripts")):
    make = [f"python3 {QKIT}/setup.py --init ./films/SHORTNAME      # SHORTNAME = the person's last name, lowercase, e.g. lincoln",
            "cd ./films/SHORTNAME && python3 scripts/next.py"]
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
CD = f"cd {shlex.quote(proj)} && "
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
                "clips.log": "Read the ERROR line: usually a clip's in/out or text is wrong. Run that clip's film.py clip command again with the fix.",
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
        ['python3 scripts/film.py set subject "FULL NAME"      # the person the user asked for (their name is in the request), e.g. "Abraham Lincoln"'])
if len(facts) < 5 or not sentence_ok:
    search_ok = importlib.util.find_spec("ddgs") or os.environ.get("SEARXNG_URL") or os.environ.get("BRAVE_API_KEY")
    do = ([] if search_ok else ["find_audio.py web needs a search engine. Run: python3 -m pip install ddgs   (or use your own web search tool for the next two lines)"]) + [f'python3 scripts/find_audio.py web "{who} biography"',
          f'python3 scripts/find_audio.py web "{who} career timeline"',
          'python3 scripts/film.py sentence "He rose from ___, it cost him ___, and then ___."      # the whole film in one sentence',
          'python3 scripts/film.py fact "Born March 3, 1960 in Ohio" https://first-source https://second-source',
          "  -> one film.py fact per fact, 5 or more. Each fact needs TWO different URLs from the search results.",
          "Use only facts you found in the search results. Copy the URLs exactly.",
          "If a search prints ERROR: web search failed, run it again or change the words."]
    say(2, "story first: one sentence and 5 facts with two sources each", do,
        why=f"story.md has {len(facts)} fact rows with two URLs (need 5)" + ("" if sentence_ok else " and no one-sentence summary yet"))

# ---- 3. audio sources ----
AUD = (".mp3", ".m4a", ".wav", ".flac", ".mp4", ".webm", ".mkv", ".opus", ".ogg", ".aac", ".mov", ".mpg", ".mpeg", ".avi",
       ".m4v", ".ts", ".3gp", ".flv", ".wma", ".aif", ".aiff", ".mka", ".amr", ".wmv")
sources = film.get("sources", {})
named = {v.get("file") for v in sources.values() if isinstance(v, dict) and isinstance(v.get("file"), str)}
srcfiles = sorted(f for f in glob.glob("src/*") if f.lower().endswith(AUD) or f in named)   # a file a source names is audio
if not srcfiles:
    say(3, "get a real recording of the subject's voice into src/",
        [f'python3 scripts/find_audio.py podcast "{who}"',
         "  -> pick a show that interviewed them; copy its feed URL",
         f'python3 scripts/find_audio.py episodes "FEED_URL" --grep "{who.split()[-1]}"',
         "  -> copy the audio URL of the episode with them in it",
         'python3 scripts/find_audio.py get "AUDIO_URL" --name interview',
         "It prints a film.py source command. Write the show name and year into it, then run it."],
        why="src/ has no audio yet. Read references/finding-audio.md if podcasts find nothing. YouTube is often blocked; prefer podcasts.")
bad_src = [k for k, v in sources.items() if holders(v) or not os.path.exists(v.get("file", ""))]
if bad_src or not sources:
    files = ", ".join(srcfiles)
    say(3, "list your recordings in film.json \"sources\"",
        [f"python3 scripts/film.py source {shlex.quote(os.path.splitext(os.path.basename(f))[0])} {shlex.quote(f)} \"SHOW (YEAR)\" URL"
          for f in srcfiles if f not in {v.get("file") for v in sources.values() if isinstance(v, dict) and not holders(v)}] +
         ["  -> write the show or event name and its year, and the URL you downloaded it from (find_audio.py get printed it).",
          "The first film.py source removes the template entries."] +
         [f"python3 scripts/film.py drop source {k}      # its file is missing" for k in bad_src if not holders(sources[k])],
        why=("these sources are template text or point to a missing file: " + ", ".join(bad_src)) if bad_src else "film.json \"sources\" is empty.")
if len(sources) < 2:
    say(3, "get a second recording (a different interview, speech or event)",
        [f'python3 scripts/find_audio.py podcast "{who}"',
         f'python3 scripts/find_audio.py archive "{who}"',
         'python3 scripts/find_audio.py get "AUDIO_URL" --name SECOND_NAME',
         "Then run the film.py source command it prints, with the show name and year filled in."],
        why="the film needs real voice from at least 2 sources (check.py and the acceptance checks require it).")

# ---- 4. transcripts ----
todo = [v["file"] for v in sources.values() if mtime(f"tx/{os.path.splitext(os.path.basename(v['file']))[0]}.json") < mtime(v["file"])]
if todo:
    say(4, "transcribe " + " and ".join(todo),
        [f"nohup python3 scripts/transcribe.py {' '.join(shlex.quote(f) for f in todo)} > out/tx.log 2>&1 &",
         "python3 scripts/next.py --wait      # waits while transcribe runs" + (": one command does every file" if len(todo) > 1 else "")],
        then=None, why="you search the transcript for quotes. A 1-hour file takes about 5-10 minutes on a CPU.")

# ---- 5. quotes ----
clips = film.get("clips", {})
real = {k: c for k, c in clips.items() if not holders(c) and c.get("out", 0) > c.get("in", 0)}
tx = sorted(glob.glob("tx/*.json"))
if holders(clips) or len(real) < 6:
    say(5, "choose 6-10 quotes and put them in film.json \"clips\"",
        [f'python3 scripts/clip.py find {tx[0] if tx else "tx/interview.json"} "a few words or an idea"',
         "  -> each result shows   \"in\": 560.9, \"out\": 562.3   and the sentence that was said",
         "Search for ideas from story.md: the start, the risk, the cost, the turn, the comeback.",
         f'python3 scripts/film.py clip {next(b for b in ["start", "risk", "cost", "turn", "payoff", "comeback"] + [f"q{n}" for n in range(7, 99)] if b not in real)} '
         f'{(next((k for k, v in sources.items() if not holders(v)), "interview"))} IN OUT "the exact words said" YEAR "what he was talking about"',
         "  -> one film.py clip per quote: a key no other clip uses (the one above is free), a source key, IN and OUT from the",
         "     result, the exact words shown after >>>, the year it was said, and what it was about.",
         "     Add --live for a crowd or phone recording. The first film.py clip removes the template clips.",
         "Use quotes from at least 2 different sources." + (f"  Clips so far: {', '.join(real)}." if real else "")],
        why=f"film.json has {len(real)} finished clips (need 6 or more)" + (" and template entries still in \"clips\"" if holders(clips) else ""))
srcs_used = {c["src"] for c in real.values()}
if len(srcs_used) < 2:
    say(5, "add a quote from your second recording",
        [f"python3 scripts/clip.py find tx/SECOND.json \"words\"      # transcripts: {', '.join(tx)}",
         "python3 scripts/film.py clip KEY SECOND_SOURCE IN OUT \"exact words\" YEAR \"what it was about\"      # SECOND_SOURCE: " +
         ", ".join(k for k in sources if k not in srcs_used)],
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
         "  1. Run the same film.py clip command again (same KEY) with the exact words from the 'heard' column.",
         "  2. Crowd or phone recording: python3 scripts/film.py clip KEY --live   Music under the voice: ... clip KEY --isolate",
         "  3. Still unverified after two tries: python3 scripts/film.py drop clip KEY"],
        why="unverified: " + ", ".join(unver))

# ---- 7. scenes ----
left = holders({k: film[k] for k in film if k not in ("_readme", "sources", "clips")})
used = {it.get("clip") for s in film.get("scenes", []) for it in s.get("items", []) if isinstance(it, dict)}
dangling = sorted(x for x in used if x and x not in clips)
unders = sorted({s["under"].get("src") for s in film.get("scenes", []) if isinstance(s.get("under"), dict)} - set(sources) - {None})
scenes = film.get("scenes", [])
if left or dangling or unders or not scenes or scenes[-1].get("type") != "end":
    order = list(real)   # "year" is when it was said, not what it is about: the agent orders and dates the cards
    do = []
    if holders(film.get("title", "<<")) or not film.get("title"): do.append('python3 scripts/film.py set title "TWO WORDS."        # 2-3 words, capitals, ends with a period')
    if holders(film.get("accent", "<<")) or not film.get("accent"): do.append('python3 scripts/film.py set accent "#C8102E"          # one color that fits the subject')
    if holders(scenes) or dangling or unders: do.append("python3 scripts/film.py scenes clear                 # removes the template scenes")
    if not scenes or holders(scenes) or dangling or unders:
        do.append("python3 scripts/film.py scene add title")
        for n, k in enumerate(order):
            c = real[k]; say_ = ' --say "One fact from story.md, max 16 words."' if n % 2 == 0 else ""
            do.append(f'python3 scripts/film.py scene add card --heading "DATE" --line "up to 7 words"{say_} --clip {k}      # {str(c.get("about", ""))[:40]}')
        do.append('python3 scripts/film.py scene add end --accent-text "2-3 WORDS."      # the answer to the title')
        do += ["  -> put the cards in the order of the events each quote is ABOUT (not the year it was said).",
               "  -> --heading is the date of that event; --line and --say are real facts from story.md. Never invent numbers.",
               "  -> a scene can play a clip with no --say: the subject must talk more than the narrator.",
               "  -> the last scene before the end card must end with a --clip (the payoff)."]
    elif scenes[-1].get("type") != "end":
        do.append('python3 scripts/film.py scene add end --accent-text "2-3 WORDS."      # the film must end on the end card')
    if left and not do:
        do = ["These fields still have template text:"] + ["  " + x for x in left[:12]] + \
             ["Fix each with python3 scripts/film.py set KEY VALUE if KEY is title, subject, accent or max_seconds;",
              "otherwise open film.json and put a real value at that spot (field list: references/film-json.md)."]
    do.append("python3 scripts/film.py scenes      # check the order")
    say(7, "write the scenes", do, why=f"{len(left)} placeholder(s) left outside clips/sources" if left else "the film has no scenes or no end card yet")

# ---- 8. narrator ----
says = [it["say"] for s in film.get("scenes", []) for it in s.get("items", []) if isinstance(it, dict) and it.get("say")]
if any(not os.path.exists(f"narr/{say_id(t)}.json") for t in says):
    say(8, "record the narrator", ["python3 scripts/narrate.py"],
        why="every row must say ok. MISREAD: run the film.py reword line it prints, with the hard word respelled the way it sounds, then narrate.py again.")

# ---- 9. timing ----
deps = ["film.json"] + glob.glob("clips/*.json") + glob.glob("narr/*.json")
plan = load("out/plan.json")
if not plan or mtime("out/plan.json") < max(mtime(p) for p in deps):
    say(9, "compute the timing", ["python3 scripts/plan.py"],
        why="if it prints OVER by or a FIX: line, do that first (remove a scene or quote; never speed up the narrator).")
limit = film.get("max_seconds", 140)
if plan.get("dur", 0) > limit:
    say(9, f"the film is too long ({plan['dur']:.0f} s, limit {limit} s)",
        ["python3 scripts/film.py scenes                # find a scene you can lose",
         "python3 scripts/film.py drop scene N          # do not change max_seconds",
         "python3 scripts/plan.py"], why="X plays at most 140 s for normal accounts.")

sp = sorted([q for q in plan.get("audio", []) if q.get("role") in ("narr", "voice", "live")], key=lambda q: q["at"])
rs = sum(q["dur"] for q in sp if q["role"] != "narr"); ns = sum(q["dur"] for q in sp if q["role"] == "narr")
nq = len({q.get("id") for q in sp if q["role"] != "narr"}); wantq = max(3, round(plan.get("dur", 0) / 25))
if rs < 0.5 * (rs + ns):
    say(9, "let the subject talk more than the narrator",
        [f"Now: real voice {rs:.0f} s, narrator {ns:.0f} s. Real voice must be at least half.",
         "Add a scene that only plays a clip:  python3 scripts/film.py scene add card --clip KEY",
         "or drop a scene that is mostly narrator:  python3 scripts/film.py scenes  then  python3 scripts/film.py drop scene N",
         "python3 scripts/next.py"], why="check.py fails a film where the narrator talks more than the subject.", then=None)
if nq < wantq:
    say(9, "add more quotes to the scenes", [f"The scenes use {nq} quotes; this length needs {wantq}.",
         "python3 scripts/film.py scene add card --heading \"YEAR\" --clip KEY      # for clips you made but did not use: " +
         ", ".join(k for k in real if k not in used), "or make new clips (step 5)."],
        why="check.py counts the quotes the film plays.")
if sp and sp[-1]["role"] == "narr":
    say(9, "give the subject the last word", ["python3 scripts/film.py scene add card --clip KEY      # goes just before the end card; use your strongest quote"],
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
        why="every row must end in ok. COVERED: python3 scripts/film.py clip KEY --isolate (crowd/phone: --live), then python3 scripts/next.py")

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
