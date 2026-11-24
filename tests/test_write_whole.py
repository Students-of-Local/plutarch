"""A full disk or a failed download leaves film.json, story.md and the source audio as they were."""
import ast, http.server, json, os, pathlib, re, resource, shutil, stat, subprocess, sys, threading, unittest, urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT


def full(): resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))      # any write past 4 KB fails, like a full disk


class Whole(Project):
    def setUp(self):
        super().setUp()
        self.film(subject="Ævar", scenes=[{"type": "card", "heading": "x" * 300}] * 40)
        with open(self.path("story.md"), "a") as f: f.write("\n" + "y" * 5000 + "\n")

    def path(self, *p): return os.path.join(self.proj, *p)
    def read(self, *p): return pathlib.Path(self.path(*p)).read_bytes()
    def listing(self): return sorted(os.path.join(d, f) for d, _, fs in os.walk(self.proj) for f in fs)

    def py(self, *args, pre=None, path=None):
        e = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
        r = subprocess.run([sys.executable, "-B", *args], cwd=self.proj, env={**e, "PYTHONPATH": path or self.stubs}, capture_output=True, text=True, preexec_fn=pre, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def script(self, name, *args, **kw): return self.py(os.path.join(KIT, name), *args, **kw)

    def save_json(self, p, obj, **kw):
        return self.py("-c", "import sys, json; from common import save_json; save_json(sys.argv[1], json.loads(sys.argv[2]))", p, json.dumps(obj),
                       path=self.stubs + os.pathsep + KIT, **kw)

    def unchanged(self, name, run):
        old, files = self.read(name), self.listing(); code, out = run()
        self.assertEqual(self.read(name), old); self.assertEqual(self.listing(), files); self.assertNotEqual(code, 0, out)
        return out

    # ---- disk full ----
    def test_film_py_save(self):
        out = self.unchanged("film.json", lambda: self.script("film.py", "set", "subject", "B", pre=full))
        self.assertIn("ERROR: could not write film.json: File too large.", out); self.assertNotIn("Traceback", out)

    def test_film_py_story(self):
        for args in (("sentence", "He rose from a log cabin, and then led the nation."), ("fact", "Elected in 1860", "https://a.test", "https://b.test")):
            self.unchanged("story.md", lambda: self.script("film.py", *args, pre=full))
        self.assertEqual(self.script("film.py", *args)[0], 0)
        self.unchanged("story.md", lambda: self.script("film.py", "drop", "fact", "1", pre=full))

    def test_save_json(self):
        pathlib.Path(self.path("out", "plan.json")).write_text('{"old": 1}')
        self.unchanged("out/plan.json", lambda: self.save_json("out/plan.json", ["x" * 9000], pre=full))
        files = self.listing(); self.assertNotEqual(self.save_json("out/new.json", ["x" * 9000], pre=full)[0], 0)
        self.assertEqual(self.listing(), files)                          # no half-written new file either

    # ---- room on disk ----
    def test_a_normal_save_writes_the_same_bytes(self):
        want = json.loads(self.read("film.json")); want["subject"] = "Bær"
        self.assertEqual(self.script("film.py", "set", "subject", "Bær")[0], 0)
        self.assertEqual(self.read("film.json"), (json.dumps(want, indent=1, ensure_ascii=False) + "\n").encode())
        obj = {"a": ["é", 1.5, None]}; files = self.listing()
        self.assertEqual(self.save_json("out/deep/x.json", obj)[0], 0)
        self.assertEqual(self.read("out/deep/x.json"), json.dumps(obj, indent=1, ensure_ascii=False).encode())
        self.assertEqual(self.listing(), sorted(files + [self.path("out", "deep", "x.json")]))

    def test_a_link_and_the_file_mode_survive(self):
        real = os.path.join(self.tmp, "real.json"); shutil.move(self.path("film.json"), real); os.symlink(real, self.path("film.json")); os.chmod(real, 0o640)
        self.assertEqual(self.script("film.py", "set", "subject", "B")[0], 0)
        self.assertTrue(os.path.islink(self.path("film.json"))); self.assertEqual(stat.S_IMODE(os.stat(real).st_mode), 0o640)
        self.assertEqual(json.loads(self.read("film.json"))["subject"], "B")

    def test_film_py_needs_no_numpy(self):
        with open(os.path.join(self.stubs, "numpy", "__init__.py"), "w") as f: f.write("raise ImportError('not here')")
        self.assertEqual(self.script("film.py", "set", "subject", "B")[0], 0)
        code, out = self.py("-c", "from common import *; np.zeros(1)", path=self.stubs + os.pathsep + KIT)
        self.assertEqual(code, 1); self.assertIn("ERROR: numpy is not usable (not here). Run: python3 scripts/setup.py --install", out)

    # ---- downloads ----
    def test_a_failed_get_keeps_the_old_recording(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if "cut" in self.path else 503); self.send_header("Content-Length", "9000"); self.end_headers(); self.wfile.write(b"part")
            def log_message(self, *a): pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        pathlib.Path(self.path("src", "a.mp3")).write_bytes(os.urandom(50000))
        for url in ("http://127.0.0.1:1/x.mp3", f"http://127.0.0.1:{srv.server_port}/down.mp3", f"http://127.0.0.1:{srv.server_port}/cut.mp3"):
            self.unchanged("src/a.mp3", lambda: self.script("find_audio.py", "get", url, "--name", "a"))

    def test_a_cut_off_voice_download_writes_nothing(self):
        """No network: urlopen is replaced by a reply that breaks off while it is read."""
        src = pathlib.Path(KIT, "narrate.py").read_text("utf8"); ns = dict(json=json, os=os, re=re, urllib=urllib, die=self.fail, write_file=None)
        f = next(f for f in ast.parse(src).body if isinstance(f, ast.FunctionDef) and f.name == "synth"); exec(compile(ast.Module([f], []), "narrate.py", "exec"), ns)
        out = self.path("narr", "o.wav")
        for eng in ("openai", "elevenlabs"):
            with mock.patch("urllib.request.urlopen") as u, mock.patch.dict(os.environ, {"OPENAI_API_KEY": "", "ELEVENLABS_API_KEY": "x"}):
                u.return_value.__enter__.return_value.read.side_effect = ConnectionResetError
                with self.assertRaises(ConnectionResetError): ns["synth"]("hi", out, {"engine": eng, "voice": "v"})
            self.assertFalse(os.path.exists(out), eng)


if __name__ == "__main__":
    unittest.main()
