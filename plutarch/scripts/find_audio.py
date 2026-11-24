#!/usr/bin/env python3
"""Find and download real audio of your subject. Every command prints plain lines you can copy from.

  python3 scripts/find_audio.py web "<full name> interview podcast"        # general web search
  python3 scripts/find_audio.py podcast "<full name>"                      # podcast episodes with them -> a get line each
  python3 scripts/find_audio.py podcast "<show name>" --shows              # find a show -> its feed URL
  python3 scripts/find_audio.py episodes <feed-url> --grep "<guest>"       # list a show's episodes -> audio URLs
  python3 scripts/find_audio.py yt "<full name> commencement speech" -n 8  # YouTube search (id, title, minutes)
  python3 scripts/find_audio.py subs <video-url>                           # captions ONLY -> tx/<id>.json (search before you download)
  python3 scripts/find_audio.py archive "<full name>"                      # Internet Archive audio/video
  python3 scripts/find_audio.py get <url> --name interview                 # download -> src/interview.<ext>
  python3 scripts/find_audio.py get <url> --name speech --start 600 --end 780   # only that part (seconds)

`get` works for podcast mp3 links, YouTube, X/Twitter posts, archive.org and most video pages (it uses yt-dlp)."""
import sys, os, argparse, json, re, subprocess, urllib.request, urllib.parse, shlex
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

UA = {"User-Agent": "Mozilla/5.0 (plutarch kit)"}
def http(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()

def cmd_web(a):
    q = a.query; rows = []
    try:
        if os.environ.get("SEARXNG_URL"):
            d = json.loads(http(os.environ["SEARXNG_URL"].rstrip("/") + "/search?format=json&q=" + urllib.parse.quote(q)))
            rows = [(r.get("title", ""), r.get("url", ""), r.get("content", "")) for r in d.get("results", [])]
        elif os.environ.get("BRAVE_API_KEY"):
            d = json.loads(http("https://api.search.brave.com/res/v1/web/search?q=" + urllib.parse.quote(q),
                                {"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"}))
            rows = [(r.get("title", ""), r.get("url", ""), r.get("description", "")) for r in d.get("web", {}).get("results", [])]
        else:
            try: from ddgs import DDGS
            except ImportError: die("no search engine set up. Do ONE of: export SEARXNG_URL=http://your-searxng:8080 | export BRAVE_API_KEY=... | pip install ddgs")
            rows = [(r.get("title", ""), r.get("href", ""), r.get("body", "")) for r in DDGS().text(q, max_results=a.n)]
    except Exception as e:
        die(f"web search failed: {e}. If you have a web-search tool in your agent, use that instead.")
    for t, u, s in rows[:a.n]: print(f"{t[:80]} | {u}\n    {re.sub(r'<[^>]+>', '', s)[:160]}")
    print(f"\n{len(rows[:a.n])} results. Open the best pages and look for: a podcast episode, a talk, or posts with video.")

def slug(s): return "-".join(re.findall(r"[a-z0-9]+", s.lower())[:3]) or "episode"   # first 3 words of the show name

def cmd_podcast(a):
    q = urllib.parse.quote(a.name)
    if a.shows:
        d = json.loads(http(f"https://itunes.apple.com/search?media=podcast&entity=podcast&limit={a.n}&term={q}"))
        for r in d.get("results", []): print(f"{r.get('collectionName', '')[:60]} | {r.get('artistName', '')[:30]} | {r.get('feedUrl', '')}")
        print("\nNext: python3 scripts/find_audio.py episodes <feed-url> --grep \"<guest or topic>\"")
        return
    d = json.loads(http(f"https://itunes.apple.com/search?media=podcast&entity=podcastEpisode&limit={a.n}&term={q}"))
    rows = [r for r in d.get("results", []) if r.get("episodeUrl")]
    if not rows:
        print(f"0 podcast episodes found for {a.name!r}.\nFIX: try python3 scripts/find_audio.py archive {shlex.quote(a.name)}"); return
    mins = lambda r: round((r.get("trackTimeMillis") or 0) / 60000)
    rows.sort(key=lambda r: not 5 <= mins(r) <= 75)              # keeps search order; episodes of 5-75 min first
    used = {os.path.splitext(f)[0] for f in os.listdir("src")} if os.path.isdir("src") else set()
    for r in rows:
        show, year = r.get("collectionName", "").strip(), (r.get("releaseDate") or "")[:4]
        name = slug(show); k = 2
        while name in used: name = f"{slug(show)}-{k}"; k += 1
        used.add(name)
        print(f"{(r.get('releaseDate') or '')[:10]} | {mins(r)} min | {show[:32]} | {r.get('trackName', '')[:70]}")
        print(f"  python3 scripts/find_audio.py get {shlex.quote(r['episodeUrl'])} --name {name} --credit {shlex.quote(f'{show} ({year})')}")
    print(f"\n{len(rows)} episodes. Pick one where {a.name} is the guest, under 75 minutes if you can "
          "(transcribing takes about 1 minute per 10 minutes of audio).\nNext: run that episode's find_audio.py get line.")

def cmd_episodes(a):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(http(a.feed, timeout=60))
    n = 0; items = list(root.iter("item"))
    for it in items:
        title = (it.findtext("title") or "").strip()
        desc = it.findtext("description") or ""
        if a.grep and a.grep.lower() not in (title + " " + desc).lower(): continue
        enc = it.find("enclosure"); url = enc.get("url") if enc is not None else ""
        dur = it.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}duration") or ""
        tr = it.find("{https://podcastindex.org/namespace/1.0}transcript")
        print(f"{(it.findtext('pubDate') or '')[5:16]} | {title[:70]} | {dur} | {url}" + (f"\n    transcript: {tr.get('url')}" if tr is not None else ""))
        n += 1
        if n >= a.n: break
    if n == 0:
        why = f"none of its {len(items)} episodes mention {a.grep!r}" if a.grep and items else "this feed lists no episodes"
        print(f"0 episodes: {why}. Running this feed again finds the same.\n"
              f"FIX: pick a different show from: python3 scripts/find_audio.py podcast NAME   (or try: python3 scripts/find_audio.py archive NAME)")
        return
    print(f"\n{n} episodes. Next: python3 scripts/find_audio.py get \"<audio url>\" --name <short-name>")

def ytdlp(args):
    extra = shlex.split(os.environ.get("YTDLP_ARGS", ""))          # e.g. YTDLP_ARGS="--cookies-from-browser firefox"
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-warnings"] + extra + args, capture_output=True, text=True)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["unknown error"]
        hint = ""
        if "Sign in" in msg[0] or "bot" in msg[0]:
            hint = " YouTube is blocking this machine. Use a podcast, X or archive.org copy of the same talk instead. Only if the user told you to use their logged-in browser: export YTDLP_ARGS=\"--cookies-from-browser firefox\""
        die("yt-dlp: " + msg[0][:200] + hint)
    return r.stdout

def cmd_yt(a):
    out = ytdlp([f"ytsearch{a.n}:{a.query}", "--flat-playlist", "--print", "%(id)s | %(title).70s | %(duration)s s | %(channel)s"])
    print(out.strip()); print("\nNext: python3 scripts/find_audio.py subs https://www.youtube.com/watch?v=<id>   (captions first, cheap)")

def cmd_subs(a):
    os.makedirs("tx", exist_ok=True)
    vid = ytdlp(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,en", "--sub-format", "json3",
                 "-o", "tx/%(id)s.%(ext)s", "--print", "after_video:%(id)s", a.url]).strip().splitlines()[-1]
    files = [f for f in os.listdir("tx") if f.startswith(vid + ".") and f.endswith(".json3")]
    if not files: die("this video has no English captions. Download it with `get` and run transcribe.py instead.")
    ev = load_json("tx/" + sorted(files)[0]).get("events", [])
    segs = []
    for e in ev:
        txt = "".join(s.get("utf8", "") for s in e.get("segs", [])).replace("\n", " ").strip()
        if txt: segs.append({"s": e.get("tStartMs", 0) / 1000, "e": (e.get("tStartMs", 0) + e.get("dDurationMs", 0)) / 1000, "text": txt})
    save_json(f"tx/{vid}.json", {"file": a.url, "segments": segs})
    print(f"OK tx/{vid}.json ({len(segs)} caption lines). Search it: python3 scripts/clip.py find tx/{vid}.json \"phrase\"\n"
          f"Captions are only for FINDING the moment. Then download that part with get --start/--end and cut with clip.py make.")

def cmd_archive(a):
    q = urllib.parse.quote(f"({a.query}) AND mediatype:(audio OR movies)")
    d = json.loads(http(f"https://archive.org/advancedsearch.php?q={q}&fl[]=identifier&fl[]=title&fl[]=year&rows={a.n}&output=json"))
    for r in d["response"]["docs"]: print(f"{str(r.get('title', ''))[:70]} | {r.get('year', '')} | https://archive.org/details/{r['identifier']}")

def cmd_get(a):
    os.makedirs("src", exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]", "", a.name) or "source"
    path = None
    if re.search(r"\.(mp3|m4a|wav|ogg|flac|aac)(\?|$)", a.url, re.I) and a.start is None:
        ext = re.search(r"\.(mp3|m4a|wav|ogg|flac|aac)(\?|$)", a.url, re.I).group(1).lower()
        path = f"src/{name}.{ext}"
        with open(path, "wb") as f: f.write(http(a.url, timeout=600))
    else:
        args = ["-f", "ba/b", "-o", f"src/{name}.%(ext)s", "--print", "after_move:filepath"]
        if a.start is not None: args += ["--download-sections", f"*{a.start}-{a.end if a.end is not None else 'inf'}"]
        path = ytdlp(args + [a.url]).strip().splitlines()[-1]
        path = os.path.relpath(path)
    if a.start is not None and not a.url.lower().startswith("http"): pass
    d = duration(path)
    credit = shlex.quote(a.credit) if a.credit else "\"SHOW (YEAR)\""
    cmd = f"python3 scripts/film.py source {name} {shlex.quote(path)} {credit} {shlex.quote(a.url)}"
    print(f"OK {path}  ({d/60:.1f} min)\n" + ("Record it:" if a.credit else "Record it (write the show or event name and its year in place of SHOW (YEAR)):") + f"\n  {cmd}"
          + (f"\nNOTE: you downloaded only {a.start}-{a.end} s, so times in this file start at 0, not at {a.start}." if a.start is not None else "")
          + "\nNext: python3 scripts/next.py")

ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("web"); p.add_argument("query"); p.add_argument("-n", type=int, default=8); p.set_defaults(fn=cmd_web)
p = sub.add_parser("podcast"); p.add_argument("name"); p.add_argument("--shows", action="store_true"); p.add_argument("-n", type=int, default=10); p.set_defaults(fn=cmd_podcast)
p = sub.add_parser("episodes"); p.add_argument("feed"); p.add_argument("--grep"); p.add_argument("-n", type=int, default=15); p.set_defaults(fn=cmd_episodes)
p = sub.add_parser("yt"); p.add_argument("query"); p.add_argument("-n", type=int, default=8); p.set_defaults(fn=cmd_yt)
p = sub.add_parser("subs"); p.add_argument("url"); p.set_defaults(fn=cmd_subs)
p = sub.add_parser("archive"); p.add_argument("query"); p.add_argument("-n", type=int, default=10); p.set_defaults(fn=cmd_archive)
p = sub.add_parser("get"); p.add_argument("url"); p.add_argument("--name", required=True); p.add_argument("--start", type=float); p.add_argument("--end", type=float); p.add_argument("--credit"); p.set_defaults(fn=cmd_get)
a = ap.parse_args(); a.fn(a)
