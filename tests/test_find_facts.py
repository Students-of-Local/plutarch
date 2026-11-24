"""find_facts.py prints film.py fact commands that run, and only for facts on two independent pages.

qwen3:4b (2026-11-24) made 105 film.py fact calls and none was accepted: its search gave it only video pages."""
import http.server, json, os, re, subprocess, sys, threading, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_next import Project, KIT

sys.path.insert(0, KIT)
import find_facts

WIKI = """<table class="infobox"><tr><td>Born <span class="bday">1809-02-12</span> February 12, 1809<li>Wrestling Hall of Fame (1992)</li></td></tr></table>
<p>Abraham Lincoln was a lawyer.<sup class="reference"><a href="#n">[1]</a></sup> In 1860, Lincoln was elected president, beating three rivals in a close race.</p>
<p>Lincoln moved to Springfield in 1837. He proposed to her in 1842. Lincoln planned a trip in 1863, but stayed home.
The bill passed and Lincoln signed the Homestead Act in 1862 at his desk in the White House after lunch.</p>
<a href="{u}/bio">1</a> <a href="{u}/copy">2</a> <a href="{u}/other">3</a> <a href="{u}/gone">4</a>"""
LINCOLN = "<p>Abraham Lincoln was born on February 12, 1809.</p>"
BIO = LINCOLN + """<p>Lincoln was elected president in 1860. He proposed to her in 1842. He planned a trip in 1863. He moved to Springfield in 1837.
 The Wrestling Hall of Fame listed this honor in 1992. </p> <p>Lincoln joined the army in 1832.</p>"""
COPY = LINCOLN + """<p>The bill passed and Lincoln signed the Homestead Act in 1862 at his desk in the White House after lunch.</p>"""
OTHER = "<p>Stephen Douglas moved to Springfield in 1837. Lincoln was elected president in 1860.</p>"


class Handler(http.server.BaseHTTPRequestHandler):
    seen = []
    def do_GET(self):
        u = f"http://127.0.0.1:{self.server.server_port}"; Handler.seen.append(self.path)
        body = {"/wiki": WIKI.replace("{u}", u), "/bio": BIO, "/copy": COPY, "/other": OTHER}.get(self.path)
        self.send_response(200 if body else 404); self.end_headers(); self.wfile.write((body or "").encode())
    def log_message(self, *a): pass


class FindFacts(Project):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler); cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close()

    def find(self, *args, who="Abraham Lincoln"):
        self.film(subject=who); Handler.seen.clear()
        env = dict(os.environ, SEARXNG_URL=self.url + "/nosearch", PLUTARCH_FACTS="", PYTHONPATH=self.stubs)
        r = subprocess.run([sys.executable, os.path.join(KIT, "find_facts.py"), *args], cwd=self.proj, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def found(self, out): return re.findall(r'film\.py fact "([^"]+)"', out)

    def test_every_printed_command_is_accepted(self):
        code, out = self.find(self.url + "/wiki"); self.assertEqual(code, 0, out)
        got = self.found(out)
        self.assertIn("Abraham Lincoln was born on February 12, 1809.", got, out)
        self.assertIn("In 1860, Lincoln was elected president.", got, out)          # cut at the clause the second page does not have
        self.assertIn("Lincoln moved to Springfield in 1837.", got)
        self.assertTrue(out.count(f'"{self.url}/bio"') >= 3 and "/other" not in out, out)   # /other never names the person in full
        for l in (l.strip() for l in out.splitlines() if "film.py fact" in l):
            r = subprocess.run(["bash", "-c", l.replace("python3 scripts/film.py", f"{sys.executable} {os.path.join(KIT, 'film.py')}")],
                               capture_output=True, text=True, env=dict(os.environ, PLUTARCH_FACTS=""))
            self.assertEqual(r.returncode, 0, l + r.stdout + r.stderr)
        code, again = self.find(self.url + "/wiki")                                  # nothing is read twice, and added facts are gone
        self.assertEqual((Handler.seen, self.found(again)), ([], []), again); self.assertIn("No more facts", again)

    def test_a_pronoun_is_never_swapped_and_a_but_is_never_cut(self):
        """A draft turned "He proposed to her on December 10, 2016" into "Williams proposed to her"."""
        got = " ".join(self.found(self.find(self.url + "/wiki")[1]))
        self.assertNotIn("proposed", got); self.assertNotIn("trip in 1863.", got)
        self.assertEqual(find_facts.variants("Lincoln planned a trip in 1863, but he never went there.", "Lincoln"),
                         ["Lincoln planned a trip in 1863, but he never went there."])

    def test_a_copy_of_the_article_is_not_a_second_page(self):
        self.assertNotIn("Homestead", " ".join(self.found(self.find(self.url + "/wiki")[1])))

    def test_the_wrong_person(self):
        code, out = self.find(self.url + "/wiki", who="Mary Todd")
        self.assertEqual(code, 1); self.assertIn('find_audio.py web "Mary Todd biography"', out)

    def test_a_subject_is_needed_first(self):
        code, out = self.find(who="<<FULL NAME>>"); self.assertEqual(code, 1); self.assertIn("film.py set subject", out)

    def test_fragments_are_left_out(self):
        for s in ("In 1977, after Jobs co-founded Apple, he left.", "Jobs, who co-founded Apple in 1976, smiled at them.", "After the 2007 season, Jobs was recognized as a star."):
            for v in find_facts.variants(s, "Jobs"): self.assertNotIn(v, ("In 1977, after Jobs co-founded Apple.", "Jobs, who co-founded Apple in 1976.", "After the 2007 season, Jobs was recognized."))
        self.assertEqual(find_facts.variants('Jobs was named "boss" in 1977 by $5 men.', "Jobs"), [])      # it must survive a shell

    def test_a_first_is_kept_whole(self):
        """A draft cut "won her first singles title as a mother" after "title"."""
        s = "In January 2020, Williams won her first singles title, beating the field, after a long wait."
        self.assertEqual(find_facts.variants(s, "Williams"), [s])

    def test_whole_sentences_only(self):
        for text, want in (("In 2013, Ginsburg dissented in Shelby County v. Holder over voting rights.", ["In 2013, Ginsburg dissented in Shelby County v. Holder over voting rights."]),
                           ("Friends saw St. Mark's Church where Ginsburg was baptized in 1899.", ["Friends saw St. Mark's Church where Ginsburg was baptized in 1899."]),
                           ("PARIS; Ruth Ginsburg has pulled out of three events in 2005.", []), ("In 1966, the year Ruth Ginsburg died.", []), ("Ruth Ginsburg, photographed in 1951.", []), ("In a 1995 interview, Ginsburg said:", []), ("In 2010, Martin Ginsburg died of cancer.", []), ("A second, Ginsburg: My Life, appeared in 1997.", [])):
            art = find_facts.Article(); art.paras = [text]
            self.assertEqual(find_facts.sentences(art, "Ruth Bader Ginsburg"), want, text)

    def test_timeline_sites_are_skipped(self):
        for u in ("https://populartimelines.com/x", "https://www.timetoast.com/x"): self.assertTrue(find_facts.SKIP.search(u), u)

    def test_a_relative_is_not_the_subject(self):
        for s in ("Albert Lewis died in 1929.", "In 2013, Warren Lewis moved out."): self.assertFalse(find_facts.about(s, "C. S. Lewis"), s)
        for s in ("C. S. Lewis died in 1963.", "Lewis wrote to Albert Lewis in 1917.", "In 1956 Lewis married.", "When Lewis left in 1917, he wrote.", "Professor Lewis spoke in 1950."):
            self.assertTrue(find_facts.about(s, "C. S. Lewis"), s)

    def test_one_page_names_the_finder(self):
        """qwen3:4b gave film.py fact one URL about 15 times and read only the usage line."""
        self.film(subject="Abraham Lincoln")
        r = subprocess.run([sys.executable, os.path.join(KIT, "film.py"), "fact", "He won in 1860.", "https://a.test"], cwd=self.proj, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("gave one page", r.stdout); self.assertIn("scripts/find_facts.py", r.stdout)

    def test_step_2_starts_with_the_finder(self):
        self.film(subject="Abraham Lincoln"); out = self.run_next()
        self.assertIn("STEP 2 of 12", out); self.assertLess(out.index("scripts/find_facts.py"), out.index("find_audio.py web"))


if __name__ == "__main__": unittest.main()
