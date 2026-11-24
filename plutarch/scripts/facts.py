#!/usr/bin/env python3
"""Check that each fact in story.md is on both of its pages. film.py fact runs this for a new fact.

  python3 scripts/facts.py        # check every fact in story.md that is not checked yet

A page passes when it names the subject and has the fact's numbers and most of its main words close together.
That shows the page talks about it. It does not prove the claim: read the page."""
import hashlib, html, json, math, os, re, sys, unicodedata, urllib.request

DONE, NEAR = "out/facts.json", 60
OFF = os.environ.get("PLUTARCH_FACTS") == "off"      # for a person who read the sources (a book, a paywall); see README
STOP = set("about after also became become been before being could during first from have into later more most only over some "
           "than that their them then there they this were when where which while will with would year years".split())

def norm(s):
    s = unicodedata.normalize("NFKD", s); return "".join(c for c in s if not unicodedata.combining(c)).lower()

def tokens(s):
    return [t.lstrip("0") or "0" if t.isdigit() else t for t in re.findall(r"\d+|[a-z]+", re.sub(r"(?<=\d),(?=\d{3})", "", norm(s)))]

def page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; plutarch)"})
    with urllib.request.urlopen(req, timeout=25) as r: t = r.read(4_000_000).decode("utf8", "replace")
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)))

def missing(fact, text, who):
    """Why this page text does not back the fact, or None."""
    toks = tokens(text); names = [n for n in tokens(who) if n not in ("jr", "sr", "ii", "iii")]
    if names and names[-1] not in toks: return f"it never says {who.split()[-1]!r}"
    nums = {t for t in tokens(fact) if t.isdigit() and len(t) > 1}
    main = {t[:5] for t in tokens(fact) if t.isalpha() and len(t) > 3 and t not in STOP and t not in names}
    gone = sorted(n for n in nums if n not in toks)
    if gone: return f"it never says {', '.join(gone)}"
    need = math.ceil(len(main) / 2); cut = [t[:5] if t.isalpha() else t for t in toks]
    for i, t in enumerate(cut):
        if t in (nums or main):
            near = set(cut[max(0, i - NEAR):i + NEAR])
            if nums <= near and len(main & near) >= need: return None
    return f"it does not say {' and '.join(sorted(nums) + ['these words']) if nums else 'these words'} together"

def problem(fact, urls, who):
    for u in urls:
        try: why = missing(fact, page(u), who)
        except Exception as e: why = f"it did not open ({str(e)[:60]}). Use a page that does, such as Wikipedia or a news story"
        if why: return f"{u}: {why}"

def key(fact, urls): return hashlib.sha1("|".join([fact.strip(), *urls]).encode()).hexdigest()

def done():
    try: return set(json.load(open(DONE, encoding="utf8")))
    except (OSError, ValueError): return set()

def passed(fact, urls):
    os.makedirs("out", exist_ok=True); d = done() | {key(fact, urls)}
    with open(DONE, "w", encoding="utf8") as f: json.dump(sorted(d), f)

def rows(story):
    """(number, fact, [url, url]) for each row of the Facts table."""
    out = []
    for l in story.splitlines():
        c = [x.strip() for x in l.strip().strip("|").split("|")]; u = re.findall(r"https?://[^\s|]+", l)
        if l.startswith("|") and c[0].isdigit() and len(u) >= 2: out.append((int(c[0]), c[1], u[:2]))
    return out

def unchecked(story):
    d = done(); return [] if OFF else [r for r in rows(story) if key(r[1], r[2]) not in d]

if __name__ == "__main__":
    who = json.load(open("film.json", encoding="utf8")).get("subject", ""); story = open("story.md", encoding="utf8").read(); bad = []
    for at, (n, fact, urls) in enumerate(rows(story), 1):
        if (n, fact, urls) not in unchecked(story): continue
        why = problem(fact, urls, who)
        print(f"{'NOT ON ITS PAGES' if why else 'OK'}: fact {at}: {fact}" + (f"\n  {why}" if why else ""), flush=True)
        if why: bad.append(at)
        else: passed(fact, urls)
    for at in reversed(bad): print(f"FIX: python3 scripts/film.py drop fact {at}      # then add a fact you read on two pages")
    if not bad: print("OK: every fact is on its pages. Next: python3 scripts/next.py")
    sys.exit(1 if bad else 0)
