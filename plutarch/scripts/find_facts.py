#!/usr/bin/env python3
"""Find dated facts about the subject that are on two pages, and print the film.py fact command for each.

  python3 scripts/find_facts.py                  # reads the subject from film.json
  python3 scripts/find_facts.py https://en.wikipedia.org/wiki/NAME     # when the search finds another person

It reads the person's Wikipedia article, the pages that article links to and the pages a web search finds. It keeps a
sentence when the article and one of those pages both pass the check in facts.py, and that page does not copy the article.
It proves no claim: read the pages of the facts you use."""
import html.parser, json, os, re, shlex, subprocess, sys, threading, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import facts

FOUND, WANT, PAGES, ARCHIVED = "out/found.json", 12, 250, 12      # archive.org refuses a reader that opens many pages
SKIP = re.compile(r"//[^/]*(wiki|timeline|timepath|timetoast|memmie|preceden|humansofhistory|characterarc|biyografi|grokipedia|dbpedia|kiddle|newworldencyclopedia|infogalactic|alchetron|fandom|doi\.org|worldcat|jstor|viaf|isni|id\.loc\.gov|d-nb|toolforge|youtube|youtu\.be|twitter|"
                  r"facebook|instagram|books\.google)|//(www\.)?x\.com/|archive\.org/details|\.(pdf|jpe?g|png|gif|mp[34]|zip)($|\?)", re.I)
SAFE = re.compile(r"https?://[\w./:?&=%#~,;+@()'*-]+")          # a link goes into a shell command in double quotes: no $ ` \ or quote mark
YEAR = re.compile(r"\b(1\d|20)\d\d\b")
INTRO = re.compile(r"(In|On|By|After|At|During|As|From|While|When|Before|Following|To|Since|For|Despite|With|Upon|Through|Although|Because|According|Even|Though|If|Once|Until)\b")
VERB = re.compile(r"\b(is|was|were|has|had|became|began|won|lost|made|gave|got|ran|led|left|took|went|came|met|sold|bought|built|wrote|said|told|held|grew|fell|"
                  r"set|spent|taught|fought|rose|broke|beat|died|chose|found|kept|sang|drew|flew|put|paid|sent|spoke|thought|\w{2,}ed)\b")
END = re.compile(r"\b(a|an|the|and|or|of|in|on|at|to|for|with|as|by|from|his|her|their|its|he|she|they|it|who|which|that|was|were|is|had|one|than|into|first|"
                 r"be|been|being|about|about an? \w+|over|under|between|including|however|also|soon|then|shortly|v)\.$|\b(was|were|is) \w+ed\.$", re.I)

PLAIN = {0x2019: "'", 0x201c: '"', 0x201d: '"', 0x2013: "-", 0x2014: " ; "}      # curly quotes and dashes
# a sentence that needs the one before it. A pronoun is never swapped for the name: "He proposed to her" is not about her.
LEANS = re.compile(r"^((In|On|By|After|At|During|As|From|Since)\b[^,]*(, \d{4})?(, [^,]*)?, )?(he|she|it|they|this|these|that|those|his|her|their|its|the (duo|pair|couple|two|group|film|book|album|song))\b"
                   r"|\b(this|these|those|also|again|to her|to him|the same|the former|the latter)\b", re.I)

ODD = re.compile(r"^(A |An )?(first|second|third|another)\b|^[A-Z ,]{4,}[;:]|;|^\W|^As a result|:[.\"]*$| - who\b|^[^,]*, the year [^,]*$|^[^,]*, (photographed|pictured|seen|shown)\b", re.I)   # leans on the line before, or a news dateline
# "won her first title" is not "won her first title since 2017": a sentence with one of these is kept whole or not at all
RANK = re.compile(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\w+teenth|\w+tieth|\d+(st|nd|rd|th)|eleventh|twelfth|hundredth|best|worst|last|only|most|least|more|less|half|never|no|not|"
                  r"(?!(w|gu|prot|requ|inter|cont|hon|for|arr|pri|t|qu|harv|inv|sugg|mod|conqu|n|ch|dig|Budap|Ever)est\b)\w{2,}est)\b", re.I)
# Only these clauses may be cut off: where, when, with whom, or what else happened. Anything else may say who claims it.
TAIL = re.compile(r",? (at|on|from|with|for|after|before|when|where|while|during|because|\w+ing|and (was|had|won|became|led|made|took|went|began|\w+ed))\b")
# and none of them when it holds a doubt, a speaker or a turn
TURN = re.compile(r"\b(but|until|if|unless|never|not|only|yet|however|though|although|accord\w+|alleg\w*|report\w*|suppos\w*|possibl\w*|perhaps|maybe|likely|apparent\w*|claim\w*|disput\w+|den(y|ied|ies|ying)|doubt\w*|"
                  r"rumou?r\w*|belie\w+|argu\w+|suggest\w*|sa(y|ys|id|ying)|writ\w+|wrote|recall\w*|remember\w*|stat(ed|es|ing)|thought|think\w*|consider\w*|reject\w*|myth\w*|legend\w*|fals\w+|hoax\w*|historian\w*|"
                  r"biographer\w*|scholar\w*|research\w*|accounts?|sources?|t(ell|old|ells|elling)|not(ed|es|ing)|insist\w*|assum\w+|cit(ed|es|ing)|depend\w*|pending|excluding|except\w*|barring|fail\w*|might|may|could|would|"
                  r"debunk\w*|contest\w*|contradict\w*|question\w*|unproven|uncertain|dubious|citation needed|better source|failed verification|who\?|when\?)", re.I)
TITLE = {"And", "The"}

class Article(html.parser.HTMLParser):
    """The paragraphs, outside links and birth date of a Wikipedia page."""
    def __init__(self):
        super().__init__(); self.urls, self.paras, self.born = [], [], ""
        self.p, self.mute, self.bday = None, 0, False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls, url = a.get("class") or "", a.get("href") or ""
        if tag == "p": self.p = []
        elif tag in ("style", "script") or (tag == "sup" and (self.mute or "reference" in cls)): self.mute += 1
        elif tag == "span" and "bday" in cls: self.bday = True
        elif tag == "a" and url.startswith(("http://", "https://")): self.urls.append(url)
    def handle_endtag(self, tag):
        if tag == "p" and self.p is not None: self.paras.append("".join(self.p)); self.p = None
        elif tag in ("style", "script", "sup") and self.mute: self.mute -= 1
    def handle_data(self, d):
        if self.bday: self.born, self.bday = self.born or d.strip(), False
        if self.mute: return
        if self.p is not None: self.p.append(d)

def last_name(who):
    n = [x for x in facts.split(who) if x.lower() not in facts.SUFFIX]; return n[-1] if n else ""

def about(t, who):
    """False when every mention of the last name is a relative's: Albert Lewis, for C. S. Lewis."""
    last = last_name(who); own = set(facts.split(who)) | TITLE; ends = {x.lower() for x in facts.split(who)} & {"jr", "sr", "ii", "iii", "iv"}
    before = [m[1] for m in re.finditer(r"(?:([^\W\d_][\w'.-]*) )?\b" + re.escape(last) + r"\b(?:,? (Jr|Sr|II|III|IV)\b)?", facts.norm(t)) if not m[2] or m[2].lower() in ends]
    return any(not b or not b[0].isupper() or facts.split(b)[-1] in own or INTRO.match(b) or facts.split(b)[-1].lower() in facts.STOP for b in before)

def variants(t, last):
    """The sentence, then shorter forms of it that end at a clause. Never cut before a 'but' or a 'not': that could turn a fact around."""
    w = t.rstrip("."); out = [w]
    for m in reversed(list(re.finditer(r", | (?:after|when|while|where|during|because) | and (?=\w+ed )|; ", w))):
        if not TAIL.match(w[m.start():]) or TURN.search(re.sub(r"\b(May) (?=\d)", " ", w[m.start():])): continue
        v = w[:m.start()].strip(" ,;"); tail = v.rsplit(",", 1)[-1].strip()
        if INTRO.match(v) and ("," not in v or len(tail.split()) < 3 or re.search(r"^\w*( \w+)? ?\b(after|before|when|as)\b", tail) or INTRO.match(tail.capitalize())): continue
        v = re.sub(r",? (and|or)( \w+)?$", "", v)
        if not RANK.search(re.sub(r"\b" + re.escape(last) + r"\b", "", v)): out.append(v)
    out = [v + "." for v in dict.fromkeys(out)]
    return [v for v in out if 5 <= len(v.split()) <= 24 and YEAR.search(v) and last in facts.split(v) and VERB.search(v) and not END.search(v) and not ODD.search(v)
            and not re.search(r"[\"`$\\|<>\u2022\ufeff]|^[^,]+, (who|which|whose) [^,]+$", v)]

ABBR = re.compile(r"\b(vs?|[SDLM]t|Mrs?|Ms|[DJS]r|Rev|Gen|Gov|Sen|Rep|Col|Sgt|Capt|Prof|Inc|Co|Hon|No|Ft)\. ")

def died(art):
    """The year of death in the article's first lines, (December 5, 1901 - December 15, 1966), or 0."""
    m = re.search(art.born[:4] + r"\s*-\s[^()]{0,40}?(\d{4})\s*[);]", " ".join(art.paras[:6]).translate(PLAIN)) if art.born else None
    return int(m[1]) if m else 0

def sentences(art, who):
    last, out = last_name(who), []
    b = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", art.born)
    if b and 1 <= int(b[2]) <= 12: out.append(f"{who} was born on {facts.MONTHS[int(b[2]) - 1].title()} {int(b[3])}, {b[1]}.")
    for p in art.paras:
        p = re.sub(r"\([^()]*\)|\[[^\]]*\]", lambda m: " \x01 " if TURN.search(m[0]) else " ", p).translate(PLAIN)      # a bracket with a doubt in it marks its sentence
        p = re.sub(r"([.!?])\s*\x01", "\x01\\1", p)
        for s in re.split(r"(?<=[a-z0-9\"\x01 ][.!?])\s+(?=[A-Z])", ABBR.sub("\\1.\0", re.sub(r"\s+", " ", p))):
            s = s.replace("\0", " ")
            s = re.sub(r" ([.,;])", r"\1", s).strip()
            if "\x01" in s: continue
            if YEAR.search(s) and last in facts.split(s) and about(s, who) and len(s.split()) <= 45 and not LEANS.search(s) and not ODD.search(s): out.append(s)
    return out

def wiki_url(who):
    q = "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch=" + urllib.parse.quote(who)
    need = {n.lower() for n in facts.split(who) if n.lower() not in facts.SUFFIX and len(n) > 1}
    for r in sorted(json.loads(facts.fetch(q))["query"]["search"], key=lambda r: facts.plainly(r["title"]) != facts.plainly(who)):      # the exact title first
        if need <= {n.lower() for n in facts.split(r["title"])}: return "https://en.wikipedia.org/wiki/" + re.sub(r"\.$", "%2E", urllib.parse.quote(r["title"].replace(" ", "_")))

def alike(a, b):
    a, b = set(facts.plainly(a).split()), set(facts.plainly(b).split()); digits = lambda s: {w for w in s if w.isdigit()}
    return bool(digits(a) & digits(b)) and len(a & b) >= 0.7 * min(len(a), len(b))

def runs(sentence, n=8):
    w = facts.plainly(sentence).split(); return [" ".join(w[i:i + n]) for i in range(len(w) - n + 1)]

def copies(text, sents):
    """How many of the article's sentences this page repeats, eight words in a row. A copy of the article is not a second source."""
    t = facts.plainly(text); return {i for i, s in enumerate(sents) if any(r in t for r in runs(s))}

def searched(who):
    """Pages a web search finds, or none: a search engine is not needed."""
    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "find_audio.py"); out = []
    for q in (f"{who} biography", f"{who} life timeline"):
        try: out += facts.links(subprocess.run([sys.executable, tool, "web", q], capture_output=True, text=True, timeout=40).stdout)
        except (OSError, subprocess.TimeoutExpired): pass
    return out

def find(who, wiki):
    raw = facts.fetch(wiki); text = facts.plain(raw); art = Article(); art.feed(raw); last = last_name(who).lower()
    if facts.missing("", text, who).startswith("it never says '"): return None
    near = searched(who)
    urls = [u for u in dict.fromkeys(near + art.urls) if SAFE.fullmatch(u) and facts.links(u) == [u] and not SKIP.search(u) and not facts.same(u, wiki)]
    urls = sorted(urls, key=lambda u: (u not in near, last not in u.lower()))[:PAGES // 2] + urls          # pages named after the person first, then the article's order
    urls = list(dict.fromkeys(urls)); old = [u for u in urls if "//web.archive.org/" in u]; late = set(old[ARCHIVED:])
    urls = [u for u in urls if u not in late][:PAGES]; pages, gate, stop = {}, threading.Semaphore(2), time.time() + 75
    def one(u):
        if u not in old: return get(u)
        with gate: get(u)
    def get(u):
        if time.time() > stop: return
        try: h = facts.fetch(u, 10); t = facts.plain(h)
        except Exception: return
        if not facts.missing("", t, who).startswith("it never says '"): pages[u] = (t, set(re.findall(r"\d+", t)), h)
    with ThreadPoolExecutor(24) as ex: list(ex.map(one, urls))
    sents = sentences(art, who); same = {u: copies(t, sents) for u, (t, _, _) in pages.items()}
    urls = sorted((u for u in urls if u in pages and len(same[u]) < 3), key=lambda u: u in near)     # the article's own sources first
    got, end, over = [], time.time() + 60, died(art) or 9999
    def keep(sent, on):
        for v in variants(sent, last_name(who)):
            if not about(v, who) or any(alike(v, g[0]) for g in got) or facts.missing(v, text, who): continue
            nums = {n for n in re.findall(r"\d+", v) if len(n) == 4}
            if YEAR.search(v) and int(YEAR.search(v)[0]) > over: continue                  # "In 2006, Disney acquired Pixar" is the company
            u = next((u for u in on if nums <= pages[u][1] and not facts.missing(v, pages[u][0], who)), None)
            if u: got.append([v, wiki, u]); return
    for i, s in enumerate(sents):
        if time.time() < end: keep(s, [u for u in urls if i not in same[u]])
    for u in urls[::-1] if len(got) < WANT else []:           # then the other pages' own sentences, the biographies a search found first
        one_page = Article()
        try: one_page.feed(pages[u][2])
        except Exception: continue
        for s in sentences(one_page, who):
            if time.time() < end and len(got) < WANT and not copies(text, [s]): keep(s, [u])
    if len(got) > WANT: got = [got[i * len(got) // WANT] for i in range(WANT)]             # spread over the whole life
    return got

def main():
    try: who = str(json.load(open("film.json", encoding="utf8")).get("subject") or "")
    except (OSError, ValueError): who = ""
    if who in (who.lower(), who.upper()): who = who.title()
    if not who or "<<" in who: print('ERROR: film.json has no subject yet.\nFIX: python3 scripts/film.py set subject "the person\'s name"'); sys.exit(1)
    search = f'python3 scripts/find_audio.py web "{who} biography"'; given = sys.argv[1] if len(sys.argv) > 1 else ""
    try: saved = json.load(open(FOUND, encoding="utf8"))
    except (OSError, ValueError): saved = {}
    if given and not SAFE.fullmatch(given): print("ERROR: give a Wikipedia address, or nothing.\nFIX: python3 scripts/find_facts.py"); sys.exit(1)
    if saved.get("who") == who and given in ("", saved.get("wiki")) and len(saved["facts"]) >= 5: got, wiki = saved["facts"], saved["wiki"]
    else:
        print("Reading the Wikipedia article and the pages it links to (about a minute) ...", flush=True)
        try:
            wiki = given or (saved.get("who") == who and saved.get("given")) or wiki_url(who)
            got = find(who, wiki) if wiki else None
        except Exception as e: print(f"ERROR: the search failed ({str(e)[:60]}).\nFIX: run it again when the network works, or search: {search}"); sys.exit(1)
        if got is None: print(f"ERROR: no Wikipedia page for {who!r}.\nFIX: search instead: {search}"); sys.exit(1)
        os.makedirs("out", exist_ok=True); json.dump({"who": who, "wiki": wiki, "given": wiki if given or wiki == saved.get("given") else "", "facts": got}, open(FOUND, "w", encoding="utf8"))
    try: have = {facts.plainly(t) for _, t, _ in facts.rows(open("story.md", encoding="utf8").read())}
    except OSError: have = set()
    new = [g for g in got if facts.plainly(g[0]) not in have and not re.search(r'["`$\\\n]', g[0]) and SAFE.fullmatch(g[1]) and SAFE.fullmatch(g[2])]
    print(f"From {wiki} and pages about the same person. If that is another person with this name, do not use these.")
    if not new: print(f"No {'more ' if got else ''}facts here are on two pages.\nNEXT: {search}"); sys.exit(0 if got else 1)
    print(f"OK: {len(new)} facts, each on two pages. Run the lines that tell the story, 5 in all, exactly as printed:")
    home = shlex.quote(os.getcwd())
    for t, a, b in new: print(f'  cd {home} && python3 scripts/film.py fact "{t}" "{a}" "{b}"')
    if len(new) + len(have) < 5: print(f"You need 5. For more: {search}")

if __name__ == "__main__": main()
