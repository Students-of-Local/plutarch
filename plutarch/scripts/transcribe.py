#!/usr/bin/env python3
"""Transcribe long source files so you can search them for quotes.
  python3 scripts/transcribe.py src/interview.mp3            -> tx/interview.json + tx/interview.txt
  python3 scripts/transcribe.py src/a.mp3 src/b.m4a          -> one after the other
Works in 10-minute chunks so memory stays small. Use clip.py find to search the result."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+"); ap.add_argument("--model", default="base.en", help="base.en is fast; small.en is more accurate")
ap.add_argument("--chunk", type=float, default=600.0)
a = ap.parse_args()
for f in a.files: need(f)
for n, file in enumerate(a.files, 1):
    total = duration(file); stem = os.path.splitext(os.path.basename(file))[0]
    segs = []; t = 0.0
    print(f"transcribing {file} ({total/60:.1f} min) with {a.model}, file {n} of {len(a.files)} ...", flush=True)
    while t < total:
        x = audio(file, t, min(total, t + a.chunk), ch=1, sr=16000)[:, 0].astype("float32")
        out, _ = whisper(a.model).transcribe(x, beam_size=1, vad_filter=True, condition_on_previous_text=False)
        for sg in out:
            segs.append({"s": round(t + sg.start, 2), "e": round(t + sg.end, 2), "text": sg.text.strip()})
        t += a.chunk
        print(f"  {min(t, total)/60:5.1f} / {total/60:.1f} min", flush=True)
    save_json(f"tx/{stem}.json", {"file": file, "duration": total, "segments": segs})
    with open(f"tx/{stem}.txt", "w", encoding="utf8") as fh:
        for s in segs: fh.write(f"[{s['s']:8.2f}] {s['text']}\n")
    print(f"OK wrote tx/{stem}.json and tx/{stem}.txt ({len(segs)} lines).", flush=True)
print(f"OK: {len(a.files)} file(s) transcribed. Next: python3 scripts/next.py")
