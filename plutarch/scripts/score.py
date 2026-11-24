#!/usr/bin/env python3
"""Music for the film. Best first:

  python3 scripts/score.py prompt             # prints the exact length + a timed prompt to paste into ANY music generator
  python3 scripts/score.py acestep            # local ACE-Step 1.5 server (uv run acestep-api): generates 3 tracks for you
  python3 scripts/score.py pick a.mp3 b.mp3   # ranks generated tracks by how well their loud/quiet shape fits the film
  python3 scripts/score.py synth              # no generator available: builds a simple score in code -> music/synth.wav

Then set film.json  "music": {"file": "music/<name>"}  (or {"synth": true}) and run mix.py."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

def mood(e0, e1, ty):
    if ty == "title": return "one huge cinematic hit that rings out, then near silence"
    if ty == "end": return "one final huge resolving major chord that rings out and fades"
    if e1 - e0 > 0.3: return "a driving build: pulsing staccato strings and low drums, rising all the way to a big hit at the end of this section"
    m = (e0 + e1) / 2
    if m < 0.25: return "very sparse and quiet: a low drone and a lone distant piano note, lots of space"
    if m < 0.45: return "minimal and contemplative: soft felt piano over warm sustained strings"
    return "warm and hopeful: strings swelling, steady pulse"

def cmd_prompt(a):
    prompt, length = build_prompt(load_plan())
    print(f"MUSIC LENGTH: {length:.1f} seconds, instrumental (no vocals, no lyrics).\n\nPROMPT:\n{prompt}")
    print("\nGenerate 2-4 versions at exactly that length, save them in music/, then: python3 scripts/score.py pick music/*.mp3\n"
          "Local ACE-Step server running?  python3 scripts/score.py acestep   does all of that for you.\n"
          "Other generators: references/voices-music-sfx.md")

def cmd_pick(a):
    plan = load_plan(); m0, m1 = music_window(plan); need_len = m1 - m0
    tt = np.arange(0, need_len, 0.5); target = np.array([energy_at(plan, m0 + x) for x in tt])
    rows = []
    for f in a.files:
        x = audio(f, ch=1)[:, 0]; n = int(0.5 * SR)
        env = np.array([np.sqrt(np.mean(x[i:i + n] ** 2)) for i in range(0, len(x) - n, n)])
        db = 20 * np.log10(env + 1e-6); L = min(len(db), len(target))
        fit = float(np.corrcoef(np.clip(db[:L], -60, 0), target[:L])[0, 1]) if L > 8 else -1
        short = len(x) / SR < need_len - 1.0
        rows.append((fit - (1 if short else 0), f, f"{len(x) / SR:.1f}s", f"{fit:+.2f}", "TOO SHORT" if short else "ok"))
    rows.sort(reverse=True)
    table([list(r[1:]) for r in rows], ["file", "length", "shape fit (-1..1)", "length check"])
    best = rows[0]
    if best[4] != "ok": print(f"\nNo track is long enough ({need_len:.1f} s needed). Generate again at that length, or use: python3 scripts/score.py synth")
    else: print(f"\nUse the top one. In film.json set:  \"music\": {{\"file\": \"{best[1]}\"}}   then run: python3 scripts/mix.py")

# ---------- fallback score made in code ----------
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"])}
def hz(s): return 440 * 2 ** ((12 * (int(s[-1]) + 1) + NOTE[s[:-1]] - 69) / 12)
CH = {"Dm": ["D2", "A2", "D3", "F3", "A3"], "Bb": ["Bb1", "F2", "Bb2", "D3", "F3"], "F": ["F2", "C3", "F3", "A3", "C4"],
      "C": ["C2", "G2", "C3", "E3", "G3"], "Gm": ["G1", "D2", "G2", "Bb2", "D3"], "A": ["A1", "E2", "A2", "C#3", "E3"]}
def cmd_synth(a):
    from scipy import signal
    plan = load_plan(); m0, m1 = music_window(plan); D = m1 - m0; N = int(D * SR)
    rng = np.random.default_rng(7); out = np.zeros((N, 2))
    def add(x, at, g=1.0, pan=0.0):
        s = int(at * SR); e = min(N, s + len(x))
        if e <= s or s < 0: return
        if x.ndim == 1: x = np.stack([x * np.cos((pan + 1) * np.pi / 4), x * np.sin((pan + 1) * np.pi / 4)], 1)
        out[s:e] += x[:e - s] * g
    def pad(f, dur, bright):
        n = int((dur + 2.0) * SR); t = np.arange(n) / SR; o = np.zeros((n, 2))
        for c, det in ((0, -0.0035), (1, 0.0035)):
            for d in (1 - det, 1 + det * 1.7):
                for k in range(1, bright + 1):
                    if f * k < 8000: o[:, c] += np.sin(2 * np.pi * f * k * d * t + rng.random() * 6.28) / k ** 1.4
        return o * (np.minimum(1, t / 1.5) * np.where(t > dur, np.exp(-(t - dur) / 0.7), 1))[:, None] * 0.05
    def piano(f):
        n = int(4.5 * SR); t = np.arange(n) / SR
        return sum(am * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (0.9 + 0.55 * k)) for k, am in ((1, 1), (2, .45), (3, .2), (4, .1))) * np.minimum(1, t / 0.004) * 0.11
    def pluck(f):
        n = int(0.3 * SR); t = np.arange(n) / SR
        return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 8) if f * k < 9000) * np.exp(-t / 0.08) * 0.045
    def kick(g):
        n = int(0.5 * SR); t = np.arange(n) / SR
        return np.sin(2 * np.pi * np.cumsum(42 + 68 * np.exp(-t / 0.035)) / SR) * np.exp(-t / 0.16) * 0.5 * g
    step = 4.6; k = 0; t = 0.0
    while t < D:
        e = energy_at(plan, m0 + t); sc = [s for s in plan["scenes"] if s["t0"] <= m0 + t < s["t1"]]
        ty = sc[0]["type"] if sc else "card"
        seq = ["Bb", "Gm", "Dm", "A"] if e < 0.25 else ["Dm", "Bb", "F", "C"]
        ch = "F" if ty == "end" else seq[k % 4]
        if e > 0.02:
            for nn in CH[ch]: add(pad(hz(nn), step, 4 if e < 0.25 else (9 if e > 0.6 else 7)), t, 0.35 + 0.65 * e)
            if 0.22 <= e < 0.62: add(piano(hz(CH[ch][(k * 2) % 5]) * 4), t + 0.6, 0.8, 0.2); add(piano(hz(CH[ch][(k * 2 + 3) % 5]) * 4), t + 2.9, 0.6, -0.1)
            if e < 0.22: add(piano(hz(CH[ch][2]) * 2), t + 1.0, 0.5, 0.15)
            if e >= 0.55:
                b = 60 / 112 / 2
                for q in range(int(step / b)):
                    add(pluck(hz(CH[ch][1 + q % 4]) * 2), t + q * b, 0.5 + 0.8 * e, -0.3 if q % 2 else 0.3)
                    if q % 2 == 0 and e > 0.7: add(kick(0.5 + 0.5 * e), t + q * b)
        t += step; k += 1
    n = int(2.6 * SR); tt = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-tt * 6.9 / 2.6)[:, None]
    ir = signal.sosfilt(signal.butter(1, 5000, "lp", fs=SR, output="sos"), ir, axis=0); ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([signal.fftconvolve(out[:, c], ir[:, c])[:N] for c in range(2)], 1)
    out = out * 0.72 + wet * 0.45
    out /= np.abs(out).max() + 1e-9
    save_wav("music/synth.wav", out * 0.7)
    print(f"OK music/synth.wav ({D:.1f} s). It is plain: a generated track (score.py prompt) will sound better. Next: python3 scripts/mix.py")

def build_prompt(plan):
    m0, m1 = music_window(plan); parts = []
    for s in plan["scenes"]:
        if not s["music"]: continue
        md = mood(s["energy"][0], s["energy"][1], s["type"])
        if s["type"] == "arena" and s.get("peak_at"):
            md = f"hope rising from near silence, then big cinematic drums and a wordless choir enter at {mmss(s['peak_at'] - m0)}, triumphant"
        if parts and parts[-1][2] == md: parts[-1][1] = s["t1"] - m0
        else: parts.append([s["t0"] - m0, s["t1"] - m0, md])
    return ("Instrumental cinematic documentary score in D minor, modern hybrid orchestral, intimate and premium, no vocals. Structure: "
            + " ".join(f"{mmss(p[0])} to {mmss(p[1])} {p[2]}." for p in parts)), m1 - m0

def cmd_acestep(a):
    """Generate with a local ACE-Step 1.5 server (start it with: uv run acestep-api). API: /release_task, /query_result, /v1/audio."""
    import json, time, urllib.request
    plan = load_plan(); prompt, length = build_prompt(plan); base = a.url.rstrip("/")
    def call(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read())
    try:
        d = call("/release_task", {"prompt": prompt, "lyrics": "[Instrumental]", "audio_duration": round(length, 1), "audio_format": "mp3", "batch_size": a.n})
    except Exception as e:
        die(f"no ACE-Step server at {base} ({e}). Start it (cd ACE-Step-1.5 && uv run acestep-api) or use: score.py prompt / score.py synth")
    tid = d["data"]["task_id"]; print(f"ACE-Step task {tid}: generating {a.n} x {length:.0f} s ...", flush=True)
    t0 = time.time()
    while True:
        r = call("/query_result", {"task_id_list": [tid]})["data"][0]
        if r["status"] == 1: break
        if r["status"] == 2: die("ACE-Step reported the generation failed. Check the server log.")
        if time.time() - t0 > a.timeout: die("ACE-Step took too long. Check the server.")
        time.sleep(5)
    res = r["result"] if isinstance(r["result"], list) else json.loads(r["result"])
    os.makedirs("music", exist_ok=True); files = []
    for k, it in enumerate(res):
        url = it["file"] if it["file"].startswith("http") else base + it["file"]
        p = f"music/acestep_{k + 1}.mp3"
        with urllib.request.urlopen(url, timeout=300) as rr, open(p, "wb") as f: f.write(rr.read())
        files.append(p)
    print("OK " + " ".join(files) + f"\nNext: python3 scripts/score.py pick {' '.join(files)}")

ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("acestep"); p.add_argument("--url", default="http://localhost:8001"); p.add_argument("-n", type=int, default=3); p.add_argument("--timeout", type=int, default=1800); p.set_defaults(fn=cmd_acestep)
sub.add_parser("prompt").set_defaults(fn=cmd_prompt)
p = sub.add_parser("pick"); p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_pick)
sub.add_parser("synth").set_defaults(fn=cmd_synth)
a = ap.parse_args(); a.fn(a)
