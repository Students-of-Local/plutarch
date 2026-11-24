"""clip.py's hints name film.py commands that run, never a hand edit of film.json.

qwen3:4b (2026-11-24) searched for the example phrase itself, then read "Copy the in/out ... into
film.json" after every search."""
import ast, contextlib, io, json, os, re, shlex, subprocess, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

CLIP = os.path.join(KIT, "clip.py")
SHELL = {"shlex": shlex, "re": re}                                 # dq comes from common.py, without its numpy import
exec(compile(ast.Module([f for f in ast.parse(open(os.path.join(KIT, "common.py")).read()).body
                         if isinstance(f, ast.FunctionDef) and f.name == "dq"], []), "common.py", "exec"), SHELL)


class ClipPy(Project):
    def clip_py(self, *args):
        env = dict(os.environ, PYTHONPATH=self.stubs)
        return subprocess.run([sys.executable, CLIP, *args], cwd=self.proj, env=env, capture_output=True, text=True)

    def test_example_search_is_refused(self):
        self.ready_for_clips()
        r = self.clip_py("find", "tx/interview.json", "a few words or an idea")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("example search", r.stdout)

    def test_one_bad_quote_does_not_stop_the_cut(self):
        """The clips after a failed one are still cut, and the job still exits 1."""
        fn = next(f for f in ast.parse(open(CLIP).read()).body if isinstance(f, ast.FunctionDef) and f.name == "cmd_make")
        made = []
        def make_one(cid, film):
            made.append(cid)
            if cid == "b": sys.exit(1)
            return [cid, "1-2", "1 s", "yes", "x"], []
        rows = []
        ns = {"sys": sys, "make_one": make_one, "load_film": lambda only: {"clips": {"a": {}, "b": {}, "c": {}}},
              "table": lambda r, h: rows.extend(r), "die": lambda m: self.fail(m)}
        exec(compile(ast.Module([fn], []), CLIP, "exec"), ns)
        said = io.StringIO()
        with contextlib.redirect_stdout(said), self.assertRaises(SystemExit) as end:
            ns["cmd_make"](type("A", (), {"ids": []}))
        self.assertEqual((made, end.exception.code), (["a", "b", "c"], 1))
        self.assertEqual([r[3] for r in rows], ["yes", "NOT CUT", "yes"])
        self.assertIn("NOT CUT: b.", said.getvalue()); self.assertIn("FIX NEEDED: 2/3", said.getvalue())

    def test_a_quote_under_a_second_is_not_cut(self):
        """qwen3:4b (2026-11-24) kept the 0.74 s quote "Post football?", and check.py heard "list for Bob." in the film."""
        fn = [f for f in ast.parse(open(CLIP).read()).body if isinstance(f, ast.FunctionDef) and f.name == "long_enough"]
        said = []
        def die(msg): said.append(msg); sys.exit(1)
        ns = {"die": die}
        exec(compile(ast.Module(fn, []), CLIP, "exec"), ns)
        with self.assertRaises(SystemExit): ns["long_enough"]("c7", 0.74, False)
        self.assertTrue(said[0].startswith("clip 'c7': the words last only 0.74 s."), said)
        self.assertIn("film.py drop clip c7", said[0])
        ns["long_enough"]("c7", 1.0, False); ns["long_enough"]("c7", 0.74, True)      # a live race call may be short
        self.assertIn("long_enough(cid, b - a, live)", open(CLIP).read())             # and make_one uses it

    def test_find_prints_apostrophes_plainly_and_the_command_runs(self):
        self.ready_for_clips()
        said = "I'm not done, that's $5 and a \"no\" from `him`."
        with open(os.path.join(self.proj, "tx", "interview.json"), "w") as f:
            json.dump({"segments": [{"s": 10.0, "e": 12.5, "text": said}]}, f)
        r = self.clip_py("find", "tx/interview.json", "not done")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cmd = next(l.strip() for l in r.stdout.splitlines() if "film.py clip" in l)
        self.assertNotIn("'\"'\"'", cmd)                          # shlex.quote's form of an apostrophe
        self.assertIn("I'm not done, that's", cmd)
        cmd = re.sub(r"\bYEAR\b", "2012", cmd).replace("what he was talking about", "being cut")
        cmd = cmd.replace("python3 scripts/film.py", f"{sys.executable} {os.path.join(KIT, 'film.py')}")
        ok = subprocess.run(["bash", "-c", cmd], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        clips = json.load(open(os.path.join(self.proj, "film.json")))["clips"]
        self.assertIn(said, [c["text"] for c in clips.values()])   # bash hands film.py the exact words

    def test_find_ends_with_a_film_py_command_with_a_free_key(self):
        self.ready_for_clips()
        with open(os.path.join(self.proj, "tx", "interview.json"), "w") as f:
            json.dump({"segments": [{"s": 10.0, "e": 12.5, "text": "I won the Heisman that year."},
                                    {"s": 12.5, "e": 15.0, "text": "Then they cut me."}]}, f)
        p = os.path.join(self.proj, "film.json"); film = json.load(open(p))
        film["clips"] = {"start": {"src": "interview", "in": 1, "out": 3, "text": "x", "year": 2020, "about": "x"}}
        json.dump(film, open(p, "w"))
        r = self.clip_py("find", "tx/interview.json", "cut me")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Copy the in/out", r.stdout)
        self.assertIn("python3 scripts/film.py clip risk interview 12.5 15.0 'Then they cut me.'", r.stdout)
        self.assertNotIn(" IN OUT ", r.stdout)                      # a small model copied IN OUT literally
        cmd = next(l.strip() for l in r.stdout.splitlines() if "film.py clip risk" in l)
        cmd = cmd.replace("YEAR", "2012")
        bad = subprocess.run(["bash", "-c", cmd.replace("python3 scripts/film.py", f"{sys.executable} {os.path.join(KIT, 'film.py')}")], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1, bad.stdout)          # "what he was talking about" is example text
        self.assertIn("example text", bad.stdout)
        good = cmd.replace('"what he was talking about"', '"being cut"')
        ok = subprocess.run(["bash", "-c", good.replace("python3 scripts/film.py", f"{sys.executable} {os.path.join(KIT, 'film.py')}")], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)              # the printed source key and free key are real
        self.assertEqual(json.load(open(p))["clips"]["risk"]["src"], "interview")

    def test_no_hint_says_to_edit_film_json(self):
        src = open(CLIP).read()
        for bad in ('Add \\"isolate\\": true', 'add \\"live\\": true', 'change \\"text\\"', 'Copy the in/out', 'add \\"{k}\\" to this clip',
                    'Widen in/out."', 'set in/out tightly', 'check in/out."'):
            self.assertFalse(bad in src, bad)

    def test_retype_commands_run(self):
        """The widen and use-heard-words commands make prints are accepted by film.py."""
        tree = ast.parse(open(CLIP).read())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "retype")
        ns = dict(SHELL); exec(compile(ast.Module([fn], []), CLIP, "exec"), ns)
        self.ready_for_clips()
        film_py = os.path.join(KIT, "film.py")
        subprocess.run([sys.executable, film_py, "clip", "turn", "interview", "10", "12.5", "I won it", "2007", "the Heisman"], cwd=self.proj, check=True, capture_output=True)
        c = json.load(open(os.path.join(self.proj, "film.json")))["clips"]["turn"]
        exec(compile(ast.Module([next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "widened")], []), CLIP, "exec"), ns)
        self.assertIn(" 9 34 ", ns["widened"]("x", {"src": "s", "in": 10, "out": 33.5, "text": "t", "year": 1, "about": "a"}))   # stays within 25 s
        for cmd in (ns["retype"]("turn", c, text="I won the Heisman, didn't I"), ns["widened"]("turn", c)):
            r = subprocess.run(["bash", "-c", cmd.replace("python3 scripts/film.py", f"{shlex.quote(sys.executable)} {shlex.quote(film_py)}")],
                               cwd=self.proj, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, cmd + "\n" + r.stdout)
        c = json.load(open(os.path.join(self.proj, "film.json")))["clips"]["turn"]
        self.assertEqual((c["in"], c["out"], c["text"]), (9.0, 13.5, "I won it"))   # each command keeps the words it was built from

    def test_caption_fix_is_a_film_py_command(self):
        """A wrong heard word is fixed with the film.py command clip.py prints, not by editing "lines" by hand."""
        tree = ast.parse(open(CLIP).read())
        ns = dict(SHELL)
        for name in ("phrases_from", "lines_cmd"):
            exec(compile(ast.Module([next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)], []), CLIP, "exec"), ns)
        self.ready_for_clips()
        film_py = os.path.join(KIT, "film.py")
        run = lambda cmd: subprocess.run(["bash", "-c", cmd.replace("python3 scripts/film.py", f"{shlex.quote(sys.executable)} {shlex.quote(film_py)}")],
                                         cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(run('python3 scripts/film.py clip turn interview 10 12.5 "I won it" 2007 "the Heisman"').returncode, 0)
        heard = [{"w": w, "s": 10 + i * 0.3, "e": 10.2 + i * 0.3, "p": 0.9} for i, w in enumerate(["I", "one", "it."])]
        with open(os.path.join(self.proj, "clips", "turn.json"), "w") as f: json.dump({"words": heard}, f)
        cmd = ns["lines_cmd"]("turn", heard)
        self.assertEqual(cmd, "python3 scripts/film.py clip turn --lines 'I one it.'")
        r = run(cmd.replace("one", "won")); self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.load(open(os.path.join(self.proj, "film.json")))["clips"]["turn"]["lines"], ["I won it."])
        r = run("python3 scripts/film.py clip turn --lines 'I won'")       # word count must match what was heard
        self.assertEqual(r.returncode, 1); self.assertIn("3 words were heard: I one it.", r.stdout)
        self.assertEqual(run("python3 scripts/film.py clip turn --no-lines").returncode, 0)
        self.assertNotIn("lines", json.load(open(os.path.join(self.proj, "film.json")))["clips"]["turn"])
        self.assertNotIn('(same number of words) and run make again', open(CLIP).read())

    def test_beat_names_and_misses_give_no_in_out(self):
        """qwen3:4b and LFM2.5-24B (2026-11-24) searched "comeback" and "risk", got a 0% hit with in/out, and used it."""
        self.ready_for_clips()
        segs = [{"s": 10.0 * i, "e": 10.0 * i + 4, "text": t} for i, t in enumerate(
            ["I won the Heisman that year.", "We lost the game in overtime.", "My father was a missionary."])]
        with open(os.path.join(self.proj, "tx", "interview.json"), "w") as f: json.dump({"segments": segs}, f)
        r = self.clip_py("find", "tx/interview.json", "the comeback")
        self.assertEqual(r.returncode, 1); self.assertIn("is a beat name", r.stdout)
        r = self.clip_py("find", "tx/interview.json", "Broncos")
        self.assertIn("no match for 'Broncos'", r.stdout); self.assertNotIn('"in":', r.stdout); self.assertNotIn("Next:", r.stdout)
        r = self.clip_py("find", "tx/interview.json", "Heisman")
        self.assertIn('"in": 0.0, "out": 4.0', r.stdout); self.assertIn("Next:", r.stdout)

    def test_step_5_prints_searches_from_the_facts(self):
        self.ready_for_clips()
        p = os.path.join(self.proj, "story.md"); s = open(p).read()
        s = s.replace("| 1 | f |", "| 1 | Won the Heisman Trophy in 2007 |").replace("| 2 | f |", "| 2 | Abraham Lincoln was drafted by the Denver Broncos |")
        open(p, "w").write(s)
        out = self.run_next()
        self.assertIn('clip.py find tx/interview.json Heisman', out)
        self.assertIn('clip.py find tx/speech.json Broncos', out)           # second search goes to the second transcript
        self.assertNotIn("Abraham", out.split("STEP 5")[1].split("THEN")[0].replace("Abraham Lincoln", ""))
        self.assertNotIn("the start, the risk", out)

    def test_free_key_lists_match(self):
        lists = [re.search(r'\["start", "risk", "cost", "turn", "payoff", "comeback"\]', open(os.path.join(KIT, n)).read())
                 for n in ("film.py", "next.py", "clip.py")]
        self.assertTrue(all(lists))


if __name__ == "__main__":
    unittest.main()
