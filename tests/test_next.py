"""next.py walks a project from nothing to the quote step, and reports waits and crashes.

Stub packages stand in for the kit's heavy dependencies, so this runs with the standard library only:
  python3 -m unittest discover tests"""
import json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "plutarch", "scripts")
NEXT = os.path.join(KIT, "next.py")
DEPS = ["numpy", "scipy", "soundfile", "pyloudnorm", "librosa", "skia", "PIL", "faster_whisper", "yt_dlp", "kokoro_onnx"]


class NextPy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.stubs = os.path.join(self.tmp, "stubs")
        for m in DEPS:
            os.makedirs(os.path.join(self.stubs, m)); open(os.path.join(self.stubs, m, "__init__.py"), "w").close()
        self.proj = os.path.join(self.tmp, "films", "test")
        for d in ("src", "tx", "clips", "narr", "out"): os.makedirs(os.path.join(self.proj, d))
        os.symlink(KIT, os.path.join(self.proj, "scripts"))
        tpl = os.path.join(ROOT, "plutarch", "templates")
        shutil.copy(os.path.join(tpl, "film.json"), self.proj); shutil.copy(os.path.join(tpl, "story.md"), self.proj)

    def tearDown(self): shutil.rmtree(self.tmp)

    def run_next(self, cwd=None, stubs=True):
        env = dict(os.environ, PYTHONPATH=self.stubs if stubs else "")
        cmd = [sys.executable, NEXT] if stubs else [sys.executable, "-S", NEXT]   # -S hides installed packages
        r = subprocess.run(cmd, cwd=cwd or self.proj, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def film(self, **kw):
        p = os.path.join(self.proj, "film.json"); f = json.load(open(p)); f.update(kw); json.dump(f, open(p, "w"))

    def test_missing_tools_is_step_0(self):
        self.assertIn("STEP 0 of 12: install the tools", self.run_next(stubs=False))

    def test_outside_a_project_says_make_one(self):
        empty = os.path.join(self.tmp, "empty"); os.makedirs(empty)
        self.assertIn("STEP 1 of 12: make the film project", self.run_next(cwd=empty))

    def test_walks_story_sources_transcripts_to_quotes(self):
        self.assertIn("write the subject's name", self.run_next())
        self.film(subject="Abraham Lincoln")
        self.assertIn("STEP 2 of 12: story first", self.run_next())
        p = os.path.join(self.proj, "story.md"); s = open(p).read()
        s = s.replace('"He/She/They ____________, it cost ____________, and then ____________."',
                      "He rose from a cabin to the presidency, it cost him dearly, and then he won.")
        s = s.replace("| 1 | | | |", "\n".join(f"| {i} | fact {i} | https://a.test/{i} | https://b.test/{i} |" for i in range(1, 6)))
        open(p, "w").write(s)
        self.assertIn("STEP 3 of 12: get a real recording", self.run_next())
        for n in ("interview", "speech"): open(os.path.join(self.proj, "src", n + ".mp3"), "wb").close()
        self.film(sources={"interview": {"file": "src/interview.mp3", "credit": "<Show or event (year)>", "url": "https://x.test"}})
        self.assertIn("list your recordings", self.run_next())  # single-angle placeholder is caught
        self.film(sources={n: {"file": f"src/{n}.mp3", "credit": f"{n} (1860)", "url": "https://x.test"} for n in ("interview", "speech")})
        self.assertIn("STEP 4 of 12: transcribe src/interview.mp3", self.run_next())
        for n in ("interview", "speech"): open(os.path.join(self.proj, "tx", n + ".json"), "w").write("{}")
        self.assertIn("STEP 5 of 12: choose 6-10 quotes", self.run_next())

    def test_crashed_job_is_reported(self):
        self.film(subject="Abraham Lincoln", sources={"interview": {"file": "src/interview.mp3", "credit": "Show (1860)", "url": "https://x.test"}})
        open(os.path.join(self.proj, "out", "tx.log"), "w").write("Traceback (most recent call last):\nRuntimeError: Library libcublas.so.12 is not found\n")
        out = self.run_next()
        self.assertIn("transcribe.py crashed", out); self.assertIn("libcublas", out)

    def test_invalid_json_points_at_the_spot(self):
        open(os.path.join(self.proj, "film.json"), "w").write('{"subject": "A" "title": 1}')
        self.assertIn("not valid JSON", self.run_next())


if __name__ == "__main__":
    unittest.main()
