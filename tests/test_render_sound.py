"""The finished file's peak must fit, whatever the AAC encoder does to it.

qwen3:4b (2026-11-24) passed 17 of 18 final checks. The last one, "peak 1.1 dB", came from the 256k AAC encode, and
check.py said "rerun mix.py", which can never change it."""
import ast, os, types, unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plutarch", "scripts")


class Sound(unittest.TestCase):
    def join(self, peaks):
        """Run render.py's join() with a fake ffmpeg that reports these peaks in turn; return the settings it used."""
        tree = ast.parse(open(os.path.join(SCRIPTS, "render.py"), encoding="utf8").read())
        want = [n for n in tree.body if getattr(n, "name", "") in ("join", "true_peak") or (isinstance(n, ast.Assign) and n.targets[0].id if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) else "") == "SOUND"]
        used, left = [], list(peaks)

        def run(cmd, **kw):
            if "ebur128=peak=true" in cmd: return types.SimpleNamespace(returncode=0, stderr=f"  True peak:\n    Peak: {left.pop(0):9.1f} dBFS\n")
            used.append((cmd[cmd.index("-b:a") + 1], any("alimiter" in c for c in cmd))); return types.SimpleNamespace(returncode=0, stderr="")
        ns = {"subprocess": types.SimpleNamespace(run=run), "die": self.fail}
        exec(compile(ast.Module(want, []), "render.py", "exec"), ns); ns["join"](); return used

    def test_a_good_first_encode_is_kept(self): self.assertEqual(self.join([-1.4]), [("256k", False)])
    def test_an_overshoot_tries_the_next_setting(self): self.assertEqual(self.join([1.1, -1.4]), [("256k", False), ("320k", False)])
    def test_a_stubborn_one_is_limited(self): self.assertEqual(self.join([1.1, 0.3, -0.4, -2.6])[-1], ("192k", True))
    def test_it_stops_when_nothing_fits(self): self.assertEqual(len(self.join([1.1] * 5)), 5)

    def test_check_names_a_command_that_can_help(self):
        line = next(l for l in open(os.path.join(SCRIPTS, "check.py"), encoding="utf8") if 'chk("peak"' in l)
        self.assertIn('"python3 scripts/render.py --mux"', line)


if __name__ == "__main__": unittest.main()
