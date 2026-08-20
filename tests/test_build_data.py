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


def build_fixture(fixtures_dir=FIXTURES, as_of="2026-08-12", fp_key=None):
    return bd.build(2026, fixtures_dir=fixtures_dir, as_of=as_of, fp_key=fp_key)


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
        # FantasyPros is optional and no key is set in the test environment,
        # so it reports "skipped" — which is explicitly not a degradation
        self.assertEqual(self.status["fantasypros"], "skipped (no key)")
        # Boone is the other optional leg; in fixture mode it loads the
        # committed fixture and reports its row counts
        self.assertTrue(self.status["boone"].startswith("ok ("), self.status["boone"])
        others = {k: v for k, v in self.status.items()
                  if k not in ("fantasypros", "boone")}
        self.assertEqual(set(others.values()), {"ok"})
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

    def test_no_signal_projection_row_is_dropped(self):
        """The Sleeper *projection* row still carries no signal and is dropped.

        This test used to assert Ricky Pearsall was absent from the pool
        entirely. That premise was the bug: FFC lists him at ADP 112, so he
        re-enters through the FFC path anyway — and used to arrive with no
        injury data at all because only the projection path consulted the
        Sleeper players DB. He is now in the pool *and* marked OUT (see
        InjuryClassification), which is the whole point of this feature."""
        self.assertEqual(self.report["sleeper_dropped_no_signal"], 1)
        rp = by_name(self.players, "Ricky Pearsall")
        self.assertIsNotNone(rp)
        self.assertEqual(rp["pts"], 0.0)
        self.assertEqual(rp["src"], "ffc (aav est)")

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

    def test_ecr_averages_expert_votes_then_falls_back(self):
        # ESPN ranks Bijan 1, Boone ranks him 4 -> the expert votes average
        self.assertEqual(by_name(self.players, "Bijan Robinson")["ecr"], 2)
        # nobody at ESPN or Boone has Jake Bates, so search_rank carries it
        self.assertEqual(by_name(self.players, "Jake Bates")["ecr"], 190)

    def test_injury_status_lands_in_note(self):
        note = by_name(self.players, "Puka Nacua")["note"]
        self.assertIn("Sleeper: Questionable", note)
        self.assertIn("(Ankle)", note)                    # body part rides along

    def test_byes_applied_from_espn(self):
        self.assertEqual(by_name(self.players, "Michael Wilson")["bye"], 8)   # ARI
        self.assertEqual(by_name(self.players, "Josh Allen")["bye"], 7)       # BUF

    def test_aav_blends_real_prices_and_floors_at_one(self):
        # Bijan: ESPN only -> ESPN's $62. Chase: ESPN $60 + Boone $48 -> $54
        self.assertEqual(by_name(self.players, "Bijan Robinson")["aav"], 62)
        self.assertEqual(by_name(self.players, "Ja'Marr Chase")["aav"], 54)
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


class InjuryClassification(unittest.TestCase):
    """The feature this pipeline exists for: nobody should ever be recommended
    a player who is out for the season."""

    @classmethod
    def setUpClass(cls):
        cls.data, cls.status, cls.report = build_fixture()
        cls.players = cls.data["players"]

    def out_names(self):
        return {p["name"] for p in self.players if p.get("out")}

    # ---- the matrix -------------------------------------------------------
    def test_classify_matrix(self):
        cases = [
            ({"injury": "Out"}, True),
            ({"injury": "IR"}, True),
            ({"injury": "ir"}, True),                   # case-insensitive
            ({"injury": "DNR"}, True),
            ({"injury": "Sus"}, True),
            ({"sleeper_status": "Injured Reserve"}, True),
            ({"espn_injury": "INJURY_RESERVE"}, True),
            ({"espn_injury": "OUT"}, True),
            ({"espn_injury": "SUSPENSION"}, True),
            ({"fp_out": True}, True),
            # ESPN's OUT is a *weekly* grade in preseason. When Sleeper says
            # the player is coming back (PUP / week-to-week), ESPN OUT must
            # not override — the second live build marked George Kittle
            # (PUP, September return) OUT this way.
            ({"espn_injury": "OUT", "injury": "PUP"}, False),
            ({"espn_injury": "OUT", "injury": "Questionable"}, False),
            ({"espn_injury": "OUT", "injury": "Doubtful"}, False),
            # ...but season-scoped ESPN designations always win
            ({"espn_injury": "INJURY_RESERVE", "injury": "PUP"}, True),
            ({"espn_injury": "SUSPENSION", "injury": "Questionable"}, True),
            # and ESPN OUT still counts when Sleeper agrees or is silent
            ({"espn_injury": "OUT", "injury": "IR"}, True),
            # explicitly NOT out — these players still practice or return
            ({"injury": "PUP"}, False),
            ({"injury": "Questionable"}, False),
            ({"injury": "Doubtful"}, False),
            ({"injury": "COV"}, False),
            ({"injury": "NA"}, False),
            ({"injury": None}, False),
            ({"sleeper_status": "Active"}, False),
            ({"sleeper_status": "Inactive"}, False),
            ({"espn_injury": "DAY_TO_DAY"}, False),
            ({"espn_injury": "QUESTIONABLE"}, False),
            ({"espn_injured": True}, False),             # the report ≠ ruled out
            ({}, False),
        ]
        for patch, want in cases:
            rec = bd.new_record("X", "WR", "SF")
            rec.update(patch)
            self.assertEqual(bd.classify_out(rec), want, patch)

    # ---- the canary -------------------------------------------------------
    def test_pearsall_enters_via_ffc_and_is_marked_out(self):
        """No Sleeper projection, in the pool through FFC's ADP, ruled out."""
        rp = by_name(self.players, "Ricky Pearsall")
        self.assertIsNotNone(rp)
        self.assertIs(rp["out"], True)
        self.assertEqual(rp["adp"], 112.0)
        self.assertIn("Sleeper: Out (PCL)", rp["note"])
        self.assertIn("PCL reconstruction", rp["note"])

    def test_backfill_joins_added_rows_to_the_sleeper_players_db(self):
        # Pearsall arrived with injury/search_rank unset until the backfill
        self.assertGreaterEqual(self.report["sleeper_backfilled"], 1)
        self.assertEqual(by_name(self.players, "Ricky Pearsall")["ecr"], 240)

    # ---- the rest of the pool --------------------------------------------
    def test_ir_player_with_a_healthy_projection_is_out(self):
        ap = by_name(self.players, "Alec Pierce")
        self.assertIs(ap["out"], True)
        self.assertGreater(ap["pts"], 100)        # the projection is fine; he is not
        self.assertIn("Sleeper: IR (Ankle)", ap["note"])

    def test_roster_status_injured_reserve_alone_is_enough(self):
        td = by_name(self.players, "Tank Dell")
        self.assertIs(td["out"], True)            # injury_status is null for him
        self.assertIn("Sleeper: Injured Reserve", td["note"])

    def test_espn_injury_status_can_rule_a_player_out(self):
        tw = by_name(self.players, "Tyler Warren")
        self.assertIs(tw["out"], True)
        self.assertIn("ESPN: Injured Reserve", tw["note"])

    def test_boone_rank_joins_the_ecr_vote(self):
        # ESPN has Bijan at rank 1; Boone says 4 -> mean 2 (rounded)
        bijan = by_name(self.players, "Bijan Robinson")
        self.assertEqual(bijan["ecr"], round((1 + 4) / 2))
        self.assertIn("boone", bijan["src"])

    def test_boone_initial_form_names_match(self):
        # Yahoo's rendered top-300 abbreviates names to "J. Gibbs" — the
        # matcher resolves initial + surname when the pool answer is unique
        self.assertIn("boone", by_name(self.players, "Jahmyr Gibbs")["src"])
        self.assertIn("boone", by_name(self.players, "Amon-Ra St. Brown")["src"])

    def test_boone_ambiguous_initials_resolve_by_rank_proximity(self):
        recs = {}
        for name, adp in (("Bijan Robinson", 1.4), ("Brian Robinson", 96.0)):
            r = bd.new_record(name, "RB", "ATL" if name.startswith("Bijan") else "WAS")
            r["sleeper_adp"] = adp
            recs[name] = r
        report = {}
        bd.apply_boone(recs, {"overall": [
            {"rank": 2, "name": "B. Robinson", "pos": ""},
            {"rank": 142, "name": "B. Robinson Jr.", "pos": ""},
            {"rank": 29, "name": "Days of Fantasy", "pos": ""},   # nav junk
        ], "values": []}, report)
        self.assertEqual(recs["Bijan Robinson"].get("boone_rank"), 2)
        self.assertEqual(recs["Brian Robinson"].get("boone_rank"), 142)
        self.assertTrue(any("Days of Fantasy" in u for u in report["boone_unmatched"]))

    def test_boone_value_blends_into_aav(self):
        # Chase: ESPN auction and Boone's $48 average together
        chase = by_name(self.players, "Ja'Marr Chase")
        self.assertGreaterEqual(chase["aav"], 40)
        self.assertNotIn("(aav est)", chase["src"])

    def test_boone_only_price_beats_the_vorp_estimate(self):
        puka = by_name(self.players, "Puka Nacua")
        self.assertNotIn("(aav est)", puka["src"])
        self.assertIn("boone", puka["src"])

    def test_boone_suffixless_spelling_matches(self):
        kw = by_name(self.players, "Kenneth Walker III")
        self.assertIn("boone", kw["src"])

    def test_boone_unmatched_rows_are_reported_not_added(self):
        self.assertIsNone(by_name(self.players, "Totally Unknown Guy"))
        self.assertTrue(any("Totally Unknown Guy" in u
                            for u in self.report["boone_unmatched"]))

    def test_missing_boone_file_is_skipped_not_degraded(self):
        tmp = tempfile.mkdtemp()
        for f in os.listdir(FIXTURES):
            if f != "boone_2026.json":
                shutil.copy(os.path.join(FIXTURES, f), os.path.join(tmp, f))
        self.addCleanup(shutil.rmtree, tmp)
        data, _s, _r = build_fixture(fixtures_dir=tmp)[0], None, None
        self.assertEqual(build_fixture(fixtures_dir=tmp)[1]["boone"],
                         "skipped (no file)")
        self.assertEqual(build_fixture(fixtures_dir=tmp)[0]["meta"]["degraded"], [])

    def test_dst_streamable_and_stalwart_notes(self):
        dsts = [p for p in self.players if p["pos"] == "DST"]
        stream = [p for p in dsts if "Streamable early" in p.get("note", "")]
        hold = [p for p in dsts if "Season-long hold" in p.get("note", "")]
        self.assertEqual(len(stream), bd.STREAM_COUNT)
        self.assertEqual(len(hold), bd.STALWART_COUNT)
        # the note names the actual opening slate
        self.assertRegex(stream[0]["note"], r"vs [A-Z?]{2,3}(, [A-Z?]{2,3}){3}")
        self.assertTrue(self.report.get("dst_schedule"))

    def test_missing_schedule_degrades_to_no_dst_notes(self):
        payload = {"settings": {"proTeams": [
            {"id": 25, "abbrev": "SF", "byeWeek": 8}]}}   # byes but no games
        recs = {}
        r = bd.new_record("Seahawks D/ST", "DST", "SEA")
        r["pts"] = 120.0
        recs["x"] = r
        report = {}
        bd.annotate_dst_schedules(recs, payload, report)
        self.assertEqual(r["flags"], [])
        self.assertIn("unavailable", report["dst_schedule"][0])

    def test_teamless_season_enders_are_dropped_not_shipped(self):
        """Sleeper parks long-retired players on 'Injured Reserve' forever;
        the second live build put Adam Vinatieri in the news briefing. A
        season-ender with no team is database residue, not a player."""
        self.assertIsNone(by_name(self.players, "Retired Ghost"))
        self.assertIn("Retired Ghost (K)", self.report["dropped_teamless_out"])
        self.assertNotIn("Retired Ghost",
                         " ".join(self.data["news"]))

    def test_pup_and_questionable_are_never_auto_out(self):
        cw = by_name(self.players, "Christian Watson")
        self.assertIsNone(cw.get("out"))
        self.assertIn("Sleeper: PUP (Knee)", cw["note"])
        for name in ("Puka Nacua", "Kenneth Walker III"):
            self.assertIsNone(by_name(self.players, name).get("out"), name)

    def test_healthy_players_carry_no_out_key(self):
        chase = by_name(self.players, "Ja'Marr Chase")
        self.assertNotIn("out", chase)            # absent, not false — smaller bundle

    def test_out_is_a_real_bool_and_survives_validation(self):
        for p in self.players:
            if "out" in p:
                self.assertIsInstance(p["out"], bool)
        bd.validate(self.data, 5, ["Ricky Pearsall|WR"])
        bad = {"meta": {"asOf": "2026-08-12"}, "news": [], "players": [
            {"name": "A B", "team": "SF", "pos": "WR", "aav": 3, "pts": 1.0,
             "src": "sleeper", "note": "", "out": 1}]}
        with self.assertRaises(bd.ValidationError):
            bd.validate(bad, 1, [])

    def test_disagreement_between_sources_is_reported(self):
        lines = self.report["injury_disagreements"]
        self.assertTrue(any("Tyler Warren" in s and "INJURY_RESERVE" in s
                            for s in lines), lines)

    def test_report_lists_every_out_player_with_a_reason(self):
        self.assertEqual(self.report["out_count"], len(self.out_names()))
        joined = "\n".join(self.report["out_players"])
        self.assertIn("Ricky Pearsall", joined)
        self.assertIn("sleeper injury_status=Out", joined)

    # ---- notes ------------------------------------------------------------
    def test_injury_notes_are_single_line_and_separator_free(self):
        rp = by_name(self.players, "Ricky Pearsall")
        self.assertNotIn("\n", rp["note"])
        pn = by_name(self.players, "Puka Nacua")          # fixture note has a "·"
        self.assertNotIn("·", pn["note"].split(" · ")[-1])
        bd.encode(self.data)                              # would reject a newline

    def test_note_has_exactly_one_sleeper_segment(self):
        """The app replaces that segment on a live refresh — two would rot."""
        for p in self.players:
            segs = [s for s in p["note"].split(" · ") if s.startswith("Sleeper: ")]
            self.assertLessEqual(len(segs), 1, p["name"])

    def test_clean_text_caps_and_flattens(self):
        self.assertEqual(bd.clean_text("a\nb  c"), "a b c")
        self.assertEqual(bd.clean_text("x · y"), "x - y")
        self.assertLessEqual(len(bd.clean_text("z" * 300)), 90)


class NewsOrdering(unittest.TestCase):
    """65 undifferentiated injury lines was the first build's failure mode."""

    @classmethod
    def setUpClass(cls):
        cls.data, _s, _r = build_fixture()
        cls.news = cls.data["news"]

    def test_season_enders_come_first(self):
        first = self.news[0]
        self.assertIn("out for the season", first)
        idx_out = max(i for i, n in enumerate(self.news) if "out for the season" in n)
        idx_day = min(i for i, n in enumerate(self.news)
                      if "Sleeper injury status" in n)
        self.assertLess(idx_out, idx_day)

    def test_season_ender_lines_name_the_body_part(self):
        line = next(n for n in self.news if "Ricky Pearsall" in n)
        self.assertIn("PCL", line)
        self.assertIn("marked OUT", line)

    def test_week_to_week_lines_say_they_are_not_out(self):
        line = next(n for n in self.news if "Puka Nacua" in n)
        self.assertIn("not auto-marked OUT", line)

    def test_out_players_are_not_recycled_as_risers(self):
        risers = [n for n in self.news if "paying up for him" in n]
        self.assertTrue(all("Pearsall" not in n and "Tank Dell" not in n
                            for n in risers), risers)

    def test_tiers_are_capped_so_one_kind_cannot_crowd_out_the_rest(self):
        kept = []
        for i in range(40):
            r = bd.new_record(f"Hurt Guy {i}", "WR", "SF")
            r.update({"injury": "IR", "out": True, "adp": float(i + 1),
                      "ecr": i + 1, "pts": 100.0})
            kept.append(r)
        for i in range(40):
            r = bd.new_record(f"Iffy Guy {i}", "WR", "SF")
            r.update({"injury": "Questionable", "adp": float(i + 60),
                      "ecr": i + 60, "pts": 100.0})
            kept.append(r)
        lines = bd.build_news(kept)
        self.assertEqual(len([n for n in lines if "out for the season" in n]), 10)
        self.assertEqual(len([n for n in lines if "Sleeper injury status" in n]), 8)
        self.assertLessEqual(len(lines), 25)


class FantasyProsLeg(unittest.TestCase):
    """Optional source: silent when unconfigured, degraded when it breaks."""

    def test_absent_key_skips_silently(self):
        data, status, report = build_fixture()
        self.assertEqual(status["fantasypros"], "skipped (no key)")
        self.assertNotIn("fantasypros", data["meta"]["degraded"])
        self.assertNotIn(bd.FP_SOURCE_LINK, data["meta"]["sources"])
        self.assertFalse(any(n.startswith("FP:") for n in data["news"]))

    def test_key_plus_fixture_activates_the_leg(self):
        data, status, report = build_fixture(fp_key="test-key")
        self.assertEqual(status["fantasypros"], "ok")
        self.assertEqual(data["meta"]["degraded"], [])
        self.assertIn(bd.FP_SOURCE_LINK, data["meta"]["sources"])
        self.assertEqual(report["fp_items"], 4)
        self.assertTrue(any(n.startswith("FP:") for n in data["news"]))

    def test_season_ending_headline_corroborates_out(self):
        data, _s, report = build_fixture(fp_key="test-key")
        eg = by_name(data["players"], "Emeka Egbuka")
        self.assertIs(eg["out"], True)            # no injury status anywhere else
        self.assertIn("FP: Emeka Egbuka tore his ACL", eg["note"])
        self.assertTrue(any("Emeka Egbuka" in s for s in report["fp_out_flagged"]))

    def test_a_non_season_ending_headline_does_not_out_anyone(self):
        data, _s, _r = build_fixture(fp_key="test-key")
        self.assertIsNone(by_name(data["players"], "Puka Nacua").get("out"))

    def test_unknown_player_in_a_headline_is_ignored(self):
        _d, _s, report = build_fixture(fp_key="test-key")
        self.assertFalse(any("Nobody Atall" in s for s in report["fp_out_flagged"]))

    def test_error_with_a_key_set_is_degraded(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for f in os.listdir(FIXTURES):
            if f != "fantasypros_news.json":
                shutil.copy(os.path.join(FIXTURES, f), os.path.join(tmp, f))
        data, status, _r = build_fixture(tmp, fp_key="test-key")
        self.assertTrue(status["fantasypros"].startswith("FAILED"))
        self.assertIn("fantasypros", data["meta"]["degraded"])

    def test_parser_tolerates_the_shapes_the_api_has_used(self):
        shapes = [
            {"news": [{"title": "A", "description": "b"}]},
            [{"headline": "A", "text": "b"}],
            {"items": [{"title": "A"}]},
            {"data": [{"name": "A", "analysis": "b"}]},
            ["A plain string headline"],
        ]
        for payload in shapes:
            items = bd.parse_fantasypros(payload)
            self.assertEqual(len(items), 1, payload)
            self.assertTrue(items[0]["headline"], payload)
        for junk in (None, {}, [], {"news": None}, 7, "nope"):
            self.assertEqual(bd.parse_fantasypros(junk), [], junk)

    def test_player_names_are_read_from_several_key_shapes(self):
        payload = {"news": [
            {"title": "T1", "description": "torn ACL", "players": ["Bijan Robinson"]},
            {"title": "T2", "description": "torn ACL",
             "player": [{"name": "Josh Allen"}]},
        ]}
        items = bd.parse_fantasypros(payload)
        self.assertEqual(items[0]["players"], ["Bijan Robinson"])
        self.assertEqual(items[1]["players"], ["Josh Allen"])


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
        # no ESPN prices left, so every dollar value without a Boone price
        # is model-derived; Boone-priced players keep a real number
        self.assertTrue(all("aav est" in p["src"] for p in data["players"]
                            if "boone" not in p["src"]))
        self.assertTrue(any("boone" in p["src"] and "aav est" not in p["src"]
                            for p in data["players"]))

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


class SuperflexAdp(unittest.TestCase):
    """Sleeper's adp_2qb is the only 2QB/superflex draft signal in the
    pipeline; the app's snake availability model reads it when the league has
    a superflex slot, so it has to survive the build intact."""

    @classmethod
    def setUpClass(cls):
        cls.data, _s, cls.report = build_fixture()
        cls.players = cls.data["players"]

    def test_quarterbacks_go_much_earlier_on_the_2qb_board(self):
        allen = by_name(self.players, "Josh Allen")
        self.assertEqual(allen["adp2"], 3.1)
        # the whole point of the field: in a 1QB room he is a mid-round pick
        self.assertLess(allen["adp2"], allen["adp"] - 15)

    def test_skill_players_slide_slightly(self):
        bijan = by_name(self.players, "Bijan Robinson")
        self.assertEqual(bijan["adp2"], 2.2)
        self.assertGreater(bijan["adp2"], bijan["adp"])

    def test_placeholder_2qb_adp_is_nulled_like_adp_ppr(self):
        # Sleeper pads adp_2qb with 999s exactly as it does adp_ppr
        mw = by_name(self.players, "Michael Wilson")
        self.assertIsNotNone(mw["adp"])
        self.assertNotIn("adp2", mw)

    def test_absent_2qb_adp_leaves_the_key_off(self):
        # the field is optional — most rows never carry it, and the app falls
        # back to ordinary ADP for those
        nacua = by_name(self.players, "Puka Nacua")
        self.assertIsNotNone(nacua["adp"])
        self.assertNotIn("adp2", nacua)

    def test_ingest_nulls_out_placeholder_2qb_adp(self):
        raw = {
            "sleeper_players": {"1": {"full_name": "Deep Guy", "position": "QB",
                                      "team": "SF", "search_rank": 2500}},
            "sleeper_projections": [
                {"player_id": "1",
                 "player": {"player_id": "1", "full_name": "Deep Guy",
                            "position": "QB", "team": "SF"},
                 "team": "SF",
                 "stats": {"pass_yd": 3000.0, "pts_ppr": 190.0,
                           "adp_ppr": 210.0, "adp_2qb": 999.0}},
            ],
        }
        recs, _ = bd.ingest_sleeper(raw, {})
        rec = next(r for r in recs.values() if r["name"] == "Deep Guy")
        self.assertEqual(rec["sleeper_adp"], 210.0)
        self.assertIsNone(rec["sleeper_adp2"])

    def test_report_counts_the_2qb_board(self):
        self.assertEqual(self.report["adp2_count"],
                         len([p for p in self.players if "adp2" in p]))
        self.assertEqual(self.report["adp2_qb_count"], 4)
        md = bd.render_report(self.data, {"sleeper_players": "ok"}, self.report)
        self.assertIn("Carrying a superflex (2QB) ADP", md)

    def test_bundle_with_2qb_adp_passes_validation(self):
        bd.validate(self.data, 5, ["Josh Allen|QB"])

    def test_validate_rejects_a_non_numeric_adp2(self):
        d = {"meta": {"asOf": "2026-08-12"}, "news": [],
             "players": [{"name": "A B", "team": "SF", "pos": "QB", "aav": 3,
                          "pts": 100.0, "src": "sleeper", "note": "",
                          "adp2": "4.5"}]}
        with self.assertRaises(bd.ValidationError):
            bd.validate(d, 1, [])
        d["players"][0]["adp2"] = 4.5
        bd.validate(d, 1, [])


class FixtureIntegrity(unittest.TestCase):
    """The fixtures are the only stand-in for the real APIs, so keep them
    honest about the shapes the builder depends on."""

    def test_fixture_files_exist_and_parse(self):
        for f in ("sleeper_players.json", "sleeper_projections.json",
                  "ffc_adp.json", "espn_kona.json", "espn_byes.json",
                  "fantasypros_news.json"):
            with open(os.path.join(FIXTURES, f), encoding="utf-8") as fh:
                json.load(fh)

    def test_sleeper_fixture_carries_the_injury_fields_the_api_sends(self):
        players = json.loads(read(os.path.join(FIXTURES, "sleeper_players.json")))
        for want in ("injury_status", "injury_body_part", "injury_notes",
                     "injury_start_date", "status"):
            self.assertTrue(all(want in v for v in players.values()), want)
        statuses = {v.get("injury_status") for v in players.values()}
        for want in ("Out", "IR", "PUP", "Questionable"):
            self.assertIn(want, statuses)
        self.assertIn("Injured Reserve",
                      {v.get("status") for v in players.values()})
        # a hand-typed note with a newline in it, exactly like the real feed
        self.assertTrue(any("\n" in (v.get("injury_notes") or "")
                            for v in players.values()))

    def test_espn_fixture_carries_injury_status(self):
        payload = json.loads(read(os.path.join(FIXTURES, "espn_kona.json")))
        pls = [r["player"] for r in payload["players"]]
        self.assertTrue(all("injuryStatus" in p for p in pls))
        self.assertIn("INJURY_RESERVE", {p["injuryStatus"] for p in pls})

    def test_sleeper_projection_fixture_carries_2qb_adp(self):
        rows = json.loads(read(os.path.join(FIXTURES, "sleeper_projections.json")))
        adp2 = {(r["player"].get("first_name", "") + " "
                 + r["player"].get("last_name", "")).strip():
                (r.get("stats") or {}).get("adp_2qb") for r in rows}
        self.assertEqual(adp2.get("Josh Allen"), 3.1)
        self.assertEqual(adp2.get("Michael Wilson"), 999.0)   # placeholder
        self.assertIsNone(adp2.get("Puka Nacua"))             # field absent
        self.assertGreaterEqual(len([v for v in adp2.values() if v]), 8)

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
