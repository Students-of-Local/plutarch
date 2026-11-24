#!/usr/bin/env bash
# Acceptance checks for the plutarch task (skill-distill step 3).
# Gets $WORKSPACE (the trial's folder) and $OUT (where evidence goes). Exit 0 only if every scripted check passes.
set -u
RUN_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="${WORKSPACE:?set WORKSPACE}"; OUT="${OUT:-$RUN_DIR/checks-out}"; mkdir -p "$OUT"
KIT=""
for c in "$RUN_DIR/skill/scripts" "$WORKSPACE/.skill/plutarch/scripts" "${CLIPDOC_SCRIPTS:-}"; do
  if [ -n "$c" ] && [ -f "$c/check.py" ]; then KIT="$c"; break; fi
done
if [ -z "$KIT" ]; then echo "FAIL cannot find the skill's check.py" | tee "$OUT/checks.log"; exit 1; fi
FINAL="$(find "$WORKSPACE" -path '*/.skill' -prune -o -path '*/out/final.mp4' -print 2>/dev/null | head -1)"
if [ -z "$FINAL" ]; then echo "FAIL no out/final.mp4 anywhere under $WORKSPACE: the student did not finish" | tee "$OUT/checks.log"; exit 1; fi
PROJ="$(dirname "$(dirname "$FINAL")")"; cd "$PROJ" || exit 1
echo "project: $PROJ" > "$OUT/checks.log"

python3 "$KIT/check.py" > "$OUT/check_table.txt" 2>&1; rc1=$?
cat "$OUT/check_table.txt" >> "$OUT/checks.log"

python3 - >> "$OUT/checks.log" 2>&1 <<'PY'
import json, sys
p = json.load(open("out/plan.json")); f = json.load(open("film.json")); bad = 0
def chk(name, ok, detail):
    global bad; bad += not ok; print(("PASS  " if ok else "FAIL  ") + f"{name:<38} {detail}")
sp = sorted([a for a in p["audio"] if a["role"] in ("narr", "voice", "live")], key=lambda a: a["at"])
real = [a for a in sp if a["role"] != "narr"]; narr = [a for a in sp if a["role"] == "narr"]
ids = {a.get("id") for a in real}; srcs = {f.get("clips", {}).get(i, {}).get("src") for i in ids} - {None}
rs = sum(a["dur"] for a in real); ns = sum(a["dur"] for a in narr)
chk("6+ real-voice clips", len(ids) >= 6, f"{len(ids)} clips")
chk("2+ sources of real voice", len(srcs) >= 2, f"{len(srcs)} sources")
sc = p["scenes"]; s0 = sc[0]; it0 = (s0.get("items") or [{}])[0]
chk("cold open on real sound", s0["type"] == "arena" or it0.get("kind") == "clip" or "clip" in it0, f"scene 1 is {s0['type']}")
chk("title and end card", any(s["type"] == "title" for s in sc) and sc[-1]["type"] == "end", " > ".join(s["type"] for s in sc))
chk("at least 60 s", p["dur"] >= 60, f"{p['dur']:.1f} s")
sys.exit(1 if bad else 0)
PY
rc2=$?

ffmpeg -v error -y -i out/final.mp4 -vf "fps=1/6,scale=216:-1,tile=8x4" -frames:v 1 "$OUT/contact.jpg" 2>/dev/null
[ -f out/sheet.jpg ] && cp out/sheet.jpg "$OUT/sheet.jpg"
[ -f story.md ] && cp story.md "$OUT/story.md"
[ -f film.json ] && cp film.json "$OUT/film.json"
grep -E "^(PASS|FAIL)" "$OUT/checks.log"
if [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ]; then echo "CHECKS PASSED"; exit 0; else echo "CHECKS FAILED (see $OUT/checks.log)"; exit 1; fi
