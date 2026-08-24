#!/usr/bin/env python3
"""Unit tests for scripts/pull_espn_league.py (offline — no network)."""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import pull_espn_league as pl  # noqa: E402


class UrlAndCookies(unittest.TestCase):
    def test_league_url_carries_every_view_the_app_reads(self):
        url = pl.league_url("30578399", "2026")
        self.assertIn("/seasons/2026/segments/0/leagues/30578399?", url)
        for view in ("mDraftDetail", "mTeam", "mRoster", "mSettings"):
            self.assertIn("view=" + view, url)

    def test_swid_braces_are_tolerated_either_way(self):
        with_braces = pl.cookie_header("abc", "{DEAD-BEEF}")
        without = pl.cookie_header("abc", "DEAD-BEEF")
        self.assertEqual(with_braces, without)
        self.assertIn("espn_s2=abc; SWID={DEAD-BEEF}", with_braces)

    def test_envelope_stamps_counts_and_never_cookies(self):
        data = {"teams": [{"id": 1}, {"id": 2}],
                "draftDetail": {"picks": [{}, {}, {}]}}
        env = pl.envelope(data, "30578399", "2026")
        self.assertEqual((env["teams"], env["picks"]), (2, 3))
        self.assertEqual(env["league_id"], "30578399")
        blob = json.dumps(env)
        self.assertNotIn("espn_s2", blob)
        self.assertNotIn("SWID", blob)
        self.assertTrue(env["pulled"])


class MainBehavior(unittest.TestCase):
    def run_main(self, env, argv=("data/x.json",)):
        old_env = dict(os.environ)
        old_argv = sys.argv
        try:
            for k in ("ESPN_S2", "SWID", "ESPN_LEAGUE_ID", "ESPN_SEASON"):
                os.environ.pop(k, None)
            os.environ.update(env)
            sys.argv = ["pull_espn_league.py", *argv]
            return pl.main()
        finally:
            os.environ.clear(); os.environ.update(old_env)
            sys.argv = old_argv

    def test_missing_secrets_is_an_explicit_skip_not_a_failure(self):
        self.assertEqual(self.run_main({}), 0)

    def test_missing_league_id_with_secrets_fails_loudly(self):
        self.assertEqual(self.run_main({"ESPN_S2": "a", "SWID": "b"}), 1)


if __name__ == "__main__":
    unittest.main()
