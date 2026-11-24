"""clip.py's hints name film.py commands that run, never a hand edit of film.json.

qwen3:4b (2026-11-24) searched for the example phrase itself, then read "Copy the in/out ... into
film.json" after every search."""
import ast, json, os, re, shlex, subprocess, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

CLIP = os.path.join(KIT, "clip.py")


class ClipPy(Project):
    def clip_py(self, *args):
        env = dict(os.environ, PYTHONPATH=self.stubs)
        return subprocess.run([sys.executable, CLIP, *args], cwd=self.proj, env=env, capture_output=True, text=True)

    def test_example_search_is_refused(self):
        self.ready_for_clips()
        r = self.clip_py("find", "tx/interview.json", "a few words or an idea")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("example search", r.stdout)

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
        self.assertIn("python3 scripts/film.py clip risk interview IN OUT", r.stdout)
        cmd = next(l.strip() for l in r.stdout.splitlines() if "film.py clip risk" in l)
        cmd = cmd.replace("IN OUT", "12.5 15").replace("YEAR", "2012").replace('"what he was talking about"', '"being cut"')
        bad = subprocess.run(["bash", "-c", cmd.replace("python3 scripts/film.py", f"{sys.executable} {os.path.join(KIT, 'film.py')}")], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1, bad.stdout)          # "the words after >>>" is example text
        self.assertIn("example text", bad.stdout)
        good = cmd.replace('"the words after >>>"', '"Then they cut me."')
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
        ns = {"shlex": shlex}; exec(compile(ast.Module([fn], []), CLIP, "exec"), ns)
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
        ns = {"shlex": shlex}
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

    def test_free_key_lists_match(self):
        lists = [re.search(r'\["start", "risk", "cost", "turn", "payoff", "comeback"\]', open(os.path.join(KIT, n)).read())
                 for n in ("film.py", "next.py", "clip.py")]
        self.assertTrue(all(lists))


if __name__ == "__main__":
    unittest.main()
