"""film.py edits film.json and story.md so that next.py moves forward, and it refuses bad input.

Runs with the standard library only:  python3 -m unittest discover tests"""
import json, os, re, shlex, subprocess, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project

FILM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plutarch", "scripts", "film.py")


class FilmPy(Project):
    def film_py(self, *args, ok=True):
        r = subprocess.run([sys.executable, FILM, *args], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0 if ok else 1, r.stdout + r.stderr)
        return r.stdout

    def data(self):
        return json.load(open(os.path.join(self.proj, "film.json")))

    def test_story_commands_pass_step_2(self):
        self.film_py("set", "subject", "Abraham Lincoln")
        self.film_py("sentence", "He rose from a log cabin, lost often, and then led the nation.")
        for i in range(1, 6): self.film_py("fact", f"Fact {i} in 1860", f"https://a.test/{i}", f"https://b.test/{i}")
        story = open(os.path.join(self.proj, "story.md")).read()
        self.assertNotIn("| 1 | | | |", story)                      # the empty template row is gone
        self.assertIn("| 5 | Fact 5 in 1860 |", story)
        self.assertIn("STEP 3 of 12", self.run_next())

    def test_the_same_fact_is_refused(self):
        """LFM2.5-24B (2026-11-24) added one fact three times to reach five rows."""
        self.film_py("set", "subject", "Abraham Lincoln")
        self.film_py("fact", "He won in 1860.", "https://a.test/1", "https://b.test/1")
        out = self.film_py("fact", "He  won in 1860", "https://a.test/2", "https://b.test/2", ok=False)
        self.assertIn("this is already fact 1", out)
        self.film_py("fact", "He won in 1864.", "https://a.test/1", "https://b.test/1")
        self.assertEqual(open(os.path.join(self.proj, "story.md")).read().lower().count("won in 186"), 2)

    def test_the_same_scene_is_refused(self):
        """qwen3:4b (2026-11-24) added one scene about seven times."""
        self.ready_for_clips()
        self.film_py("clip", "c1", "interview", "1", "3", "hello there", "1860", "x")
        self.film_py("set", "title", "the long road"); self.film_py("scenes", "clear")
        add = ("scene", "add", "card", "--heading", "1860", "--say", "He won.", "--clip", "c1")
        self.film_py("scene", "add", "title"); self.film_py(*add)
        out = self.film_py(*add, ok=False)
        self.assertIn("scene 2 already plays", out); self.assertIn("film.py drop scene 2", out)
        self.assertEqual(len(self.data()["scenes"]), 2)
        self.film_py("scene", "add", "card", "--heading", "1861", "--say", "He left.")   # new items are fine
        self.film_py("scene", "add", "card", "--heading", "1862"); self.film_py("scene", "add", "card", "--heading", "1863")
        self.film_py("drop", "scene", "2"); self.film_py(*add)

    def test_help_prints_usage_and_in_out_points_at_find(self):
        out = self.film_py("clip", "--help")                       # a small model asked for help and got an ERROR
        self.assertIn("film.py clip start interview 560.9 562.3", out)
        self.assertNotIn("ERROR", out)
        out = self.film_py("clip", "start", "interview", "IN", "OUT", "words", "2010", "about", ok=False)
        self.assertIn('printed after "in": and "out":', out)

    def test_refuses_bad_input(self):
        self.film_py("fact", "x", "https://a.test", "https://a.test", ok=False)        # same URL twice
        self.film_py("fact", "x", "a.test", "https://b.test", ok=False)                # not a URL
        self.film_py("set", "accent", "red", ok=False)
        self.film_py("set", "title", "THIS TITLE IS FAR TOO LONG", ok=False)
        self.film_py("scene", "add", "card", "--line", "up to 7 words", ok=False)     # example text from next.py
        self.film_py("sentence", "He rose from ___, it cost him ___, and then ___.", ok=False)
        open(os.path.join(self.proj, "src", "a.mp3"), "wb").close()
        self.film_py("source", "a", "src/a.mp3", "SHOW (YEAR)", "https://x.test", ok=False)
        self.film_py("source", "a", "src/a.mp3", "Some show", "https://x.test", ok=False)   # no year
        self.film_py("source", "b", "src/missing.mp3", "Show (2019)", "https://x.test", ok=False)
        self.film_py("source", "a", "src/a.mp3", "Show (2019)", "https://x.test")
        self.film_py("clip", "k", "a", "10", "45", "words", "2019", "about", ok=False)  # 35 s is not one quote
        self.film_py("clip", "k", "nosuch", "10", "12", "words", "2019", "about", ok=False)
        self.film_py("clip", "k", "a", "12", "10", "words", "2019", "about", ok=False)
        self.assertEqual(list(self.data()["sources"]), ["a"])        # the template sources are gone

    def test_invalid_json_is_reported_not_overwritten(self):
        p = os.path.join(self.proj, "film.json"); open(p, "w").write('{"subject": "A" "title": 1}')
        self.assertIn("not valid JSON", self.film_py("set", "subject", "B", ok=False))
        self.assertEqual(open(p).read(), '{"subject": "A" "title": 1}')

    def test_scenes_keep_the_end_card_last(self):
        self.ready_for_clips()
        self.film_py("clip", "c1", "interview", "1", "3", "hello there", "1860", "x")
        self.film_py("set", "title", "the long road")
        self.film_py("scenes", "clear")
        self.film_py("scene", "add", "title")
        self.film_py("scene", "add", "end", "--accent-text", "HE KEPT GOING.")
        self.film_py("scene", "add", "card", "--heading", "1860", "--say", "He won.", "--clip", "c1", "--big")
        self.film_py("scene", "add", "card", "--heading", "1859", "--at", "2")
        sc = self.data()["scenes"]
        self.assertEqual([s["type"] for s in sc], ["title", "card", "card", "end"])
        self.assertEqual(sc[1]["heading"], "1859")
        self.assertEqual(sc[2]["items"], [{"say": "He won."}, {"clip": "c1", "big": True}])
        self.assertEqual(sc[0]["text"], "THE LONG ROAD.")
        self.film_py("drop", "clip", "c1")
        self.assertEqual(self.data()["scenes"][2]["items"], [{"say": "He won."}])   # no dangling clip left behind

    def test_next_py_commands_reach_the_narrator(self):
        """Run what next.py prints at steps 5 and 7, with the example text filled in, and land on step 8."""
        self.ready_for_clips()
        out = self.run_next()
        clip_cmd = next(c for c in self.commands(out) if "film.py clip" in c)
        self.assertIn("&& python3 scripts/film.py clip start interview", clip_cmd)
        for i in range(6):
            src = "interview" if i % 2 else "speech"
            self.film_py("clip", f"c{i}", src, str(10 * i), str(10 * i + 3), f"words {i}", str(1860 + i), "about")
        for k, c in self.data()["clips"].items():          # stand in for clip.py make (old-kit format, no spec)
            with open(os.path.join(self.proj, "clips", k + ".json"), "w") as f:
                json.dump({"id": k, "wanted": c["text"], "in_exact": c["in"], "out_exact": c["out"], "live": False, "verified": "asr"}, f)
        out = self.run_next()
        self.assertIn("STEP 7 of 12", out)
        fill = {"TWO WORDS.": "THE LONG ROAD.", "2-3 WORDS.": "HE KEPT GOING.", "up to 7 words": "A real line",
                "One fact from story.md, max 16 words.": "He was elected in 1860.", "DATE": "1860"}
        for c in self.commands(out):
            if "film.py" not in c: continue
            self.assertTrue(c.startswith("cd "), c)                   # works in a shell that forgets cd
            for k, v in fill.items(): c = c.replace(f'"{k}"', shlex.quote(v))
            r = subprocess.run(["bash", "-c", c], cwd=self.tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, c + "\n" + r.stdout + r.stderr)
        self.assertIn("STEP 8 of 12: record the narrator", self.run_next())
        types = [s["type"] for s in self.data()["scenes"]]
        self.assertEqual((types[0], types[-1], types.count("card")), ("title", "end", 6))

    def ready_for_scenes(self, clips):
        self.ready_for_clips()
        for k, (yr, about) in clips.items():
            self.film_py("clip", k, "interview" if k != "s" else "speech", "1", "3", f"words {k}", str(yr), about)
        for k, c in self.data()["clips"].items():
            with open(os.path.join(self.proj, "clips", k + ".json"), "w") as f:
                json.dump({"id": k, "wanted": c["text"], "in_exact": c["in"], "out_exact": c["out"], "live": False, "verified": "asr"}, f)

    def test_scene_list_does_not_date_quotes_by_when_they_were_said(self):
        """A 2020 podcast about a 2007 game: the card is not headed 2020 and keeps the order the agent chose."""
        self.ready_for_scenes({"game": (2020, "the 2007 game"), "early": (2008, "his first season"), "a": (2019, "x"),
                               "b": (2019, "x"), "c": (2019, "x"), "s": (2019, "x")})
        cards = [c for c in self.commands(self.run_next()) if "scene add card" in c]
        self.assertNotIn('"2020"', " ".join(cards))
        self.assertIn("--clip game", cards[0])                 # order as added, not sorted by recording year
        self.assertIn("the 2007 game", cards[0])

    def test_leftover_placeholder_never_clears_real_scenes(self):
        self.ready_for_scenes({k: (1860, "x") for k in ("a", "b", "c", "d", "e", "s")})
        self.film_py("set", "title", "THE LONG ROAD."); self.film_py("set", "accent", "#B22234")
        self.film_py("scenes", "clear"); self.film_py("scene", "add", "title")
        self.film_py("scene", "add", "card", "--heading", "1860", "--clip", "a")
        self.film_py("scene", "add", "end", "--accent-text", "HE KEPT GOING.")
        self.film(narrator={"engine": "kokoro", "voice": "<<pick a voice>>"})
        out = self.run_next()
        self.assertIn("narrator.voice", out); self.assertNotIn("scenes clear", out)

    def test_source_in_use_is_not_dropped(self):
        self.ready_for_scenes({"a": (1860, "x")})
        self.assertIn("drop clip a", self.film_py("drop", "source", "interview", ok=False))
        self.film_py("drop", "clip", "a"); self.film_py("drop", "source", "interview")
        self.assertNotIn("interview", self.data()["sources"])

    def test_step_5_placeholders_are_refused(self):
        """The <...> placeholders in step 5 of references/steps.md, copied verbatim, change nothing."""
        skill = open(os.path.join(os.path.dirname(FILM), "..", "references", "steps.md")).read()
        step5 = skill[skill.index("### 5. Write the scenes"):]
        lines = [l for l in step5[:step5.index("### 6")].splitlines() if l.startswith("python3 scripts/film.py") and "<" in l]
        self.assertGreaterEqual(len(lines), 4)
        before = open(os.path.join(self.proj, "film.json")).read()
        for l in lines: self.film_py(*shlex.split(l)[2:], ok=False)
        self.assertEqual(open(os.path.join(self.proj, "film.json")).read(), before)

    def test_new_title_reaches_the_title_and_end_cards(self):
        self.film_py("set", "subject", "Abraham Lincoln"); self.film_py("set", "title", "THE LONG ROAD.")
        self.film_py("scenes", "clear"); self.film_py("scene", "add", "title")
        self.film_py("scene", "add", "end", "--accent-text", "HE KEPT GOING.")
        self.film_py("set", "title", "ROAD."); self.film_py("set", "subject", "Abe Lincoln")
        sc = self.data()["scenes"]
        self.assertEqual((sc[0]["text"], sc[1]["text"], sc[0]["sub"][0]), ("ROAD.", "ROAD.", "ABE LINCOLN"))

    def test_clip_flags_change_without_retyping(self):
        self.ready_for_scenes({"a": (1860, "x")})
        self.film_py("clip", "a", "--live", "--isolate")
        self.film_py("clip", "a", "interview", "1", "3", "new words", "1860", "x")      # retyped: flags kept
        c = self.data()["clips"]["a"]; self.assertEqual((c["live"], c["isolate"], c["text"]), (True, True, "new words"))
        self.film_py("clip", "a", "--no-live"); self.assertFalse(self.data()["clips"]["a"]["live"])


    def says(self):
        return [i["say"] for sc in self.data()["scenes"] for i in sc.get("items", []) if "say" in i]

    def test_reword_changes_one_narrator_line(self):
        self.film_py("scenes", "clear")
        self.film_py("scene", "add", "card", "--heading", "1860", "--say", "He won in 1860.", "--say", "He won in 1860, then wept.")
        self.film_py("scene", "add", "card", "--heading", "1861", "--say", "Nguyen built the bridge.")
        self.film_py("reword", "He won in 1860.", "He won in eighteen sixty.")          # exact line beats the longer one
        self.assertEqual(self.says(), ["He won in eighteen sixty.", "He won in 1860, then wept.", "Nguyen built the bridge."])
        out = self.film_py("reword", "nguyen", "Win built the bridge.")                  # unique start, any case
        self.assertIn("Next: python3 scripts/next.py", out)
        self.assertEqual(self.says()[2], "Win built the bridge.")
        self.assertIn("2 narrator lines", self.film_py("reword", "He won", "x y", ok=False))
        self.assertIn("Win built the bridge.", self.film_py("reword", "Lincoln", "x y", ok=False))   # no match lists the lines
        self.film_py("reword", "Win built", "the line, respelled", ok=False)            # narrate.py's example text
        self.film_py("reword", "Win built", "<the new line>", ok=False)
        self.assertEqual(self.says()[2], "Win built the bridge.")

    def test_narrate_prints_a_reword_line_that_runs(self):
        """The command narrate.py prints for a MISREAD line finds that line once the example is replaced."""
        src = open(os.path.join(os.path.dirname(FILM), "narrate.py")).read()
        self.assertIn("film.py reword {shlex.quote(' '.join(text.split()[:6]))} \\\"the line, respelled\\\"", src)
        self.film_py("scenes", "clear")
        text = "Tebow's 2007 season ended with the Heisman Trophy."
        self.film_py("scene", "add", "card", "--heading", "2007", "--say", text)
        cmd = f"python3 {FILM} reword {shlex.quote(' '.join(text.split()[:6]))} " + shlex.quote("Tebow's two thousand seven season ended with the Heisman.")
        r = subprocess.run(["bash", "-c", cmd], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.says(), ["Tebow's two thousand seven season ended with the Heisman."])


    def test_a_quote_shorter_than_a_second_is_refused(self):
        self.ready_for_clips()
        self.assertIn("0.8 s long", self.film_py("clip", "payoff", "interview", "4007.5", "4008.3", "of the four", "2020", "x", ok=False))
        self.film_py("clip", "payoff", "interview", "4007", "4008", "it was worth it", "2020", "x")

    def test_a_key_holds_one_quote(self):
        """LFM2.5-24B (2026-11-24) typed every quote as key "start", so each one replaced the last."""
        self.ready_for_clips()
        self.film_py("clip", "start", "interview", "38.61", "45.09", "an honor", "2020", "x", "--live")
        self.film_py("clip", "start", "interview", "39", "45", "an honor to be here", "2020", "x")       # overlap: a correction
        self.assertEqual((self.data()["clips"]["start"]["text"], self.data()["clips"]["start"]["live"]), ("an honor to be here", True))
        out = self.film_py("clip", "start", "interview", "45.09", "49", "this is happening", "2020", "x", ok=False)
        self.assertIn("film.py clip risk interview 45.09 49", out)
        self.film_py("clip", "start", "speech", "39", "45", "other source", "2020", "x", ok=False)
        self.assertEqual(list(self.data()["clips"]), ["start"])
        self.film_py("clip", "start", "interview", "45.09", "49", "this is happening", "2020", "x", "--replace")
        self.assertEqual(self.data()["clips"]["start"]["in"], 45.09)

    def test_step_5_command_names_a_free_key_and_refuses_a_verbatim_copy(self):
        self.ready_for_clips()
        self.film_py("clip", "start", "interview", "1", "3", "words", "2020", "x")
        out = self.run_next()
        cmd = next(c for c in self.commands(out) if "film.py clip " in c)
        self.assertIn("film.py clip risk interview IN OUT", cmd)
        self.assertIn("Clips so far: start.", out)
        before = open(os.path.join(self.proj, "film.json")).read()
        r = subprocess.run(["bash", "-c", cmd], cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(open(os.path.join(self.proj, "film.json")).read(), before)


if __name__ == "__main__":
    unittest.main()
