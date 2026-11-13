import unittest
from unittest import mock

import sources
import watcher
from filters import evaluate
from models import Job


def job(title="Junior Backend Engineer", location="Remote - Worldwide", text="Python, Django and REST APIs.", remote=None):
    return Job("greenhouse", "acme", "1", title, location, remote, "https://x/1", text)


class FilterTests(unittest.TestCase):
    def reasons(self, **kw):
        return evaluate(job(**kw)).reasons

    def test_good_job_is_kept_and_scored(self):
        r = evaluate(job())
        self.assertTrue(r.keep, r.reasons)
        self.assertGreater(r.score, 4)

    def test_plain_remote_with_fully_remote_text(self):
        r = evaluate(job(location="", text="We are fully remote. Python and Docker."))
        self.assertTrue(r.keep, r.reasons)

    def test_us_work_authorization(self):
        rs = self.reasons(location="Remote - US", text="You must be legally authorized to work in the United States.")
        self.assertIn("work_auth_us", rs)
        self.assertIn("region_restricted", rs)

    def test_us_based_only(self):
        self.assertIn("us_only", self.reasons(text="US based applicants only."))

    def test_clearance(self):
        self.assertIn("clearance", self.reasons(text="Active Secret Clearance required."))

    def test_no_sponsorship(self):
        self.assertIn("no_sponsorship", self.reasons(text="We are unable to provide visa sponsorship."))
        self.assertIn("no_sponsorship", self.reasons(text="This role is not eligible for immigration sponsorship."))

    def test_onsite_only_and_not_remote(self):
        rs = self.reasons(location="Madison, WI", text="Apply today ON SITE ONLY.")
        self.assertIn("onsite_only", rs)
        self.assertIn("not_remote", rs)

    def test_hybrid_flag(self):
        self.assertIn("hybrid_or_onsite", self.reasons(location="Remote / Hybrid", remote=True))

    def test_senior_and_role(self):
        self.assertIn("senior_title", self.reasons(title="Senior Backend Engineer"))
        self.assertIn("role_mismatch", self.reasons(title="Marketing Manager"))

    def test_years_of_experience(self):
        self.assertIn("experience_years", self.reasons(text="Requires 3+ years of professional experience."))
        self.assertNotIn("experience_years", self.reasons(text="Founded 10 years ago."))

    def test_region_markers_are_allowed(self):
        self.assertTrue(evaluate(job(location="Remote - Worldwide")).keep)
        self.assertIn("region_restricted", self.reasons(location="Remote (EMEA)"))  # filters.py: only worldwide markers are open
        self.assertIn("region_restricted", self.reasons(location="Remote - Canada"))


class SourceTests(unittest.TestCase):
    def test_greenhouse_html_is_stripped(self):
        fake = {"jobs": [{"id": 7, "title": "Backend Engineer", "location": {"name": "Remote"},
                          "absolute_url": "https://u", "content": "&lt;p&gt;Fully remote &amp;amp; fun&lt;/p&gt;"}]}
        with mock.patch.object(sources, "_get", return_value=fake):
            (j,) = list(sources.fetch_greenhouse("acme"))
        self.assertEqual(j.text, "Fully remote & fun")
        self.assertEqual(j.job_id, "7")

    def test_lever_and_ashby_mapping(self):
        lever = [{"id": "a", "text": "Junior Python Dev", "categories": {"location": "Remote"},
                  "workplaceType": "remote", "hostedUrl": "https://l", "descriptionPlain": "Python"}]
        ashby = {"jobs": [{"id": "b", "title": "Data Engineer", "location": "Anywhere", "isRemote": True,
                           "jobUrl": "https://a", "descriptionPlain": "SQL"}]}
        with mock.patch.object(sources, "_get", return_value=lever):
            (l,) = list(sources.fetch_lever("x"))
        with mock.patch.object(sources, "_get", return_value=ashby):
            (a,) = list(sources.fetch_ashby("y"))
        self.assertIs(l.remote, True)
        self.assertIs(a.remote, True)


class WatcherTests(unittest.TestCase):
    def test_dedup_filter_and_alert_cap(self):
        good = job()
        bad = Job("greenhouse", "acme", "2", "Junior Backend Engineer", "Remote - US", None, "https://x/2",
                  "Must be authorized to work in the United States")
        sent = []
        with mock.patch.object(sources, "fetch", return_value=iter([good, bad])), \
             mock.patch.object(watcher.notify, "send", side_effect=sent.append), \
             mock.patch.object(watcher.time, "sleep"):
            s1 = watcher.run_check([{"source": "greenhouse", "name": "acme"}], db_path=":memory:")
        self.assertEqual((s1["new"], s1["kept"], s1["excluded"]), (2, 1, 1))
        self.assertEqual(len(sent), 1)

    def test_second_run_sends_nothing_new(self):
        import storage
        conn_path = ":memory:"  # separate memory DB per connect, so test via real file
        import os, tempfile
        path = os.path.join(tempfile.mkdtemp(), "s.db")
        sent = []
        for _ in range(2):
            with mock.patch.object(sources, "fetch", return_value=iter([job()])), \
                 mock.patch.object(watcher.notify, "send", side_effect=sent.append), \
                 mock.patch.object(watcher.time, "sleep"):
                watcher.run_check([{"source": "greenhouse", "name": "acme"}], db_path=path)
        self.assertEqual(len(sent), 1)

    def test_broken_board_does_not_stop_run(self):
        def boom(*a):
            raise RuntimeError("404")
        with mock.patch.object(sources, "fetch", side_effect=boom), mock.patch.object(watcher.time, "sleep"):
            s = watcher.run_check([{"source": "lever", "name": "nope"}], db_path=":memory:")
        self.assertEqual(s["errors"], 1)

    def test_404_board_is_skipped_next_time(self):
        import os, tempfile, requests
        path = os.path.join(tempfile.mkdtemp(), "s.db")
        resp = requests.Response(); resp.status_code = 404
        calls = []
        def boom(*a):
            calls.append(a); raise requests.HTTPError("404", response=resp)
        entry = [{"source": "lever", "name": "gone"}]
        for _ in range(2):
            with mock.patch.object(sources, "fetch", side_effect=boom), mock.patch.object(watcher.time, "sleep"):
                s = watcher.run_check(entry, db_path=path)
        self.assertEqual(len(calls), 1)
        self.assertEqual(s["skipped_dead"], 1)

    def test_many_boards_in_parallel(self):
        boards = [{"source": "ashby", "name": f"c{i}"} for i in range(30)]
        def fake(src, name):
            return iter([Job("ashby", name, "1", "Junior Backend Engineer", "Remote - Worldwide", None, "u", "Python")])
        with mock.patch.object(sources, "fetch", side_effect=fake), \
             mock.patch.object(watcher.notify, "send"), mock.patch.object(watcher.time, "sleep"):
            s = watcher.run_check(boards, db_path=":memory:")
        self.assertEqual((s["fetched"], s["kept"], s["errors"]), (30, 30, 0))


if __name__ == "__main__":
    unittest.main()
