#!/usr/bin/env python3
"""Turn film.json (scenes in order) into exact times: out/plan.json. You never type timestamps yourself.

  python3 scripts/plan.py          # prints every scene with start, end and length, and the total

Run it again after ANY change to film.json, clips or narration."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

TYPES = ("title", "card", "arena", "stack", "chart", "end")
ENERGY = {"title": (1.0, 0.35), "card": (0.3, 0.35), "arena": (0.45, 0.95), "stack": (0.2, 0.2), "chart": (0.4, 1.0), "end": (1.0, 0.6)}
film = load_film()
for k in ("title", "subject", "scenes"):
    if not film.get(k): die(f"film.json needs \"{k}\"")
sources = film.get("sources", {}); clips = film.get("clips", {})
t = 0.0; scenes = []; aud = []; caps = []; tags = []; impacts = []; rows = []
n_sc = len(film["scenes"])
for i, sc in enumerate(film["scenes"]):
    ty = sc.get("type")
    if ty not in TYPES: die(f"scene {i + 1}: \"type\" must be one of {', '.join(TYPES)} (got {ty!r})")
    S = dict(sc); S["i"] = i; S["id"] = sc.get("id", f"s{i + 1}"); S["t0"] = round(t, 3)
    pre = sc.get("pre", 0.0 if ty in ("title", "end") else 0.45); post = sc.get("post", 0.0 if ty in ("title", "end") else 0.6)
    cur = t + pre; items = []; first = True
    for it in sc.get("items", []):
        if "gap" in it or "hold" in it:
            cur += float(it.get("gap", it.get("hold"))); first = True; continue
        if not first: cur += 0.28
        first = False
        if "say" in it:
            p = f"narr/{say_id(it['say'])}.json"
            if not os.path.exists(p): die(f"scene {i + 1}: narrator line not made yet (\"{it['say'][:40]}...\"). Run: python3 scripts/narrate.py")
            d = load_json(p)
            items.append({"kind": "say", "at": round(cur, 3), "dur": d["dur"], "text": it["say"], "words": d["words"]})
            aud.append({"role": "narr", "file": f"narr/{d['id']}.wav", "at": round(cur, 3), "dur": d["dur"], "scene": i, "label": it["say"][:40]})
            cur += d["dur"]
        elif "clip" in it:
            cid = it["clip"]
            if cid not in clips: die(f"scene {i + 1}: clip '{cid}' is not defined in film.json \"clips\"")
            p = f"clips/{cid}.json"
            if not os.path.exists(p): die(f"clip '{cid}' not cut yet. Run: python3 scripts/clip.py make {cid}")
            d = load_json(p); c = clips[cid]; srcd = sources.get(c["src"], {})
            items.append({"kind": "clip", "id": cid, "at": round(cur, 3), "dur": d["dur"], "words": d["words"]})
            aud.append({"role": "live" if d.get("live") else "voice", "file": f"clips/{cid}.wav", "at": round(cur, 3), "dur": d["dur"], "scene": i,
                        "id": cid, "label": d["heard"][:40], "vocals": f"clips/{cid}.vocals.wav" if os.path.exists(f"clips/{cid}.vocals.wav") else None})
            big = bool(it.get("big", d["dur"] < 1.7 and ty == "card" and not sc.get("lines")))
            ph = d["phrases"]
            for k, p_ in enumerate(ph):
                wt = [round(cur + w["s"], 3) for w in p_["words"]]
                t1 = wt[-1] + 0.4
                off = min(t1 + 1.0, cur + ph[k + 1]["words"][0]["s"] - 0.04) if k + 1 < len(ph) else t1 + 0.8
                caps.append({"t0": wt[0], "t1": round(t1, 3), "off": round(off, 3), "text": p_["text"], "wt": wt, "style": "big" if big else "cap",
                             "scene": i, "who": c.get("speaker") if k == len(ph) - 1 else None})
            who = (c.get("speaker") or film["subject"]).upper()
            tags.append({"t0": round(cur, 3), "t1": round(cur + d["dur"] + 0.3, 3), "text": f"{who} — {srcd.get('credit', c['src']).upper()}"})
            cur += d["dur"]
        else: die(f"scene {i + 1}: each item must be {{\"say\": ...}}, {{\"clip\": ...}} or {{\"gap\": seconds}} (got {it})")
    end = cur + post
    if ty in ("title", "end"): end = max(end, t + float(sc.get("hold", 3.4 if ty == "title" else 6.5)))
    u = sc.get("under")
    if u:
        uf = sources[u["src"]]["file"] if u.get("src") in sources else u.get("file")
        if not uf or not os.path.exists(uf): die(f"scene {i + 1}: \"under\" needs \"src\" (a source id) or \"file\" that exists")
        ud = float(u.get("out", duration(uf))) - float(u.get("in", 0))
        if not items: end = max(end, t + ud)
        aud.append({"role": "crowd", "file": uf, "in": float(u.get("in", 0)), "at": round(t, 3), "dur": round(min(ud, end - t), 3), "scene": i,
                    "gain": float(u.get("gain", -18)), "drums": bool(u.get("drums")), "label": "under: " + os.path.basename(uf)})
        if u.get("credit") or u.get("src") in sources:
            tags.append({"t0": round(t + 0.2, 3), "t1": round(min(end, t + 6) - 0.4, 3), "text": (u.get("credit") or sources[u["src"]].get("credit", "")).upper()})
    end = max(end, t + float(sc.get("min", {"chart": 7.0, "card": 2.5}.get(ty, 1.5))))
    S["t1"] = round(end, 3); S["items"] = items
    # text timing
    says_ = [x for x in items if x["kind"] == "say"]
    lines = sc.get("lines", []); la = []
    for k, ln in enumerate(lines):
        txt = ln["text"] if isinstance(ln, dict) else ln; at = None
        if isinstance(ln, dict) and ln.get("at"):
            key = norm_word(ln["at"])
            for sy in says_:
                hit = [w for w in sy["words"] if norm_word(w["w"]).startswith(key)]
                if hit: at = sy["at"] + hit[0]["s"] - 0.15; break
        if at is None:
            at = says_[0]["at"] + says_[0]["dur"] * 0.9 * k / max(1, len(lines)) - 0.1 if says_ else t + 0.5 + 0.9 * k
        la.append({"text": txt, "at": round(max(t + 0.15, at), 3)})
    S["lines"] = la
    if ty == "stack":
        cl = [x for x in items if x["kind"] == "clip"]
        if not cl or not sc.get("words"): die(f"scene {i + 1}: a stack scene needs one clip item and \"words\": [the big words, in spoken order]")
        st = []; k = 0; ws = [(x["at"] + w["s"], norm_word(w["w"])) for x in cl for w in x["words"]]
        for wd in sc["words"]:
            key = norm_word(wd)[:5]
            while k < len(ws) and not ws[k][1].startswith(key): k += 1
            if k >= len(ws): die(f"scene {i + 1}: stack word '{wd}' is not said in the clip (after the previous word). Heard: {' '.join(w for _, w in ws)}")
            st.append({"text": wd.upper(), "at": round(ws[k][0], 3)}); k += 1
        S["stack"] = st
    if ty == "chart":
        pts = sc.get("points")
        if not pts or len(pts) < 3: die(f"scene {i + 1}: a chart needs \"points\": [[x, value], ...] (3 or more, real numbers with a source)")
        if not sc.get("source"): die(f"scene {i + 1}: a chart needs \"source\": where the numbers come from (a URL or a publication name). Never invent chart numbers.")
    if ty == "arena":
        pk = sc.get("peak")
        if pk:
            m = [x for x in items if x.get("id") == pk]
            if not m: die(f"scene {i + 1}: \"peak\" must be the id of a clip in this scene")
            S["peak_at"] = round(m[0]["at"] - 0.25, 3); impacts.append(S["peak_at"])
    S["impact"] = bool(sc.get("impact", ty in ("title", "end")))
    if S["impact"]: impacts.append(S["t0"])
    e = sc.get("energy", (0.15, 0.15) if sc.get("bg") == "pulse" else ENERGY[ty]); S["energy"] = [float(e[0]), float(e[1])]
    S["music"] = bool(sc.get("music", not (i == 0 and ty == "arena")))
    scenes.append(S)
    what = " + ".join((x["kind"] + ":" + (x.get("id") or x["text"][:18])) for x in items) or ("under " + os.path.basename(u.get("file", u.get("src", ""))) if u else "-")
    rows.append([i + 1, S["id"], ty, f"{S['t0']:.1f}", f"{S['t1']:.1f}", f"{S['t1'] - S['t0']:.1f}s", what[:60]])
    t = end
for k, S in enumerate(scenes):
    S["suck"] = k + 1 < len(scenes) and scenes[k + 1]["impact"]      # go dark and silent just before the next impact
caps.sort(key=lambda c_: c_["t0"])
for c1, c2 in zip(caps, caps[1:]):                                   # never two quotes on screen at once
    c1["off"] = round(min(c1["off"], max(c1["wt"][-1] + 0.15, c2["t0"] - 0.04)), 3)
plan = {"title": film["title"], "subject": film["subject"], "accent": list(hexrgb(film.get("accent", "#76B900"))), "fps": 30, "size": [1080, 1920],
        "dur": round(t, 3), "max_seconds": film.get("max_seconds", 140), "scenes": scenes, "audio": aud, "captions": caps, "tags": tags,
        "impacts": sorted(set(impacts)), "music": film.get("music", {"synth": True}),
        "credits": [s.get("credit", k) for k, s in sources.items()]}
save_json("out/plan.json", plan)
table(rows, ["#", "id", "type", "start", "end", "length", "contents"])
over = t - plan["max_seconds"]
print(f"\nTOTAL {t:.1f} s (limit {plan['max_seconds']} s). " + (f"OVER by {over:.1f} s: cut a clip, shorten narrator lines or remove a scene, then run plan.py again." if over > 0 else "OK."))
sp = sorted([x for x in aud if x["role"] in ("narr", "voice", "live")], key=lambda x: x["at"])
rs = sum(x["dur"] for x in sp if x["role"] != "narr"); ns = sum(x["dur"] for x in sp if x["role"] == "narr")
nq = len({x.get("id") for x in sp if x["role"] != "narr"}); wantq = max(3, round(t / 25))
print(f"REAL VOICE {rs:.0f} s, NARRATOR {ns:.0f} s, QUOTES {nq}.")
if rs < 0.5 * (rs + ns): print(f"FIX: the narrator talks more than the subject. Add quotes or cut narrator lines until real voice is at least half ({(rs + ns) / 2:.0f} s). check.py fails otherwise.")
if nq < wantq: print(f"FIX: a film this long needs at least {wantq} quotes (you have {nq}). check.py fails otherwise.")
if sp and sp[-1]["role"] == "narr": print("FIX: the last thing said must be the subject's own voice, not the narrator. check.py fails otherwise.")
if not over > 0: print("Next: python3 scripts/score.py prompt   (music)  then  python3 scripts/mix.py")
sys.exit(1 if over > 0 else 0)
