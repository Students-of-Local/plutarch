"""A fact must be on both of its pages.

qwen3:4b (2026-11-24) wrote a wrong birth year and draft year into story.md with real URLs, and next.py
counted them as sourced because it only counted links."""
import http.server, json, os, shlex, subprocess, sys, threading, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

FAR = "filler " * 200
NAME = "<p>Abraham Lincoln was a lawyer.</p>"
PAGES = {
    "/a": NAME + "<p>He was elected president on November 6, 1860, beating three rivals.</p>",
    "/b": "<script>var x = 1777</script><b>Abraham Lincoln</b> won: on November 06, 1860 he was elected president.",
    "/noyear": NAME + "<p>He was elected president in November, on day 6 of that month.</p>",
    "/far": NAME + f"<p>He was elected president on November 6. {FAR} A railway opened in 1860.</p>",
    "/surname": "<p>Robert Lincoln was not elected president on November 6, 1860.</p>",
    "/noname": "<p>Stephen Douglas was not elected president on November 6, 1860.</p>",
    "/p%C3%A9": NAME + "<p>He was elected president on November 6, 1860.</p>",
    "/born": NAME + "<p>He was born 1947 in Australia.</p>", "/born2": NAME + "<p>He was born 1947 in Australia.</p>",
    "/note": NAME + '<p>Elected president on November 6, 1860.<sup class="reference"><a>[9]</a></sup> He won three states.</p>',
    "/note2": NAME + "<p>Elected president on Nov. 6, 1860. He won 3 states.</p>",
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

    def test_an_accented_address_opens(self):
        self.assertEqual(self.fact("/a", "/p\u00e9")[0], 0)

    def test_a_title_or_suffix_is_not_the_name(self):
        self.film(subject="Dr. Abraham Lincoln Jr.")
        self.assertEqual(self.kit("film.py", "fact", FACT, self.url + "/a", self.url + "/b")[0], 0)

    def test_the_subject_must_be_set_first(self):
        code, out = self.kit("film.py", "fact", FACT, self.url + "/a", self.url + "/b")
        self.assertEqual(code, 1); self.assertIn("film.py set subject", out)

    def test_a_new_subject_is_checked_again(self):
        self.story(*self.GOOD, self.GOOD[0]); self.kit("facts.py")
        self.assertNotIn("check the facts", self.kit("next.py")[1])
        self.film(subject="Stephen Douglas"); self.assertIn("check the facts", self.kit("next.py")[1])

    def test_off_says_nothing_was_checked(self):
        self.assertIn("nothing was checked", self.kit("facts.py", off=True)[1])

    def test_a_fact_without_numbers(self):
        code, out = self.fact("/a", "/noyear", "Elected president in November")
        self.assertEqual(code, 0, out)

    def test_refused_and_not_written(self):
        for page, why in (("/noyear", "it never says 1860"), ("/far", "together"), ("/noname", "it never says 'Abraham Lincoln'"),
                          ("/surname", "it never says 'Abraham Lincoln'"), ("/gone", "did not open")):
            code, out = self.fact("/a", page)
            self.assertEqual(code, 1, page + out); self.assertIn(why, out); self.assertIn(self.url + page, out)
        for text, why in (("Elected president on November 6, 1777", "it never says 1777"),      # 1777 is only in a script tag
                          ("Elected president on November 9, 1860", "it never says 9"),         # a one-digit day by its month
                          ("Elected governor of Florida on November 6, 1860", "it never says florida"),
                          ("Won 3 Nobel prizes", "it never says nobel"), ("Elected president on November 60, 1860", "60")):
            code, out = self.fact("/a", "/b", text)
            self.assertEqual(code, 1, text + out); self.assertIn(why, out)
        self.assertIn("it never says austria", self.fact("/born", "/born2", "Born 1947 in Austria")[1])
        for text in ("Elected president on October 6, 1860", "Elected president on Oct 6, 1860", "Elected president on November 9, 1860",
                     "Won two states in 1860"):                                                   # 9 is only a footnote; three states, not two
            self.assertEqual(self.fact("/note", "/note2", text)[0], 1, text)
        for p in ("/a", "/a#early-life", "/a/"): self.assertIn("same URL", self.fact("/a", p)[1])
        self.assertEqual(self.rows(), 0)

    def test_off_is_for_a_person_who_checked(self):
        self.assertEqual(self.fact("/noyear", "/gone", off=True)[0], 0)

    def story(self, *lines, tail="\n"):
        self.film(subject="Abraham Lincoln"); p = os.path.join(self.proj, "story.md")
        self.blank = s = getattr(self, "blank", None) or open(p).read()
        s = s.replace('"He/She/They ____________, it cost ____________, and then ____________."', "He rose from a cabin to the presidency, it cost him, and then he won.")
        a = s.index("| 1 | | | |")
        open(p, "w").write(s[:a] + "\n".join(lines).replace("U", self.url) + tail)

    GOOD = [f"| {i} | {FACT} | U/a | U/b |" for i in range(1, 5)]

    def test_hand_written_rows_are_checked_too(self):
        for bad in ("| 5 | Elected president in 1859 | U/a | U/b |", "| 5. | Elected president in 1859 | U/a | U/b |",
                    "| Elected president in 1859 | U/a | U/b |",
                    "| 5 | Elected president in 1859 | [a](U/a) | [b](U/b) |"):
            for tail in ("\n", ""):                                                                 # the last line of the file
                self.story(*self.GOOD, bad, tail=tail)
                self.assertIn("STEP 2 of 12: check the facts against their pages", self.kit("next.py")[1])
                code, out = self.kit("facts.py")
                self.assertEqual(code, 1, bad); self.assertIn("NOT ON ITS PAGES: fact 5: Elected president in 1859", out)
                fix = next(l for l in out.splitlines() if l.startswith("FIX: "))
                self.assertEqual(self.kit("film.py", *shlex.split(fix, comments=True)[3:])[0], 0)
                self.assertIn("4 fact rows", self.kit("next.py")[1], bad)      # the good ones stay checked; one more is needed
                self.assertEqual(self.kit("facts.py")[0], 0)

    def test_the_drop_line_names_the_wrong_row(self):
        """A one-URL row above a bad row made the number off by one and dropped a good fact."""
        self.story("| 1 | Elected president in 1860 | U/a |", self.GOOD[1], "| 3 | Elected president in 1859 | U/a | U/b |")
        out = self.kit("facts.py")[1]
        fixes = [l for l in out.splitlines() if l.startswith("FIX: ")]
        self.assertEqual([shlex.split(f, comments=True)[5] for f in fixes], ["3", "1"], out)
        for f in fixes: self.assertEqual(self.kit("film.py", *shlex.split(f, comments=True)[3:])[0], 0)
        left = open(os.path.join(self.proj, "story.md")).read()
        self.assertIn(FACT, left); self.assertNotIn("1859", left)

    def test_rows_anywhere_are_checked(self):
        for bad in (["", "| 6 | Elected president in 1859 | U/a | U/b |"], ["  | 6 | Elected president in 1859 | U/a | U/b |"],
                    ["6 | Elected president in 1859 | U/a | U/b", self.GOOD[0]], ["| 6 | Elected president in 1859 | Wikipedia | a book |"],
                    ["", "## Beats", "| # | Beat |", "|---|---|", "| 1 | Title |", "", "| 6 | Elected president in 1859 | U/a | U/b |"],
                    ["", "| Fact | One | Two |", "|---|---|---|", "| Elected president in 1859 | U/a | U/b |"],
                    ["| 6 | Elected president in 1859 | U/a | U/b |", "|---|---|"], ["| 6 | Elected president in 1859 | Wikipedia | a book |", "---"],
                    ["| 6 | Date | Elected president in 1859 | U/a | U/b |"], ["| 6 | Elected president in 1859 | U/a,U/b |"]):
            self.story(*self.GOOD, self.GOOD[0], *bad)
            code, out = self.kit("facts.py"); self.assertEqual(code, 1, bad)
            fixes = [l for l in out.splitlines() if l.startswith("FIX: ")]; self.assertEqual(len(fixes), 1, out)
            self.kit("film.py", *shlex.split(fixes[0], comments=True)[3:]); self.assertEqual(self.kit("facts.py")[0], 0, bad)
            left = open(os.path.join(self.proj, "story.md")).read()
            self.assertNotIn("1859", left); self.assertGreaterEqual(left.count(FACT), 5)

    def test_true_rows_pass_in_any_form(self):
        self.story(f"| 1 | {FACT} | [a](U/a) | [b](U/b) |", f"| 2 | {FACT} | <U/a> | <U/b> |", f"| 3. | {FACT} | U/a, U/b |", tail="")
        code, out = self.kit("facts.py"); self.assertEqual(code, 0, out); self.assertEqual(out.count("OK: fact"), 3)

    def test_added_facts_need_no_second_check(self):
        for n, day in enumerate(("November 6, 1860", "Nov 6, 1860", "November 6 in 1860", "6 November 1860", "November 1860"), 1):
            code, out = self.fact("/a", "/b", f"Elected president on {day}"); self.assertEqual(code, 0, day)
            self.assertIn(f"{5 - n} more to add" if n < 5 else "Next: python3 scripts/next.py", out)    # qwen3:4b stopped after a bare OK
        self.assertEqual(len(__import__("re").findall("(?m)^\\| [1-5] \\| Elected", open(os.path.join(self.proj, "story.md")).read())), 5)
        self.kit("film.py", "sentence", "He rose from a cabin to the presidency, it cost him, and then he won.")
        self.assertIn("STEP 3 of 12", self.kit("next.py")[1])

    def test_a_dead_network_drops_nothing(self):
        self.story(*[g.replace("U", "http://127.0.0.1:9") for g in self.GOOD])
        code, out = self.kit("facts.py")
        self.assertEqual(code, 1); self.assertIn("NOT CHECKED", out); self.assertIn("again", out)
        self.assertFalse([l for l in out.splitlines() if l.startswith("FIX: ") and "film.py drop" in l], out)


if __name__ == "__main__": unittest.main()
