#!/usr/bin/env python3
"""Find quotes in a transcript, then cut them exactly and get a start time for every word.

  python3 scripts/clip.py find tx/interview.json "words he said"       # where is it said? (prints in/out seconds)
  python3 scripts/clip.py make                                         # cut every clip in film.json -> clips/<id>.wav + .json
  python3 scripts/clip.py make bet                                     # redo one clip
  python3 scripts/clip.py show bet                                     # print its words and times

`make` only needs ROUGH in/out (within ~1.5 s) plus the words you want ("text"). It snaps the cut to the
exact word edges for you. Mark noisy recordings (crowds, phones) live with film.py clip KEY --live: the voice is separated
from the noise and the timing is checked against the pitch of the voice."""
import sys, os, re, argparse, difflib, shlex
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

BEATS = ["start", "risk", "cost", "turn", "payoff", "comeback"]   # same list as film.py and next.py
EXAMPLE_QUERIES = {"a few words or an idea", "words he said", "a phrase you want"}

def free_key(used):
    return next((b for b in BEATS + [f"q{n}" for n in range(7, 99)] if b not in used), "q99")

def retype(cid, c, **change):
    """The film.py command that changes this clip (film.py keeps its --live and --isolate)."""
    c = dict(c, **change); q = dq; t = lambda v: v if isinstance(v, str) else f"{float(v):g}"
    return (f"python3 scripts/film.py clip {cid} {c.get('src')} {t(c.get('in', 0))} {t(c.get('out', 0))} "
            f"{q(str(c.get('text') or 'the exact words said'))} {c.get('year') or 'YEAR'} {q(str(c.get('about') or 'what he was talking about'))}")

def lines_cmd(cid, sel):
    """The film.py command that sets this clip's captions, filled with the heard words."""
    return f"python3 scripts/film.py clip {cid} --lines " + " ".join(dq(p["text"]) for p in phrases_from(sel, None)[0])

def widened(cid, c):
    i = max(0.0, float(c["in"]) - 1); return retype(cid, c, **{"in": i, "out": min(float(c["out"]) + 1, i + 25)})

def cmd_find(a):
    if a.phrase.split() and set(a.phrase.lower().replace("the ", " ").split()) <= set(BEATS):
        die(f"{a.phrase!r} is a beat name (a clip key), not words anyone said. Search for a word from your story.md "
            "facts: a name, a place, a year. next.py step 5 prints ready searches.")
    if a.phrase.strip().lower() in EXAMPLE_QUERIES:
        die(f"{a.phrase!r} is the example search. Search for words the person really said: a name, a place, "
            "or a word from your story.md facts, like \"Heisman\" or \"cut\".")
    tx = load_json(a.transcript)["segments"]
    q = [norm_word(w) for w in a.phrase.split() if norm_word(w)]
    if not q: die("empty phrase")
    cands = []
    for i in range(len(tx)):
        for n in (1, 2, 3):
            if i + n > len(tx): break
            words = [norm_word(w) for s in tx[i:i + n] for w in s["text"].split()]
            words = [w for w in words if w]
            m = difflib.SequenceMatcher(None, q, words)
            hit = sum(b.size for b in m.get_matching_blocks())
            score = hit / len(q) - 0.03 * n - 0.002 * max(0, len(words) - len(q))
            cands.append((score, i, n))
    cands.sort(reverse=True); seen = []; shown = 0
    if not cands or cands[0][0] < 0.3:
        print(f"no match for {a.phrase!r} in {a.transcript}: nobody says it there.\n"
              "FIX: search a different word (a name, a place, a year), or the other transcript.")
        return
    top = None
    for score, i, n in cands:
        if score < 0.3: break
        if any(abs(i - j) < 2 for j in seen): continue
        seen.append(i); shown += 1
        s, e = tx[i]["s"], tx[i + n - 1]["e"]
        if top is None: top = (s, e, ' '.join(x['text'] for x in tx[i:i + n]).strip())
        print(f"\n#{shown}  match {max(0, score) * 100:.0f}%   \"in\": {s:.1f}, \"out\": {e:.1f}")
        if i > 0: print(f"     before: {tx[i - 1]['text'][-90:]}")
        print(f"     >>>     {' '.join(x['text'] for x in tx[i:i + n])}")
        if i + n < len(tx): print(f"     after:  {tx[i + n]['text'][:90]}")
        if shown >= a.n: break
    try: film = json.load(open("film.json", encoding="utf8"))
    except FileNotFoundError: film = {}
    stem = os.path.splitext(os.path.basename(a.transcript))[0]
    src = next((k for k, v in film.get("sources", {}).items() if isinstance(v, dict) and os.path.splitext(os.path.basename(str(v.get("file", ""))))[0] == stem), "SOURCE")
    used = [k for k, v in film.get("clips", {}).items() if isinstance(v, dict) and "<<" not in json.dumps(v)]
    credit = str(film.get("sources", {}).get(src, {}).get("credit", "")) if isinstance(film.get("sources", {}).get(src), dict) else ""
    year = (re.findall(r"\b(?:1[6-9]|20)\d\d\b", credit) or ["YEAR"])[-1]
    s, e, words = top
    print(f"\nNext: to keep #1, run this. Change only the last quoted part to what he was talking about"
          f"{'' if year != 'YEAR' else ' and YEAR to the year he said it'}.\n"
          f"For another result, use its \"in\" and \"out\" numbers and its >>> words instead (clip.py make snaps rough numbers).\n"
          f"  python3 scripts/film.py clip {free_key(used)} {shlex.quote(src)} {s:.1f} {e:.1f} {dq(words)} {year} \"what he was talking about\"")

def voicing(x, sr):
    """Per-10ms flags: is a steady voice pitch present? Returns (times, flags)."""
    import librosa
    y = librosa.resample(x.astype(np.float32), orig_sr=sr, target_sr=22050)
    _, vf, _ = librosa.pyin(y, fmin=70, fmax=300, sr=22050, frame_length=2048, hop_length=220)
    return np.arange(len(vf)) * 220 / 22050, vf.astype(bool)

def voiced_islands(t, vf, min_len=0.25, join=0.25):
    """Stretches of speech: voiced runs, joined across gaps shorter than `join` seconds."""
    runs = []; i = 0
    while i < len(vf):
        if vf[i]:
            j = i
            while j + 1 < len(vf) and vf[j + 1]: j += 1
            runs.append([float(t[i]), float(t[j]) + 0.01]); i = j + 1
        else: i += 1
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < join: merged[-1][1] = r[1]
        else: merged.append(r)
    return [r for r in merged if r[1] - r[0] >= min_len]

def isolate(x, sr):
    """Voice-only version of a stereo clip using demucs. Returns None if demucs is not installed."""
    try:
        import torch
        from demucs.pretrained import get_model
        from demucs.apply import apply_model
    except Exception:
        return None
    import librosa
    m = get_model("htdemucs"); m.eval()
    y = np.stack([librosa.resample(x[:, c].astype(np.float32), orig_sr=sr, target_sr=44100) for c in range(2)])
    t = torch.tensor(y)[None]; ref = t.mean(1, keepdim=True)
    with torch.no_grad():
        out = apply_model(m, (t - ref.mean()) / (ref.std() + 1e-8), shifts=0, split=True, overlap=0.25)[0]
    v = (out[m.sources.index("vocals")] * (ref.std() + 1e-8) + ref.mean()).numpy()
    return np.stack([librosa.resample(v[c], orig_sr=44100, target_sr=sr) for c in range(2)], 1)

def best_span(words, text):
    """Indices (i, j) of the run of heard words that best matches the wanted text."""
    H = [norm_word(w["w"]) for w in words]; Q = [norm_word(w) for w in text.split() if norm_word(w)]
    m = difflib.SequenceMatcher(None, Q, H, autojunk=False)
    blocks = [b for b in m.get_matching_blocks() if b.size]
    if not blocks: return None, 0.0
    i, j = blocks[0].b, blocks[-1].b + blocks[-1].size - 1
    return (i, j), sum(b.size for b in blocks) / max(1, len(Q))

def phrases_from(words, lines):
    if lines:
        need_n = sum(len(l.split()) for l in lines)
        if need_n == len(words):
            out = []; k = 0
            for l in lines:
                n = len(l.split()); out.append({"text": l, "words": [{"w": tw, "s": words[k + q]["s"]} for q, tw in enumerate(l.split())]}); k += n
            return out, None
        warn = f"the captions (\"lines\") have {need_n} words but {len(words)} were heard; using the heard words."
    else: warn = None
    out = []; cur = []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 9
        if gap > 0.38 or len(cur) >= 9 or (w["w"][-1:] in ".?!" and len(cur) >= 3):
            out.append(cur); cur = []
    if cur: out.append(cur)
    return [{"text": " ".join(w["w"] for w in p), "words": [{"w": w["w"], "s": w["s"]} for w in p]} for p in out], warn

def align_words(x, sr, text):
    """Place every word of a KNOWN sentence on the audio (forced alignment). Returns [(start, end)] per word, or None."""
    try:
        import torch, torchaudio, librosa
        bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
        model = bundle.get_model(); labels = bundle.get_labels()
    except Exception:
        return None
    dic = {ch: i for i, ch in enumerate(labels)}
    toks = text.split(); all_caps = text.upper() == text
    forms = []
    for t in toks:
        core = re.sub(r"[^A-Za-z']", "", t.replace("’", "'"))
        if not core: forms.append([])
        elif core.isupper() and 1 < len(core) <= 5 and not all_caps: forms.append(list(core))   # acronym: C E O
        else: forms.append([core.upper()])
    flat = [w for f in forms for w in f]
    if not flat: return None
    tr = "|".join(flat)
    if any(ch not in dic for ch in tr): return None
    wav = torch.tensor(librosa.resample(x.astype(np.float32), orig_sr=sr, target_sr=16000))[None]
    wav = wav / (wav.abs().max() + 1e-9) * 0.7
    with torch.inference_mode():
        em, _ = model(wav); em = torch.log_softmax(em, -1)
    if em.shape[1] < len(tr) * 2: return None
    al, _ = torchaudio.functional.forced_align(em, torch.tensor([[dic[ch] for ch in tr]]), blank=0)
    al = al[0].tolist(); ratio = wav.shape[1] / em.shape[1] / 16000
    spans = []; prev = 0
    for fr, lab in enumerate(al):
        if lab != 0 and lab != prev: spans.append([fr, fr])
        elif lab != 0: spans[-1][1] = fr
        prev = lab
    if len(spans) != len(tr): return None
    sub = []; pos = 0
    for w in flat:
        sp = spans[pos:pos + len(w)]; sub.append((sp[0][0] * ratio, (sp[-1][1] + 1) * ratio)); pos += len(w) + 1
    out = []; k = 0
    for f in forms:
        if f: out.append((sub[k][0], sub[k + len(f) - 1][1])); k += len(f)
        else: out.append(None)
    for i, v in enumerate(out):          # tokens with no letters (numbers) sit just after the previous word
        if v is None:
            p = out[i - 1][1] if i > 0 and out[i - 1] else 0.0
            out[i] = (p, p + 0.2)
    return out

def snap_to_sound(sel, x, sr):
    """Speech recognizers start a word too early when it follows a pause (the pause ends up inside the word).
    Move every word that starts in silence forward to where its sound really begins."""
    from scipy import signal
    y = signal.sosfilt(signal.butter(2, 120, "hp", fs=sr, output="sos"), x)
    hop = int(0.01 * sr); n = (len(y) - 3 * hop) // hop
    if n < 20: return 0, False
    db = np.array([20 * np.log10(np.sqrt(np.mean(y[i * hop:i * hop + 3 * hop] ** 2)) + 1e-7) for i in range(n)])
    thr = np.percentile(db, 95) - 22.0; moved = 0
    noisy = np.percentile(db, 15) > thr                      # no silence between words: music or noise under the voice
    for k, w in enumerate(sel):
        i0 = min(n - 1, int(w["s"] / 0.01)); i1 = min(n - 4, int((w["e"] - 0.05) / 0.01))
        if db[i0] > thr: continue
        for i in range(i0, max(i0, i1)):
            if (db[i:i + 4] > thr).all():
                if i * 0.01 - w["s"] > 0.08: w["s"] = round(i * 0.01 - 0.02, 3); moved += 1
                break
    return moved, noisy

def long_enough(cid, secs, live):
    if not live and secs < 1.0:
        die(f"clip '{cid}': the words last only {secs:.2f} s. A quote is 1 to 9 seconds: check.py can't hear a shorter one again in the film. "
            f"Pick a longer line, or: python3 scripts/film.py drop clip {cid}")

def make_one(cid, film):
    import librosa
    c = film["clips"][cid]
    for k in ("src", "in", "out"):
        if k not in c: die(f"clip '{cid}' needs \"{k}\"")
    if c["src"] not in film.get("sources", {}): die(f"clip '{cid}' uses source '{c['src']}' which is not in \"sources\"")
    src = film["sources"][c["src"]]["file"]; need(src)
    live = bool(c.get("live")); pad = 1.5
    w0 = max(0.0, c["in"] - pad); w1 = min(duration(src), c["out"] + pad)
    st = audio(src, w0, w1, ch=2)
    notes = []; want = c.get("text") or " ".join(c.get("lines", []))
    def heard(x):
        return words_of(librosa.resample(x.mean(1).astype(np.float32), orig_sr=SR, target_sr=16000), "small.en")
    sel = None; verified = "unverified"; prev_e = next_s = None; conflict = 0.0
    vocals = isolate(st, SR)                                   # voice without music/noise: used to time the words
    if vocals is None: notes.append("demucs not installed, so word timing uses the raw audio (fine for clean interviews). For music or noise under the voice: pip install demucs")
    if live:
        if not want: die(f"clip '{cid}' is live, so it needs \"text\": the exact words that are said.")
        base = vocals if vocals is not None else st
        lo = max(0.0, c["in"] - w0 - 0.3); hi = min(len(base) / SR, c["out"] - w0 + 1.0)
        tt, vf = voicing(base[int(lo * SR):int(hi * SR)].mean(1), SR)
        isl = [[a_ + lo, b_ + lo] for a_, b_ in voiced_islands(tt, vf)]
        if isl:
            onset = isl[0][0]
            sents = [x for x in re.split(r"(?<=[.?!])\s+", want.strip()) if x]
            sel = []
            if len(sents) == len(isl) and len(sents) > 1:        # one stretch of speech per sentence: align each on its own
                for k, (sn, (ia, ib)) in enumerate(zip(sents, isl)):
                    a0 = max(isl[k - 1][1] + 0.05 if k else 0.0, ia - 0.35)
                    b0 = min(isl[k + 1][0] - 0.05 if k + 1 < len(isl) else hi, ib + 0.45)
                    times = align_words(base[int(a0 * SR):int(b0 * SR)].mean(1), SR, sn)
                    if not times: sel = []; break
                    sel += [{"w": tok, "s": round(a0 + s_, 3), "e": round(a0 + e_, 3), "p": 1.0} for tok, (s_, e_) in zip(sn.split(), times)]
            if not sel:
                a0 = max(0.0, onset - 0.4)
                times = align_words(base[int(a0 * SR):int(hi * SR)].mean(1), SR, want)
                if times:
                    sel = [{"w": tok, "s": round(a0 + s_, 3), "e": round(a0 + e_, 3), "p": 1.0} for tok, (s_, e_) in zip(want.split(), times)]
                    starts = [i0 for i0, _ in isl]
                    for k in range(1, len(sel)):       # a word after a pause starts where the voice comes back in
                        if sel[k - 1]["w"][-1:] in ".?!" or sel[k]["s"] - sel[k - 1]["e"] > 0.3:
                            nxt = [x for x in starts if x > sel[k - 1]["s"] + 0.2 and abs(x - sel[k]["s"]) < 1.5]
                            if nxt:
                                d = max(0.16, sel[k]["e"] - sel[k]["s"]); sel[k]["s"] = round(nxt[0] - 0.06, 3)
                                sel[k]["e"] = round(min(sel[k]["s"] + d, sel[k + 1]["s"] - 0.02 if k + 1 < len(sel) else 1e9), 3)
            if sel:                                         # cross-check against plain speech recognition: two methods must not disagree
                ws_c = heard(base); sp_c, cov_c = best_span(ws_c, want) if ws_c else (None, 0)
                if sp_c and cov_c >= 0.4:
                    cs = [dict(w) for w in ws_c[sp_c[0]:sp_c[1] + 1]]; snap_to_sound(cs, base.mean(1), SR)
                    ops = difflib.SequenceMatcher(None, [norm_word(w["w"]) for w in sel], [norm_word(w["w"]) for w in cs]).get_opcodes()
                    df = [abs(sel[a1 + k]["s"] - cs[b1 + k]["s"]) for tag, a1, a2, b1, b2 in ops if tag == "equal" for k in range(a2 - a1)]
                    off = [d for d in df if d > 0.6]
                    if len(df) >= 3 and len(off) >= 2 and len(off) / len(df) >= 0.25: conflict = float(max(off))
            if sel and conflict:
                notes.append(f"NOT VERIFIED: two timing methods disagree by up to {conflict:.1f} s on this clip, so its captions cannot be trusted. "
                             f"If this is not a crowd or phone recording: python3 scripts/film.py clip {cid} --no-live, and run make again. Otherwise set IN and OUT tightly around the sentence (clip.py find shows them):  " + retype(cid, c, **{"in": "IN", "out": "OUT"}) + f"   or drop the quote: python3 scripts/film.py drop clip {cid}")
            elif sel:
                verified = "pitch"
                notes.append(f"voice starts at {onset + w0:.2f} s (pitch); every word of \"text\" was placed by forced alignment.")
            else:
                sel = None; notes.append("forced alignment unavailable (needs torch + torchaudio); fell back to plain speech recognition.")
        else: notes.append("no steady voice pitch found in this window. Find the sentence again (clip.py find) and set IN and OUT:  " + retype(cid, c, **{"in": "IN", "out": "OUT"}))
    if sel is None:
        words = heard(vocals if vocals is not None else st)
        if not words: die(f"clip '{cid}': no speech heard between {w0:.1f} and {w1:.1f} s of {src}. Check in/out with clip.py find.")
        if want:
            span, cover = best_span(words, want)
            if span is None or cover < 0.85:
                die(f"clip '{cid}': could not find all of \"{want[:70]}\" near {c['in']}-{c['out']} s.\n       Heard there: \"{' '.join(w['w'] for w in words)[:200]}\"\n"
                    f"       Fix in/out (clip.py find), or give the exact words said there:  " + retype(cid, c, text="the exact words said") +
                    ("" if live else f"\n       If the recording is noisy (crowd, phone):  python3 scripts/film.py clip {cid} --live"))
            i, j = span
        else:
            inside = [k for k, w in enumerate(words) if w["s"] + w0 >= c["in"] - 0.15 and w["e"] + w0 <= c["out"] + 0.15]
            if not inside: die(f"clip '{cid}': no whole words between in and out. Widen the cut:  " + widened(cid, c))
            i, j = inside[0], inside[-1]
        sel = [dict(w) for w in words[i:j + 1]]
        mv, _ = snap_to_sound(sel, (vocals if vocals is not None else st).mean(1), SR)
        if mv: notes.append(f"{mv} word(s) that followed a pause were moved to where their sound really starts.")
        if want:                                            # words of "text" that speech recognition did not hear inside the cut
            hn = [norm_word(w["w"]) for w in sel]; wn = [norm_word(x) for x in want.split()]
            miss = [want.split()[k] for tag, a1, a2, _, _ in difflib.SequenceMatcher(None, wn, hn).get_opcodes() if tag in ("delete", "replace") for k in range(a1, a2)]
            if miss: notes.append(f"NOT IN THE CUT: \"{' '.join(miss)}\" (from your \"text\") was not heard, so the film will play and show only the words in the \"heard\" column. "
                                  "If the quote still makes sense, use the heard words:\n    " + retype(cid, c, text=" ".join(w["w"] for w in sel)) +
                                  "\n  If not, widen the cut by 1 s and run make again, or pick another quote:\n    " +
                                  widened(cid, c))
        if vocals is not None and not c.get("isolate"):     # how loud is everything that is NOT the voice, while he speaks?
            i0, i1 = int(sel[0]["s"] * SR), int(sel[-1]["e"] * SR); n_ = min(len(st), len(vocals)); i1 = min(i1, n_)
            rv = np.sqrt((vocals[i0:i1] ** 2).mean()) + 1e-9; rr = np.sqrt(((st[i0:i1] - vocals[i0:i1]) ** 2).mean()) + 1e-9
            if 20 * np.log10(rr / rv) > -15:
                notes.append(f"there is music or noise under this voice. Use the cleaned voice in the film:  python3 scripts/film.py clip {cid} --isolate")
        prev_e = words[i - 1]["e"] if i > 0 else None; next_s = words[j + 1]["s"] if j + 1 < len(words) else None
    a = sel[0]["s"] - (0.25 if verified == "pitch" else 0.08); b = sel[-1]["e"] + (0.30 if verified == "pitch" else 0.20)
    if prev_e is not None: a = max(a, (prev_e + sel[0]["s"]) / 2)
    if next_s is not None: b = min(b, (sel[-1]["e"] + next_s) / 2 + 0.03)
    a = max(0.0, a); b = min(len(st) / SR, b); long_enough(cid, b - a, live)
    for w in sel: w["s"] = round(w["s"] - a, 3); w["e"] = round(w["e"] - a, 3)
    keep = vocals if (c.get("isolate") and vocals is not None) else st
    save_wav(f"clips/{cid}.wav", keep[int(a * SR):int(b * SR)])
    if live and vocals is not None: save_wav(f"clips/{cid}.vocals.wav", vocals[int(a * SR):int(b * SR)])
    elif os.path.exists(f"clips/{cid}.vocals.wav"): os.remove(f"clips/{cid}.vocals.wav")
    heard_text = " ".join(w["w"] for w in sel)
    low = [w["w"] for w in sel if w["p"] < 0.5]
    phr, warn = phrases_from(sel, c.get("lines"))
    if warn: notes.append(warn + "  Set them again, changing only wrong words:  " + lines_cmd(cid, sel))
    sim = similarity(want, heard_text) if want else 1.0
    if verified != "pitch" and not conflict:
        verified = "asr" if (len(low) <= max(1, len(sel) // 4) and sim >= 0.8) else "unverified"
    if verified == "unverified" and not conflict:
        notes.append("NOT VERIFIED: you cannot listen, so either pick a cleaner recording of this line, "
                     f"or mark it live (python3 scripts/film.py clip {cid} --live), check its exact words, and run make again.")
    gone = [k for k in ("year", "about") if not c.get(k)]
    if gone: notes.append(f"this clip has no {' or '.join(gone)} (when / what he was talking about), and check.py fails without it:  " + retype(cid, c))
    save_json(f"clips/{cid}.json", {"id": cid, "src": c["src"], "in_exact": round(w0 + a, 3), "out_exact": round(w0 + b, 3),
              "dur": round(b - a, 3), "heard": heard_text, "wanted": want, "similarity": round(sim, 2), "live": live,
              "verified": verified, "low_confidence": low, "words": sel, "phrases": phr, "spec": clip_spec(c)})
    return [cid, f"{w0 + a:.2f}-{w0 + b:.2f}", f"{b - a:.2f}s", verified, heard_text[:70]], notes

def cmd_make(a):
    film = load_film(only=("sources", "clips"))
    ids = a.ids or list(film.get("clips", {}))
    if not ids: die("film.json has no \"clips\" yet")
    rows = []; lost = []; bad = 0
    for cid in ids:
        if cid not in film["clips"]: die(f"no clip named '{cid}' in film.json")
        try: row, notes = make_one(cid, film)
        except SystemExit:                                     # make_one printed its ERROR line; cut the other clips anyway
            lost.append(cid); rows.append([cid, "-", "-", "NOT CUT", "-"]); continue
        rows.append(row)
        for n in notes: print(f"  [{cid}] {n}")
        bad += row[3] == "unverified"
    table(rows, ["clip", "exact in-out (s)", "length", "verified", "heard"])
    if lost: print(f"\nNOT CUT: {', '.join(lost)}. Running make again gives the same result until that quote changes. Next: python3 scripts/next.py")
    bad += len(lost)
    print(f"\n{'OK' if not bad else 'FIX NEEDED'}: {len(rows) - bad}/{len(rows)} clips verified. Captions use the \"heard\" words. "
          f"If a heard word is wrong, python3 scripts/clip.py show KEY prints the command that fixes it.")
    sys.exit(1 if bad else 0)

def cmd_show(a):
    d = load_json(f"clips/{a.id}.json")
    print(f"{d['id']}  {d['dur']}s  verified={d['verified']}  similarity={d['similarity']}")
    for p in d["phrases"]: print("  " + "  ".join(f"{w['w']}@{w['s']:.2f}" for w in p["words"]))
    print("If a caption word is wrong, run this with only the wrong words changed (keep the same number of words):\n  "
          + lines_cmd(a.id, d["words"]))

ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
f = sub.add_parser("find"); f.add_argument("transcript"); f.add_argument("phrase"); f.add_argument("-n", type=int, default=4); f.set_defaults(fn=cmd_find)
m = sub.add_parser("make"); m.add_argument("ids", nargs="*"); m.set_defaults(fn=cmd_make)
s = sub.add_parser("show"); s.add_argument("id"); s.set_defaults(fn=cmd_show)
a = ap.parse_args(); a.fn(a)
