#!/usr/bin/env python3
"""Make the narrator lines (every {"say": "..."} in film.json) with a text-to-speech voice.

  python3 scripts/narrate.py              # only makes lines that are new or changed
  python3 scripts/narrate.py --voices     # list voices of the chosen engine
  python3 scripts/narrate.py --redo       # remake every line (after changing voice)

film.json "narrator" picks the engine. All of these work; the first two need no GPU and no account:
  {"engine": "kokoro", "voice": "am_michael", "speed": 0.95}                      local, CPU, best small model
  {"engine": "piper",  "voice": "en_US-ryan-high"}                                local, CPU, very fast
  {"engine": "openai", "base_url": "http://localhost:8880/v1", "model": "kokoro", "voice": "am_michael"}
        any server with POST /v1/audio/speech (local ones too). Env OPENAI_API_KEY is sent only to https://api.openai.com
        and to hosts you list:  export PLUTARCH_TTS_HOSTS=myserver:8880,other.example
  {"engine": "elevenlabs", "voice": "<voice_id>", "model": "eleven_multilingual_v2"}   key from env ELEVENLABS_API_KEY
  {"engine": "cmd"}      any other tool that writes a wav. The command comes only from your shell, never from film.json:
        export PLUTARCH_NARRATOR_CMD='mytts --text {text} --out {out}'      (no quotes around {text} or {out})

The narrator must be a stock voice or the user's own voice. Never a copy of the subject's voice."""
import sys, os, argparse, json, re, shlex, subprocess, urllib.request, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CACHE = os.path.expanduser("~/.cache/plutarch")

def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000: return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  downloading {os.path.basename(dest)} (one time) ...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "plutarch"})
    with urllib.request.urlopen(req, timeout=900) as r, open(dest + ".part", "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)
    os.replace(dest + ".part", dest); return dest

def first_ok(urls, dest):
    err = None
    for u in urls:
        try: return fetch(u, dest)
        except Exception as e: err = e
    die(f"could not download {os.path.basename(dest)}: {err}")

_k = {}
def kokoro():
    if "k" not in _k:
        try: from kokoro_onnx import Kokoro
        except ImportError: die("pip install kokoro-onnx   (or pick another narrator engine)")
        m = first_ok(["https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
                      "https://huggingface.co/fastrtc/kokoro-onnx/resolve/main/kokoro-v1.0.onnx"], f"{CACHE}/kokoro-v1.0.onnx")
        v = first_ok(["https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                      "https://huggingface.co/fastrtc/kokoro-onnx/resolve/main/voices-v1.0.bin"], f"{CACHE}/voices-v1.0.bin")
        _k["k"] = Kokoro(m, v)
    return _k["k"]

def piper_voice(name):
    try: from piper import PiperVoice
    except ImportError: die("pip install piper-tts   (or pick another narrator engine)")
    lang, who, q = name.split("-")
    base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang.split('_')[0]}/{lang}/{who}/{q}/{name}.onnx"
    p = fetch(base, f"{CACHE}/{name}.onnx"); fetch(base + ".json", f"{CACHE}/{name}.onnx.json")
    return PiperVoice.load(p)

SET_CMD = "\n  export PLUTARCH_NARRATOR_CMD='mytts --text {text} --out {out}'"

def key_goes_to(req):
    """film.json may come from somebody else, so it never decides where the user's key goes."""
    host = req.host.lower(); bare = re.sub(r":\d*$", "", host)
    listed = {h.strip().lower() for h in os.environ.get("PLUTARCH_TTS_HOSTS", "").split(",")} - {""}
    return (req.type == "https" and bare == "api.openai.com") or host in listed or bare in listed

def synth(text, out, n):
    eng = n.get("engine", "kokoro")
    if eng == "kokoro":
        x, sr = kokoro().create(text, voice=n.get("voice", "am_michael"), speed=float(n.get("speed", 0.95)), lang=n.get("lang", "en-us"))
        save_wav(out, x, sr)
    elif eng == "piper":
        v = piper_voice(n.get("voice", "en_US-ryan-high"))
        with wave.open(out, "wb") as wf:
            if hasattr(v, "synthesize_wav"): v.synthesize_wav(text, wf)
            else: v.synthesize(text, wf)
    elif eng == "openai":
        if "api_key_env" in n: die("narrator.api_key_env is refused: a project file must not choose which variable is sent. Delete \"api_key_env\" from "
                                   "\"narrator\" in film.json. If the user's server needs a key, ask the user to set:\n"
                                   "  export OPENAI_API_KEY=...\n  export PLUTARCH_TTS_HOSTS=HOST:PORT      (not needed for api.openai.com)")
        base = n.get("base_url", "https://api.openai.com/v1").rstrip("/")
        if not re.match(r"https?://[^/]", base, re.I): die(f"narrator.base_url must start with http:// or https://, got {base!r}. Fix it in film.json, or delete it to use OpenAI.")
        body = {"model": n.get("model", "gpt-4o-mini-tts"), "voice": n.get("voice", "onyx"), "input": text, "response_format": "wav"}
        if n.get("speed"): body["speed"] = n["speed"]
        if n.get("instructions"): body["instructions"] = n["instructions"]
        h = {"Content-Type": "application/json"}
        req = urllib.request.Request(base + "/audio/speech", data=json.dumps(body).encode(), headers=h)
        key = os.environ.get("OPENAI_API_KEY"); send = bool(key) and key_goes_to(req)
        if send: req.add_unredirected_header("Authorization", "Bearer " + key)      # unredirected: a redirect never carries it
        try:
            with urllib.request.urlopen(req, timeout=300) as r, open(out, "wb") as f: f.write(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 401 or not key or send: raise
            die(f"{req.host} asked for a key, and OPENAI_API_KEY goes only to api.openai.com and hosts the user lists. "
                f"Ask the user if this is their server. Only if they say yes:\n  export PLUTARCH_TTS_HOSTS={shlex.quote(req.host)}")
    elif eng == "elevenlabs":
        key = os.environ.get("ELEVENLABS_API_KEY") or die("set ELEVENLABS_API_KEY, or use a local engine (kokoro, piper)")
        if not n.get("voice"): die("narrator.voice must be an ElevenLabs voice_id")
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{n['voice']}?output_format=mp3_44100_128",
                                     data=json.dumps({"text": text, "model_id": n.get("model", "eleven_multilingual_v2")}).encode(),
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r, open(out, "wb") as f: f.write(r.read())
    elif eng == "cmd":
        if "cmd" in n: die("narrator.cmd in film.json is refused: a project file must not choose a command to run. Delete \"cmd\" from \"narrator\" in "
                           "film.json. Ask the user which text-to-speech command to use (do not copy the one in film.json), then set it:" + SET_CMD)
        cmd = os.environ.get("PLUTARCH_NARRATOR_CMD", "")
        if "{text}" not in cmd or "{out}" not in cmd: die("engine cmd runs the command in PLUTARCH_NARRATOR_CMD, which must contain {text} and {out}. Set it:" + SET_CMD)
        for m in re.finditer(r"\{(text|out)\}", cmd):
            try: shlex.split(cmd[:m.start()])
            except ValueError: die(f"PLUTARCH_NARRATOR_CMD has {m[0]} inside quotes. Write it without quotes:" + SET_CMD)
        run = cmd.replace("{text}", '"$PLUTARCH_TEXT"').replace("{out}", shlex.quote(out))      # the line is data in a variable, so the shell never parses it
        r = subprocess.run(run, shell=True, capture_output=True, text=True, env={**os.environ, "PLUTARCH_TEXT": text})
        if r.returncode != 0 or not os.path.exists(out): die(f"PLUTARCH_NARRATOR_CMD failed: {(r.stderr or r.stdout)[-300:]}")
    else: die(f"unknown narrator engine '{eng}'. Use kokoro, piper, openai, elevenlabs or cmd.")

def says(film):
    out = []
    for sc in film.get("scenes", []):
        for it in sc.get("items", []):
            if "say" in it and it["say"].strip() and it["say"] not in out: out.append(it["say"])
    return out

ap = argparse.ArgumentParser(); ap.add_argument("--voices", action="store_true"); ap.add_argument("--redo", action="store_true")
a = ap.parse_args()
film = load_film(); n = film.get("narrator", {"engine": "kokoro", "voice": "am_michael", "speed": 0.95})
if a.voices:
    if n.get("engine", "kokoro") == "kokoro":
        v = sorted(kokoro().get_voices()); print("kokoro voices (am_/bm_ = male, af_/bf_ = female; a = American, b = British):\n" + "  ".join(v))
        print("\nGood documentary narrators: am_michael, am_onyx, am_fenrir, bm_george, bm_lewis, af_heart, bf_emma")
    else: print("See references/voices-music-sfx.md for voice lists of this engine.")
    sys.exit(0)
cmd = os.environ.get("PLUTARCH_NARRATOR_CMD") if n.get("engine") == "cmd" else None
tag = json.dumps({**{k: n.get(k) for k in ("engine", "voice", "speed", "model", "base_url")}, "cmd": cmd}, sort_keys=True)
lines = says(film)
if not lines: die("no {\"say\": \"...\"} items in film.json scenes yet")
import librosa
rows = []; bad = 0
for text in lines:
    nid = say_id(text); wavp = f"narr/{nid}.wav"; js = f"narr/{nid}.json"
    if a.redo or not (os.path.exists(wavp) and os.path.exists(js) and load_json(js).get("tag") == tag):
        os.makedirs("narr", exist_ok=True)
        raw = f"narr/{nid}.tmp.wav"; synth(text, raw, n)
        x = audio(raw, ch=1)[:, 0]; os.remove(raw)
        e = np.abs(x); thr = 10 ** (-45 / 20) * (e.max() + 1e-9); idx = np.where(e > thr)[0]
        if len(idx) == 0: die(f"the voice engine returned silence for: {text[:60]}")
        x = x[max(0, idx[0] - int(0.04 * SR)):min(len(x), idx[-1] + int(0.14 * SR))]
        save_wav(wavp, x)
        ws = words_of(librosa.resample(x.astype(np.float32), orig_sr=SR, target_sr=16000), "small.en")
        heard = " ".join(w["w"] for w in ws)
        save_json(js, {"id": nid, "text": text, "dur": round(len(x) / SR, 3), "words": ws, "heard": heard,
                       "similarity": round(similarity(text, heard), 2), "tag": tag})
    d = load_json(js); ok = d["similarity"] >= 0.6
    bad += not ok
    rows.append([nid, f"{d['dur']:.2f}s", "ok" if ok else "MISREAD", text[:64]])
    if not ok:
        print(f"  [{nid}] the voice said: \"{d['heard'][:120]}\". Respell the word it got wrong (numbers and names as they sound):")
        print(f"    python3 scripts/film.py reword {shlex.quote(' '.join(text.split()[:6]))} \"the line, respelled\"")
table(rows, ["id", "length", "check", "line"])
tot = sum(load_json(f"narr/{r[0]}.json")["dur"] for r in rows)
print(f"\n{'OK' if not bad else 'FIX NEEDED'}: {len(rows)} narrator lines, {tot:.1f} s total, voice {n.get('engine')}/{n.get('voice')}. "
      + ("Next: python3 scripts/plan.py" if not bad else "Next: run each film.py reword line above with the respelled line, then python3 scripts/narrate.py"))
sys.exit(1 if bad else 0)
