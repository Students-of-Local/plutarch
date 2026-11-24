#!/usr/bin/env python3
"""Check the finished film. Run this before you say you are done. Exit code 0 = every check passed.

  python3 scripts/check.py                 # checks out/final.mp4 against out/plan.json

It cannot be fooled by "looks fine": it measures the file. Fix every FAIL, rerun the step it names, check again."""
import sys, os, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ap = argparse.ArgumentParser(); ap.add_argument("--final", default="out/final.mp4"); ap.add_argument("--plan", default="out/plan.json")
ap.add_argument("--stems", default="out"); ap.add_argument("--clips", default="clips")
a = ap.parse_args()
need(a.final, "Run: python3 scripts/render.py"); need(a.plan, "Run: python3 scripts/plan.py")
plan = load_json(a.plan); res = []
def chk(name, ok, detail, fix=""): res.append((name, bool(ok), detail, fix))
def probe(sel, ent):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", sel, "-show_entries", ent, "-of", "csv=p=0", a.final], capture_output=True, text=True).stdout.strip()

# 1 container
v = probe("v:0", "stream=codec_name,width,height,r_frame_rate,pix_fmt").split(","); au = probe("a:0", "stream=codec_name,sample_rate").split(",")
chk("video format", all(k in v for k in ("h264", "1080", "1920", "30/1", "yuv420p")), " ".join(v) + " (want h264 1080 1920 yuv420p 30/1)", "render.py makes this; do not re-encode by hand")
chk("audio format", au[:1] == ["aac"], " ".join(au), "render.py makes this")
d = duration(a.final); lim = plan.get("max_seconds", 140)
chk("length", d <= lim + 0.5 and abs(d - plan["dur"]) < 0.6, f"{d:.1f} s (limit {lim} s, plan {plan['dur']:.1f} s)", "shorten film.json, then plan.py, mix.py, render.py")
# 2 loudness
e = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.final, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
I = float([l for l in e.splitlines() if l.strip().startswith("I:")][-1].split()[1]); P = float([l for l in e.splitlines() if "Peak:" in l][-1].split()[1])
chk("loudness", -15.6 <= I <= -13.0, f"{I} LUFS (target -14)", "rerun mix.py then render.py"); chk("peak", P <= -0.9, f"{P} dB (must be below -1)", "rerun mix.py")
x = audio(a.final, ch=1)[:, 0]; n = int(0.1 * SR); r = np.array([np.sqrt(np.mean(x[i:i + n] ** 2)) for i in range(0, len(x) - n, n)])
quiet = r < 10 ** (-50 / 20); run = best = 0; where = 0
for i, q in enumerate(quiet[:-15]):
    run = run + 1 if q else 0
    if run > best: best, where = run, i
chk("no dead air", best * 0.1 <= 1.5, f"longest silence {best * 0.1:.1f} s" + (f" ending at {where * 0.1:.1f} s" if best else ""), "a scene has no sound: add music (score.py) or remove the gap")
# 3 picture
def luma(t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", a.final, "-frames:v", "1", "-vf", "scale=270:480,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8) if raw else np.zeros(1, np.uint8)
f0 = luma(0.0); chk("first frame not black", f0.max() > 60, f"brightest pixel {int(f0.max())}/255 (it is the thumbnail)", "scene 1 must show something at 0.0 s: make it an arena with \"reveal\": \"hits\", or a card whose first item is a clip (no narrator line first)")
dark = [s["id"] for s in plan["scenes"] if luma((s["t0"] + s["t1"]) / 2).max() < 50]
chk("every scene shows something", not dark, "empty scenes: " + ", ".join(dark) if dark else f"{len(plan['scenes'])} scenes", "open out/sheet.jpg (render.py --sheet) and fix those scenes")
# 4 every line sits exactly where the plan says (waveform match), captions follow the words, and the words are right
from scipy import signal
F8 = audio(a.final, ch=1, sr=8000)[:, 0]
def locate(path, at, dur):
    c = audio(path, ch=1, sr=8000)[:, 0][:int(min(dur, 6.0) * 8000)]
    lo = max(0.0, at - 1.5); seg = F8[int(lo * 8000):int((at + 1.5) * 8000) + len(c)]
    if len(seg) <= len(c) or len(c) < 800: return None, 0.0
    xc = np.abs(signal.correlate(seg, c, mode="valid")); k = int(np.argmax(xc))
    return lo + k / 8000, float(xc[k] / (np.median(xc) + 1e-12))
spoken = [q for q in plan["audio"] if q["role"] in ("voice", "narr", "live")]
worst = 0.0; lost = []; n_loc = 0
for q in spoken:
    if not q.get("file") or not os.path.exists(q["file"]): continue
    t, strength = locate(q["file"], q["at"], q["dur"]); n_loc += 1
    if t is None or strength < 4: lost.append(f"{q['label'][:24]} @ {q['at']:.1f}s")
    else: worst = max(worst, abs(t - q["at"]))
chk("every line is where the plan says", n_loc > 0 and not lost and worst <= 0.10,
    ("not found in the final audio: " + "; ".join(lost)) if lost else f"{n_loc} lines located, worst offset {worst:.3f} s",
    "out/plan.json, out/mix.wav and out/final.mp4 are out of step: rerun plan.py, mix.py, render.py in that order")
stale = []
for q in spoken:
    p = f"{a.clips}/{q.get('id')}.json"
    if q.get("id") and os.path.exists(p) and load_json(p).get("words"):
        w0 = q["at"] + load_json(p)["words"][0]["s"]
        if not any(abs(c["wt"][0] - w0) < 0.03 for c in plan["captions"]): stale.append(q["id"])
chk("captions follow the words", not stale, "captions not matching their clip: " + ", ".join(stale) if stale else "caption times come from the verified word times",
    "a clip was recut after planning: rerun plan.py, mix.py, render.py")
import librosa
pick = [q for q in spoken if q["role"] != "live"]; pick = pick[:: max(1, len(pick) // 5)][:6]; miss = []
for q in pick:
    s0 = max(0, q["at"] - 0.3); seg = audio(a.final, s0, q["at"] + q["dur"] + 0.3, ch=1, sr=16000)[:, 0].astype(np.float32)
    heard = " ".join(w["w"] for w in words_of(seg, "base.en"))
    capw = [c for c in plan["captions"] if q["at"] - 0.05 <= c["wt"][0] <= q["at"] + q["dur"]] if q["role"] == "voice" else []
    want = " ".join(c["text"] for c in capw) if capw else (q.get("text") or q["label"])
    if similarity(want[:len(heard) + 20], heard) < 0.5: miss.append(f"{q['at']:.1f}s wanted \"{want[:30]}\" heard \"{heard[:30]}\"")
chk("the words you hear are the words shown", not miss, "; ".join(miss) if miss else f"{len(pick)} lines re-heard in the final file", "fix the clip \"lines\"/narrator text, then clip.py make / narrate.py, plan.py, mix.py, render.py")
# 5 every voice is audible over the music
sv, sm = f"{a.stems}/stem_voice.wav", f"{a.stems}/stem_music.wav"
if os.path.exists(sv) and os.path.exists(sm):
    V = audio(sv, ch=1)[:, 0]; M = audio(sm, ch=1)[:, 0]; worst = (99, "")
    for q in [q for q in plan["audio"] if q["role"] in ("voice", "narr", "live")]:
        i, j = int(q["at"] * SR), int((q["at"] + q["dur"]) * SR)
        g = speech_gap(V[i:j], M[i:j])
        if g < worst[0]: worst = (g, q["label"])
    chk("voice over music", worst[0] >= 8.0, f"quietest line is {worst[0]:.1f} dB above the music (\"{worst[1][:30]}\")", "rerun mix.py; if it still fails add \"isolate\": true to that clip (crowd or phone recording: \"live\": true), then clip.py make, plan.py, mix.py, render.py --mux")
else: chk("voice over music", False, "stems missing", "run mix.py")
# 6 honesty: sources, dates, verified clips
film = load_json("film.json") if os.path.exists("film.json") else None
if film:
    used = {q["id"] for q in plan["audio"] if q.get("id")}
    nocred = [k for k, s in film.get("sources", {}).items() if not s.get("credit")]
    noctx = [k for k in used if not (film["clips"][k].get("year") and film["clips"][k].get("about"))]
    unver = [k for k in used if os.path.exists(f"{a.clips}/{k}.json") and load_json(f"{a.clips}/{k}.json").get("verified") == "unverified"]
    chk("every source credited", not nocred and any(s["type"] == "end" for s in plan["scenes"]), "missing credit: " + ", ".join(nocred) if nocred else "credits on the end card", "add \"credit\" to each source; last scene must be type end")
    chk("every quote has year + context", not noctx, "missing: " + ", ".join(noctx) if noctx else f"{len(used)} clips", "add \"year\" and \"about\" to those clips (what was he talking about?)")
    chk("every quote verified", not unver, "unverified: " + ", ".join(unver) if unver else f"{len(used)} clips", "rerun clip.py make; noisy clips need \"live\": true")
# 7 it is the subject's film: enough real voice, and the subject speaks last
sp = sorted([q for q in plan["audio"] if q["role"] in ("narr", "voice", "live")], key=lambda q: q["at"])
rs = sum(q["dur"] for q in sp if q["role"] != "narr"); ns = sum(q["dur"] for q in sp if q["role"] == "narr")
nq = len({q.get("id") for q in sp if q["role"] != "narr"}); wantq = max(3, round(plan["dur"] / 25))
chk("real voice is half the talking", rs >= 0.5 * (rs + ns), f"real voice {rs:.0f} s, narrator {ns:.0f} s", "add quotes or cut narrator lines in film.json, then narrate.py, plan.py, mix.py, render.py")
chk("enough real quotes", nq >= wantq, f"{nq} quotes (need {wantq} for this length)", "add quotes: clip.py find, add to film.json clips and scenes, clip.py make, plan.py, mix.py, render.py")
chk("the subject has the last word", bool(sp) and sp[-1]["role"] != "narr", ("last: \"" + sp[-1]["label"][:36] + "\"") if sp else "nothing is said", "end the last speaking scene with a clip, not a narrator line")
ok = all(r[1] for r in res)
table([["PASS" if r[1] else "FAIL", r[0], r[2]] for r in res], ["", "check", "measured"])
for r in res:
    if not r[1]: print(f"FIX {r[0]}: {r[3]}")
print(f"\n{'ALL CHECKS PASSED' if ok else 'NOT DONE: ' + str(sum(not r[1] for r in res)) + ' check(s) failed'}  ({a.final})")
sys.exit(0 if ok else 1)
