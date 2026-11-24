#!/usr/bin/env python3
"""Draw the film from out/plan.json + out/mix.wav. Vertical 1080x1920, 30 fps.

  python3 scripts/render.py --sheet            # FIRST: a few frames of every scene -> out/sheet.jpg  (look at it!)
  python3 scripts/render.py --stills 12.5 40   # single frames at those seconds -> out/still_*.png
  python3 scripts/render.py                    # full render -> out/final.mp4   (minutes; run once)
  python3 scripts/render.py --scene rise       # re-render one scene by id, then rebuild out/final.mp4
  python3 scripts/render.py --mux              # only the sound changed (mix.py rerun): rebuild out/final.mp4 in seconds

Your own scene: put custom.py in the project with  def draw(c, T, scene, K): ...  and use "type": "card", "custom": true."""
import sys, os, math, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
try: import skia
except ImportError: die("pip install skia-python")

plan = load_plan(); WD, HT = plan["size"]; FPS = plan["fps"]; DUR = plan["dur"]; SC = plan["scenes"]
ACC = tuple(plan["accent"]); BG = (11, 11, 10); FG = (237, 231, 220); DIM = (138, 133, 124); LAMP = (255, 246, 228)
SYNC = load_json("out/sync.json") if os.path.exists("out/sync.json") else {"hits": {}, "heart": [], "impacts": [], "beats": []}
ENV = np.load("out/env.npz") if os.path.exists("out/env.npz") else None
CUR = {"T": 0.0}

# ---------- fonts ----------
FD = os.path.join(KIT, "..", "fonts"); WGHT = int.from_bytes(b"wght", "big")
def face(fn, w):
    p = os.path.join(FD, fn)
    if not os.path.exists(p): return skia.Typeface.MakeDefault() if hasattr(skia.Typeface, "MakeDefault") else skia.Typeface()
    tf = skia.Typeface.MakeFromFile(p)
    try:
        C = skia.FontArguments.VariationPosition.Coordinate; fa = skia.FontArguments()
        fa.setVariationDesignPosition(skia.FontArguments.VariationPosition(skia.FontArguments.VariationPosition.Coordinates([C(WGHT, w)])))
        return tf.makeClone(fa)
    except Exception: return tf
TF = {"bold": face("Antonio-VF.ttf", 700), "it": face("CormorantGaramond-Italic-VF.ttf", 500),
      "ser": face("CormorantGaramond-VF.ttf", 500), "mono": face("JetBrainsMono-VF.ttf", 500)}
_fc = {}
def font(k, size):
    if (k, size) not in _fc:
        f = skia.Font(TF[k], size); f.setSubpixel(True); f.setEdging(skia.Font.Edging.kAntiAlias); _fc[(k, size)] = f
    return _fc[(k, size)]

# ---------- drawing helpers ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ramp(t, a, b): return clamp((t - a) / (b - a)) if b > a else float(t >= a)
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def eio(x): x = clamp(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def eoe(x): x = clamp(x); return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)
def spring(x, damp=6.0, freq=11.0): return 0.0 if x <= 0 else 1 - math.exp(-damp * x) * math.cos(freq * x)
def sstep(x, a, b): x = clamp((x - a) / (b - a)); return x * x * (3 - 2 * x)
def col(rgb, a=1.0): return skia.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(255 * clamp(a)))
def paint(rgb, a=1.0, stroke=0, blur=0):
    p = skia.Paint(AntiAlias=True, Color=col(rgb, a))
    if stroke: p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke)
    if blur: p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p
def width(s, f, track=0): return f.measureText(s) + track * max(0, len(s) - 1)
def text(c, s, x, y, f, rgb, a=1.0, align="c", track=0, blur=0):
    if a <= 0.003 or not s: return
    w = width(s, f, track); x -= w / 2 if align == "c" else (w if align == "r" else 0)
    p = paint(rgb, a, blur=blur)
    if track == 0: c.drawString(s, x, y, f, p)
    else:
        for ch in s: c.drawString(ch, x, y, f, p); x += f.measureText(ch) + track
def wrap(s, f, maxw):
    lines = []; cur = ""
    for w in s.split(" "):
        tst = (cur + " " + w).strip()
        if width(tst, f) > maxw and cur: lines.append(cur); cur = w
        else: cur = tst
    if cur: lines.append(cur)
    if len(lines) == 2:                                  # balance two lines
        ws = s.split(" "); best = None
        for k in range(1, len(ws)):
            m = max(width(" ".join(ws[:k]), f), width(" ".join(ws[k:]), f))
            if m <= maxw and (best is None or m < best[0]): best = (m, [" ".join(ws[:k]), " ".join(ws[k:])])
        if best: lines = best[1]
    return lines
def fit(kind, s, size, maxw):
    while size > 30 and width(s, font(kind, size)) > maxw: size -= 4
    return font(kind, size)
def text_in(c, s, x, y, f, rgb, tt, t0, dur=0.6, dy=26, amul=1.0, track=0, maxw=None):
    p = eoe(ramp(tt, t0, t0 + dur))
    if p <= 0.001: return 0
    lines = wrap(s, f, maxw) if maxw else [s]
    for k, ln in enumerate(lines): text(c, ln, x, y + dy * (1 - p) + k * f.getSize() * 1.18, f, rgb, min(1, p * 1.15) * amul, "c", track)
    return len(lines)
def sprite(n, rgb, fn):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32); r = np.hypot(xx - (n - 1) / 2, yy - (n - 1) / 2) / ((n - 1) / 2)
    a = np.clip(fn(r), 0, 1); a[r > 1] = 0; arr = np.zeros((n, n, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3] = rgb[0], rgb[1], rgb[2], (a * 255).astype(np.uint8)
    return skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
SG_W = sprite(96, LAMP, lambda r: np.exp(-(r * 2.4) ** 2)); SG_A = sprite(96, ACC, lambda r: np.exp(-(r * 2.4) ** 2))
DISC = [sprite(64, LAMP, (lambda r, f=f: (1 - r) / f)) for f in (0.10, 0.3, 0.6, 1.0)]
SAMP = skia.SamplingOptions(skia.FilterMode.kLinear)
def spr(c, img, x, y, R, a, plus=False):
    if a <= 0.004 or R <= 0: return
    p = skia.Paint(); p.setAlphaf(min(1.0, a))
    if plus: p.setBlendMode(skia.BlendMode.kPlus)
    c.drawImageRect(img, skia.Rect.MakeLTRB(x - R, y - R, x + R, y + R), SAMP, p)
LOWS = skia.Surface(WD // 4, HT // 4)
def lowlayer(c, fn):
    """Big soft light drawn small then scaled up: cheap bloom."""
    lc = LOWS.getCanvas(); lc.clear(skia.Color(0, 0, 0, 0)); lc.save(); lc.scale(0.25, 0.25); fn(lc); lc.restore()
    p = skia.Paint(); p.setBlendMode(skia.BlendMode.kPlus)
    c.drawImageRect(LOWS.makeImageSnapshot(), skia.Rect.MakeWH(WD, HT), SAMP, p)
_dr = np.random.default_rng(41)
DUST = [(_dr.uniform(120, 960), _dr.uniform(0, 1700), _dr.uniform(0, 6.28), _dr.uniform(0.5, 1.6)) for _ in range(90)]
def dust(c, T, a=1.0, x0=120, x1=960):
    if a <= 0.01: return
    for x, y, ph, sz in DUST:
        if x0 <= x <= x1:
            spr(c, SG_W, x + 20 * math.sin(T * 0.5 + ph), (y - T * 16 * sz) % 1700 + 80, 5 * sz + 2, a * (0.05 + 0.17 * (0.5 + 0.5 * math.sin(T * 1.7 + ph * 3))))
def env(name, T):
    if ENV is None: return 0.3
    a = ENV[name]; return float(a[min(len(a) - 1, max(0, int(T * FPS)))])
def hitpulse(T, hits, dec=7.0):
    v = 0.0
    for h, g in hits:
        if h <= T: v = max(v, g * math.exp(-(T - h) * dec))
    return v
def beat_pulse(T, since, dec=10.0):
    b = [x for x in SYNC["beats"] if since <= x <= T]
    return math.exp(-(T - b[-1]) * dec) if b else 0.0
def impact_flash(c, lt, strength=0.42):
    fl = math.exp(-lt * 13)
    if lt >= 0 and fl > 0.01: c.drawRect(skia.Rect(0, 0, WD, HT), paint(FG, strength * fl))

# ---------- overlays: captions, source tags, grain ----------
def draw_caps(c, T, scene):
    for cp in plan["captions"]:
        cold = cp["scene"] == 0 and cp["t0"] < 1.2      # film opens on a quote: its words are on screen (dim) from frame 0, so the first frame is never black
        if not ((0.0 if cold else cp["t0"] - 0.1) <= T <= cp["off"] + 0.25): continue
        big = cp["style"] == "big"; size = 112 if big else 62
        y = 980 if big else (1600 if scene["type"] == "arena" else (1590 if scene["type"] == "stack" else 1480))
        f = font("it", size); fade = 1 - eo(ramp(T, cp["off"], cp["off"] + 0.22))
        lines = wrap(cp["text"], f, 960 if big else 900); lh = size * 1.16; y0 = y - (len(lines) - 1) * lh / 2; wi = 0
        for li, ln in enumerate(lines):
            x = WD / 2 - width(ln, f) / 2
            for w in ln.split(" "):
                wt = cp["wt"][min(wi, len(cp["wt"]) - 1)]
                a = eo(ramp(T, wt - 0.02, wt + 0.14)); dy = 9 * (1 - eo(ramp(T, wt - 0.02, wt + 0.22)))
                if cold: a = 0.45 + 0.55 * a; dy = 0
                a *= fade
                if a > 0:
                    text(c, w, x, y0 + li * lh + dy + 2, f, (0, 0, 0), a * 0.7, "l", blur=6); text(c, w, x, y0 + li * lh + dy, f, FG, a, "l")
                x += f.measureText(w + " "); wi += 1
        if cp.get("who"):
            text(c, "— " + cp["who"].upper(), WD / 2, y0 + len(lines) * lh + 10, font("mono", 26), DIM, eo(ramp(T, cp["t1"], cp["t1"] + 0.3)) * fade, "c", 3)
def draw_tags(c, T):
    for tg in plan["tags"]:
        a = eo(ramp(T, tg["t0"], tg["t0"] + 0.4)) * (1 - eo(ramp(T, tg["t1"] - 0.4, tg["t1"]))) * 0.85
        if a > 0: text(c, tg["text"], WD / 2, 1800, fit("mono", tg["text"], 24, 980), DIM, a, "c", 2.5)
_gr = np.random.default_rng(3); GRAIN = []
for _ in range(6):
    g = _gr.integers(0, 255, (HT // 2, WD // 2), dtype=np.uint8); rgba = np.dstack([g, g, g, np.full_like(g, 255)])
    GRAIN.append(skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType))
VIG = skia.Paint(Shader=skia.GradientShader.MakeRadial(skia.Point(WD / 2, 900), 1250, [skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, 170)], [0, 0.45, 1.0]))
def post(c, T):
    c.drawRect(skia.Rect(0, 0, WD, HT), VIG)
    p = skia.Paint(); p.setAlphaf(0.06); p.setBlendMode(skia.BlendMode.kOverlay)
    c.drawImageRect(GRAIN[int(T * FPS) % 6], skia.Rect(0, 0, WD, HT), skia.SamplingOptions(), p)

def headings(c, T, s, y=380, big=96):
    """Scene heading + lines, each easing in at its own time."""
    hd = s.get("heading")
    if hd: text_in(c, hd.upper(), WD / 2, y, fit("bold", hd.upper(), big, 960), FG, T, s["t0"] + 0.05, 0.6, 28, s.get("_amul", 1.0))
    yy = y + 80
    for ln in s.get("lines", []):
        n = text_in(c, ln["text"], WD / 2, yy, font("ser", 52), FG if s["type"] != "chart" else DIM, T, ln["at"], 0.55, 20, s.get("_amul", 1.0), maxw=1000)
        yy += 70 * max(1, n)

# ---------- scenes ----------
def sc_title(c, T, s):
    lt = T - s["t0"]; amp = 10 * math.exp(-lt * 7); k = 1.24 - 0.24 * spring(lt, 7.5, 13.0) + 0.010 * lt
    dust(c, T, 0.5 * ramp(lt, 0.2, 1.4)); t_ = s.get("text", plan["title"]); f = fit("bold", t_, 236, 960)
    dot = t_.endswith("."); body = t_[:-1] if dot else t_
    c.save(); c.translate(WD / 2 + math.sin(lt * 95) * amp, 930 + math.cos(lt * 83) * amp); c.scale(k, k)
    w1 = width(body, f); w2 = width(".", f) if dot else 0; x0 = -(w1 + w2) / 2
    c.drawString(body, x0, 0, f, paint(FG, 1))
    if dot and lt > 0.22:
        dp = clamp(spring(lt - 0.22, 9.0, 14.0), 0, 1.3); cx = x0 + w1 + w2 / 2
        c.save(); c.translate(cx, -18); c.scale(dp, dp); c.translate(-cx, 18); c.drawString(".", x0 + w1, 0, f, paint(ACC, 1)); c.restore()
    c.restore()
    w = 760 * eoe(ramp(lt, 0.5, 1.5)); c.drawLine(WD / 2 - w / 2, 1000, WD / 2 + w / 2, 1000, paint(ACC, 1, stroke=3))
    for k_, sub in enumerate(s.get("sub", [])):
        p = eoe(ramp(lt, 0.9 + 0.4 * k_, 1.7 + 0.4 * k_))
        text(c, sub.upper(), WD / 2, 1080 + 55 * k_ + 16 * (1 - p), font("mono", 34 - 6 * min(k_, 1)), FG if k_ == 0 else DIM, p, "c", 10 + 14 * (1 - p))
    impact_flash(c, lt)
    fo = ramp(T, s["t1"] - 0.25, s["t1"])
    if fo > 0: c.drawRect(skia.Rect(0, 0, WD, HT), paint(BG, fo))

def ecg(c, T, y, alpha):
    pth = skia.Path(); first = True
    for x in range(40, 1041, 4):
        tx = T - (1040 - x) / 420.0; v = 0
        for lub, dub, g in SYNC["heart"]:
            if abs(tx - lub) < 0.5:
                d = tx - lub; d2 = tx - dub
                v += g * (-130 * math.exp(-(d / 0.016) ** 2) + 55 * math.exp(-((d - 0.04) / 0.02) ** 2) - 60 * math.exp(-(d2 / 0.018) ** 2) + 20 * math.exp(-((d2 - 0.05) / 0.03) ** 2))
        (pth.moveTo if first else pth.lineTo)(x, y + v); first = False
    c.drawPath(pth, paint(FG, alpha * 0.35, stroke=6, blur=6)); c.drawPath(pth, paint(FG, alpha, stroke=2.2))

def sc_card(c, T, s):
    lt = T - s["t0"]; bg = s.get("bg", "dark")
    if bg == "glow":
        fl = 0.93 + 0.07 * math.sin(T * 13.1) * math.sin(T * 7.3)
        lowlayer(c, lambda lc: lc.drawCircle(WD / 2, 520, 330, paint((60, 56, 48), 0.55 * eo(ramp(lt, 0, 1.5)) * fl, blur=120)))
        dust(c, T, 0.35 * ramp(lt, 0.3, 2.0), 260, 820)
    if s.get("ghost"): text(c, str(s["ghost"]), WD / 2, 1060, fit("bold", str(s["ghost"]), 520, 1040), FG, 0.045 * eo(ramp(lt, 0, 1.2)), "c")
    if s.get("custom"):
        import custom; custom.draw(c, T, s, sys.modules[__name__])
    out = 1 - ramp(T, s["t1"] - 0.3, s["t1"]); s["_amul"] = out
    headings(c, T, s, 560 if bg == "glow" else 380, 150 if bg == "glow" else 96)
    if bg == "pulse": ecg(c, T, 1180, 0.75 * eo(ramp(lt, 0.2, 1.0)) * out)

def sc_stack(c, T, s):
    lt = T - s["t0"]; st = s["stack"]; out = 1 - ramp(T, s["t1"] - 0.45, s["t1"])
    if s.get("heading"): text_in(c, s["heading"].upper(), WD / 2, 250, font("mono", 30), DIM, T, s["t0"] + 0.2, 0.7, 14, out, track=12)
    sh = max([6 * math.exp(-(T - w["at"]) * 9) for w in st if T >= w["at"]] or [0])
    dy = min(158, 1000 / max(1, len(st))); f = font("bold", int(150 * dy / 158))
    c.save(); c.translate(math.sin(T * 93) * sh, math.cos(T * 79) * sh)
    for i, w in enumerate(st):
        if T < w["at"] - 0.03: continue
        nx = st[i + 1]["at"] if i + 1 < len(st) else None; latest = nx is None or T < nx
        hold = 1.0 if latest else 0.26 + 0.74 * (1 - eo(ramp(T, nx, nx + 0.35)))
        a = eoe(ramp(T, w["at"] - 0.03, w["at"] + 0.14)) * hold * out
        k = min(1.0, 900 / width(w["text"], f)) * (1.38 - 0.38 * spring(T - w["at"] + 0.03, 8.0, 13.0)); y = 440 + i * dy
        c.save(); c.translate(WD / 2, y - 52); c.scale(k, k); c.translate(0, 52)
        text(c, w["text"], 0, 0, f, ACC if (latest and w["text"] == str(s.get("accent_word", "")).upper()) else FG, a, "c"); c.restore()
    c.restore()

CX0, CX1, CY0, CY1 = 120, 980, 1180, 420
def human(v, prefix=""):
    for lim, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= lim: return f"{prefix}{v / lim:g}{suf}"
    return f"{prefix}{v:g}"
def sc_chart(c, T, s):
    from scipy.interpolate import PchipInterpolator
    if "_p" not in s:
        P = np.array(sorted(s["points"]), float); s["_p"] = PchipInterpolator(P[:, 0], P[:, 1]); s["_x"] = (P[0, 0], P[-1, 0]); s["_P"] = P
    f_, (xa, xb), P = s["_p"], s["_x"], s["_P"]; unit = float(s.get("unit", 1)); pre = s.get("prefix", "")
    prog = ramp(T, s["t0"] + 0.6, s["t1"] - 1.3) ** 1.6; upto = xa + (xb - xa) * prog
    val = lambda x: float(f_(min(max(x, xa), xb)))
    seen = P[P[:, 0] <= upto, 1]; ym = max(val(upto), seen.max() if len(seen) else 0) * 1.22 + 1e-9
    ym = max(ym, P[:3, 1].max() * 1.3)
    X = lambda x: CX0 + (x - xa) / (xb - xa + (xb - xa) * 0.02) * (CX1 - CX0); Y = lambda v: CY0 - (v / ym) * (CY0 - CY1)
    kick = beat_pulse(T, s["t0"]) * (0.3 + 0.7 * prog); sx, sy = math.sin(T * 91) * 5 * kick, math.cos(T * 77) * 5 * kick
    al = eoe(ramp(T, s["t0"] + 0.2, s["t0"] + 1.3)) * (1 - ramp(T, s["t1"] - 0.12, s["t1"]) if s["suck"] else 1)
    c.save(); c.translate(sx, sy)
    c.drawLine(CX0, CY0, CX1, CY0, paint(DIM, 0.5 * al, stroke=1.5))
    span = xb - xa; stp = next(k for k in (1, 2, 4, 5, 10, 20, 25, 50, 100) if span / k <= 6)
    xt = math.ceil(xa / stp) * stp
    while xt <= xb:
        c.drawLine(X(xt), CY0, X(xt), CY0 + 12, paint(DIM, 0.5 * al, stroke=1.5)); text(c, f"{xt:g}", X(xt), CY0 + 46, font("mono", 24), DIM, 0.7 * al); xt += stp
    mag = 10 ** math.floor(math.log10(ym))
    for v in [m * k for m in (mag / 10, mag) for k in (1, 2, 5)]:
        ta = sstep(v / ym, 0.10, 0.20) * (1 - sstep(v / ym, 0.90, 1.04))
        if ta > 0.01:
            c.drawLine(CX0, Y(v), CX1, Y(v), paint(DIM, 0.14 * al * ta, stroke=1)); text(c, human(v * unit, pre), CX0 - 12, Y(v) + 8, font("mono", 22), DIM, 0.65 * al * ta, "r")
    if s.get("label"): text(c, s["label"].upper(), CX0, CY1 - 40, font("mono", 22), DIM, 0.7 * al, "l", 2)
    if prog > 0:
        n = max(2, int(200 * prog)); pts = [(X(xa + (upto - xa) * i / n), Y(val(xa + (upto - xa) * i / n))) for i in range(n + 1)]
        pth = skia.Path()
        for i, (x, y) in enumerate(pts): (pth.moveTo if i == 0 else pth.lineTo)(x, y)
        area = skia.Path(pth); area.lineTo(pts[-1][0], CY0); area.lineTo(pts[0][0], CY0); area.close()
        c.drawPath(area, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear([skia.Point(0, CY1), skia.Point(0, CY0)], [col(ACC, 0.20 * al), col(ACC, 0.0)])))
        c.drawPath(pth, paint(ACC, al, stroke=3.5)); x, y = pts[-1]
        spr(c, SG_A, x, y, 34 + 26 * kick, (0.55 + 0.4 * kick) * al, plus=True); c.drawCircle(x, y, 7.5, paint(ACC, al))
    c.restore()
    stamps = sorted(s.get("stamps", [])); shown = False
    for k, (sx_, big, small) in enumerate(stamps):
        ts = s["t0"] + 0.6 + (s["t1"] - 1.3 - s["t0"] - 0.6) * ((sx_ - xa) / (xb - xa)) ** (1 / 1.6)
        nxt = s["t0"] + 0.6 + (s["t1"] - 1.3 - s["t0"] - 0.6) * ((stamps[k + 1][0] - xa) / (xb - xa)) ** (1 / 1.6) if k + 1 < len(stamps) else s["t1"]
        if ts <= T < nxt:
            shown = True; a = eo(ramp(T, ts, ts + 0.1)) * (1 - eo(ramp(T, nxt - 0.2, nxt))) if k + 1 < len(stamps) else eo(ramp(T, ts, ts + 0.1)) * al
            k_ = 1.32 - 0.32 * spring(T - ts, 8.5, 14.0)
            c.save(); c.translate(WD / 2, 250); c.scale(k_, k_); text(c, big.upper(), 0, 0, fit("bold", big.upper(), 120, 900), ACC, a); c.restore()
            p = eoe(ramp(T, ts + 0.12, ts + 0.6)); text(c, small.upper(), WD / 2, 312 + 12 * (1 - p), font("mono", 28), FG, a * 0.85 * p, "c", 3)
            d = T - ts
            if d < 0.8: c.drawCircle(X(sx_) + sx, Y(val(sx_)) + sy, 13 + 70 * eoe(d / 0.8), paint(ACC, 0.7 * (1 - d / 0.8), stroke=2))
    if not shown:
        first_ts = s["t1"] if not stamps else s["t0"] + 0.6 + (s["t1"] - 1.3 - s["t0"] - 0.6) * ((stamps[0][0] - xa) / (xb - xa)) ** (1 / 1.6)
        s["_amul"] = (1 - eo(ramp(T, first_ts - 0.25, first_ts))) * al; headings(c, T, s, 250, 110)

# arena: a crowd of lights on curved balconies around one accent figure
_ar = np.random.default_rng(23); TIER = []
for k in range(6):
    rx = 215 + k * 72 + k * k * 2.5; n = 40 + k * 15
    TIER.append(dict(k=k, y=340 + k * 152 + k * k * 4, rx=rx, ry=rx * 0.11 + 8 + k * 7, th=np.sort(_ar.uniform(0, 2 * np.pi, n)), ph=_ar.uniform(0, 6.28, n),
                     lit=_ar.uniform(0, 1, n), r=2.0 + k * 0.55, slab=10 + k * 5, rail=12 + k * 3))
GROUND = []
for _ in range(230):
    while True:
        ang = _ar.uniform(0, 2 * np.pi); rad = np.sqrt(_ar.uniform(0.11, 1.0)) * 560; x = 540 + math.cos(ang) * rad; y = 1500 + math.sin(ang) * rad * 0.23
        if 0 < x < 1080: break
    GROUND.append((x, y, _ar.uniform(0, 6.28), _ar.uniform(0, 1)))
GROUND.sort(key=lambda p: p[1])
def arc(cx, cy, rx, ry, a0, a1, dy=0, n=80):
    p = skia.Path()
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n; (p.moveTo if i == 0 else p.lineTo)(cx + rx * math.cos(a), cy + ry * math.sin(a) + dy)
    return p
def arena(c, T, lit=1.0, stand=0.0, energy=0.5, glow=0.0, master=1.0, rings=(), flash=0.0, ignite=None, wave=None, bounce=0.0, shaft=1.0):
    g = 0.5 + glow; acl = tuple(min(255, int(v * 0.6 + 100)) for v in ACC)
    def glows(lc):
        for i, (off, w0, w1, sp) in enumerate(((-150, 60, 260, 0.21), (-20, 40, 200, 0.17), (110, 70, 300, 0.13), (240, 30, 180, 0.19))):
            sw = 26 * math.sin(T * sp + i * 1.9); p = skia.Path()
            p.moveTo(540 + off * 0.3 - w0, -60); p.lineTo(540 + off * 0.3 + w0, -60); p.lineTo(540 + off * 1.6 + sw + w1, 1750); p.lineTo(540 + off * 1.6 + sw - w1, 1750); p.close()
            lc.drawPath(p, paint(LAMP, (0.034 + 0.018 * math.sin(T * 0.7 + i) + flash * 0.04) * master * shaft, blur=38))
        cone = skia.Path(); cone.moveTo(510, -40); cone.lineTo(570, -40); cone.lineTo(700, 1505); cone.lineTo(380, 1505); cone.close()
        lc.drawPath(cone, paint(acl, (0.04 + 0.035 * glow) * master, blur=30))
        lc.drawOval(skia.Rect(350, 1460, 730, 1540), paint(ACC, (0.12 + 0.14 * glow) * master, blur=22)); lc.drawCircle(540, 1497, 26 + 30 * glow, paint(ACC, 0.34 * min(1, g) * master, blur=18))
    lowlayer(c, glows)
    for fl in TIER:
        k = fl["k"]; y, rx, ry = fl["y"], fl["rx"], fl["ry"]; ig = ignite[k] if ignite else None; since = (T - ig) if ig is not None else 99.0
        st_ = master * (0.30 + 0.70 * clamp(since / 0.5)) if ig is not None else master
        c.drawPath(arc(540, y, rx, ry, math.pi, 2 * math.pi), paint(DIM, 0.10 * st_, stroke=1.0))
        if since > 0.3:
            for th, ph, l in zip(fl["th"], fl["ph"], fl["lit"]):
                if math.sin(th) < 0 and l < lit:
                    c.drawCircle(540 + rx * math.cos(th), y + ry * math.sin(th) - fl["rail"] * 0.6 - stand * 6, fl["r"] * 0.75,
                                 paint(LAMP, (0.10 + (0.30 + 0.25 * (0.5 + 0.5 * math.sin(T * 8 + ph * 3))) * energy) * master * clamp((since - 0.3) / 0.5)))
        band = arc(540, y, rx, ry, 0, math.pi); band.addPath(arc(540, y, rx, ry, math.pi, 0, dy=fl["slab"])); band.close()
        c.drawPath(band, paint((20, 20, 19), 0.92 * st_)); c.drawPath(arc(540, y, rx, ry, 0, math.pi, dy=fl["slab"]), paint(DIM, 0.16 * st_, stroke=1.0))
        for th, ph, l in zip(fl["th"], fl["ph"], fl["lit"]):
            sn = math.sin(th); x = 540 + rx * math.cos(th)
            if sn < 0 or x < -30 or x > 1110: continue
            if ig is not None: ts = since - abs(th - math.pi / 2) / (math.pi / 2) * 0.45; on = ts >= 0; boost = math.exp(-ts * 4.5) if on else 0.0
            else: on = l < lit; boost = 0.0
            r = fl["r"] * (0.85 + 0.35 * sn)
            if not on: c.drawCircle(x, y + ry * sn - fl["rail"] * 0.55, r * 0.8, paint(LAMP, 0.05 * st_)); continue
            yy = y + ry * sn - fl["rail"] * 0.55 - stand * (8 + k * 2) * (0.6 + 0.4 * math.sin(ph)) - bounce * (4 + k * 1.6) * (0.55 + 0.45 * math.sin(ph * 5))
            fk = 0.5 + 0.5 * math.sin(T * 9 + ph * 3); a = 0.22 + (0.5 + 0.3 * fk) * energy + 0.7 * boost
            spr(c, SG_W, x, yy, r * (5.0 + 4.0 * energy + 7 * boost), 0.34 * a * master); c.drawCircle(x, yy, r * (1 + 0.35 * energy + 0.5 * boost), paint(LAMP, min(1, a) * master))
            if fk > 0.985 - 0.02 * energy:
                L = 10 + 4 * k; c.drawLine(x - L, yy, x + L, yy, paint(LAMP, 0.55 * master, stroke=1.2)); c.drawLine(x, yy - L, x, yy + L, paint(LAMP, 0.45 * master, stroke=1.2))
        c.drawPath(arc(540, y, rx, ry, 0.05, math.pi - 0.05, dy=-fl["rail"]), paint(FG, (0.10 + 0.05 * energy) * st_, stroke=1.2)); c.drawPath(arc(540, y, rx, ry, 0, math.pi), paint(FG, 0.22 * st_, stroke=1.6))
        if ig is not None and 0 <= since < 1.1:
            w = eoe(since / 0.55); c.drawPath(arc(540, y, rx, ry, math.pi / 2 - w * math.pi / 2, math.pi / 2 + w * math.pi / 2, dy=-fl["rail"], n=60), paint(LAMP, 0.85 * (1 - since / 1.1) * master, stroke=2.4))
    for h, gg in rings:
        d = T - h
        if 0 <= d < 1.4:
            pr = eoe(d / 1.4); rr = 30 + 560 * pr
            c.drawOval(skia.Rect(540 - rr, 1500 - rr * 0.23, 540 + rr, 1500 + rr * 0.23), paint(ACC, 0.5 * gg * (1 - d / 1.4) * master, stroke=2.2 + 2 * (1 - pr)))
    for x, y, ph, l in GROUND:
        if y > 1500 and abs(x - 540) < 40: continue
        rn = math.hypot((x - 540) / 560.0, (y - 1500) / (560 * 0.23))
        if l >= lit or (wave is not None and rn > wave): c.drawCircle(x, y, 2.6, paint(LAMP, 0.05 * master)); continue
        depth = (y - 1370) / 260.0; fk = 0.5 + 0.5 * math.sin(T * 7 + ph * 2)
        boost = max(0.0, 1 - (wave - rn) * 5) if (wave is not None and wave < 1.05) else 0.0
        di = 0 if depth < 0.45 else (1 if depth < 0.68 else (2 if depth < 0.88 else 3))
        spr(c, DISC[di], x, y - stand * 7 - bounce * (5 + 6 * depth) * (0.55 + 0.45 * math.sin(ph * 5)), (3.2 + 5.5 * depth) * (1.15 + 0.5 * di), min(1, 0.22 + 0.55 * energy * fk + 0.6 * boost) * master)
    c.drawCircle(540, 1497, 8.5, paint(ACC, min(1, g) * master)); c.drawCircle(540, 1497, 3.2, paint(tuple(min(255, v + 110) for v in ACC), min(1, g) * master))

def name_rows(c, T, word, mains, master):
    f = font("bold", 230); row = " ".join([word.upper()] * 3)
    for i in range(9):
        bump = max([g * math.exp(-(T - h - (8 - i) * 0.035) * 5.5) for h, g in mains if 0 <= T - h - (8 - i) * 0.035 < 0.9] or [0])
        x = WD / 2 + T * (10 if i % 2 else -10) + (i % 2) * 140 - 70 - width(row, f, 18) / 2; p = paint(FG, (0.040 + 0.085 * bump) * master, stroke=1.6)
        for ch in row: c.drawString(ch, x, 230 + i * 205, f, p); x += f.measureText(ch) + 18

def sc_arena(c, T, s):
    lt = T - s["t0"]; e = env("crowd", T)
    if s.get("reveal", "rise") == "hits":                       # cold open: start tight on the figure, crane back on each drum hit
        hits = [tuple(h) for h in SYNC["hits"].get(str(s["i"]), [])]; mains = [h for h in hits if h[1] > 0.5]
        mt = [h[0] for h in mains] or [s["t0"] + (s["t1"] - s["t0"]) * q for q in (0.16, 0.3, 0.44, 0.58, 0.72, 0.86)]
        while len(mt) < 6: mt.append(mt[-1] + 0.6)
        def stepped(levels):
            v = levels[0]
            for i, h in enumerate(mt[:5]): v += (levels[i + 1] - levels[i]) * eoe(ramp(T, h, h + 0.75))
            return v
        hp = hitpulse(T, hits); hpm = hitpulse(T, mains, 4.0); late = ramp(T, mt[4] + 0.4, s["t1"]) ** 2
        z = stepped([2.5, 2.0, 1.62, 1.32, 1.12, 1.0]) + 0.085 * late + 0.014 * hp; cy = stepped([1392, 1300, 1205, 1105, 1020, 960]) + 30 * late
        ign = {5: mt[0], 4: mt[1], 3: mt[2], 2: mt[3], 1: mt[4], 0: mt[4] + 0.22}; fade = 0.6 + 0.4 * eo(ramp(lt, 0.0, 0.3))
        if s.get("chant"):
            zb = 1 + (z - 1) * 0.3; c.save(); c.translate(540, 960); c.scale(zb, zb); c.translate(-540, -960 - (cy - 960) * 0.25)
            name_rows(c, T, s["chant"], mains, ramp(T, mt[0], mt[0] + 0.7) * fade); c.restore()
        c.save(); c.translate(540, 960); c.scale(z, z); c.translate(-540, -cy)
        arena(c, T, 1.0, 0.3, 0.30 + 0.38 * e + 0.34 * hp, 0.25 + 0.2 * e + 0.65 * hp, fade, mains, hp, ign, 1.06 * eio(ramp(lt, 0.12, 1.25)), hpm, ramp(lt, 0.9, 3.2))
        dust(c, T, 0.9 * ramp(lt, 1.0, 3.0)); c.restore()
    else:                                                        # the room fills with light, then erupts at the peak
        pk = s.get("peak_at", s["t0"] + (s["t1"] - s["t0"]) * 0.6); bp = beat_pulse(T, pk, 9.0)
        lit = eio(ramp(T, s["t0"] + 1.0, pk - 3.0)) * 0.55 + 0.45 * eio(ramp(T, pk - 3.0, pk)); stand = eio(ramp(T, pk - 2.5, pk + 0.2))
        fl = math.exp(-(T - pk) * 5) if T >= pk else 0
        energy = 0.15 + 0.85 * clamp(e + 0.35 * env("music", T) + (0.35 * bp if T > pk else 0))
        glow = 0.25 + 0.8 * eo(ramp(T, pk, pk + 0.4)) * (1 - 0.4 * ramp(T, pk + 0.8, pk + 2.8)) + 0.25 * bp
        k = 1.0 + 0.05 * eio(ramp(T, s["t0"], s["t1"])) + 0.035 * fl
        rb = [b for b in SYNC["beats"] if pk < b <= T and b - pk < 12]
        c.save(); c.translate(540, 1000); c.scale(k, k); c.translate(-540, -1000)
        arena(c, T, lit, stand, energy, glow, eo(ramp(lt, 0, 1.2)), [(b, 0.35) for b in rb[1::4]][-3:] + [(pk, 1.0)], fl, None, None, 0.6 * bp if T > pk else 0.0, 0.35 + 0.65 * eio(ramp(T, pk - 6, pk)))
        dust(c, T, 0.7 * ramp(T, pk - 6, pk - 1)); c.restore()
        if s.get("heading") or s.get("lines"):
            ca = eo(ramp(T, s["lines"][0]["at"] - 0.5 if s.get("lines") else s["t0"], (s["lines"][0]["at"] if s.get("lines") else s["t0"]) + 0.1)) * (1 - eo(ramp(T, pk + 0.3, pk + 0.8)))
            c.drawRect(skia.Rect(0, 130, WD, 430), skia.Paint(Shader=skia.GradientShader.MakeLinear([skia.Point(0, 130), skia.Point(0, 430)], [col(BG, 0), col(BG, 0.8 * ca), col(BG, 0.8 * ca), col(BG, 0)], [0.0, 0.23, 0.77, 1.0])))
            s["_amul"] = 1 - eo(ramp(T, pk + 0.3, pk + 0.8)); s2 = dict(s); s2["t0"] = (s["lines"][0]["at"] - 0.3) if s.get("lines") else s["t0"]; headings(c, T, s2, 260, 96)
        if fl > 0.01: c.drawRect(skia.Rect(0, 0, WD, HT), paint(FG, 0.22 * fl))
    if any(cp["scene"] == s["i"] and cp["t0"] - 0.3 <= T <= cp["off"] + 0.3 for cp in plan["captions"]):
        c.drawRect(skia.Rect(0, 1430, WD, 1790), skia.Paint(Shader=skia.GradientShader.MakeLinear([skia.Point(0, 1430), skia.Point(0, 1790)], [col(BG, 0), col(BG, 0.66), col(BG, 0.66), col(BG, 0)], [0.0, 0.3, 0.75, 1.0])))

def sc_end(c, T, s):
    lt = T - s["t0"]; amp = 9 * math.exp(-lt * 7); k = 1.22 - 0.22 * spring(lt, 7.5, 13.0) + 0.006 * lt
    dust(c, T, 0.45 * ramp(lt, 0.3, 1.6)); t_ = s.get("text", plan["title"]); acc_t = s.get("accent_text")
    c.save(); c.translate(WD / 2 + math.sin(lt * 95) * amp, 880 + math.cos(lt * 83) * amp); c.scale(k, k)
    text(c, t_, 0, 0, fit("bold", t_, 210, 940), FG, 1.0 - (0.45 * eo(ramp(lt, 0.75, 1.15)) if acc_t else 0)); c.restore()
    if acc_t:
        p = eoe(ramp(lt, 0.95, 1.75)); f = fit("bold", acc_t, 150, 960)
        if p > 0.001:
            text(c, acc_t, WD / 2, 1060 + 26 * (1 - p), f, ACC, 0.28 * p * (0.6 + 0.4 * (0.5 + 0.5 * math.sin(T * 2.2))), "c", 30 * (1 - p), blur=16)
            text(c, acc_t, WD / 2, 1060 + 26 * (1 - p), f, ACC, min(1, p * 1.2), "c", 30 * (1 - p))
    cr = []; cur_ = "AUDIO: "
    for x in plan["credits"]:                         # keep each credit whole when wrapping
        add_ = x.upper() if cur_.endswith(": ") else " · " + x.upper()
        if width(cur_ + add_, font("mono", 22), 1.5) > 940 and not cur_.endswith(": "): cr.append(cur_); cur_ = x.upper()
        else: cur_ += add_
    cr.append(cur_)
    for i, ln in enumerate(cr): text_in(c, ln, WD / 2, 1700 + 40 * i, font("mono", 22), DIM, lt, 2.4 + 0.15 * i, 0.7, 12, track=1.5)
    impact_flash(c, lt, 0.5)
    fo = ramp(T, s["t1"] - 1.0, s["t1"] - 0.05)
    if fo > 0: c.drawRect(skia.Rect(0, 0, WD, HT), paint(BG, fo))

FN = {"title": sc_title, "card": sc_card, "stack": sc_stack, "chart": sc_chart, "arena": sc_arena, "end": sc_end}
SURF = skia.Surface(WD, HT)
def scene_at(T):
    for s in SC:
        if s["t0"] <= T < s["t1"]: return s
    return SC[-1]
def frame(T, s=None):
    s = s or scene_at(T); CUR["T"] = T; c = SURF.getCanvas(); c.clear(col(BG))
    if s["suck"] and T >= s["t1"] - 0.15: return SURF.makeImageSnapshot().toarray()          # black beat before the impact
    if s["type"] in ("card", "stack", "chart"):                                              # nothing sits still: slow push + drift
        k = 1.0 + 0.028 * (T - s["t0"]) / max(0.1, s["t1"] - s["t0"])
        c.save(); c.translate(540 + 3 * math.sin(T * 0.37), 960 + 2.5 * math.sin(T * 0.29 + 1)); c.scale(k, k); c.translate(-540, -960); FN[s["type"]](c, T, s); c.restore()
    else: FN[s["type"]](c, T, s)
    if s["impact"] and s["type"] not in ("title", "end"): impact_flash(c, T - s["t0"], 0.3)
    if s["type"] not in ("title", "end"): draw_caps(c, T, s); draw_tags(c, T)
    post(c, T); return SURF.makeImageSnapshot().toarray()

def encode_scene(s):
    out = f"out/scenes/{s['i']:02d}.mp4"; tmp = out + ".tmp.mp4"; f0, f1 = round(s["t0"] * FPS), round(s["t1"] * FPS)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{WD}x{HT}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), tmp], stdin=subprocess.PIPE)
    for fi in range(f0, f1): p.stdin.write(frame(fi / FPS, s).tobytes())
    p.stdin.close()
    if p.wait() != 0: die(f"ffmpeg failed on scene {s['id']}")
    os.replace(tmp, out); print(f"  scene {s['i'] + 1}/{len(SC)} {s['id']}: {f1 - f0} frames", flush=True)

def to_img(a):
    from PIL import Image
    return Image.fromarray(a[..., [2, 1, 0]])

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sheet", action="store_true"); ap.add_argument("--stills", nargs="*", type=float); ap.add_argument("--scene"); ap.add_argument("--mux", action="store_true")
    a = ap.parse_args(); os.makedirs("out/scenes", exist_ok=True)
    if a.stills:
        for T in a.stills: to_img(frame(T)).save(f"out/still_{T:07.2f}.png"); print(f"out/still_{T:07.2f}.png")
        sys.exit(0)
    if a.sheet:
        from PIL import Image, ImageDraw
        shots = []
        for s in SC:
            d = s["t1"] - s["t0"]
            for q in ((0.5,) if d < 4 else (0.3, 0.75) if d < 9 else (0.2, 0.5, 0.85)): shots.append((s, s["t0"] + d * q))
        w, h = 270, 480; cols = min(8, len(shots)); rows = (len(shots) + cols - 1) // cols
        sh = Image.new("RGB", (w * cols, (h + 20) * rows), (40, 40, 40)); dr = ImageDraw.Draw(sh)
        rows = []; bad = 0
        for i, (s, T) in enumerate(shots):
            fr = frame(T, s); g = fr[..., :3].max(2)                    # numbers, for agents that cannot look at pictures
            ink = float((g > 110).mean()) * 100; edge = s["type"] != "arena" and bool((g[150:1750, :26] > 150).any() or (g[150:1750, -26:] > 150).any())
            black = s["suck"] and T >= s["t1"] - 0.15
            flag = "thin" if (ink < 0.15 and not black) else ("CUT OFF AT EDGE" if edge else "ok")
            rows.append([s["id"], s["type"], f"{T:.1f}", f"{ink:.1f}%", flag])
            sh.paste(to_img(fr).resize((w, h)), ((i % cols) * w, (i // cols) * (h + 20))); dr.text(((i % cols) * w + 4, (i // cols) * (h + 20) + h + 4), f"{s['id']} @ {T:.1f}s", fill=(255, 255, 0))
        for s in SC:                                                  # a scene is EMPTY only if every sampled moment of it is
            mine = [r for r in rows if r[0] == s["id"]]; allthin = all(r[4] == "thin" for r in mine)
            for r in mine:
                if r[4] == "thin": r[4] = "EMPTY" if allthin else "ok (quiet moment)"
        bad = sum(r[4] in ("EMPTY", "CUT OFF AT EDGE") for r in rows)
        sh.save("out/sheet.jpg", quality=88)
        table(rows, ["scene", "type", "at (s)", "bright area", "result"])
        print(f"\n{'OK' if not bad else 'FIX NEEDED'}: out/sheet.jpg ({len(shots)} frames). If you can view images, look at it: every scene shows its text, nothing cut off.\n"
              + ("EMPTY = nothing is drawn at that moment (missing heading/lines/clip?). CUT OFF = text is too long for the screen: shorten it.\n" if bad else "")
              + "Then: python3 scripts/render.py   (takes minutes: run it in the background and poll the log)")
        sys.exit(1 if bad else 0)
    need("out/mix.wav", "Run: python3 scripts/mix.py")
    todo = [] if a.mux else [s for s in SC if (not a.scene or s["id"] == a.scene)]
    if a.scene and not todo and not a.mux: die(f"no scene with id '{a.scene}'. Ids: {', '.join(s['id'] for s in SC)}")
    for s in todo: encode_scene(s)
    miss = [s["id"] for s in SC if not os.path.exists(f"out/scenes/{s['i']:02d}.mp4")]
    if miss: die(f"scenes not rendered yet: {miss}. Run render.py with no arguments.")
    with open("out/scenes/list.txt", "w") as f: f.write("".join(f"file '{s['i']:02d}.mp4'\n" for s in SC))
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "out/scenes/list.txt", "-i", "out/mix.wav", "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest", "out/final.mp4"], capture_output=True, text=True)
    if r.returncode != 0: die("ffmpeg join failed: " + r.stderr[-300:])
    print(f"OK out/final.mp4 ({duration('out/final.mp4'):.1f} s). Next: python3 scripts/check.py")
