#!/usr/bin/env python3
"""Transcribe a long source file so you can search it for quotes.
  python3 scripts/transcribe.py src/interview.mp3            -> tx/interview.json + tx/interview.txt
Works in 10-minute chunks so memory stays small. Use clip.py find to search the result."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("file"); ap.add_argument("--model", default="base.en", help="base.en is fast; small.en is more accurate")
ap.add_argument("--chunk", type=float, default=600.0)
a = ap.parse_args()
need(a.file); total = duration(a.file)
stem = os.path.splitext(os.path.basename(a.file))[0]
segs = []; t = 0.0
print(f"transcribing {a.file} ({total/60:.1f} min) with {a.model} ...", flush=True)
while t < total:
    x = audio(a.file, t, min(total, t + a.chunk), ch=1, sr=16000)[:, 0].astype("float32")
    out, _ = whisper(a.model).transcribe(x, beam_size=1, vad_filter=True, condition_on_previous_text=False)
    for sg in out:
        segs.append({"s": round(t + sg.start, 2), "e": round(t + sg.end, 2), "text": sg.text.strip()})
    t += a.chunk
    print(f"  {min(t, total)/60:5.1f} / {total/60:.1f} min", flush=True)
save_json(f"tx/{stem}.json", {"file": a.file, "duration": total, "segments": segs})
with open(f"tx/{stem}.txt", "w", encoding="utf8") as f:
    for s in segs: f.write(f"[{s['s']:8.2f}] {s['text']}\n")
print(f"OK wrote tx/{stem}.json and tx/{stem}.txt ({len(segs)} lines). Next: python3 scripts/next.py")
