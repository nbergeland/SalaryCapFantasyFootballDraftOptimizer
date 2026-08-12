#!/usr/bin/env python3
"""Unit tests for scripts/build_data.py.

Everything runs in ``--fixtures-dir`` mode against the committed JSONs in
tests/fixtures/, so the suite needs no network (and no ``requests``).

    python3 -m unittest discover -s tests -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import build_data as bd  # noqa: E402

FIXTURES = os.path.join(REPO, "tests", "fixtures")
INDEX = os.path.join(REPO, "index.html")

# tiny pool, so the production floor of 450 is out of reach here
SMALL = dict(min_players=5)


def build_fixture(fixtures_dir=FIXTURES, as_of="2026-08-12"):
    return bd.build(2026, fixtures_dir=fixtures_dir, as_of=as_of)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def by_name(players, name):
    for p in players:
        if p["name"] == name:
            return p
    return None


class NormalizationParity(unittest.TestCase):
    """norm_name must agree with normName() in index.html character for
    character — the expectations below were produced by running the JS
    implementation over the same inputs under node."""

    JS_TABLE = [
        ("Ja'Marr Chase", "jamarrchase"),
        ("Amon-Ra St. Brown", "amonrastbrown"),
        ("Marvin Harrison Jr.", "marvinharrison"),
        ("Kenneth Walker III", "kennethwalker"),
        ("A.J. Brown", "ajbrown"),
        ("D.K. Metcalf", "dkmetcalf"),
        ("Michael Wilson", "michaelwilson"),
        ("Odell Beckham Jr", "odellbeckham"),
        ("Steve Smith Sr.", "stevesmith"),
        ("Robert Griffin III", "robertgriffin"),
        ("Seahawks D/ST", "seahawksdst"),
        ("49ers D/ST", "ersdst"),          # digits are stripped, as in the JS
        ("Chris Godwin", "chrisgodwin"),
        ("Vikings D/ST", "vikingsdst"),
        ("Irv Smith Jr.", "irvsmith"),
        ("Michael Pittman Jr.", "michaelpittman"),
        ("Travis Etienne Jr.", "travisetienne"),
        ("Marquise Brown", "marquisebrown"),
        ("Deebo Samuel Sr.", "deebosamuel"),
        ("Brian Thomas Jr.", "brianthomas"),
        ("Calvin Ridley", "calvinridley"),
        ("Ivan Pace Jr.", "ivanpace"),
        ("Jeff Wilson", "jeffwilson"),
        ("Kyle Pitts Sr.", "kylepitts"),
    ]

    def test_norm_name_matches_js(self):
        for raw, want in self.JS_TABLE:
            self.assertEqual(bd.norm_name(raw), want, raw)

    def test_norm_name_folds_diacritics(self):
        # FFC writes accented names Sleeper spells plain; a bare non-[a-z]
        # strip made "Piñeiro" into "pieiro" and the match missed (seen on
        # the first live build). The JS never sees both spellings at once,
        # so the fold is Python-only and deliberately beyond parity.
        self.assertEqual(bd.norm_name("Eddy Piñeiro"), "eddypineiro")
        self.assertEqual(bd.norm_name("Eddy Pineiro"), "eddypineiro")

    def test_norm_pos(self):
        cases = {"QB": "QB", "qb": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
                 "K": "K", "PK": "K", "DEF": "DST", "DST": "DST", "D/ST": "DST",
                 "D": "DST", "Defense": "DST", "": None, "P": None, "LB": None}
        for raw, want in cases.items():
            self.assertEqual(bd.norm_pos(raw), want, raw)

    def test_canon_team_aliases(self):
        self.assertEqual(bd.canon_team("JAC"), "JAX")
        self.assertEqual(bd.canon_team("WSH"), "WAS")
        self.assertEqual(bd.canon_team("wsh"), "WAS")
        self.assertEqual(bd.canon_team("OAK"), "LV")
        self.assertEqual(bd.canon_team("SEA"), "SEA")
        self.assertEqual(bd.canon_team(""), "")
        self.assertEqual(bd.canon_team("FA"), "")     # free agents carry no team

    def test_pkey_dst_is_team_only(self):
        # D/ST rows are matched by team, never by name spelling
        self.assertEqual(bd.pkey("Seahawks D/ST", "DST", "SEA"),
                         bd.pkey("Seattle Seahawks", "DST", "SEA"))
        self.assertEqual(bd.dst_name("SEA"), "Seahawks D/ST")
        self.assertEqual(bd.dst_name("WAS"), "Commanders D/ST")


class FixtureBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.status, cls.report = build_fixture()
        cls.players = cls.data["players"]

    def test_all_sources_ok(self):
        self.assertEqual(set(self.status.values()), {"ok"})
        self.assertEqual(self.data["meta"]["degraded"], [])

    def test_michael_wilson_present(self):
        """The canary: absent from the hand-curated 190-player snapshot."""
        mw = by_name(self.players, "Michael Wilson")
        self.assertIsNotNone(mw)
        self.assertEqual((mw["pos"], mw["team"]), ("WR", "ARI"))
        self.assertEqual(mw["src"], "sleeper+espn+ffc")

    def test_stat_keys_are_what_the_app_scores(self):
        for p in self.players:
            for k in (p.get("stats") or {}):
                self.assertIn(k, bd.STAT_KEYS, f"{p['name']} has stat key {k}")
        allen = by_name(self.players, "Josh Allen")
        # Sleeper's pass_int is remapped to the app's "int"
        self.assertEqual(allen["stats"]["int"], 11.0)
        self.assertNotIn("pass_int", allen["stats"])

    def test_suffix_and_apostrophe_names_match_across_sources(self):
        for name in ("Kenneth Walker III", "Ja'Marr Chase", "Amon-Ra St. Brown",
                     "Marvin Harrison Jr."):
            p = by_name(self.players, name)
            self.assertIsNotNone(p, name)
            # matched in all three sources rather than duplicated
            self.assertTrue(p["src"].startswith("sleeper+espn+ffc"), (name, p["src"]))
            dupes = [q for q in self.players if bd.norm_name(q["name"]) ==
                     bd.norm_name(name) and q["pos"] == p["pos"]]
            self.assertEqual(len(dupes), 1, f"{name} duplicated: {dupes}")

    def test_no_signal_row_is_dropped(self):
        self.assertIsNone(by_name(self.players, "Ricky Pearsall"))
        self.assertEqual(self.report["sleeper_dropped_no_signal"], 1)

    def test_espn_only_player_inside_rank_300_is_added(self):
        tw = by_name(self.players, "Tyler Warren")
        self.assertIsNotNone(tw)
        self.assertEqual(tw["src"], "espn")
        self.assertEqual(tw["ecr"], 95)

    def test_espn_only_player_outside_rank_300_is_reported_not_added(self):
        self.assertIsNone(by_name(self.players, "Deep Bench Wideout"))
        self.assertTrue(any("Deep Bench Wideout" in s
                            for s in self.report["espn_unmatched"]))

    def test_ffc_only_player_with_adp_is_added(self):
        eg = by_name(self.players, "Emeka Egbuka")
        self.assertIsNotNone(eg)
        self.assertEqual(eg["adp"], 92.4)
        self.assertEqual(eg["src"], "ffc (aav est)")

    def test_team_priority_sleeper_over_espn(self):
        ds = by_name(self.players, "Deebo Samuel")
        self.assertEqual(ds["team"], "WAS")           # ESPN still says SF
        self.assertTrue(any("Deebo Samuel" in m for m in self.report["team_mismatches"]))

    def test_ffc_team_alias_is_normalized(self):
        # FFC lists Deebo as WSH; after aliasing it agrees with Sleeper, so the
        # only disagreement recorded for him is ESPN's
        line = [m for m in self.report["team_mismatches"] if "Deebo" in m][0]
        self.assertIn("ffc=WAS", line)

    def test_projection_blend_and_split_flag(self):
        jt = by_name(self.players, "Jonathan Taylor")
        self.assertAlmostEqual(jt["pts"], 0.6 * 314.0 + 0.4 * 214.0, places=1)
        self.assertIn("projection split", jt["note"])
        chase = by_name(self.players, "Ja'Marr Chase")
        self.assertNotIn("projection split", chase["note"])   # 373 vs 366 is fine

    def test_negative_projection_is_clamped_to_zero(self):
        # Sleeper really does this: return specialists (e.g. Derius Davis)
        # project slightly negative in offense-only scoring, which tripped the
        # pts >= 0 validation gate on the first live build.
        recs = {"x": {"sleeper_pts": -0.9, "espn_pts": None, "flags": [], "name": "X", "pos": "WR"}}
        bd.blend_projections(recs, {})
        self.assertEqual(recs["x"]["pts"], 0.0)
        recs = {"x": {"sleeper_pts": -0.9, "espn_pts": 4.0, "flags": [], "name": "X", "pos": "WR"}}
        bd.blend_projections(recs, {})
        self.assertAlmostEqual(recs["x"]["pts"], 0.4 * 4.0, places=1)

    def test_adp_is_median_of_sleeper_and_ffc(self):
        bijan = by_name(self.players, "Bijan Robinson")
        self.assertAlmostEqual(bijan["adp"], (1.4 + 1.6) / 2, places=2)

    def test_ecr_prefers_espn_rank_then_search_rank(self):
        self.assertEqual(by_name(self.players, "Bijan Robinson")["ecr"], 1)
        # nobody at ESPN has Jake Bates, so Sleeper's search_rank carries it
        self.assertEqual(by_name(self.players, "Jake Bates")["ecr"], 190)

    def test_injury_status_lands_in_note(self):
        self.assertIn("Sleeper: Questionable", by_name(self.players, "Puka Nacua")["note"])

    def test_byes_applied_from_espn(self):
        self.assertEqual(by_name(self.players, "Michael Wilson")["bye"], 8)   # ARI
        self.assertEqual(by_name(self.players, "Josh Allen")["bye"], 7)       # BUF

    def test_aav_prefers_espn_and_floors_at_one(self):
        self.assertEqual(by_name(self.players, "Bijan Robinson")["aav"], 62)
        self.assertEqual(by_name(self.players, "Ja'Marr Chase")["aav"], 60)
        self.assertTrue(all(p["aav"] >= 1 for p in self.players))
        self.assertTrue(all(isinstance(p["aav"], int) for p in self.players))
        # ESPN never priced him, so his dollar value is model-derived and says so
        self.assertIn("aav est", by_name(self.players, "Emeka Egbuka")["src"])
        self.assertIsNotNone(self.report["aav_mae_vs_espn"])

    def test_all_32_dsts_present_with_canonical_names(self):
        dst = [p for p in self.players if p["pos"] == "DST"]
        self.assertEqual(len(dst), 32)
        names = {p["name"] for p in dst}
        # the names the current bundle already uses — keeps playerId stable
        for n in ("Seahawks D/ST", "Rams D/ST", "Texans D/ST", "Eagles D/ST"):
            self.assertIn(n, names)
        self.assertEqual({p["team"] for p in dst}, set(bd.NFL_TEAMS))

    def test_news_is_generated_from_live_signal(self):
        news = self.data["news"]
        self.assertTrue(news)
        self.assertLessEqual(len(news), 25)
        self.assertTrue(any("Puka Nacua" in n and "Questionable" in n for n in news))
        self.assertTrue(all(isinstance(n, str) for n in news))

    def test_meta_carries_attribution(self):
        self.assertIn("Fantasy Football Calculator", self.data["meta"]["attribution"])
        self.assertEqual(self.data["meta"]["asOf"], "2026-08-12")

    def test_bundle_passes_its_own_validation(self):
        bd.validate(self.data, 5, ["Michael Wilson|WR", "Seahawks D/ST|DST"])


class Cutoff(unittest.TestCase):
    def test_keeps_ranked_players_and_trims_by_consensus(self):
        recs = {}
        for i in range(700):
            r = bd.new_record(f"Player {i}", "WR", "SF")
            r["pts"] = 300 - i * 0.1
            r["adp"] = float(i + 1) if i < 500 else None
            r["ecr"] = i + 1 if i < 500 else None
            r["espn_rank"] = None
            r["aav"] = 1
            recs[f"k{i}"] = r
        kept = bd.apply_cutoff(recs, {}, top_n=600, top_k=24)
        self.assertEqual(len(kept), 600)
        # everyone with an ADP survives regardless of the top-N line
        self.assertTrue(all(r["adp"] is not None for r in kept[:500]))

    def test_placeholder_adp_and_deep_espn_ranks_do_not_defeat_the_cutoff(self):
        # The first live build kept all 3219 rows: Sleeper stamps 999-style
        # adp defaults on nearly every projection row, and ESPN ranks ~1000
        # players. Neither is a reason to keep someone.
        recs = {}
        for i in range(1000):
            r = bd.new_record(f"Player {i}", "WR", "SF")
            r["pts"] = 300 - i * 0.1
            r["adp"] = 999.0            # placeholder ADP for everyone
            r["ecr"] = None
            r["espn_rank"] = i + 1 if i < 900 else None   # deep ESPN ranks
            r["aav"] = 1
            recs[f"k{i}"] = r
        kept = bd.apply_cutoff(recs, {}, top_n=600, top_k=24)
        self.assertEqual(len(kept), 600)

    def test_ingest_nulls_out_placeholder_sleeper_adp(self):
        raw = {
            "sleeper_players": {"1": {"full_name": "Deep Guy", "position": "WR",
                                       "team": "SF", "search_rank": 2500}},
            "sleeper_projections": [
                {"player_id": "1",
                 "player": {"player_id": "1", "full_name": "Deep Guy",
                            "position": "WR", "team": "SF"},
                 "team": "SF",
                 "stats": {"rec": 5.0, "rec_yd": 40.0, "pts_ppr": 9.0,
                           "adp_ppr": 999.0}},
            ],
        }
        recs, _ = bd.ingest_sleeper(raw, {})
        rec = next(r for r in recs.values() if r["name"] == "Deep Guy")
        self.assertIsNone(rec["sleeper_adp"])

    def test_all_dsts_and_top_kickers_survive_a_tiny_top_n(self):
        data, _s, _r = build_fixture()
        self.assertEqual(len([p for p in data["players"] if p["pos"] == "DST"]), 32)
        self.assertEqual(len([p for p in data["players"] if p["pos"] == "K"]), 3)


class OutageMatrix(unittest.TestCase):
    """Sleeper is load-bearing; ESPN and FFC are allowed to disappear."""

    def _subset(self, drop):
        tmp = tempfile.mkdtemp()
        for f in os.listdir(FIXTURES):
            if f not in drop:
                shutil.copy(os.path.join(FIXTURES, f), os.path.join(tmp, f))
        self.addCleanup(shutil.rmtree, tmp)
        return tmp

    def test_missing_sleeper_players_aborts(self):
        with self.assertRaises(bd.SourceError):
            build_fixture(self._subset({"sleeper_players.json"}))

    def test_missing_sleeper_projections_aborts(self):
        with self.assertRaises(bd.SourceError):
            build_fixture(self._subset({"sleeper_projections.json"}))

    def test_missing_espn_degrades(self):
        data, status, _r = build_fixture(self._subset({"espn_kona.json"}))
        self.assertIn("espn_kona", data["meta"]["degraded"])
        self.assertTrue(status["espn_kona"].startswith("FAILED"))
        self.assertIsNotNone(by_name(data["players"], "Michael Wilson"))
        # no ESPN prices left, so every dollar value is model-derived
        self.assertTrue(all("aav est" in p["src"] for p in data["players"]))

    def test_missing_ffc_degrades(self):
        data, _s, _r = build_fixture(self._subset({"ffc_adp.json"}))
        self.assertIn("ffc_adp", data["meta"]["degraded"])
        self.assertIsNone(by_name(data["players"], "Emeka Egbuka"))
        # Sleeper's own ADP still carries the field
        self.assertEqual(by_name(data["players"], "Bijan Robinson")["adp"], 1.4)

    def test_missing_byes_degrades(self):
        data, _s, _r = build_fixture(self._subset({"espn_byes.json"}))
        self.assertIn("espn_byes", data["meta"]["degraded"])
        # FFC still supplies a bye for the players it lists
        self.assertEqual(by_name(data["players"], "Michael Wilson")["bye"], 8)
        self.assertIsNone(by_name(data["players"], "Tyler Warren").get("bye"))


class Encoding(unittest.TestCase):
    def test_encode_is_single_line_ascii(self):
        blob = bd.encode({"meta": {"asOf": "2026-01-01"}, "news": ["Ámon-Rá"],
                          "players": []})
        self.assertNotIn("\n", blob)
        self.assertTrue(all(ord(c) < 128 for c in blob))

    def test_encode_rejects_script_close(self):
        with self.assertRaises(bd.ValidationError):
            bd.encode({"news": ["</script><script>alert(1)</script>"]})


class SpliceRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.copy = os.path.join(self.tmp, "index.html")
        shutil.copy(INDEX, self.copy)
        self.report = os.path.join(self.tmp, "DATA_REPORT.md")
        self.before = read(self.copy)

    def _run(self, *extra):
        return bd.main([
            "--fixtures-dir", FIXTURES, "--index", self.copy,
            "--report", self.report, "--as-of", "2026-08-12",
            "--min-players", "5",
            "--sanity-names", "Michael Wilson|WR,Seahawks D/ST|DST",
            *extra,
        ])

    def test_round_trip_through_a_copy_of_index_html(self):
        self.assertEqual(self._run(), 0)
        after = read(self.copy)
        data = bd.read_bundle(after)
        self.assertIsNotNone(by_name(data["players"], "Michael Wilson"))
        # the bundle must stay one line, and the file must keep its shape
        self.assertEqual(after.count("\n"), self.before.count("\n"))
        self.assertEqual(after.count(bd.DATA_START), 1)
        self.assertEqual(after.count(bd.DATA_END), 1)
        # everything outside the markers is byte-identical
        a = self.before.index(bd.DATA_START)
        b = self.before.index(bd.DATA_END)
        c = after.index(bd.DATA_START)
        d = after.index(bd.DATA_END)
        self.assertEqual(self.before[:a], after[:c])
        self.assertEqual(self.before[b:], after[d:])
        self.assertTrue(os.path.exists(self.report))
        self.assertIn("Fantasy Football Calculator", read(self.report))

    def test_rebuild_is_idempotent(self):
        self.assertEqual(self._run(), 0)
        once = read(self.copy)
        self.assertEqual(self._run(), 0)
        self.assertEqual(read(self.copy), once)

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self._run("--dry-run"), 0)
        self.assertEqual(read(self.copy), self.before)
        self.assertFalse(os.path.exists(self.report))

    def test_sanity_gate_abort_leaves_the_file_untouched(self):
        rc = bd.main([
            "--fixtures-dir", FIXTURES, "--index", self.copy,
            "--report", self.report, "--min-players", "5",
            "--sanity-names", "Nonexistent Person|WR",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(read(self.copy), self.before)
        self.assertFalse(os.path.exists(self.report))

    def test_min_count_gate_abort_leaves_the_file_untouched(self):
        rc = bd.main([
            "--fixtures-dir", FIXTURES, "--index", self.copy,
            "--report", self.report, "--min-players", "450",
        ])
        self.assertEqual(rc, 1)
        self.assertEqual(read(self.copy), self.before)

    def test_required_source_outage_leaves_the_file_untouched(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty)
        rc = bd.main(["--fixtures-dir", empty, "--index", self.copy,
                      "--report", self.report, "--min-players", "5"])
        self.assertEqual(rc, 1)
        self.assertEqual(read(self.copy), self.before)


class Validation(unittest.TestCase):
    def base(self):
        return {"meta": {"asOf": "2026-08-12"}, "news": [],
                "players": [{"name": "A B", "team": "SF", "pos": "WR", "aav": 3,
                             "pts": 100.0, "src": "sleeper", "note": ""}]}

    def test_rejects_duplicate_player_ids(self):
        d = self.base()
        d["players"].append(dict(d["players"][0]))
        with self.assertRaises(bd.ValidationError):
            bd.validate(d, 1, [])

    def test_rejects_bad_position(self):
        d = self.base()
        d["players"][0]["pos"] = "LB"
        with self.assertRaises(bd.ValidationError):
            bd.validate(d, 1, [])

    def test_rejects_unknown_stat_key(self):
        d = self.base()
        d["players"][0]["stats"] = {"tackles": 90}
        with self.assertRaises(bd.ValidationError):
            bd.validate(d, 1, [])

    def test_rejects_sub_dollar_aav(self):
        d = self.base()
        d["players"][0]["aav"] = 0
        with self.assertRaises(bd.ValidationError):
            bd.validate(d, 1, [])

    def test_accepts_a_clean_bundle(self):
        bd.validate(self.base(), 1, ["A B|WR"])


class FixtureIntegrity(unittest.TestCase):
    """The fixtures are the only stand-in for the real APIs, so keep them
    honest about the shapes the builder depends on."""

    def test_fixture_files_exist_and_parse(self):
        for f in ("sleeper_players.json", "sleeper_projections.json",
                  "ffc_adp.json", "espn_kona.json", "espn_byes.json"):
            with open(os.path.join(FIXTURES, f), encoding="utf-8") as fh:
                json.load(fh)

    def test_fixtures_cover_the_awkward_cases(self):
        players = json.loads(read(os.path.join(FIXTURES, "sleeper_players.json")))
        names = {v.get("full_name") for v in players.values()}
        self.assertIn("Michael Wilson", names)
        self.assertIn("Ja'Marr Chase", names)           # apostrophe
        self.assertIn("Marvin Harrison Jr.", names)     # suffix
        defs = [v for v in players.values() if v["position"] == "DEF"]
        self.assertGreaterEqual(len(defs), 2)


if __name__ == "__main__":
    unittest.main()
