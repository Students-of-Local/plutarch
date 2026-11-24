#!/usr/bin/env python3
"""Change film.json and story.md with one command each, so you never hand-edit JSON.

  python3 scripts/film.py set subject "Abraham Lincoln"        # also: title "THE LONG ROAD."  accent "#B22234"
  python3 scripts/film.py sentence "He rose from a log cabin, lost again and again, and then led the nation."
  python3 scripts/film.py fact "Elected president on November 6, 1860" https://source-one https://source-two
  python3 scripts/film.py source interview src/interview.mp3 "Show Name (2019)" https://where-you-got-it
  python3 scripts/film.py clip start interview 560.9 562.3 "the exact words" 2010 "what he was talking about"
      add --live for a crowd or phone recording, --isolate for music under the voice
      each quote has its own key; a key that holds a different quote is refused (--replace swaps it)
  python3 scripts/film.py clip start --isolate                  # change one clip: --live --isolate --no-live --no-isolate
  python3 scripts/film.py clip start --lines "I was told" "I could not do it"   # captions: the heard words, corrected
      clip.py prints this command with the heard words filled in; change only the wrong words (--no-lines undoes it)
  python3 scripts/film.py scenes clear                          # remove the template scenes
  python3 scripts/film.py scene add card --heading "NOVEMBER 6, 1860" --line "Elected president" --say "One fact." --clip start
  python3 scripts/film.py scene add title                       # uses "title" and "subject"
  python3 scripts/film.py scene add end --accent-text "HE KEPT GOING."
  python3 scripts/film.py scenes                                # list scenes with numbers
      new scenes go before the end card; --at 2 puts one at position 2
  python3 scripts/film.py reword "First words of a narrator line" "The line, respelled the way it sounds."
  python3 scripts/film.py drop scene 3        # also: drop clip KEY, drop source KEY, drop fact 2
  python3 scripts/film.py show                                  # what is in film.json now

Scene items play in the order you give --say, --clip and --gap. Run python3 scripts/next.py after changes."""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts
from common import write_file

FILM, STORY = "film.json", "story.md"
USAGE = __doc__.split("\n\n", 1)[1]

def die(msg, fix=None):
    print("ERROR: " + msg)
    if fix: print("FIX: " + fix)
    sys.exit(1)

def load():
    if not os.path.exists(FILM): die("no film.json here.", "cd into the film project (the folder with film.json), or run next.py.")
    try: return json.load(open(FILM, encoding="utf8"))
    except json.JSONDecodeError as e:
        die(f"film.json is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}).", "fix that spot by hand once; after that use film.py.")

def save(f):
    write_file(FILM, json.dumps(f, indent=1, ensure_ascii=False) + "\n")

def placeholder(s): return "<<" in s or bool(re.search(r"<[A-Za-z][^<>]*>", s))   # same rule as next.py
def is_tpl(x): return "<<" in json.dumps(x)
def words(s): return len(s.split())
def num(s, what):
    try: return float(s)
    except ValueError: die(f"{what} must be a number of seconds, got {s!r}.", "copy the numbers from clip.py find, e.g. 560.9")

def cmd_set(a):
    if len(a) != 2 or a[0] not in ("subject", "title", "accent", "max_seconds"):
        die("use: film.py set subject|title|accent|max_seconds VALUE")
    k, v = a; f = load()
    if k == "title":
        v = v.upper().strip()
        if not v.endswith("."): v += "."
        if not 1 <= words(v) <= 4: die(f"title {v!r} should be 2-3 words.")
    if k == "accent" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", v): die(f"accent {v!r} is not a color.", 'use a hex color like "#C8102E".')
    if k == "max_seconds":
        v = int(num(v, "max_seconds"))
        if v > 140: print("NOTE: over 140 s only plays for X Premium accounts. Only do this if the user said so.")
    old = f.get(k)
    for sc in f.get("scenes", []):                     # the title and end cards show these: keep them in step
        if k == "title" and sc.get("type") in ("title", "end") and sc.get("text") == old: sc["text"] = v
        if k == "subject" and sc.get("type") == "title" and isinstance(old, str) and sc.get("sub", [None])[0] == old.upper(): sc["sub"][0] = v.upper()
    f[k] = v; save(f); print(f"OK {k} = {v}")

def story():
    if not os.path.exists(STORY): die("no story.md here.", "cd into the film project.")
    return open(STORY, encoding="utf8").read()

def cmd_sentence(a):
    if len(a) != 1 or words(a[0]) < 6: die('use: film.py sentence "the whole film in one sentence"')
    s = story(); m = re.search(r"(## The film in one sentence\s*\n)(.*)\n", s)
    if not m: die("story.md has no '## The film in one sentence' heading.")
    write_file(STORY, s[:m.start(2)] + a[0].strip() + s[m.end(2):]); print("OK one sentence written to story.md")

def fact_rows(s):
    return [r[0] for r in facts.rows(s)]      # line numbers

def cmd_fact(a):
    if len(a) != 3: die('use: film.py fact "the fact with its date" URL1 URL2')
    text, u1, u2 = a
    for u in (u1, u2):
        if not u.startswith(("http://", "https://")): die(f"{u!r} is not a URL.", "copy the full https:// address from the search result.")
    if facts.same(u1, u2): die("the two sources are the same URL.", "each fact needs two different sources.")
    who = str(load().get("subject") or "")
    if not facts.OFF:
        if not who or is_tpl(who): die("film.json has no subject yet.", 'python3 scripts/film.py set subject "the person\'s name", then add the fact.')
        bad = facts.problem(text, [u1, u2], who)
        if bad: die(f"this fact is not added. {bad[0]}.", "run it again when the network works. If it fails twice, use another page." if bad[1] else "open the page and use what it says, or use another page. Never guess a date or number.")
    s = story(); lines = s.splitlines()
    try: head = next(i for i, l in enumerate(lines) if l.startswith("| # | Fact"))
    except StopIteration: die("story.md has no Facts table.")
    i = head + 2
    while i < len(lines) and lines[i].startswith("|"):
        if re.fullmatch(r"\|\s*\d*\s*\|\s*\|\s*\|\s*\|", lines[i].strip()): del lines[i]; continue   # empty template row
        i += 1
    n = len([l for l in lines[head + 2:i] if l.startswith("|")]) + 1
    lines.insert(i, f"| {n} | {text.strip()} | {u1} | {u2} |")
    write_file(STORY, "\n".join(lines) + "\n"); facts.passed(text, [u1, u2], who); print(f"OK fact {n} added to story.md. " + (f"{5 - n} more to add." if n < 5 else "Next: python3 scripts/next.py"))

def no_audio(path):
    try: p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired): return False
    return p.returncode == 0 and "audio" not in p.stdout      # a file ffprobe can't read is reported by transcribe.py

def cmd_source(a):
    if len(a) != 4: die('use: film.py source KEY FILE "Credit (year)" URL')
    k, path, credit, url = a; f = load()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", k): die(f"key {k!r}: use letters, digits, - and _ only.")
    if not os.path.exists(path): die(f"{path} does not exist.", "download it first with find_audio.py get, then use the file it printed.")
    if no_audio(path): die(f"{path} has no sound in it (a video-only download).", "get it again with find_audio.py get, which downloads the audio.")
    if "<" in credit or "YEAR" in credit or not re.search(r"\b(1[6-9]|20)\d\d\b", credit):
        die(f"credit {credit!r} needs the real show or event name and its year.", 'e.g. "The Turf podcast (2025)" or "Gettysburg Address (1863)".')
    src = {kk: v for kk, v in f.get("sources", {}).items() if not is_tpl(v)}      # first real source drops the template ones
    src[k] = {"file": path, "credit": credit, "url": url}; f["sources"] = src; save(f)
    print(f"OK source {k} -> {path}   ({len(src)} source(s)). Next: python3 scripts/next.py")

BEATS = ["start", "risk", "cost", "turn", "payoff", "comeback"]
def free_key(used):
    return next((b for b in BEATS + [f"q{n}" for n in range(7, 99)] if b not in used), "q99")

def cmd_clip(a):
    flags = [x for x in a if x.startswith("--")]; a = [x for x in a if not x.startswith("--")]
    if "--lines" in flags: return clip_lines(a)
    if len(a) == 1 and flags:                           # film.py clip KEY --isolate | --live | --no-live | --no-isolate
        f = load(); c = f.get("clips", {}).get(a[0])
        if not isinstance(c, dict) or is_tpl(c): die(f"no clip {a[0]!r}.")
        for x in flags:
            if x not in ("--live", "--isolate", "--no-live", "--no-isolate", "--no-lines", "--replace"): die(f"unknown option {x}.")
            if x == "--no-lines": c.pop("lines", None)
            elif x != "--replace": c[x.replace("--no-", "--")[2:]] = not x.startswith("--no-")
        save(f); print(f"OK clip {a[0]}: live={bool(c.get('live'))} isolate={bool(c.get('isolate'))}"); return
    if len(a) != 7: die('use: film.py clip KEY SOURCE IN OUT "exact words" YEAR "what it is about"  [--live] [--isolate]')
    k, src, i, o, text, year, about = a; f = load()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", k): die(f"key {k!r}: use letters, digits, - and _ only.")
    if src not in f.get("sources", {}) or is_tpl(f["sources"][src]):
        die(f"no source {src!r}.", "use one of: " + ", ".join(kk for kk, v in f.get("sources", {}).items() if not is_tpl(v)))
    i, o = num(i, "IN"), num(o, "OUT")
    if o <= i: die(f"OUT ({o}) must be after IN ({i}).")
    if o - i < 1: die(f"this quote is {o - i:.1f} s long.", "a quote is 1-20 seconds and makes sense alone: pick a longer one.")
    if o - i > 25: die(f"this quote is {o - i:.0f} s long.", "a quote is 1-20 seconds: pick one sentence.")
    try: year = int(year)
    except ValueError: die(f"YEAR must be a year like 2010, got {year!r}.")
    clips = {kk: v for kk, v in f.get("clips", {}).items() if not is_tpl(v)}
    c = {"src": src, "in": i, "out": o, "text": text.strip(), "year": year, "about": about.strip()}
    if "--live" in flags: c["live"] = True
    if "--isolate" in flags: c["isolate"] = True
    old = clips.get(k)
    if old and "--replace" not in flags and (old.get("src") != src or not (i < old.get("out", 0) and o > old.get("in", 0))):
        die(f"clip {k!r} is already a different quote: {old.get('src')} {old.get('in')}-{old.get('out')} \"{str(old.get('text', ''))[:50]}\".",
            f"give each quote its own key: film.py clip {free_key(clips)} {src} {i:g} {o:g} ...   (add --replace only to swap out {k!r}).")
    for kk in ("live", "isolate", "lines"):            # keep what was set on this clip before unless told otherwise
        if kk in clips.get(k, {}) and kk not in c and f"--no-{kk}" not in flags: c[kk] = clips[k][kk]
    clips[k] = c; f["clips"] = clips; save(f); print(f"OK clip {k} ({o - i:.1f} s)   ({len(clips)} clip(s))")

def clip_lines(a):
    """film.py clip KEY --lines "caption line" ...: the caption words, one argument per line, same count as heard."""
    if len(a) < 2: die('use: film.py clip KEY --lines "first caption line" "second caption line" ...')
    k, lines = a[0], [l.strip() for l in a[1:]]
    f = load(); c = f.get("clips", {}).get(k)
    if not isinstance(c, dict) or is_tpl(c): die(f"no clip {k!r}.", "use one of: " + ", ".join(kk for kk, v in f.get("clips", {}).items() if not is_tpl(v)))
    long = [l for l in lines if words(l) > 9 or not l]
    if long: die(f"caption line {long[0]!r} has {words(long[0])} words.", "a caption line is 1-9 words: split it into two arguments.")
    try: heard = [w["w"] for w in json.load(open(f"clips/{k}.json", encoding="utf8"))["words"]]
    except (OSError, ValueError, KeyError, TypeError): heard = None
    n = sum(words(l) for l in lines)
    if heard is not None and n != len(heard):
        die(f"these lines have {n} words, but {len(heard)} words were heard: {' '.join(heard)}",
            f"give exactly {len(heard)} words: copy the command clip.py printed for {k} and change only the wrong words.")
    c["lines"] = lines; save(f)
    print(f"OK clip {k}: captions set ({len(lines)} line(s), {n} words). Next: python3 scripts/next.py")

SCENE_FLAGS = {"--at": "_at", "--id": "id", "--heading": "heading", "--bg": "bg", "--ghost": "ghost", "--text": "text",
               "--accent-text": "accent_text", "--accent-word": "accent_word", "--reveal": "reveal", "--chant": "chant", "--peak": "peak"}

def cmd_scene(a):
    if not a or a[0] != "add" or len(a) < 2: die("use: film.py scene add TYPE [--heading H] [--line L] [--say S] [--clip KEY] [--gap N] ...")
    typ = a[1]; f = load()
    if typ not in ("card", "title", "stack", "arena", "end"): die(f"scene type {typ!r}.", "use card, title, stack, arena or end (charts: edit film.json by hand).")
    sc = {"type": typ}; items = []; lines = []; sub = []; wordlist = []; it = iter(a[2:]); clips = f.get("clips", {})
    for x in it:
        if x == "--big":
            if not items or "clip" not in items[-1]: die("--big goes right after a --clip.")
            items[-1]["big"] = True; continue
        try: v = next(it)
        except StopIteration: die(f"{x} needs a value after it.")
        if x in SCENE_FLAGS: sc[SCENE_FLAGS[x]] = v
        elif x == "--line":
            if words(v) > 7: die(f"screen line {v!r} has {words(v)} words.", "screen lines are at most 7 words.")
            lines.append(v)
        elif x == "--sub": sub.append(v)
        elif x == "--words": wordlist += v.split()
        elif x == "--say":
            if words(v) > 16: die(f"narrator line has {words(v)} words.", "narrator lines are at most 16 words: one fact.")
            items.append({"say": v})
        elif x == "--clip":
            if v not in clips or is_tpl(clips[v]): die(f"no clip {v!r}.", "add it first with film.py clip, or use one of: " + ", ".join(k for k, c in clips.items() if not is_tpl(c)))
            items.append({"clip": v})
        elif x == "--gap": items.append({"gap": num(v, "--gap")})
        else: die(f"unknown option {x}.", "options: --heading --line --say --clip --gap --big --bg --ghost --words --accent-word --text --sub --accent-text --peak --id --at")
    if lines:
        if len(lines) > 3: die("at most 3 --line per scene.")
        sc["lines"] = lines
    if sub: sc["sub"] = sub[:2]
    if wordlist: sc["words"] = wordlist
    if items: sc["items"] = items
    title = f.get("title", ""); title = "" if "<<" in title else title
    if typ == "title":
        if not title: die("set the title first: film.py set title \"TWO WORDS.\"")
        sc.setdefault("text", title)
        if not sub and "<<" not in f.get("subject", "<<"): sc["sub"] = [f["subject"].upper()]
    if typ == "end":
        if not title: die("set the title first: film.py set title \"TWO WORDS.\"")
        sc.setdefault("text", title)
        if "accent_text" not in sc: die("an end scene needs --accent-text \"2-3 WORDS.\" (the answer to the title)")
    if typ == "card" and not (sc.get("heading") or lines or items): die("a card needs a --heading, a --line or an item.")
    if typ == "stack":
        n = sum("clip" in i for i in items)
        if n != 1 or not wordlist: die("a stack needs exactly one --clip and --words \"3 to 6 words he says in that clip\".")
    if typ == "arena": sc.setdefault("reveal", "hits")
    scenes = [s for s in f.get("scenes", []) if not is_tpl(s)]
    at = sc.pop("_at", None)
    if at is not None: pos = min(max(int(num(at, "--at")), 1), len(scenes) + 1) - 1
    elif typ != "end" and scenes and scenes[-1].get("type") == "end": pos = len(scenes) - 1   # keep the end card last
    else: pos = len(scenes)
    scenes.insert(pos, sc); f["scenes"] = scenes; save(f)
    print(f"OK scene {pos + 1} of {len(scenes)}: {typ} {sc.get('heading', sc.get('text', ''))}")

def cmd_scenes(a):
    f = load()
    if a == ["clear"]:
        f["scenes"] = []; save(f); print("OK all scenes removed. Add them in order with film.py scene add ..."); return
    for n, s in enumerate(f.get("scenes", []), 1):
        its = " ".join(("say" if "say" in i else f"clip:{i['clip']}" if "clip" in i else f"gap:{i.get('gap')}") for i in s.get("items", []) if isinstance(i, dict))
        print(f"{n:2}  {s.get('type'):<6} {str(s.get('heading', s.get('text', '')))[:30]:<30} {its}" + ("   <<TEMPLATE>>" if is_tpl(s) else ""))
    if not f.get("scenes"): print("no scenes yet")

def cmd_drop(a):
    if len(a) != 2 or a[0] not in ("scene", "clip", "source", "fact"): die("use: film.py drop scene N | clip KEY | source KEY | fact N")
    what, k = a
    if what == "fact":
        s = story(); rows = fact_rows(s); n = int(num(k, "N"))
        if not 1 <= n <= len(rows): die(f"there are {len(rows)} facts.")
        ls = s.splitlines(); del ls[rows[n - 1]]; write_file(STORY, "\n".join(ls) + "\n"); print(f"OK fact {n} removed"); return
    f = load()
    if what == "scene":
        sc = f.get("scenes", []); n = int(num(k, "N"))
        if not 1 <= n <= len(sc): die(f"there are {len(sc)} scenes (film.py scenes lists them).")
        del sc[n - 1]
    else:
        d = f.get(what + "s", {})
        if k not in d: die(f"no {what} {k!r}.")
        if what == "source":
            users = [c for c, v in f.get("clips", {}).items() if isinstance(v, dict) and v.get("src") == k and not is_tpl(v)]
            under = [str(n) for n, s in enumerate(f.get("scenes", []), 1) if isinstance(s.get("under"), dict) and s["under"].get("src") == k]
            if users: die(f"clips {', '.join(users)} use source {k}.", f"drop them first: film.py drop clip {users[0]}")
            if under: die(f"scene(s) {', '.join(under)} play sound from source {k}.", f"film.py drop scene {under[0]}")
        del d[k]
        if what == "clip":
            for s in f.get("scenes", []): s["items"] = [i for i in s.get("items", []) if not (isinstance(i, dict) and i.get("clip") == k)]
    save(f); print(f"OK {what} {k} removed")

def cmd_reword(a):
    if len(a) != 2: die('use: film.py reword "first words of the old line" "the new line"')
    old, new = a[0].strip(), a[1].strip(); f = load()
    if not old: die("give the first words of the narrator line to change.")
    if not new: die("the new line is empty.")
    if words(new) > 16: die(f"narrator line has {words(new)} words.", "narrator lines are at most 16 words: one fact.")
    texts = []
    for sc in f.get("scenes", []):
        for it in sc.get("items", []):
            if isinstance(it, dict) and isinstance(it.get("say"), str) and it["say"] not in texts: texts.append(it["say"])
    hit = [t for t in texts if t.strip() == old] or [t for t in texts if t.strip().lower().startswith(old.lower())]
    if len(hit) != 1:
        shown = "\n".join("  " + t for t in (hit or texts)) or "  (no narrator lines yet)"
        die(f"{len(hit) or 'no'} narrator lines start with {old!r}:\n{shown}", "give the first words of exactly one line above.")
    n = 0
    for sc in f.get("scenes", []):
        for it in sc.get("items", []):
            if isinstance(it, dict) and it.get("say") == hit[0]: it["say"] = new; n += 1
    save(f); print(f"OK {n} narrator item(s) now say: {new!r}. Next: python3 scripts/next.py")

def cmd_show(a):
    f = load(); real = lambda d: [k for k, v in d.items() if not is_tpl(v)]
    print(f"subject: {f.get('subject')}   title: {f.get('title')}   accent: {f.get('accent')}")
    print(f"sources: {', '.join(real(f.get('sources', {}))) or '-'}")
    for k, c in f.get("clips", {}).items():
        if not is_tpl(c): print(f"  clip {k:<12} {c['src']:<10} {c['in']:>7.1f}-{c['out']:<7.1f} {c.get('year', '')}  \"{c['text'][:50]}\"")
    print(f"scenes: {len(f.get('scenes', []))}" + (" (template scenes still there: film.py scenes clear)" if any(is_tpl(s) for s in f.get("scenes", [])) else ""))
    if os.path.exists(STORY): print(f"facts in story.md: {len(fact_rows(story()))}")

EXAMPLES = {"FULL NAME", "TWO WORDS.", "2-3 WORDS.", "up to 7 words", "One fact from story.md, max 16 words.", "SHOW (YEAR)", "URL",
            "the exact words said", "what he was talking about", "Born March 3, 1960 in Ohio", "https://first-source",
            "https://second-source", "https://where-you-got-it", "YEAR", "DATE", "KEY", "SECOND_SOURCE", "IN", "OUT",
            "the line, respelled", "the words after >>>", "SOURCE", "First words of a narrator line", "The line, respelled the way it sounds.",
            "I was told", "I could not do it"}
if any(x in ("-h", "--help") for x in sys.argv[1:]): print(USAGE); sys.exit(0)
for x in sys.argv[2:]:
    if x.strip() in ("IN", "OUT"):
        die(f"{x!r} is the example text from next.py.", 'use the two numbers clip.py find printed after "in": and "out":, like 560.9 562.3.')
    if x.strip() in EXAMPLES or "___" in x or placeholder(x):
        die(f"{x!r} is the example text from next.py.", "write the real value for this film there, then run the command again.")

CMDS = {"set": cmd_set, "sentence": cmd_sentence, "fact": cmd_fact, "source": cmd_source, "clip": cmd_clip,
        "scene": cmd_scene, "scenes": cmd_scenes, "drop": cmd_drop, "reword": cmd_reword, "show": cmd_show}
if len(sys.argv) < 2 or sys.argv[1] not in CMDS: print(USAGE); sys.exit(0 if len(sys.argv) < 2 else 1)
CMDS[sys.argv[1]](sys.argv[2:])
