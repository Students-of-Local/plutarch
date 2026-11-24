"""next.py walks a project from nothing to the quote step, and reports waits and crashes.

Stub packages stand in for the kit's heavy dependencies, so this runs with the standard library only:
  python3 -m unittest discover tests"""
import json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "plutarch", "scripts")
NEXT = os.path.join(KIT, "next.py")
DEPS = ["numpy", "scipy", "soundfile", "pyloudnorm", "librosa", "skia", "PIL", "faster_whisper", "yt_dlp", "kokoro_onnx"]

os.environ["PLUTARCH_FACTS"] = "off"      # the fixtures' fact URLs are made up; test_facts.py checks the check


class Project(unittest.TestCase):
    """A film project made from the templates, with stub packages for the kit's dependencies."""
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

    def commands(self, out):
        return [l.strip() for l in out.splitlines() if l.strip().startswith(("python3 ", "nohup ", "cd "))]

    def ready_for_clips(self):
        """A project whose story, two sources and transcripts are done."""
        self.film(subject="Abraham Lincoln",
                  sources={n: {"file": f"src/{n}.mp3", "credit": f"{n} (1860)", "url": "https://x.test"} for n in ("interview", "speech")})
        p = os.path.join(self.proj, "story.md"); s = open(p).read()
        s = s.replace('"He/She/They ____________, it cost ____________, and then ____________."', "He rose from a cabin to the presidency, it cost him dearly, and then he won.")
        open(p, "w").write(s.replace("| 1 | | | |", "\n".join(f"| {i} | f | https://a.test/{i} | https://b.test/{i} |" for i in range(1, 6))))
        for n in ("interview", "speech"):
            open(os.path.join(self.proj, "src", n + ".mp3"), "wb").close()
            with open(os.path.join(self.proj, "tx", n + ".json"), "w") as f: f.write("{}")


class NextPy(Project):
    def test_a_quote_that_cannot_be_cut_is_not_a_crash(self):
        """qwen3:4b (2026-11-24) ran clip.py make 16 times on one 0.8 s quote that next.py called a crash."""
        self.ready_for_clips()
        p = os.path.join(self.proj, "film.json"); film = json.load(open(p))
        film["clips"] = {k: {"src": "speech" if k == "turn" else "interview", "in": 10, "out": 12, "text": "x", "year": 1860, "about": "x"}
                         for k in ("start", "risk", "cost", "turn", "payoff", "comeback", "last")}
        json.dump(film, open(p, "w")); os.utime(p, (1000, 1000))
        log = os.path.join(self.proj, "out", "clips.log"); os.makedirs(os.path.dirname(log), exist_ok=True)
        line = "ERROR: clip 'payoff': could not find all of \"of the four\" near 4007.5-4008.3 s.\n"
        open(log, "w").write(line)
        out = self.run_next()
        self.assertIn("STEP 6 of 12: replace the quotes that could not be cut", out)
        self.assertIn("python3 scripts/film.py drop clip payoff", out)
        self.assertNotIn("crashed", out)
        os.utime(log, (1000, 1000)); os.utime(p, (2000, 2000))     # film.json changed since: the stale log is ignored
        out = self.run_next()
        self.assertIn("STEP 6 of 12: cut and verify the quotes", out)
        open(log, "w").write("Traceback (most recent call last):\n" + line); os.utime(p, (1000, 1000))
        self.assertIn("clip.py make crashed", self.run_next())      # a real crash is still one

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

    def test_every_printed_command_is_valid_bash(self):
        empty = os.path.join(self.tmp, "empty"); os.makedirs(empty)
        outs = [self.run_next(), self.run_next(cwd=self.tmp), self.run_next(cwd=empty)]
        self.film(subject="Abraham Lincoln"); outs.append(self.run_next())
        for o in outs:
            for c in self.commands(o):
                r = subprocess.run(["bash", "-n", "-c", c], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"not valid bash: {c}\n{r.stderr}")

    def test_old_project_does_not_hide_new_one(self):
        self.film(subject="Tim Tebow")
        out = self.run_next(cwd=self.tmp)
        self.assertIn("films/test   subject: Tim Tebow", out)
        self.assertIn("setup.py --init ./films/SHORTNAME", out)

    def test_replaced_recording_is_transcribed_again(self):
        self.ready_for_clips()
        self.assertIn("STEP 5", self.run_next())
        t = os.path.getmtime(os.path.join(self.proj, "tx", "interview.json"))
        os.utime(os.path.join(self.proj, "src", "interview.mp3"), (t + 10, t + 10))
        self.assertIn("STEP 4 of 12: transcribe src/interview.mp3", self.run_next())

    def test_one_command_transcribes_every_pending_recording(self):
        """LFM2.5-24B (2026-11-24) ran the first transcribe, then polled a finished log and never started the second."""
        self.ready_for_clips()
        for n in ("interview", "speech"): os.remove(os.path.join(self.proj, "tx", n + ".json"))
        cmds = [c for c in self.commands(self.run_next()) if "transcribe.py" in c]
        self.assertEqual(len(cmds), 1, cmds)
        self.assertIn("transcribe.py src/interview.mp3 src/speech.mp3 >", cmds[0])
        with open(os.path.join(self.proj, "tx", "speech.json"), "w") as f: f.write("{}")
        cmds = [c for c in self.commands(self.run_next()) if "transcribe.py" in c]
        self.assertEqual(len(cmds), 1, cmds)
        self.assertIn("transcribe.py src/interview.mp3 >", cmds[0]); self.assertNotIn("speech", cmds[0])

    def test_any_downloaded_recording_counts(self):
        """qwen3:4b (2026-11-24) got src/interview.mpg from archive.org; next.py kept saying src/ had no audio."""
        self.film(subject="Tim Tebow")
        p = os.path.join(self.proj, "story.md"); s = open(p).read()
        s = s.replace('"He/She/They ____________, it cost ____________, and then ____________."', "He rose, it cost him, and then he won.")
        open(p, "w").write(s.replace("| 1 | | | |", "\n".join(f"| {i} | f | https://a.test/{i} | https://b.test/{i} |" for i in range(1, 6))))
        open(os.path.join(self.proj, "src", "interview.mpg"), "wb").close()
        self.assertIn("film.py source interview src/interview.mpg", self.run_next())
        open(os.path.join(self.proj, "src", "speech.xyz"), "wb").close()
        self.film(sources={"interview": {"file": "src/interview.mpg", "credit": "Show (2010)", "url": "https://x.test"},
                           "speech": {"file": "src/speech.xyz", "credit": "Event (2012)", "url": "https://x.test"}})
        self.assertIn("STEP 4 of 12: transcribe src/interview.mpg and src/speech.xyz", self.run_next())

    def test_wait_before_starting_says_start_it(self):
        """qwen3:4b (2026-11-24) ran next.py --wait three times without running the nohup line, then gave up."""
        self.ready_for_clips()
        os.remove(os.path.join(self.proj, "tx", "speech.json"))
        self.assertNotIn("NOT STARTED", self.run_next())
        env = dict(os.environ, PYTHONPATH=self.stubs)
        out = subprocess.run([sys.executable, NEXT, "--wait"], cwd=self.proj, env=env, capture_output=True, text=True).stdout
        self.assertIn("NOT STARTED: nothing is running", out); self.assertIn("nohup python3 scripts/transcribe.py src/speech.mp3", out)

    def test_transcribe_skips_a_missing_file(self):
        """LFM2.5-24B (2026-11-24) copied the steps.md example src/speech.m4a; one missing file stopped the whole job."""
        bin_ = os.path.join(self.tmp, "bin"); os.makedirs(bin_)
        p = os.path.join(bin_, "ffprobe"); open(p, "w").write("#!/bin/sh\nexit 1\n"); os.chmod(p, 0o755)   # CI has no ffmpeg
        env = dict(os.environ, PYTHONPATH=self.stubs, PATH=bin_ + os.pathsep + os.environ["PATH"])
        tr = os.path.join(KIT, "transcribe.py")
        r = subprocess.run([sys.executable, tr, "src/interview.mp3", "src/speech.m4a"], cwd=self.proj, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("none of these files exist", r.stdout + r.stderr)
        open(os.path.join(self.proj, "src", "interview.mp3"), "wb").close()
        r = subprocess.run([sys.executable, tr, "src/interview.mp3", "src/speech.m4a"], cwd=self.proj, env=env, capture_output=True, text=True)
        self.assertIn("SKIP src/speech.m4a: no such file", r.stdout)
        rest = (r.stdout + r.stderr).split("SKIP src/speech.m4a", 1)[1]
        self.assertIn("src/interview.mp3", rest); self.assertNotIn("none of these files exist", rest)   # it went on to the file that exists

    def test_a_recording_without_sound(self):
        """LFM2.5-24B (2026-11-24) saved a video-only download as a source; transcribe.py failed on it and next.py called that a crash."""
        self.ready_for_clips(); os.remove(os.path.join(self.proj, "tx", "speech.json"))
        with open(os.path.join(self.proj, "out", "tx.log"), "w") as f:
            f.write("OK wrote tx/interview.json\nERROR: ffmpeg could not read audio from src/speech.mp3: [out#0] Output file does not contain any stream\nError opening output files: Invalid argument\n")
        out = self.run_next()
        self.assertIn("replace the recording that has no sound", out); self.assertIn("film.py drop source speech", out); self.assertNotIn("crashed", out)
        subprocess.run([sys.executable, os.path.join(KIT, "film.py"), "drop", "source", "speech"], cwd=self.proj, capture_output=True)
        out = self.run_next(); self.assertNotIn("crashed", out); self.assertNotIn("no sound", out)
        bin_ = os.path.join(self.tmp, "bin"); os.makedirs(bin_); p = os.path.join(bin_, "ffprobe")
        env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ["PATH"])
        for said, code, want in (("video", 0, 1), ("video\naudio", 0, 0), ("", 1, 0)):              # no sound, sound, ffprobe failed
            with open(p, "w") as f: f.write(f"#!/bin/sh\nprintf '{said}'\nexit {code}\n")
            os.chmod(p, 0o755)
            r = subprocess.run([sys.executable, os.path.join(KIT, "film.py"), "source", "talk", "src/speech.mp3", "The Talk (1860)", "https://x.test"],
                               cwd=self.proj, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, want, r.stdout + r.stderr); self.assertEqual("has no sound" in r.stdout + r.stderr, bool(want))

    def test_hand_written_keys_are_named(self):
        """LFM2.5-24B (2026-11-24) wrote "facts" and "audio_sources" into film.json with python3 -c; next.py kept saying 0 facts."""
        self.film(subject="Tim Tebow")
        self.assertNotIn("NOTE: film.json has keys", self.run_next())
        self.film(facts=[{"Fact": "x"}], audio_sources=[])
        out = self.run_next()
        self.assertIn("NOTE: film.json has keys the kit never reads: audio_sources, facts.", out)
        self.assertIn("STEP 2 of 12", out)

    def test_old_kit_cut_is_redone_after_an_edit(self):
        self.ready_for_clips()
        clips = {f"c{i}": {"src": "interview" if i % 2 else "speech", "in": 10.0 * i, "out": 10.0 * i + 3, "text": f"words {i}", "year": 1860, "about": "x"} for i in range(6)}
        self.film(clips=clips)
        for k, c in clips.items():   # what clip.py of the previous release stored: no "spec"
            with open(os.path.join(self.proj, "clips", k + ".json"), "w") as f:
                json.dump({"id": k, "wanted": c["text"], "in_exact": c["in"] + 0.2, "out_exact": c["out"] - 0.1, "live": False, "verified": "asr"}, f)
        self.assertNotIn("STEP 6", self.run_next())
        clips["c3"]["text"] = "different words"; self.film(clips=clips)
        out = self.run_next()
        self.assertIn("STEP 6 of 12: cut and verify the quotes", out); self.assertIn("c3", out)

    def test_crashed_job_is_reported(self):
        self.film(subject="Abraham Lincoln", sources={"interview": {"file": "src/interview.mp3", "credit": "Show (1860)", "url": "https://x.test"}})
        open(os.path.join(self.proj, "out", "tx.log"), "w").write("Traceback (most recent call last):\nRuntimeError: Library libcublas.so.12 is not found\n")
        out = self.run_next()
        self.assertIn("transcribe.py crashed", out); self.assertIn("libcublas", out)

    def test_invalid_json_points_at_the_spot(self):
        open(os.path.join(self.proj, "film.json"), "w").write('{"subject": "A" "title": 1}')
        self.assertIn("not valid JSON", self.run_next())

    def test_skill_folder_is_never_a_film_project(self):
        skill = os.path.join(self.tmp, "skill"); shutil.copytree(os.path.join(ROOT, "plutarch"), skill, symlinks=True)
        env = dict(os.environ, PYTHONPATH=self.stubs)
        r = subprocess.run([sys.executable, os.path.join(skill, "scripts", "next.py")], cwd=skill, env=env, capture_output=True, text=True)
        self.assertIn("leave the skill folder", r.stdout)
        r = subprocess.run([sys.executable, os.path.join(skill, "scripts", "setup.py"), "--init", "./films/x"], cwd=skill, env=env, capture_output=True, text=True)
        self.assertFalse(os.path.exists(os.path.join(skill, "films")), r.stdout + r.stderr)


    def test_init_prints_the_first_step(self):
        """setup.py --init ends with next.py's first step, so the agent never has to find it."""
        bin_ = os.path.join(self.tmp, "bin"); os.makedirs(bin_)
        for t in ("ffmpeg", "ffprobe"):
            p = os.path.join(bin_, t); open(p, "w").write("#!/bin/sh\nexit 0\n"); os.chmod(p, 0o755)
        env = dict(os.environ, PYTHONPATH=self.stubs, PATH=bin_ + os.pathsep + os.environ["PATH"])
        r = subprocess.run([sys.executable, os.path.join(KIT, "setup.py"), "--init", "films/new"], cwd=self.tmp, env=env, capture_output=True, text=True)
        folder = os.path.join(self.tmp, "films", "new")
        self.assertIn("FIRST STEP", r.stdout, r.stdout + r.stderr)
        tail = r.stdout[r.stdout.index("FIRST STEP"):]
        self.assertIn("STEP 2 of 12", tail)
        self.assertIn(f"cd {folder} && python3 scripts/film.py set subject", tail)
        self.assertNotIn("Replace every value", open(os.path.join(folder, "film.json")).read())


    def test_damaged_kit_is_reported(self):
        """LFM2.5-8B (2026-11-24) overwrote the kit's setup.py with the text "SETUP OK"."""
        skill = os.path.join(self.tmp, "skill"); shutil.copytree(os.path.join(ROOT, "plutarch"), skill, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
        open(os.path.join(skill, "scripts", "setup.py"), "w").write("SETUP OK\n")
        env = dict(os.environ, PYTHONPATH=self.stubs)
        r = subprocess.run([sys.executable, os.path.join(skill, "scripts", "next.py")], cwd=self.proj, env=env, capture_output=True, text=True)
        self.assertIn("STEP 0 of 12: the skill is damaged", r.stdout, r.stderr)
        self.assertIn("setup.py", r.stdout)
        self.assertNotIn("__pycache__", os.listdir(os.path.join(skill, "scripts")))   # the check writes nothing


if __name__ == "__main__":
    unittest.main()
