"""find_audio.py podcast finds episodes with the person and prints get lines that need no editing.

LFM2.5-24B (2026-11-24) spent 35 minutes at step 3: podcast "Tim Tebow" searched show names and
returned one fantasy football show that never had him on."""
import ast, json, os, re, shlex, sys, tempfile, types, unittest, urllib.parse
from contextlib import redirect_stdout
from io import StringIO

KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plutarch", "scripts")
SRC = os.path.join(KIT, "find_audio.py")
REPLY = {"results": [
    {"collectionName": "The Long Show", "trackName": "Tim Tebow, 3 hours", "releaseDate": "2025-05-12T00:00:00Z",
     "trackTimeMillis": 207 * 60000, "episodeUrl": "https://a.test/long.mp3"},
    {"collectionName": "Passion + Purpose Podcast", "trackName": "Tim Tebow on Finding His Calling", "releaseDate": "2026-04-27T00:00:00Z",
     "trackTimeMillis": 39 * 60000, "episodeUrl": "https://a.test/p.mp3?aid=rss&x=1"},
    {"collectionName": "No Audio", "trackName": "x", "releaseDate": "2020-01-01"}]}


def load(*names, **env):
    tree = ast.parse(open(SRC).read())
    ns = dict(json=json, os=os, re=re, shlex=shlex, urllib=urllib, **env)
    for n in names:
        exec(compile(ast.Module([next(f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == n)], []), SRC, "exec"), ns)
    return ns


class Podcast(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd(); self.tmp = tempfile.mkdtemp(); os.chdir(self.tmp)
    def tearDown(self): os.chdir(self.cwd)

    def run_fn(self, ns, fn, **args):
        out = StringIO()
        with redirect_stdout(out): ns[fn](types.SimpleNamespace(**args))
        return out.getvalue()

    def test_episodes_come_with_runnable_get_lines(self):
        urls = []
        ns = load("slug", "cmd_podcast", http=lambda u, **k: (urls.append(u), json.dumps(REPLY).encode())[1])
        out = self.run_fn(ns, "cmd_podcast", name="Tim Tebow", shows=False, n=10, long=False)
        self.assertIn("entity=podcastEpisode", urls[0])
        gets = [l.strip() for l in out.splitlines() if "find_audio.py get" in l and l.startswith("  ")]
        self.assertEqual(len(gets), 1, out)                                  # no audio URL: skipped; 207 minutes: hidden
        self.assertIn("1 episode(s) over 90 minutes hidden (add --long", out)
        out = self.run_fn(ns, "cmd_podcast", name="Tim Tebow", shows=False, n=10, long=True)
        gets = [l.strip() for l in out.splitlines() if "find_audio.py get" in l and l.startswith("  ")]
        self.assertEqual(len(gets), 2, out)
        self.assertIn("--name passion-purpose-podcast ", gets[0])                       # the 39-minute episode comes before the 207-minute one
        argv = shlex.split(gets[0])
        self.assertEqual(argv[argv.index("--credit") + 1], "Passion + Purpose Podcast (2026)")
        self.assertEqual(argv[3], "https://a.test/p.mp3?aid=rss&x=1")
        self.assertNotRegex(out, r"FEED_URL|AUDIO_URL|<")

    def test_get_with_credit_prints_a_complete_source_command(self):
        ns = load("cmd_get", http=lambda u, **k: b"x", duration=lambda p: 2340.0, ytdlp=None)
        out = self.run_fn(ns, "cmd_get", url="https://a.test/p.mp3", name="passion", start=None, end=None, credit="Passion + Purpose Podcast (2026)")
        cmd = next(l.strip() for l in out.splitlines() if "film.py source" in l)
        self.assertEqual(shlex.split(cmd)[3:], ["passion", "src/passion.mp3", "Passion + Purpose Podcast (2026)", "https://a.test/p.mp3"])
        self.assertNotIn("SHOW (YEAR)", out)

    def test_no_year_means_no_credit(self):
        """A credit like "Show ()" would reach the screen; without a year get asks for SHOW (YEAR) instead."""
        reply = {"results": [{"collectionName": "Undated", "trackName": "x", "trackTimeMillis": 600000, "episodeUrl": "https://a.test/u.mp3"}]}
        ns = load("slug", "cmd_podcast", http=lambda u, **k: json.dumps(reply).encode())
        out = self.run_fn(ns, "cmd_podcast", name="Tim Tebow", shows=False, n=10, long=False)
        self.assertIn("get https://a.test/u.mp3 --name undated\n", out); self.assertNotIn("--credit", out)

    def test_nothing_found_points_at_archive(self):
        ns = load("slug", "cmd_podcast", http=lambda u, **k: b'{"results": []}')
        self.assertIn("FIX: try python3 scripts/find_audio.py archive 'Nobody Known'",
                      self.run_fn(ns, "cmd_podcast", name="Nobody Known", shows=False, n=10, long=False))


if __name__ == "__main__":
    unittest.main()
