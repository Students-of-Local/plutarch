"""A fact must be on both of its pages.

qwen3:4b (2026-11-24) wrote a wrong birth year and draft year into story.md with real URLs, and next.py
counted them as sourced because it only counted links."""
import http.server, json, os, shlex, subprocess, sys, threading, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

FAR = "filler " * 200
PAGES = {
    "/a": "<p>Abraham Lincoln was elected president on November 6, 1860, beating three rivals.</p>",
    "/b": "<html><script>var x = 1777</script><b>Lincoln</b> won the 1860 election and became the elected president in November 1860 (the 6th). Day 06.",
    "/noyear": "<p>Lincoln was elected president in November, on day 6 of that month.</p>",
    "/far": f"<p>Lincoln was elected president in November, on day 6. {FAR} A railway opened in 1860.</p>",
    "/other": "<p>Stephen Douglas was not elected president on November 6, 1860.</p>",
}
FACT = "Elected president on November 6, 1860"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path); self.send_response(200 if body else 404); self.end_headers(); self.wfile.write((body or "").encode())
    def log_message(self, *a): pass


class Facts(Project):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler); cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close()

    def kit(self, script, *args, off=False):
        env = dict(os.environ, PLUTARCH_FACTS="off" if off else "", PYTHONPATH=self.stubs)
        r = subprocess.run([sys.executable, os.path.join(KIT, script), *args], cwd=self.proj, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def fact(self, p1, p2, text=FACT, **kw):
        self.film(subject="Abraham Lincoln"); return self.kit("film.py", "fact", text, self.url + p1, self.url + p2, **kw)

    def rows(self): return open(os.path.join(self.proj, "story.md")).read().count("127.0.0.1")

    def test_a_fact_on_both_pages_is_added(self):
        code, out = self.fact("/a", "/b")
        self.assertEqual(code, 0, out); self.assertGreater(self.rows(), 0)

    def test_a_fact_without_numbers(self):
        code, out = self.fact("/a", "/noyear", "Lincoln was elected president in November")
        self.assertEqual(code, 0, out)

    def test_refused_and_not_written(self):
        for page, why in (("/noyear", "it never says 1860"), ("/far", "together"), ("/other", "it never says 'Lincoln'"), ("/gone", "did not open")):
            code, out = self.fact("/a", page)
            self.assertEqual(code, 1, page + out); self.assertIn(why, out); self.assertIn(self.url + page, out)
        code, out = self.fact("/a", "/b", "Elected president on November 6, 1777")      # 1777 is only in a script tag
        self.assertEqual(code, 1, out); self.assertIn("it never says 1777", out)
        self.assertEqual(self.rows(), 0)

    def test_off_is_for_a_person_who_checked(self):
        self.assertEqual(self.fact("/noyear", "/gone", off=True)[0], 0)

    def test_hand_written_rows_are_checked_too(self):
        self.film(subject="Abraham Lincoln"); p = os.path.join(self.proj, "story.md"); s = open(p).read()
        s = s.replace('"He/She/They ____________, it cost ____________, and then ____________."', "He rose from a cabin to the presidency, it cost him, and then he won.")
        good = f"| {{}} | {FACT} | {self.url}/a | {self.url}/b |"; bad = f"| 5 | Elected president in 1859 | {self.url}/a | {self.url}/b |"
        open(p, "w").write(s.replace("| 1 | | | |", "\n".join([good.format(i) for i in range(1, 5)] + [bad])))
        out = self.kit("next.py")[1]
        self.assertIn("STEP 2 of 12: check the facts against their pages", out); self.assertIn("python3 scripts/facts.py", out)
        code, out = self.kit("facts.py")
        self.assertEqual(code, 1); self.assertIn("NOT ON ITS PAGES: fact 5: Elected president in 1859", out)
        fix = next(l for l in out.splitlines() if l.startswith("FIX: "))
        self.assertIn("film.py drop fact 5", fix)
        self.assertEqual(self.kit("film.py", *shlex.split(fix, comments=True)[3:])[0], 0)
        self.assertIn("4 fact rows", self.kit("next.py")[1])        # the good ones stay checked; one more is needed
        self.assertEqual(self.kit("facts.py")[0], 0)


if __name__ == "__main__": unittest.main()
