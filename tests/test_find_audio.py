"""find_audio.py says what to do when a feed has nothing to offer.

qwen3:4b (2026-11-24) ran episodes on a 3-episode fantasy football feed 15 times; each run printed
"0 episodes" and a get hint, never that the show was the wrong one."""
import os, subprocess, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>Fantasy</title>
<item><title>Episode 1 - Auction</title><description>draft talk</description><enclosure url="https://x.test/1.m4a"/></item>
<item><title>Episode 2 - Keepers</title><description>keepers</description><enclosure url="https://x.test/2.m4a"/></item>
</channel></rss>"""


class FindAudio(Project):
    def episodes(self, *extra):
        p = os.path.join(self.tmp, "feed.xml"); open(p, "w").write(FEED)
        env = dict(os.environ, PYTHONPATH=self.stubs)
        r = subprocess.run([sys.executable, os.path.join(KIT, "find_audio.py"), "episodes", "file://" + p, *extra],
                           cwd=self.proj, env=env, capture_output=True, text=True)
        return r.stdout + r.stderr

    def test_no_match_says_pick_another_show(self):
        out = self.episodes("--grep", "Tebow")
        self.assertIn("none of its 2 episodes mention 'Tebow'", out)
        self.assertIn("pick a different show", out); self.assertNotIn("Next:", out)

    def test_matches_still_list_and_hint_get(self):
        out = self.episodes("--grep", "keepers")
        self.assertIn("Episode 2 - Keepers", out); self.assertIn("1 episodes. Next:", out)


if __name__ == "__main__":
    unittest.main()
