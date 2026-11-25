"""Each script's closing "Next:" hint names only a step next.py would print at that point.

A hint that skips ahead sends a small model past a gate: after one transcript, transcribe.py used to
point at quote search while next.py still needed a second recording (LFM2.5-24B, 2026-11-24)."""
import os, re, unittest

KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plutarch", "scripts")
# script -> scripts its Next: hints may name. next.py is always allowed.
ALLOWED = {
    "transcribe.py": set(), "plan.py": set(), "film.py": set(), "facts.py": set(), "clip.py": {"film.py"}, "setup.py": {"setup.py"},
    "find_audio.py": {"find_audio.py"}, "score.py": {"mix.py", "score.py"},
    "mix.py": {"render.py"}, "narrate.py": {"plan.py", "narrate.py"}, "render.py": {"check.py"},
}


class Hints(unittest.TestCase):
    def test_hints_follow_next_py(self):
        for name, ok in ALLOWED.items():
            src = open(os.path.join(KIT, name)).read()
            for target in re.findall(r"Next:[^\"']*?scripts/(\w+\.py)", src):
                self.assertIn(target, ok | {"next.py"}, f"{name} hints at {target}")

    def test_check_py_never_sends_a_model_to_film_json(self):
        """qwen3:4b (2026-11-24) finished a film, read "cut narrator lines in film.json", edited the file by hand and said it was done."""
        src = open(os.path.join(KIT, "check.py")).read()
        for name in ("first frame not black", "real voice is half the talking", "enough real quotes"):
            line = next(l for l in src.splitlines() if f'chk("{name}"' in l)
            self.assertIn("python3 scripts/film.py ", line, name); self.assertNotIn("film.json", line, name)
        cut = int(re.search(r"l\.strip\(\)\[:(\d+)\] for l in fails", open(os.path.join(KIT, "next.py")).read())[1])     # next.py must not cut a command in half
        self.assertGreater(cut, max(len(l.split('", "', 1)[-1]) for l in src.splitlines() if "film.py scene add" in l))
        self.assertRegex(src, r'if not ok: print\(.*Do not edit film\.json by hand.*python3 scripts/next\.py')

    def test_every_hint_is_listed(self):
        for name in os.listdir(KIT):
            if name.endswith(".py") and "Next:" in open(os.path.join(KIT, name)).read():
                self.assertIn(name, ALLOWED, f"{name} prints a Next: hint; add it to ALLOWED")


if __name__ == "__main__":
    unittest.main()
