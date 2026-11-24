#!/usr/bin/env python3
"""Check that each fact in story.md is on both of its pages. film.py fact runs this for a new fact.

  python3 scripts/facts.py        # check every fact in story.md that is not checked yet

A page passes when it has the subject's full name, and the fact's numbers, its names (places, teams, awards) and half of
its other words within 12 words of each other. That shows the page says them together. It does not prove the claim: read
the page."""
import hashlib, html, json, math, os, re, sys, unicodedata, urllib.request

DONE, NEAR = "out/facts.json", 12
OFF = os.environ.get("PLUTARCH_FACTS") == "off"      # for a person who read the sources (a book, a paywall); see README
STOP = set("a about after also an and are as at became become been before being by could during first for from had has have he her him his in "
           "into is it its later more most of on only or over she some than that the their them then there they this to was were when "
           "where which while who will with would year years".split())
MONTHS = "january february march april may june july august september october november december".split()
SPELLED = dict(zip("0123456789", "zero one two three four five six seven eight nine".split()))

def norm(s):
    s = unicodedata.normalize("NFKD", s); return "".join(c for c in s if not unicodedata.combining(c))

def split(s):
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", norm(s))
    return [t.lstrip("0") or "0" if t.isdigit() else t for t in re.findall(r"\d+|[A-Za-z]+", s)]

def page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; plutarch)"})
    with urllib.request.urlopen(req, timeout=25) as r: t = r.read(4_000_000).decode(r.headers.get_content_charset() or "utf8", "replace")
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)))

def missing(fact, text, who):
    """Why this page text does not back the fact, or None."""
    toks = [t.lower() for t in split(text)]; names = [n.lower() for n in split(who)]
    last = [i for i, t in enumerate(toks) if names and t == names[-1]]
    if names and not any(names[0] in toks[max(0, i - 3):i + 1] for i in last): return f"it never says '{' '.join(names).title()}'"
    words = split(fact); low = [w.lower() for w in words]; nums, ones, proper, main = set(), set(), set(), set()
    for i, (w, l) in enumerate(zip(words, low)):
        if w.isdigit():
            by_month = any(x in MONTHS for x in low[max(0, i - 1):i + 2])
            (nums if len(w) > 1 or by_month else ones).add(w)
        elif l in names or l in STOP: continue
        elif i and w[0].isupper() and l not in MONTHS: proper.add(l)
        elif len(l) > 3 or l in MONTHS: main.add(l[:5])
    absent = sorted((nums | proper) - set(toks))
    if absent: return f"it never says {', '.join(absent)}"
    cut = [t[:5] if t.isalpha() else t for t in toks]; need = math.ceil(len(main) / 2)
    start = nums or proper or main
    for i, t in enumerate(toks):
        if t in start or (start is main and cut[i] in main):
            a, b = max(0, i - NEAR), i + NEAR + 1; near = set(toks[a:b])
            if nums | proper <= near and all(o in near or SPELLED[o] in near for o in ones) and len(main & set(cut[a:b])) >= need: return None
    return f"it does not say these together: {', '.join(sorted(nums | ones | proper) + sorted(l for l in low if l[:5] in main))}"

CLOSED = (401, 403, 404, 410, 451)
def problem(fact, urls, who):
    """(why, try again?) when a page does not back the fact, or None."""
    if len(urls) < 2 or urls[0] == urls[1]: return "it needs two different pages", False
    for u in urls[:2]:
        try: why, again = missing(fact, page(u), who), False
        except Exception as e:
            again = getattr(e, "code", None) not in CLOSED
            why = f"it did not open ({str(e)[:60]}). " + ("The network or the site failed" if again else "Use a page that does, such as Wikipedia or a news story")
        if why: return f"{u}: {why}", again

def key(fact, urls, who): return hashlib.sha1("|".join([who, fact.strip(), *urls[:2]]).encode()).hexdigest()

def done():
    try: return set(json.load(open(DONE, encoding="utf8")))
    except (OSError, ValueError): return set()

def passed(fact, urls, who):
    os.makedirs("out", exist_ok=True); d = done() | {key(fact, urls, who)}
    with open(DONE, "w", encoding="utf8") as f: json.dump(sorted(d), f)

def rows(story):
    """(line number, fact, urls) for each filled row of the Facts table. next.py, film.py drop and this script all count these."""
    ls = story.splitlines(); out = []
    head = next((i for i, l in enumerate(ls) if l.startswith("| # | Fact")), len(ls))
    for i in range(head + 1, len(ls)):
        if not ls[i].startswith("|"): break
        c = [x.strip() for x in ls[i].strip().strip("|").split("|")]
        if "http" in ls[i]: out.append((i, c[1] if len(c) > 1 and re.fullmatch(r"\W*\d*\W*", c[0]) else c[0], re.findall(r"https?://[^\s|]+", ls[i])))
    return out

def unchecked(story, who):
    d = done(); return [] if OFF else [r for r in rows(story) if key(r[1], r[2], who) not in d]

if __name__ == "__main__":
    who = str(json.load(open("film.json", encoding="utf8")).get("subject") or ""); story = open("story.md", encoding="utf8").read()
    todo = unchecked(story, who); drop, again = [], 0
    for at, r in enumerate(rows(story), 1):
        if r not in todo: continue
        bad = problem(r[1], r[2], who)
        print(f"{'OK' if not bad else 'NOT CHECKED' if bad[1] else 'NOT ON ITS PAGES'}: fact {at}: {r[1]}" + (f"\n  {bad[0]}" if bad else ""), flush=True)
        if not bad: passed(r[1], r[2], who)
        elif bad[1]: again += 1; print(f"  Still not open after two more tries? python3 scripts/film.py drop fact {at}, then add it with another page.")
        else: drop.append(at)
    for at in reversed(drop): print(f"FIX: python3 scripts/film.py drop fact {at}      # then add a fact you read on two pages")
    if again and not drop: print("FIX: python3 scripts/facts.py      # again, when the network works")
    if not drop and not again: print("OK: every fact is on its pages. Next: python3 scripts/next.py")
    sys.exit(1 if drop or again else 0)
