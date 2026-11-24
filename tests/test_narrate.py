"""narrate.py: a film.json somebody else wrote can't run a command or send the user's key anywhere."""
import ast, glob, hashlib, http.server, json, os, pathlib, re, shlex, subprocess, sys, threading, unittest, urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

SRC = os.path.join(KIT, "narrate.py")
SAY_ID = lambda t: "n" + hashlib.md5(t.encode("utf8")).hexdigest()[:9]      # common.say_id
DROP = ("OPENAI_API_KEY", "PLUTARCH_NARRATOR_CMD", "PLUTARCH_TTS_HOSTS", "PLUTARCH_TTS_KEY")


class Server:
    """Loopback server that records the Authorization header of every request."""
    def __init__(self, status=200, to=None):
        seen = self.seen = []
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path.endswith(("/audio/speech", "/x")): seen.append(self.headers.get("Authorization"))      # other programs probe new ports
                self.send_response(status)
                if to: self.send_header("Location", to)
                self.end_headers(); self.wfile.write(b"wav")
            do_POST = do_GET
            def log_message(self, *a): pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); self.host = f"127.0.0.1:{self.srv.server_port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
    def close(self): self.srv.shutdown(); self.srv.server_close()


class Narrate(Project):
    def server(self, **kw):
        s = Server(**kw); self.addCleanup(s.close); return s

    def narrate(self, narrator, say="Hello there.", code=1, **env):
        """Run the real script. The voice engines are stubs, so it stops after the first line is made (code 1)."""
        film = {"subject": "A", "title": "T.", "narrator": narrator, "scenes": [{"type": "card", "items": [{"say": say}]}]}
        with open(os.path.join(self.proj, "film.json"), "w") as f: json.dump(film, f)
        e = {k: v for k, v in os.environ.items() if k not in DROP and not k.lower().endswith("_proxy")}
        e["HOME"] = self.tmp                                            # the command's folder, outside the project
        r = subprocess.run([sys.executable, "-B", SRC], cwd=self.proj, env={**e, "PYTHONPATH": self.stubs, **env}, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def made(self):
        return [pathlib.Path(p).read_bytes() for p in glob.glob(os.path.join(self.proj, "narr", "*.tmp.wav"))]

    def ran(self): return any(os.path.exists(os.path.join(d, "RAN")) for d in (self.proj, self.tmp))

    # ---- cmd ----
    def test_cmd_in_film_json_is_refused(self):
        for env in ({}, {"PLUTARCH_NARRATOR_CMD": "true {text} > {out}"}):
            out = self.narrate({"engine": "cmd", "cmd": "touch RAN; true {text} > {out}"}, **env)
            self.assertFalse(self.ran()); self.assertEqual(self.made(), [])
            self.assertIn("\n  PLUTARCH_NARRATOR_CMD='", out); self.assertIn('Delete "cmd"', out)
            self.assertNotIn("touch RAN", out)                          # an agent copies what is printed

    def test_no_cmd_prints_the_env_line(self):
        for c in ("", "true {text}", "true {out}"):
            self.assertIn("\n  PLUTARCH_NARRATOR_CMD='", self.narrate({"engine": "cmd"}, PLUTARCH_NARRATOR_CMD=c))

    def test_cmd_from_the_environment_runs(self):
        with open(os.path.join(self.tmp, "x.wav"), "wb") as f: f.write(b"voice")
        with open(os.path.join(self.proj, "x.wav"), "wb") as f: f.write(b"the project's")
        self.narrate({"engine": "cmd"}, PLUTARCH_NARRATOR_CMD="cp x.wav {out} # {text}")
        self.assertEqual(self.made(), [b"voice"])

    def test_a_relative_command_never_runs_a_project_file(self):
        with open(os.path.join(self.proj, "tts.py"), "w") as f: f.write("open('RAN', 'w')")
        for cmd in ("python3 tts.py {text} {out}", "python3 -m tts {text} {out}"):
            self.assertIn("PLUTARCH_NARRATOR_CMD failed", self.narrate({"engine": "cmd"}, PLUTARCH_NARRATOR_CMD=cmd)); self.assertFalse(self.ran(), cmd)

    def test_a_line_is_never_an_option(self):
        self.narrate({"engine": "cmd"}, say="-w/tmp/x", PLUTARCH_NARRATOR_CMD="printf '%s' {text} > {out}")
        self.assertEqual(self.made(), [b" -w/tmp/x"])

    def test_a_made_line_is_kept_until_the_command_changes(self):
        cmd, say = "mytts --key sk-canary --text {text} --out {out}", "Hello there."
        old = dict(engine="cmd", voice=None, speed=None, model=None, base_url=None, cmd=cmd)
        new = {**old, "cmd": "sha256:" + hashlib.sha256(cmd.encode()).hexdigest()}
        os.makedirs(os.path.join(self.proj, "narr"), exist_ok=True)
        base = os.path.join(self.proj, "narr", SAY_ID(say)); pathlib.Path(base + ".wav").write_bytes(b"old")
        for tag in (old, new):
            pathlib.Path(base + ".json").write_text(json.dumps({"dur": 1, "similarity": 1.0, "heard": say, "tag": json.dumps(tag, sort_keys=True)}))
            self.assertIn("OK: 1 narrator lines", self.narrate({"engine": "cmd"}, say, code=0, PLUTARCH_NARRATOR_CMD=cmd))
            self.assertIn("PLUTARCH_NARRATOR_CMD failed", self.narrate({"engine": "cmd"}, say, PLUTARCH_NARRATOR_CMD="false {text} {out}"))
        self.assertIn("sha256:", pathlib.Path(SRC).read_text("utf8").split("tag = ")[1].splitlines()[0])      # what is saved never holds the command

    def test_the_line_is_never_run(self):
        for cmd in ("printf %s {text} > {out}", "true {text}; printf %s {text} > {out} # {text}"):
            for say in ('"; touch RAN; "', "'; touch RAN; '", "$(touch RAN)", "`touch RAN`", "a\ntouch RAN\n", "{out}; touch RAN"):
                self.narrate({"engine": "cmd"}, say=say, PLUTARCH_NARRATOR_CMD=cmd)
                self.assertFalse(self.ran(), (cmd, say)); self.assertEqual(self.made(), [say.encode()], cmd)
                for p in glob.glob(os.path.join(self.proj, "narr", "*")): os.remove(p)

    def test_placeholders_inside_quotes_are_refused(self):
        """In quotes the line would be split, spoken as a variable name, or parsed by a second shell."""
        for cmd in ('sh -c "true {text}" > {out}', "true '{text}' > {out}", 'true {text} > "{out}"'):
            out = self.narrate({"engine": "cmd"}, say="$(touch RAN)", PLUTARCH_NARRATOR_CMD=cmd)
            self.assertIn("inside quotes", out); self.assertFalse(self.ran()); self.assertEqual(self.made(), [])

    # ---- openai ----
    def test_api_key_env_is_refused(self):
        s = self.server()
        out = self.narrate({"engine": "openai", "base_url": f"http://{s.host}", "api_key_env": "OTHER"}, OTHER="canary", PLUTARCH_TTS_HOSTS=f"http://{s.host}")
        self.assertEqual(s.seen, []); self.assertIn("PLUTARCH_TTS_KEY=... PLUTARCH_TTS_HOSTS=", out)

    def test_a_key_goes_only_to_its_own_servers(self):
        for hosts, want in (("", None), ("http://127.0.0.1:1, other.example", None), ("other.example, http://{}", "Bearer canary"), ("HTTP://{}/v1", "Bearer canary"),
                            ("{}", None), ("https://{}", None), ("127.0.0.1", None), ("http://127.0.0.1", None)):
            s = self.server()
            self.narrate({"engine": "openai", "base_url": f"http://{s.host}/v1"}, OPENAI_API_KEY="openai", PLUTARCH_TTS_KEY="canary", PLUTARCH_TTS_HOSTS=hosts.format(s.host))
            self.assertEqual(s.seen, [want], hosts); self.assertEqual(self.made(), [b"wav"])

    def test_a_redirect_never_carries_the_key(self):
        other = self.server(); s = self.server(status=302, to=f"http://{other.host}/x")
        self.narrate({"engine": "openai", "base_url": f"http://{s.host}/v1"}, PLUTARCH_TTS_KEY="canary", PLUTARCH_TTS_HOSTS=f"http://{s.host},http://{other.host}")
        self.assertEqual(s.seen, ["Bearer canary"]); self.assertEqual(other.seen, [None])

    def test_a_server_that_wants_the_key_says_ask_the_user(self):
        for status in (401, 403):
            s = self.server(status=status); proxy = {}
            for proxy in ({}, {"http_proxy": f"http://{s.host}"}):      # the proxy's own name is never the one to list
                host = "tts.example:8880" if proxy else s.host
                out = self.narrate({"engine": "openai", "base_url": f"http://{host}/v1"}, OPENAI_API_KEY="canary", PLUTARCH_TTS_HOSTS="a.example", **proxy)
                self.assertIn(f"PLUTARCH_TTS_HOSTS=a.example,http://{host} python3 scripts/narrate.py", out); self.assertIn("Ask the user", out); self.assertNotIn("canary", out)
            self.assertEqual(s.seen, [None, None])

    def test_base_url_must_be_http(self):
        for base in ("file:///etc/passwd", "ftp://127.0.0.1/x", "URL:file:///etc/passwd", "localhost:8880", "http://"):
            out = self.narrate({"engine": "openai", "base_url": base}, OPENAI_API_KEY="canary")
            self.assertIn("ERROR: narrator.base_url must start with http", out); self.assertNotIn("Traceback", out)

    def test_only_the_real_openai_host_is_trusted(self):
        """No network: the request is caught before it is sent."""
        ns = dict(json=json, os=os, re=re, shlex=shlex, urllib=urllib, die=self.fail)
        for f in ast.parse(pathlib.Path(SRC).read_text("utf8")).body:
            if isinstance(f, ast.FunctionDef) and f.name in ("synth", "key_for", "origin"): exec(compile(ast.Module([f], []), SRC, "exec"), ns)
        good = ("https://api.openai.com/v1", "https://API.openai.com:443/v1/", None)
        bad = ("https://api.openai.com.evil.example/v1", "http://api.openai.com/v1", "https://evil.example/api.openai.com", "https://api.openai.com@evil.example/v1",
               "https://api.openai.com%2eevil.example/v1", "https://evil.example\\@api.openai.com/v1", "https://evil.example#@api.openai.com/v1")
        for base in good + bad:
            with mock.patch("urllib.request.urlopen", side_effect=InterruptedError) as sent, mock.patch.dict(os.environ, {"OPENAI_API_KEY": "canary"}):
                os.environ.pop("PLUTARCH_TTS_HOSTS", None)
                with self.assertRaises(InterruptedError): ns["synth"]("hi", "o.wav", {"engine": "openai", **({"base_url": base} if base else {})})
            self.assertEqual(sent.call_args[0][0].get_header("Authorization"), "Bearer canary" if base in good else None, base)


if __name__ == "__main__":
    unittest.main()
