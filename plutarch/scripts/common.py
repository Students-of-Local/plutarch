"""Shared helpers for the plutarch kit. Run every script from your PROJECT folder (the one with film.json)."""
import json, os, shlex, subprocess, sys, hashlib, re
import numpy as np

SR = 48000
KIT = os.path.dirname(os.path.realpath(__file__))      # realpath: works when the project links to this folder

def die(msg):
    print("ERROR: " + msg); sys.exit(1)

def dq(s):
    """Shell-quote text a model will copy or edit. shlex.quote turns I'm into I'"'"'m, which small models break."""
    s = str(s)
    return shlex.quote(s) if "'" not in s else '"' + re.sub(r'([\\"$`])', r'\\\1', s) + '"'

def need(path, hint=""):
    if not os.path.exists(path): die(f"missing {path}. {hint}")

def load_json(p):
    try:
        with open(p, encoding="utf8") as f: return json.load(f)
    except json.JSONDecodeError as e:
        die(f"{p} is not valid JSON (line {e.lineno}, col {e.colno}): {e.msg}")

def save_json(p, obj):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf8") as f: json.dump(obj, f, indent=1, ensure_ascii=False)

def load_film(p="film.json", only=None):
    """only = top-level keys that must be free of <<placeholders>> (None = the whole file)."""
    need(p, "Make a project first: python3 <skill>/scripts/setup.py --init <folder>")
    film = load_json(p); left = []
    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items(): walk(v, f"{path}.{k}" if path else k)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, f"{path}[{i}]")
        elif isinstance(x, str) and "<<" in x: left.append(f"{path}: {x[:60]}")
    for k, v in film.items():
        if only is None or k in only: walk(v, k)
    if left:
        where = "film.json" if only is None else "film.json (" + ", ".join(only) + ")"
        die(where + " still has " + str(len(left)) + " template placeholder(s). Replace every <<...>> with real content (delete template entries you do not use):\n  " + "\n  ".join(left[:8]))
    return film

def audio(path, ss=None, to=None, ch=2, sr=SR):
    """Decode any media file to float64 [n, ch] with ffmpeg."""
    need(path)
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None: cmd += ["-ss", f"{max(0, ss):.3f}"]
    if to is not None: cmd += ["-to", f"{to:.3f}"]
    cmd += ["-i", path, "-vn", "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout: die(f"ffmpeg could not read audio from {path}: {r.stderr.decode()[:200]}")
    return np.frombuffer(r.stdout, np.float32).reshape(-1, ch).astype(np.float64)

def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: die(f"ffprobe could not read {path}")

def save_wav(path, x, sr=SR):
    import soundfile as sf
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sf.write(path, np.asarray(x, np.float32), sr)

def clip_spec(c):
    """Fingerprint of the clip fields that change the cut. next.py compares it to find stale clips."""
    keep = {k: c.get(k) for k in ("src", "in", "out", "text", "lines", "live", "isolate")}
    return hashlib.md5(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:10]

def say_id(text):
    return "n" + hashlib.md5(text.strip().encode("utf8")).hexdigest()[:9]

_models = {}
def whisper(model="small.en"):
    if model not in _models:
        from faster_whisper import WhisperModel
        _models[model] = WhisperModel(model, device=os.environ.get("PLUTARCH_DEVICE", "cpu"), compute_type="int8",
                                      cpu_threads=max(2, (os.cpu_count() or 2)))   # cpu by default: "auto" crashes where an NVIDIA driver exists without CUDA libraries
    return _models[model]

def words_of(x16k, model="small.en", vad=False):
    """x16k: mono float32 at 16 kHz. Returns [{w,s,e,p}] with times in seconds."""
    segs, _ = whisper(model).transcribe(np.asarray(x16k, np.float32), word_timestamps=True,
                                        condition_on_previous_text=False, vad_filter=vad)
    out = []
    for sg in segs:
        for w in (sg.words or []):
            out.append({"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3), "p": round(float(w.probability), 2)})
    return out

def norm_word(w): return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))

def similarity(a, b):
    import difflib
    A = [norm_word(w) for w in a.split()]; B = [norm_word(w) for w in b.split()]
    A = [w for w in A if w]; B = [w for w in B if w]
    if not A or not B: return 0.0
    return difflib.SequenceMatcher(None, A, B).ratio()

def hexrgb(h, default=(118, 185, 0)):
    try:
        h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception: return default

def table(rows, head):
    w = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    line = lambda r: "  ".join(str(c).ljust(w[i]) for i, c in enumerate(r))
    print(line(head)); print("  ".join("-" * x for x in w))
    for r in rows: print(line(r))

def load_plan():
    need("out/plan.json", "Run: python3 scripts/plan.py")
    return load_json("out/plan.json")

def music_window(plan):
    """(start, end) of the music in film time: from the first scene that has music to the end."""
    on = [s for s in plan["scenes"] if s["music"]]
    return (on[0]["t0"] if on else 0.0), plan["dur"]

def energy_at(plan, t):
    """Target intensity of the music at film time t (0 = silence, 1 = full)."""
    for s in plan["scenes"]:
        if s["t0"] <= t < s["t1"]:
            if not s["music"]: return 0.0
            p = (t - s["t0"]) / max(1e-6, s["t1"] - s["t0"]); e0, e1 = s["energy"]
            if s["type"] in ("title", "end"): return e1 + (e0 - e1) * np.exp(-p * 5)
            return e0 + (e1 - e0) * p
    return 0.0

def mmss(t): return f"{int(t // 60)}:{int(t % 60):02d}"


def speech_gap(v, m, sr=SR):
    """How many dB the voice sits above the music, measured only while the voice is actually speaking (pauses ignored)."""
    n = max(1, int(0.1 * sr)); k = min(len(v), len(m)) // n
    if k < 1: return 99.0
    vr = np.sqrt(np.mean(v[:k * n].reshape(k, n) ** 2, 1)); mr = np.sqrt(np.mean(m[:k * n].reshape(k, n) ** 2, 1))
    act = vr > max(vr.max() * 0.1, 1e-4)
    if not act.any(): return 99.0
    return float(20 * np.log10((np.sqrt(np.mean(vr[act] ** 2)) + 1e-9) / (np.sqrt(np.mean(mr[act] ** 2)) + 1e-9)))
