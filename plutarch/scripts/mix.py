#!/usr/bin/env python3
"""Build the finished soundtrack from out/plan.json: out/mix.wav (+ stems and sync data for the picture).

  python3 scripts/mix.py

It levels every voice, ducks the music under speech, adds impacts/risers/heartbeat, fixes any line the music
is covering, and masters to -14 LUFS. Read the table it prints: every line must say ok."""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy import signal
import pyloudnorm as pyln

plan = load_plan(); DUR = plan["dur"]; FPS = plan["fps"]; N = int(DUR * SR); T = np.arange(N) / SR
rng = np.random.default_rng(5); meter = pyln.Meter(SR)
def sos(kind, f, order=2): return signal.butter(order, f, kind, fs=SR, output="sos")
def lufs(x): return meter.integrated_loudness(x if len(x) > SR else np.tile(x, (int(SR * 1.3 / max(1, len(x))) + 2, 1)))
def norm(x, target):
    l = lufs(x)
    return x if not np.isfinite(l) else x * 10 ** ((target - l) / 20)
def fade(x, fi, fo):
    n = len(x); i = min(n // 2, int(fi * SR)); o = min(n // 2, int(fo * SR))
    if i: x[:i] *= (np.linspace(0, 1, i) ** 1.5)[:, None]
    if o: x[n - o:] *= (np.linspace(1, 0, o) ** 1.5)[:, None]
    return x
def add(bus, x, at, g=1.0):
    s = int(round(at * SR)); e = min(N, s + len(x))
    if s < 0: x = x[-s:]; s = 0
    if e > s: bus[s:e] += x[:e - s] * g
def presence(x, f0, db, q=0.8):
    b, a = signal.iirpeak(f0, q, fs=SR); return x + signal.lfilter(b, a, x, axis=0) * (10 ** (db / 20) - 1)
def comp(x, thr=-24, ratio=2.5, rel=0.15):
    a_r = np.exp(-1 / (rel * SR)); env = signal.lfilter([1 - a_r], [1, -a_r], np.max(np.abs(x), 1))
    over = np.maximum(0, 20 * np.log10(env + 1e-9) - thr); return x * (10 ** (-over * (1 - 1 / ratio) / 20))[:, None]
def make_ir(secs, damp, pre):
    n = int(secs * SR); tt = np.arange(n) / SR
    ir = signal.sosfilt(sos("lp", damp, 1), rng.standard_normal((n, 2)) * np.exp(-tt * 6.9 / secs)[:, None], axis=0)
    ir = np.vstack([np.zeros((int(pre * SR), 2)), ir]); return ir / np.sqrt((ir ** 2).sum(0))
HALL = make_ir(2.6, 5500, 0.012); ROOM = make_ir(0.6, 7000, 0.004)
def reverb(x, ir, wet): return x * (1 - wet) + np.stack([signal.fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1) * wet
def stereo(x): return np.repeat(x, 2, 1) if x.shape[1] == 1 else x
def boom(g=1.0):
    n = int(4.0 * SR); tt = np.arange(n) / SR
    x = np.sin(2 * np.pi * np.cumsum(30 + 40 * np.exp(-tt / 0.25)) / SR) * np.exp(-tt / 1.1)
    nz = signal.sosfilt(sos("lp", 900), rng.standard_normal(n)) * np.exp(-tt / 0.5) * 0.25
    return reverb(stereo(((x + nz) * 0.7 * g)[:, None]), HALL, 0.2)
def riser(dur):
    n = int(dur * SR); nz = rng.standard_normal((n, 2)); out = np.zeros_like(nz); zi = None
    for i in range(0, n, 1024):
        s_ = sos("lp", min(300 * 40 ** (i / n), 16000))
        if zi is None: zi = np.zeros((s_.shape[0], 2, 2))
        out[i:i + 1024], zi = signal.sosfilt(s_, nz[i:i + 1024], axis=0, zi=zi)
    return out * ((np.arange(n) / n) ** 2.2)[:, None] * 0.2
def thump(f0, f1, dec, g):
    n = int(0.6 * SR); tt = np.arange(n) / SR
    return stereo((np.sin(2 * np.pi * np.cumsum(f1 + (f0 - f1) * np.exp(-tt / 0.035)) / SR) * np.exp(-tt / dec) * g)[:, None])
def sfx_file(name, fallback):
    p = f"sfx/{name}.wav"
    return norm(audio(p), -15) if os.path.exists(p) else fallback

voice = np.zeros((N, 2)); crowd = np.zeros((N, 2)); music = np.zeros((N, 2)); sfx = np.zeros((N, 2))
sync = {"hits": {}, "heart": [], "impacts": plan["impacts"], "beats": []}
scenes = plan["scenes"]
for a in plan["audio"]:
    sc = scenes[a["scene"]]
    if a["role"] in ("narr", "voice"):
        x = audio(a["file"], ch=1); x = signal.sosfilt(sos("hp", 70 if a["role"] == "narr" else 85), x, axis=0)
        x = presence(x, 180, 1.5, 0.7) if a["role"] == "narr" else x
        x = comp(stereo(presence(x, 3600, 1.8)))
        if a["role"] == "narr": x = reverb(x, ROOM, 0.08)
        add(voice, fade(norm(x, -16.5 if a["role"] == "narr" else -17.0), 0.012, 0.04), a["at"])
    elif a["role"] == "live":
        x = audio(a["file"])
        if a.get("vocals") and os.path.exists(a["vocals"]):       # lift the voice out of the noise
            v = signal.sosfilt(sos("hp", 110), audio(a["vocals"]), axis=0); n = min(len(x), len(v))
            x = x[:n] * 0.6 + v[:n] * (np.sqrt(np.mean(x[:n] ** 2)) / (np.sqrt(np.mean(v[:n] ** 2)) + 1e-9)) * 1.25
        x = reverb(presence(signal.sosfilt(sos("hp", 95), x, axis=0), 2800, 2.5), HALL, 0.10)
        add(voice, fade(norm(x, -15.5), 0.05, 0.25), a["at"])
    elif a["role"] == "crowd":
        x = audio(a["file"], a["in"], a["in"] + a["dur"])
        x = reverb(presence(signal.sosfilt(sos("hp", 100), x, axis=0), 3000, 2.5), HALL, 0.25)
        x = fade(norm(comp(x, -22), a["gain"]), 0.5, 0.05 if sc["suck"] else 0.8)
        if sc["suck"]: x = x[:max(1, len(x) - int(0.15 * SR))]
        if sc["type"] == "arena" and sc.get("peak_at"):               # swell into the peak, then get out of the way of the speech
            tt = a["at"] + np.arange(len(x)) / SR; pk = sc["peak_at"]
            x *= np.interp(tt, [a["at"], pk - 3.5, pk - 0.3, pk + 1.0, pk + 2.0], [0.6, 0.6, 2.1, 2.1, 0.75])[:, None]
        add(crowd, x, a["at"])
        if a.get("drums"):                                         # drums on the beat of the crowd (chants, claps)
            import librosa
            y = librosa.resample(x.mean(1).astype(np.float32), orig_sr=SR, target_sr=22050)
            _, bt = librosa.beat.beat_track(y=y, sr=22050); bt = librosa.frames_to_time(bt, sr=22050)
            hits = []
            for k, b in enumerate(bt):
                if b < 1.0 or b > a["dur"] - 0.4: continue
                p = b / a["dur"]
                if k % 2 == 0: g = 0.55 + 0.45 * p; add(sfx, reverb(thump(120, 50, 0.20, 0.9), HALL, 0.18), a["at"] + b - 0.005, g); hits.append([round(a["at"] + b, 3), round(g, 2)])
                elif p > 0.5: g = 0.3 + 0.4 * p; add(sfx, thump(170, 80, 0.10, 0.5), a["at"] + b - 0.005, g); hits.append([round(a["at"] + b, 3), round(g * 0.6, 2)])
            sync["hits"][str(sc["i"])] = hits
            sub = np.arange(len(x)) / SR
            add(sfx, stereo(((np.sin(2 * np.pi * 36.7 * sub) + 0.5 * np.sin(2 * np.pi * 55 * sub)) * np.minimum(1, sub / 3.0) ** 2 * 0.09)[:, None]), a["at"])
# impacts, risers, heartbeat
for k, t0 in enumerate(plan["impacts"]):
    add(sfx, fade(sfx_file("impact", boom()).copy(), 0, 1.5), t0, 1.0)
    prev = [s for s in scenes if abs(s["t1"] - t0) < 0.01 and s["suck"]]
    if prev and prev[0]["t1"] - prev[0]["t0"] > 3.2:
        r = sfx_file("riser", riser(2.6)); add(sfx, r, t0 - 0.15 - len(r) / SR)
for sc in scenes:
    if sc.get("bg") == "pulse":
        tb = sc["t0"] + 0.5
        while tb < sc["t1"] - 1.2:
            g = 0.9 * (1 - 0.6 * (tb - sc["t0"]) / (sc["t1"] - sc["t0"]))
            add(sfx, thump(75, 40, 0.14, 0.55), tb, g); add(sfx, thump(70, 38, 0.12, 0.38), tb + 0.24, g)
            sync["heart"].append([round(tb, 3), round(tb + 0.24, 3), round(g, 2)]); tb += 1.6
# music
m0, m1 = music_window(plan); mcfg = plan["music"]; mfile = mcfg.get("file") if isinstance(mcfg, dict) else None
if not mfile:
    if not os.path.exists("music/synth.wav"): die("no music yet. Run: python3 scripts/score.py synth   (or generate a track and set film.json \"music\": {\"file\": ...})")
    mfile = "music/synth.wav"
M = audio(mfile)
if len(M) / SR < (m1 - m0) - 1.0 and not mcfg.get("loop"):
    die(f"music is {len(M) / SR:.1f} s but the film needs {m1 - m0:.1f} s. Run score.py prompt and generate at that length (or score.py synth).")
M = norm(np.tile(M, (int(np.ceil((m1 - m0) * SR / len(M))), 1))[:int((m1 - m0) * SR)], -16.0)
add(music, fade(M, 0.02, 1.2), m0)
eng = np.array([energy_at(plan, x) for x in np.arange(0, DUR, 0.05)])
g = np.interp(T, np.arange(0, DUR, 0.05), np.where(eng > 0, 0.24 + 0.76 * eng, 0.0))
g = signal.sosfiltfilt(sos("lp", 1.5, 1), g)
for sc in scenes:                                                   # silence right before an impact makes it hit
    if sc["suck"]: g[(T >= sc["t1"] - 0.15) & (T < sc["t1"])] = 0.0
    if sc.get("peak_at"):
        pk = sc["peak_at"]; m_ = (T >= sc["t0"]) & (T < pk); g[m_] = np.minimum(g[m_], 0.42)
music *= np.clip(g, 0, 1.2)[:, None]
try:
    import librosa
    _, bt = librosa.beat.beat_track(y=librosa.resample(M.mean(1).astype(np.float32), orig_sr=SR, target_sr=22050), sr=22050)
    sync["beats"] = [round(float(b) + m0, 3) for b in librosa.frames_to_time(bt, sr=22050)]
except Exception: pass
# duck music (and crowd a little) under speech
venv = signal.sosfilt(sos("lp", 6, 1), np.max(np.abs(voice), 1)); venv /= np.percentile(venv[venv > 1e-4], 95) + 1e-9 if (venv > 1e-4).any() else 1
duck = signal.sosfiltfilt(sos("lp", 3, 1), 1 - 0.76 * np.clip(venv * 1.8, 0, 1))
music *= duck[:, None]; crowd *= (0.55 + 0.45 * duck)[:, None]
# any line still covered? pull the music down under just that line
def db(x): return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
def gap_of(a):
    i, j = int(a["at"] * SR), int((a["at"] + a["dur"]) * SR)
    return speech_gap(voice[i:j, 0], (music + crowd * (0 if a["role"] == "live" else 1))[i:j, 0])
spoken = [a for a in plan["audio"] if a["role"] in ("narr", "voice", "live")]
for a in spoken:
    gp = gap_of(a)
    if gp < 10.0:
        cut = 10 ** (-(10.5 - gp) / 20); i, j = int((a["at"] - 0.25) * SR), int((a["at"] + a["dur"] + 0.25) * SR)
        i = max(0, i); j = min(N, j); r = int(0.25 * SR); env = np.ones(j - i) * cut
        env[:r] = np.linspace(1, cut, r)[:len(env[:r])]; env[-r:] = np.linspace(cut, 1, r)[-len(env[-r:]):]
        music[i:j] *= env[:, None]
        if a["role"] != "live": crowd[i:j] *= env[:, None]
rows = []; bad = 0
for a in spoken:
    gp = gap_of(a); ok = gp >= 8.0; bad += not ok
    rows.append([f"{a['at']:.1f}", a["role"], a["label"], "no music here" if gp > 60 else f"{gp:.1f} dB", "ok" if ok else "COVERED"])
mix = voice + crowd + music + sfx
L = lufs(mix); k = 10 ** ((-16.0 - L) / 20)
os.makedirs("out", exist_ok=True)
save_wav("out/mix_pre.wav", mix * k)
for nm, x in (("voice", voice), ("music", music), ("crowd", crowd), ("sfx", sfx)): save_wav(f"out/stem_{nm}.wav", x * k)
r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "out/mix_pre.wav", "-af",
                    "alimiter=limit=0.86:attack=2:release=50:level=false,loudnorm=I=-13.5:TP=-1.6:LRA=11", "-ar", str(SR), "out/mix.wav"], capture_output=True, text=True)
if r.returncode != 0: die("ffmpeg mastering failed: " + r.stderr[-300:])
os.remove("out/mix_pre.wav")
hop = SR // FPS; nf = int(DUR * FPS)
def fenv(x): return np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) for i in range(nf)])
def nrm(e): return e / (np.percentile(e[e > 0], 98) + 1e-9) if (e > 0).any() else e
np.savez("out/env.npz", voice=nrm(fenv(voice[:, 0])), crowd=nrm(fenv((crowd + sfx * 0.5)[:, 0])), music=nrm(fenv(music[:, 0])))
save_json("out/sync.json", sync)
table(rows, ["at (s)", "kind", "line", "voice over music", "result"])
e = subprocess.run(["ffmpeg", "-hide_banner", "-i", "out/mix.wav", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
I = [l for l in e.splitlines() if l.strip().startswith("I:")][-1].split()[1]; P = [l for l in e.splitlines() if "Peak:" in l][-1].split()[1]
print(f"\n{'OK' if not bad else 'FIX NEEDED'}: out/mix.wav  {DUR:.1f} s  loudness {I} LUFS (target -14)  peak {P} dB (must be below -1)."
      + ("" if not bad else " A COVERED line means the recording itself is too noisy: add \"live\": true to that clip, run clip.py make, plan.py, mix.py again.")
      + "\nNext: python3 scripts/render.py --sheet")
sys.exit(1 if bad else 0)
