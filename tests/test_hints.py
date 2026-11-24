"""Each script's closing "Next:" hint names only a step next.py would print at that point.

A hint that skips ahead sends a small model past a gate: after one transcript, transcribe.py used to
point at quote search while next.py still needed a second recording (LFM2.5-24B, 2026-11-24)."""
import os, re, unittest

KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plutarch", "scripts")
# script -> scripts its Next: hints may name. next.py is always allowed.
ALLOWED = {
    "transcribe.py": set(), "plan.py": set(), "film.py": set(), "clip.py": {"film.py"}, "setup.py": {"setup.py"},
    "find_audio.py": {"find_audio.py"}, "score.py": {"mix.py", "score.py"},
    "mix.py": {"render.py"}, "narrate.py": {"plan.py", "narrate.py"}, "render.py": {"check.py"},
}


class Hints(unittest.TestCase):
    def test_hints_follow_next_py(self):
        for name, ok in ALLOWED.items():
            src = open(os.path.join(KIT, name)).read()
            for target in re.findall(r"Next:[^\"']*?scripts/(\w+\.py)", src):
                self.assertIn(target, ok | {"next.py"}, f"{name} hints at {target}")

    def test_every_hint_is_listed(self):
        for name in os.listdir(KIT):
            if name.endswith(".py") and "Next:" in open(os.path.join(KIT, name)).read():
                self.assertIn(name, ALLOWED, f"{name} prints a Next: hint; add it to ALLOWED")


if __name__ == "__main__":
    unittest.main()
