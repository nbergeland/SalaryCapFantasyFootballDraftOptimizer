#!/usr/bin/env python3
"""Build the bundled player dataset that lives inside index.html.

The app ships as a single self-contained HTML file with its player pool
spliced between the ``/*__DATA__*/`` … ``/*__END_DATA__*/`` markers.  This
script rebuilds that blob from free, no-auth data sources and rewrites the
markers in place.  It is normally run by ``.github/workflows/data-refresh.yml``
on a daily cron; the runner has the outbound network access this project's dev
sandbox does not.

Sources
-------
Sleeper players    api.sleeper.app/v1/players/nfl        roster, teams, injuries, search_rank
Sleeper projections api.sleeper.com/projections/nfl/YYYY season stat projections, pts_ppr, adp_ppr, adp_2qb
FFC ADP            fantasyfootballcalculator.com        real-draft ADP (attribution requested)
ESPN kona          lm-api-reads.fantasy.espn.com        auction values, PPR ranks, 2nd projection
ESPN pro teams     lm-api-reads.fantasy.espn.com        bye weeks
FantasyPros news   api.fantasypros.com                  optional, needs FANTASYPROS_API_KEY

Outage policy: if either Sleeper source fails the build aborts and nothing is
written (yesterday's data stays live).  ESPN/FFC are degradable — the build
proceeds and records the loss in ``meta.degraded`` and in DATA_REPORT.md.
FantasyPros is *optional*: with no ``FANTASYPROS_API_KEY`` in the environment
the leg is skipped silently (that is not a degradation); with a key set, a
failure is reported as degraded like any other soft source.

Injuries: every player is classified out / not out (see ``classify_out``) and
players ruled out for the season ship with ``out: true`` so the app can drop
them from recommendations without the user hand-marking anyone.

Offline use: ``--fixtures-dir DIR`` reads ``sleeper_players.json``,
``sleeper_projections.json``, ``ffc_adp.json``, ``espn_kona.json`` and
``espn_byes.json`` from DIR instead of the network.  A missing optional file is
treated exactly like that source being down, which is how the unit tests
exercise the outage matrix.

Usage
-----
    python3 scripts/build_data.py                          # real build, writes index.html
    python3 scripts/build_data.py --fixtures-dir tests/fixtures --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from datetime import date, datetime, timezone

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

DATA_START = "/*__DATA__*/"
DATA_END = "/*__END_DATA__*/"

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]

# ADP values at/after this pick are placeholder defaults, not draft signal
# (29 rounds × 12 teams ≈ 350; Sleeper pads the deep pool with 999s).
MAX_REAL_ADP = 350.0

# stat keys consumed by scorePlayer() in index.html — do not rename without
# changing the app.  Sleeper calls interceptions ``pass_int``; the app calls
# it ``int``, so that one is remapped on the way in.
STAT_KEYS = ["pass_yd", "pass_td", "int", "rush_yd", "rush_td", "rec", "rec_yd", "rec_td"]
SLEEPER_STAT_SOURCE = {
    "pass_yd": "pass_yd",
    "pass_td": "pass_td",
    "int": "pass_int",
    "rush_yd": "rush_yd",
    "rush_td": "rush_td",
    "rec": "rec",
    "rec_yd": "rec_yd",
    "rec_td": "rec_td",
}

# Sleeper's abbreviations are canon for this project.
NFL_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
    "TEN", "WAS",
]

TEAM_ALIASES = {
    "JAC": "JAX", "WSH": "WAS", "WFT": "WAS", "LVR": "LV", "OAK": "LV",
    "GBP": "GB", "SFO": "SF", "TBB": "TB", "NOS": "NO", "KCC": "KC",
    "NEP": "NE", "ARZ": "ARI", "BLT": "BAL", "HST": "HOU", "CLV": "CLE",
    "SD": "LAC", "SDG": "LAC", "STL": "LAR", "LA": "LAR", "NWE": "NE",
    "NYA": "NYJ",
}

ESPN_TEAM_BY_ID = {
    1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN",
    8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR",
    15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI",
    22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB", 28: "WAS",
    29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}

ESPN_POS_BY_ID = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}

# canonical D/ST display names — these match the names already in the shipped
# bundle, which keeps playerId() (name|pos) stable for existing users' marks.
DST_NICKNAME = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LAC": "Chargers", "LAR": "Rams", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}

# replacement level (draftable starter count) per position in a 12-team league
REPLACEMENT_RANK = {"QB": 13, "RB": 30, "WR": 42, "TE": 13, "K": 13, "DST": 13}

# 12 teams x $200, minus the $1 minimum bid reserved for each of 16 roster spots
AUCTION_ROOM = 2400 - 12 * 16

DEFAULT_SANITY_NAMES = [
    "Ja'Marr Chase|WR", "Bijan Robinson|RB", "Puka Nacua|WR",
    "Jahmyr Gibbs|RB", "Justin Jefferson|WR", "CeeDee Lamb|WR",
    "Saquon Barkley|RB", "Amon-Ra St. Brown|WR", "Malik Nabers|WR",
    "Brock Bowers|TE", "Trey McBride|TE", "Josh Allen|QB",
    "Lamar Jackson|QB", "Jayden Daniels|QB", "Patrick Mahomes|QB",
    "Christian McCaffrey|RB", "Jonathan Taylor|RB", "Nico Collins|WR",
    "A.J. Brown|WR", "Drake London|WR",
    # the canary that motivated this pipeline: absent from the hand-curated
    # 190-player snapshot even though he is a startable WR
    "Michael Wilson|WR",
]

SOURCE_LINKS = [
    "https://api.sleeper.app/v1/players/nfl",
    "https://api.sleeper.com/projections/nfl",
    "https://fantasyfootballcalculator.com/adp",
    "https://lm-api-reads.fantasy.espn.com (kona_player_info)",
]

FP_SOURCE_LINK = "https://api.fantasypros.com/v2/json/nfl/news (FantasyPros)"

FFC_ATTRIBUTION = "ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com)."

# --------------------------------------------------------------------------
# injury classification
# --------------------------------------------------------------------------
# Sleeper's injury_status vocabulary is
#   Questionable / Doubtful / Out / IR / PUP / Sus / DNR / COV / NA
# Only the ones below mean "he will not play, plan without him".  PUP is
# deliberately absent: a PUP player is expected back (often by week 5), and
# auto-benching him would be worse than the disease.  Questionable/Doubtful are
# week-to-week and get a note, never an OUT.
SLEEPER_OUT_STATUSES = {"IR", "OUT", "DNR", "SUS"}
SLEEPER_OUT_ROSTER_STATUS = "injured reserve"        # players DB `status` field
ESPN_OUT_STATUSES = {"INJURY_RESERVE", "OUT", "SUSPENSION"}
ESPN_STATUS_LABEL = {"INJURY_RESERVE": "Injured Reserve", "OUT": "Out",
                     "SUSPENSION": "Suspended"}
# a headline containing one of these plus a pool player's name is treated as
# season-ending corroboration (FantasyPros leg only)
FP_OUT_KEYWORDS = [
    "out for the season", "out for season", "season-ending", "season ending",
    "miss the season", "misses the season", "done for the season",
    "torn acl", "tore his acl", "torn achilles", "ruptured achilles",
    "tore his achilles", "torn pcl", "tore his pcl", "torn patellar",
    "placed on injured reserve", "placed on ir", "moved to injured reserve",
    "suspended for the season", "season-long suspension",
]


# --------------------------------------------------------------------------
# normalization — byte-for-byte mirrors of the JS helpers in index.html
# --------------------------------------------------------------------------

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")
_NON_ALPHA_RE = re.compile(r"[^a-z]")


def norm_name(s) -> str:
    """Mirror of normName() in index.html (~line 2555), plus a diacritic fold
    the JS never needs (its sources agree on spelling; ours don't - FFC writes
    "Eddy Piñeiro" where Sleeper has "Eddy Pineiro", and a bare strip would
    turn ñ into nothing instead of n)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return _NON_ALPHA_RE.sub("", _SUFFIX_RE.sub("", s.lower()))


def norm_pos(raw):
    """Mirror of normPos() in index.html (~line 640)."""
    p = re.sub(r"[^A-Z/]", "", str(raw or "").upper())
    if p.startswith("DEF") or p in ("DST", "D/ST", "D"):
        return "DST"
    if p == "PK":
        return "K"
    for q in POSITIONS:
        if p.startswith(q):
            return q
    return None


def canon_team(raw) -> str:
    t = re.sub(r"[^A-Z]", "", str(raw or "").upper())
    if not t:
        return ""
    t = TEAM_ALIASES.get(t, t)
    return t if t in NFL_TEAMS else ""


def dst_name(team: str) -> str:
    nick = DST_NICKNAME.get(team)
    return f"{nick} D/ST" if nick else f"{team} D/ST"


def pkey(name: str, pos: str, team: str = "") -> str:
    """Join key used to match a player across sources."""
    if pos == "DST":
        return "DST|" + (team or norm_name(name))
    return norm_name(name) + "|" + pos


def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

class SourceError(Exception):
    pass


def get_json(url, headers=None, timeout=30, retries=3, sleep=time.sleep):
    """GET + parse JSON with backoff.  ``requests`` is imported lazily so that
    fixture-mode runs (and the unit tests) work without it installed."""
    import requests  # noqa: PLC0415 — deliberate: only the network path needs it

    backoff = [2, 8, 30]
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers or {}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001 — any failure is retryable here
            last = e
            if attempt < retries - 1:
                sleep(backoff[min(attempt, len(backoff) - 1)])
    raise SourceError(f"{url}: {last}")


def espn_filter_header():
    return {
        "x-fantasy-filter": json.dumps({
            "players": {
                "limit": 1000,
                "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "PPR"},
            }
        }),
        "accept": "application/json",
        "user-agent": "berg-sheets-data-refresh/1.0",
    }


def load_sources(season, fixtures_dir=None):
    """Return ``(raw, status)``.  ``status`` maps source name -> "ok" or an
    error string.  Raises SourceError if a required Sleeper source is missing."""
    raw, status = {}, {}

    def fixture(name):
        path = os.path.join(fixtures_dir, name)
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    plan = [
        ("sleeper_players", "sleeper_players.json",
         lambda: get_json("https://api.sleeper.app/v1/players/nfl", timeout=90), True),
        ("sleeper_projections", "sleeper_projections.json",
         lambda: get_json(
             f"https://api.sleeper.com/projections/nfl/{season}"
             "?season_type=regular&order_by=ppr"
             "&position[]=QB&position[]=RB&position[]=WR&position[]=TE"
             "&position[]=K&position[]=DEF", timeout=60), True),
        ("ffc_adp", "ffc_adp.json",
         lambda: get_json(
             "https://fantasyfootballcalculator.com/api/v1/adp/ppr"
             f"?teams=12&year={season}"), False),
        ("espn_kona", "espn_kona.json",
         lambda: get_json(
             "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
             f"{season}/segments/0/leaguedefaults/3?view=kona_player_info",
             headers=espn_filter_header()), False),
        ("espn_byes", "espn_byes.json",
         lambda: get_json(
             "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
             f"{season}?view=proTeamSchedules_wl"), False),
    ]

    for name, filename, fetch, required in plan:
        try:
            raw[name] = fixture(filename) if fixtures_dir else fetch()
            status[name] = "ok"
        except Exception as e:  # noqa: BLE001
            status[name] = f"FAILED: {e}"
            raw[name] = None
            if required:
                raise SourceError(f"required source {name} unavailable: {e}") from e
    return raw, status


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def _sleeper_name(pl):
    if pl.get("full_name"):
        return str(pl["full_name"]).strip()
    parts = [pl.get("first_name") or "", pl.get("last_name") or ""]
    return " ".join(p for p in parts if p).strip()


def clean_text(text, limit=90):
    """One-line, ``·``-free, length-capped copy of free text.

    Sleeper's injury_notes are hand-typed and routinely carry newlines; the
    bundle is spliced into a single-line JSON blob (``encode`` rejects
    newlines outright) and notes are ``" · "``-joined segments the app splits
    on, so both characters have to go before the text is stored."""
    s = re.sub(r"\s+", " ", str(text or "").replace("·", "-")).strip()
    if len(s) > limit:
        s = s[:limit - 1].rstrip() + "…"
    return s


def index_sleeper_players(players_db):
    """id -> record, plus a key -> record index.

    The key index is what lets rows that entered through ESPN/FFC find their
    Sleeper injury data later (``backfill_from_sleeper``) — for everyone but
    D/ST ``pkey`` is name+position, so it doubles as a name index."""
    by_id, by_key = {}, {}
    for pid, pl in (players_db or {}).items():
        if not isinstance(pl, dict):
            continue
        pos = norm_pos(pl.get("position"))
        if pos is None and pl.get("fantasy_positions"):
            for fp in pl["fantasy_positions"]:
                pos = norm_pos(fp)
                if pos:
                    break
        if pos is None:
            continue
        team = canon_team(pl.get("team"))
        name = dst_name(team) if pos == "DST" and team else _sleeper_name(pl)
        if not name:
            continue
        rec = {"id": str(pid), "name": name, "pos": pos, "team": team,
               "search_rank": pl.get("search_rank"),
               "injury": pl.get("injury_status"),
               "injury_body": pl.get("injury_body_part") or None,
               "injury_notes": clean_text(pl.get("injury_notes")) or None,
               "sleeper_status": pl.get("status") or None}
        by_id[str(pid)] = rec
        by_key.setdefault(pkey(name, pos, team), rec)
    return by_id, by_key


def new_record(name, pos, team):
    return {
        "name": name, "pos": pos, "team": team,
        "stats": None, "sleeper_pts": None, "sleeper_adp": None,
        "sleeper_adp2": None,
        "search_rank": None, "injury": None, "injury_body": None,
        "injury_notes": None, "sleeper_status": None,
        "espn_rank": None, "espn_aav": None, "espn_pts": None, "espn_team": "",
        "espn_injury": None, "espn_injured": None,
        "fp_out": False, "fp_note": None,
        "ffc_adp": None, "ffc_team": "",
        "bye": None, "sources": set(), "flags": [],
    }


def copy_sleeper_injury(rec, db):
    """Move the players-DB injury fields onto a pool record."""
    rec["injury"] = db.get("injury")
    rec["injury_body"] = db.get("injury_body")
    rec["injury_notes"] = db.get("injury_notes")
    rec["sleeper_status"] = db.get("sleeper_status")


def ingest_sleeper(raw, report):
    """Sleeper projections joined to the players DB — this is the base pool."""
    by_id, by_key = index_sleeper_players(raw.get("sleeper_players"))
    report["sleeper_players_count"] = len(by_id)

    recs = {}
    dropped = 0
    rows = raw.get("sleeper_projections") or []
    if isinstance(rows, dict):                      # defensive: some mirrors wrap it
        rows = rows.get("projections") or list(rows.values())
    for row in rows:
        if not isinstance(row, dict):
            continue
        meta = row.get("player") or {}
        pid = str(row.get("player_id") or meta.get("player_id") or "")
        db = by_id.get(pid)
        pos = norm_pos(meta.get("position") or (db or {}).get("pos"))
        if pos is None:
            continue
        team = canon_team(row.get("team") or meta.get("team") or (db or {}).get("team"))
        if pos == "DST":
            if not team:
                continue
            name = dst_name(team)
        else:
            name = _sleeper_name(meta) or (db or {}).get("name") or ""
        if not name:
            continue

        st_raw = row.get("stats") or {}
        stats = {}
        for k in STAT_KEYS:
            v = st_raw.get(SLEEPER_STAT_SOURCE[k])
            if v:
                stats[k] = round(float(v), 1)
        pts = st_raw.get("pts_ppr")
        adp = st_raw.get("adp_ppr")
        # Sleeper stamps an adp_ppr on nearly every projection row, with
        # 999-style defaults deep in the pool. An "ADP" beyond pick ~350
        # (29 rounds, 12 teams) is a placeholder, not a draft signal — treating
        # it as real kept all 3219 rows at the cutoff and would feed junk
        # ranks into snake mode.
        if adp is not None and float(adp) >= MAX_REAL_ADP:
            adp = None
        # superflex/2QB ADP from the same feed: in an SF room the QBs go two
        # rounds earlier than their 1QB ADP suggests, and the app's snake
        # availability model is only as good as the ranks it reads. Same
        # placeholder rule — Sleeper pads this field with 999s too.
        adp2 = st_raw.get("adp_2qb")
        if adp2 is not None and float(adp2) >= MAX_REAL_ADP:
            adp2 = None

        if not stats and adp is None and pos not in ("K", "DST"):
            dropped += 1                            # no signal at all — skip
            continue

        key = pkey(name, pos, team)
        rec = recs.get(key) or new_record(name, pos, team)
        rec["stats"] = stats or None
        rec["sleeper_pts"] = round(float(pts), 1) if pts is not None else None
        rec["sleeper_adp"] = round(float(adp), 1) if adp is not None else None
        rec["sleeper_adp2"] = round(float(adp2), 1) if adp2 is not None else None
        rec["sources"].add("sleeper")
        if db:
            rec["search_rank"] = db.get("search_rank")
            copy_sleeper_injury(rec, db)
            if db.get("team"):
                rec["team"] = db["team"]
        recs[key] = rec

    # every D/ST gets a slot even if projections omit them
    for team in NFL_TEAMS:
        key = pkey("", "DST", team)
        if key not in recs:
            rec = new_record(dst_name(team), "DST", team)
            rec["sources"].add("sleeper")
            recs[key] = rec

    report["sleeper_projection_rows"] = len(rows)
    report["sleeper_dropped_no_signal"] = dropped
    return recs, by_key


def ingest_espn(raw, recs, report):
    payload = raw.get("espn_kona")
    if not payload:
        return
    added, matched, unmatched = 0, 0, []
    for row in payload.get("players") or []:
        pl = row.get("player") or row
        pos = ESPN_POS_BY_ID.get(pl.get("defaultPositionId"))
        if pos is None:
            continue
        team = ESPN_TEAM_BY_ID.get(pl.get("proTeamId"), "")
        name = dst_name(team) if pos == "DST" and team else str(pl.get("fullName") or "").strip()
        if not name:
            continue
        ranks = (pl.get("draftRanksByRankType") or {}).get("PPR") or {}
        rank = ranks.get("rank")
        aav = ranks.get("auctionValue")
        if not aav:
            aav = (pl.get("ownership") or {}).get("auctionValueAverage")
        pts = None
        for st in pl.get("stats") or []:
            # statSourceId 1 = projection, statSplitTypeId 0 = full season
            if st.get("statSourceId") == 1 and st.get("statSplitTypeId") == 0:
                pts = st.get("appliedTotal")
                break

        key = pkey(name, pos, team)
        rec = recs.get(key)
        if rec is None:
            if rank is not None and rank <= 300:
                rec = new_record(name, pos, team)
                recs[key] = rec
                added += 1
            else:
                unmatched.append(f"{name} ({team} {pos}) rank={rank}")
                continue
        else:
            matched += 1
        rec["espn_rank"] = rank
        rec["espn_aav"] = round(float(aav), 1) if aav else None
        rec["espn_pts"] = round(float(pts), 1) if pts else None
        rec["espn_team"] = team
        # ESPN's own injury read — a second opinion on Sleeper's. `injured` is
        # true for anyone on the report (questionable included), so only
        # injuryStatus decides OUT; `injured` is kept for the disagreement log.
        rec["espn_injury"] = pl.get("injuryStatus")
        rec["espn_injured"] = pl.get("injured")
        rec["sources"].add("espn")
    report["espn_matched"] = matched
    report["espn_added"] = added
    report["espn_unmatched"] = unmatched


def ingest_ffc(raw, recs, report):
    payload = raw.get("ffc_adp")
    if not payload:
        return
    rows = payload.get("players") if isinstance(payload, dict) else payload
    added, matched, unmatched = 0, 0, []
    for row in rows or []:
        pos = norm_pos(row.get("position"))
        if pos is None:
            continue
        team = canon_team(row.get("team"))
        name = dst_name(team) if pos == "DST" and team else str(row.get("name") or "").strip()
        adp = row.get("adp")
        if not name or adp is None:
            continue
        key = pkey(name, pos, team)
        rec = recs.get(key)
        if rec is None:
            rec = new_record(name, pos, team)
            recs[key] = rec
            added += 1
        else:
            matched += 1
        rec["ffc_adp"] = round(float(adp), 1)
        rec["ffc_team"] = team
        if row.get("bye"):
            rec["bye"] = int(row["bye"])
        rec["sources"].add("ffc")
        if not rec["sources"] - {"ffc"}:
            unmatched.append(f"{name} ({team} {pos}) adp={adp}")
    report["ffc_matched"] = matched
    report["ffc_added"] = added
    report["ffc_unmatched"] = unmatched


def backfill_from_sleeper(recs, by_key, report):
    """Join ESPN/FFC-added rows back to the Sleeper players DB.

    A player whose Sleeper projection was dropped for having no signal at all
    (no stat line, no ADP) can still re-enter the pool through FFC's ADP or
    ESPN's ranks — and used to arrive with ``injury`` and ``search_rank``
    unset, because only the projection path ever consulted the players DB.
    Ricky Pearsall was the canary: out for the season after PCL surgery,
    recommended at ADP 112 because nothing in the pipeline knew he was hurt.
    """
    filled, teams = 0, 0
    for rec in recs.values():
        if rec["injury"] is not None or rec["search_rank"] is not None:
            continue
        db = by_key.get(pkey(rec["name"], rec["pos"], rec["team"]))
        if db is None and rec["pos"] != "DST":
            # the row may carry ESPN/FFC's team while Sleeper has him elsewhere;
            # for everyone but D/ST pkey ignores team, so one lookup is enough
            db = by_key.get(pkey(rec["name"], rec["pos"], ""))
        if db is None:
            continue
        rec["search_rank"] = db.get("search_rank")
        copy_sleeper_injury(rec, db)
        if db.get("team") and db["team"] != rec["team"]:
            rec["team"] = db["team"]            # Sleeper is canon for teams
            teams += 1
        filled += 1
    report["sleeper_backfilled"] = filled
    report["sleeper_backfilled_teams"] = teams


def ingest_byes(raw, recs):
    payload = raw.get("espn_byes")
    byes = {}
    if payload:
        for t in ((payload.get("settings") or {}).get("proTeams") or []):
            team = canon_team(t.get("abbrev")) or ESPN_TEAM_BY_ID.get(t.get("id"), "")
            if team and t.get("byeWeek"):
                byes[team] = int(t["byeWeek"])
    for rec in recs.values():
        if byes.get(rec["team"]):
            rec["bye"] = byes[rec["team"]]
    return byes


STREAM_WEEKS = 4          # "streamable" = a soft slate across the opening month
STREAM_COUNT = 8          # how many soft-slate DSTs get the note
STALWART_COUNT = 5        # top-N season-long DSTs get the hold note


def extract_schedule(payload, weeks=STREAM_WEEKS):
    """{team: {week: opponent}} for the opening weeks, from ESPN's pro-team
    schedule view (the same payload the bye weeks come from).  The view is
    fetched for byes either way; the games list rides along for free.
    Defensive throughout — an ESPN shape change degrades to {} and the
    annotation simply doesn't happen that night."""
    sched = {}
    for t in (((payload or {}).get("settings") or {}).get("proTeams") or []):
        team = canon_team(t.get("abbrev")) or ESPN_TEAM_BY_ID.get(t.get("id"), "")
        if not team:
            continue
        games = t.get("proGamesByScoringPeriod") or {}
        for wk_raw, lst in games.items():
            try:
                wk = int(wk_raw)
            except (TypeError, ValueError):
                continue
            if not (1 <= wk <= weeks) or not lst:
                continue
            g = lst[0]
            home = ESPN_TEAM_BY_ID.get(g.get("homeProTeamId"), "")
            away = ESPN_TEAM_BY_ID.get(g.get("awayProTeamId"), "")
            opp = away if home == team else home if away == team else ""
            if opp:
                sched.setdefault(team, {})[wk] = opp
    return sched


def offense_strength_ranks(recs):
    """team -> rank 1..32 by projected offensive output (1 = most points =
    the opponent a defense least wants to see).  Derived from our own pool:
    the sum of each team's top six offensive projections."""
    by_team = {}
    for rec in recs.values():
        if rec["pos"] in ("K", "DST") or rec.get("out") or not rec["team"]:
            continue
        by_team.setdefault(rec["team"], []).append(rec["pts"] or 0.0)
    totals = {t: sum(sorted(v, reverse=True)[:6]) for t, v in by_team.items()}
    ranked = sorted(totals, key=lambda t: -totals[t])
    return {t: i + 1 for i, t in enumerate(ranked)}


def annotate_dst_schedules(recs, byes_payload, report):
    """Flag streamable openers (soft weeks 1-4) and season-long stalwarts on
    D/ST rows.  'Soft' is measured against our own projections: the average
    offense rank of the first four opponents, higher = weaker slate."""
    sched = extract_schedule(byes_payload)
    ranks = offense_strength_ranks(recs)
    dsts = [r for r in recs.values() if r["pos"] == "DST"]
    if not sched or not ranks or not dsts:
        report["dst_schedule"] = ["schedule data unavailable — no annotations"]
        return
    rows = []
    for rec in dsts:
        opps = [sched.get(rec["team"], {}).get(w) for w in range(1, STREAM_WEEKS + 1)]
        known = [o for o in opps if o and o in ranks]
        if len(known) < 3:
            continue
        softness = sum(ranks[o] for o in known) / len(known)
        rows.append((softness, rec, opps))
    rows.sort(key=lambda x: -x[0])
    for i, (softness, rec, opps) in enumerate(rows):
        slate = ", ".join(o or "?" for o in opps)
        if i < STREAM_COUNT:
            rec["flags"].append(
                f"Streamable early: soft weeks 1-{STREAM_WEEKS} (vs {slate})")
    for rec in sorted(dsts, key=lambda r: -(r["pts"] or 0))[:STALWART_COUNT]:
        rec["flags"].append("Season-long hold: top-5 projected defense")
    report["dst_schedule"] = [
        f"{rec['name']}: avg opponent offense rank {softness:.1f} "
        f"(vs {', '.join(o or '?' for o in opps)}) — season proj {rec['pts']:.0f}"
        for softness, rec, opps in rows]


def resolve_teams(recs, report):
    """Sleeper > ESPN > FFC.  Every disagreement is reported."""
    mismatches = []
    for rec in recs.values():
        have = [t for t in (rec["team"], rec["espn_team"], rec["ffc_team"]) if t]
        if len({*have}) > 1:
            mismatches.append(
                f"{rec['name']} ({rec['pos']}): sleeper={rec['team'] or '—'} "
                f"espn={rec['espn_team'] or '—'} ffc={rec['ffc_team'] or '—'}")
        if not rec["team"]:
            rec["team"] = rec["espn_team"] or rec["ffc_team"] or ""
    report["team_mismatches"] = mismatches


def blend_projections(recs, report):
    splits = []
    for rec in recs.values():
        # Sleeper projects a handful of return specialists slightly negative
        # (offense-only scoring); the app treats pts as non-negative.
        s = rec["sleeper_pts"] if rec["sleeper_pts"] is None else max(0.0, rec["sleeper_pts"])
        e = rec["espn_pts"] if rec["espn_pts"] is None else max(0.0, rec["espn_pts"])
        if s is not None and e is not None:
            rec["pts"] = round(0.6 * s + 0.4 * e, 1)
            gap = abs(s - e)
            if gap > 30 and gap > 0.25 * max(s, e, 1):
                rec["flags"].append(f"projection split: Sleeper {s:.0f} vs ESPN {e:.0f}")
                splits.append(f"{rec['name']} ({rec['pos']}): sleeper={s} espn={e}")
        elif s is not None:
            rec["pts"] = round(s, 1)
        elif e is not None:
            rec["pts"] = round(e, 1)
        else:
            rec["pts"] = 0.0
    report["projection_splits"] = splits


def blend_ranks(recs):
    for rec in recs.values():
        rec["adp"] = median([rec["sleeper_adp"], rec["ffc_adp"]])
        if rec["adp"] is not None:
            rec["adp"] = round(rec["adp"], 1)
        # 2QB/superflex ADP has one source today — FFC publishes 2QB boards
        # but not through the ppr endpoint we pull, so there is nothing to
        # blend against yet. Kept as a median so a second feed drops straight in.
        rec["adp2"] = median([rec["sleeper_adp2"]])
        if rec["adp2"] is not None:
            rec["adp2"] = round(rec["adp2"], 1)
        ecr = rec["espn_rank"]
        if ecr is None:
            sr = rec["search_rank"]
            ecr = sr if isinstance(sr, (int, float)) and 0 < sr < 3000 else None
        rec["ecr"] = int(ecr) if ecr is not None else None


def compute_aav(recs, report):
    """ESPN auction value where we have one; VORP-derived dollars elsewhere,
    with the VORP scale calibrated against the ESPN-priced players."""
    by_pos = {}
    for rec in recs.values():
        by_pos.setdefault(rec["pos"], []).append(rec)
    repl = {}
    for pos, group in by_pos.items():
        pts = sorted((r["pts"] for r in group), reverse=True)
        n = REPLACEMENT_RANK.get(pos, 13)
        repl[pos] = pts[n - 1] if len(pts) >= n else (pts[-1] if pts else 0.0)
    for rec in recs.values():
        rec["vorp"] = max(0.0, rec["pts"] - repl[rec["pos"]])

    total_vorp = sum(r["vorp"] for r in recs.values())
    k = (AUCTION_ROOM / total_vorp) if total_vorp > 0 else 0.0

    priced = [r for r in recs.values() if r["espn_aav"] and r["espn_aav"] >= 3]
    priced_ids = {id(r) for r in priced}
    calib = 1.0
    if priced and k > 0:
        pred = sum(k * r["vorp"] for r in priced)
        if pred > 0:
            calib = sum(r["espn_aav"] for r in priced) / pred
            calib = min(3.0, max(0.33, calib))
    scale = k * calib

    errors = []
    for rec in recs.values():
        est = max(1, int(round(scale * rec["vorp"])))
        rec["aav_est"] = est
        if rec["espn_aav"]:
            rec["aav"] = max(1, int(round(rec["espn_aav"])))
            rec["aav_src"] = "espn"
            if id(rec) in priced_ids:
                errors.append(abs(est - rec["aav"]))
        else:
            rec["aav"] = est
            rec["aav_src"] = "est"

    report["aav_replacement"] = {p: round(v, 1) for p, v in repl.items()}
    report["aav_scale"] = round(scale, 4)
    report["aav_calibration"] = round(calib, 4)
    report["aav_espn_priced"] = len(priced)
    report["aav_mae_vs_espn"] = round(sum(errors) / len(errors), 2) if errors else None


def consensus_key(rec):
    """Lower is better.  Blend of the ranks we have; unranked players fall in
    behind everything ranked, ordered by projection."""
    vals = [v for v in (rec.get("adp"), rec.get("ecr")) if v is not None]
    if vals:
        return sum(vals) / len(vals)
    return 1000.0 + max(0.0, 500.0 - rec["pts"])


def apply_cutoff(recs, report, top_n=600, top_k=24):
    ordered = sorted(recs.values(), key=consensus_key)
    keep = set()
    for rec in ordered[:top_n]:
        keep.add(id(rec))
    kickers = [r for r in ordered if r["pos"] == "K"][:top_k]
    for rec in kickers:
        keep.add(id(rec))
    for rec in ordered:
        if rec["pos"] == "DST":
            keep.add(id(rec))
        # a rank someone would actually draft at — ESPN's kona feed carries
        # ~1000 ranked rows and would otherwise defeat the cutoff entirely
        elif rec["espn_rank"] is not None and rec["espn_rank"] <= 300:
            keep.add(id(rec))
        elif rec["adp"] is not None and rec["adp"] < MAX_REAL_ADP:
            keep.add(id(rec))
    kept = [r for r in ordered if id(r) in keep]
    report["cutoff_pool"] = len(recs)
    report["cutoff_kept"] = len(kept)
    return kept


def _sleeper_says_comeback(rec):
    """Sleeper carries a designation that means "expected back" — PUP or a
    week-to-week grade.  When it does, ESPN's bare OUT must not override it."""
    return str(rec.get("injury") or "").strip().upper() in \
        {"PUP", "QUESTIONABLE", "DOUBTFUL"}


def classify_out(rec):
    """True when the player will not play this season — the flag the app reads.

    Deliberately conservative: only statuses that mean "gone", never the
    week-to-week ones.  A false OUT costs the user a draftable player, so the
    bar is a season-ending status from a source, not an inference.

    ESPN's OUT needs special care: in preseason it is a *this-week* grade, not
    a season verdict — the first live build marked George Kittle (PUP, back by
    September) OUT because ESPN graded him Out for a week nobody plays.  So
    ESPN OUT counts only when Sleeper does not carry a comeback-grade
    designation; ESPN INJURY_RESERVE and SUSPENSION are season-scoped and
    always count."""
    if str(rec.get("injury") or "").strip().upper() in SLEEPER_OUT_STATUSES:
        return True
    if str(rec.get("sleeper_status") or "").strip().lower() == SLEEPER_OUT_ROSTER_STATUS:
        return True
    espn = str(rec.get("espn_injury") or "").strip().upper()
    if espn in ("INJURY_RESERVE", "SUSPENSION"):
        return True
    if espn == "OUT" and not _sleeper_says_comeback(rec):
        return True
    return bool(rec.get("fp_out"))


def out_reasons(rec):
    """Human-readable list of why ``classify_out`` said yes."""
    why = []
    if str(rec.get("injury") or "").strip().upper() in SLEEPER_OUT_STATUSES:
        why.append(f"sleeper injury_status={rec['injury']}")
    if str(rec.get("sleeper_status") or "").strip().lower() == SLEEPER_OUT_ROSTER_STATUS:
        why.append("sleeper status=Injured Reserve")
    espn = str(rec.get("espn_injury") or "").strip().upper()
    if espn in ("INJURY_RESERVE", "SUSPENSION") or \
            (espn == "OUT" and not _sleeper_says_comeback(rec)):
        why.append(f"espn injuryStatus={rec['espn_injury']}")
    if rec.get("fp_out"):
        why.append("fantasypros headline")
    return why


def flag_injuries(recs, report):
    """Stamp the OUT flag and record what the sources disagreed about."""
    out_lines, disagreements = [], []
    for rec in recs.values():
        rec["out"] = classify_out(rec)
        if rec["out"]:
            out_lines.append(
                f"{rec['name']} ({rec['team'] or 'FA'} {rec['pos']}): "
                + ", ".join(out_reasons(rec)))
        sleeper_out = (str(rec.get("injury") or "").strip().upper() in SLEEPER_OUT_STATUSES
                       or str(rec.get("sleeper_status") or "").strip().lower()
                       == SLEEPER_OUT_ROSTER_STATUS)
        espn_out = str(rec.get("espn_injury") or "").strip().upper() in ESPN_OUT_STATUSES
        if "espn" in rec["sources"] and rec.get("espn_injury") and sleeper_out != espn_out:
            disagreements.append(
                f"{rec['name']} ({rec['pos']}): sleeper={rec.get('injury') or '—'}"
                f"/{rec.get('sleeper_status') or '—'} espn={rec['espn_injury']}")
    report["out_players"] = sorted(out_lines)
    report["injury_disagreements"] = sorted(disagreements)
    report["out_count"] = len(out_lines)


def provenance(rec):
    order = [s for s in ("sleeper", "espn", "ffc") if s in rec["sources"]]
    base = "+".join(order) or "unknown"
    return base if rec["aav_src"] == "espn" else base + " (aav est)"


def sleeper_note(rec):
    """The single ``Sleeper: …`` note segment.

    Exactly one per note, always last, so the app can replace it wholesale on
    a live refresh instead of stacking a new status on top of a stale one."""
    status = rec.get("injury")
    if not status and str(rec.get("sleeper_status") or "").strip().lower() \
            == SLEEPER_OUT_ROSTER_STATUS:
        status = "Injured Reserve"
    if not status:
        return ""
    seg = f"Sleeper: {status}"
    if rec.get("injury_body"):
        seg += f" ({rec['injury_body']})"
    if rec.get("injury_notes"):
        seg += f" — {rec['injury_notes']}"
    return seg


def build_note(rec):
    bits = list(rec["flags"])
    espn_status = str(rec.get("espn_injury") or "").strip().upper()
    if espn_status in ESPN_OUT_STATUSES:
        bits.append("ESPN: " + ESPN_STATUS_LABEL[espn_status])
    if rec.get("fp_note"):
        bits.append("FP: " + clean_text(rec["fp_note"], 110))
    seg = sleeper_note(rec)
    if seg:
        bits.append(seg)
    return " · ".join(bits)


def to_player(rec):
    p = {
        "name": rec["name"], "team": rec["team"], "pos": rec["pos"],
        "aav": int(rec["aav"]), "pts": rec["pts"], "src": provenance(rec),
        "note": build_note(rec),
    }
    if rec.get("out"):
        # the app treats this as the *data default*; a user who disagrees can
        # still un-check him and that override survives the next build
        p["out"] = True
    if rec["stats"]:
        p["stats"] = rec["stats"]
    if rec["adp"] is not None:
        p["adp"] = rec["adp"]
    # optional: only superflex leagues read it, and only Sleeper supplies it
    if rec.get("adp2") is not None:
        p["adp2"] = rec["adp2"]
    if rec["ecr"] is not None:
        p["ecr"] = rec["ecr"]
    if rec["bye"]:
        p["bye"] = rec["bye"]
    return p


def build_news(kept, limit=25, fp_items=None, tier_caps=(10, 5, 8)):
    """The old hand-written prose rots within weeks; generate the briefing from
    what Sleeper actually reports today instead.

    Ordered by severity, because the first build put 65 undifferentiated
    injury lines in the feed and "Questionable" read exactly like "torn ACL":

      1. season-enders — the players this build auto-marked OUT (cap 10)
      2. FantasyPros headlines, when that leg is active (cap 5)
      3. week-to-week statuses: Questionable / Doubtful / PUP (cap 8)
      4. team disagreements between sources
      5. ADP risers
    """
    lines = []
    cap_out, cap_fp, cap_day = tier_caps

    def why_out(rec):
        bits = []
        if rec.get("injury_body"):
            bits.append(rec["injury_body"])
        if rec.get("injury_notes"):
            bits.append(rec["injury_notes"])
        return f" ({'; '.join(bits)})" if bits else ""

    def out_status(rec):
        if rec.get("injury"):
            return rec["injury"]
        if str(rec.get("sleeper_status") or "").strip().lower() == SLEEPER_OUT_ROSTER_STATUS:
            return "Injured Reserve"
        espn = str(rec.get("espn_injury") or "").strip().upper()
        if espn in ESPN_STATUS_LABEL:
            return ESPN_STATUS_LABEL[espn]
        return "reported out" if rec.get("fp_out") else "ruled out"

    season_enders = sorted((r for r in kept if r.get("out")), key=consensus_key)
    for rec in season_enders[:cap_out]:
        status = out_status(rec)
        lines.append(
            f"{rec['name']} ({rec['team'] or 'FA'} {rec['pos']}) — out for the season"
            f"{why_out(rec)}. Status {status}; he is marked OUT here and left out "
            f"of every recommendation. Un-check him on the Data tab if you disagree.")
        if len(lines) >= limit:
            return lines[:limit]

    for headline in (fp_items or [])[:cap_fp]:
        lines.append("FP: " + headline)
        if len(lines) >= limit:
            return lines[:limit]

    day_to_day = sorted(
        (r for r in kept if r["injury"] and not r.get("out")), key=consensus_key)
    for rec in day_to_day[:cap_day]:
        lines.append(
            f"{rec['name']} ({rec['team'] or 'FA'} {rec['pos']}) — Sleeper injury status: "
            f"{rec['injury']}{why_out(rec)}. Week-to-week, not auto-marked OUT — "
            f"verify game-day status before you draft.")
        if len(lines) >= limit:
            return lines[:limit]

    # nobody needs "the room is paying up for him" about a player who is done
    # for the year — the season-ender tier already said everything worth saying
    moved = sorted(
        (r for r in kept if not r.get("out")
         and r["espn_team"] and r["team"] and r["espn_team"] != r["team"]),
        key=consensus_key)
    for rec in moved:
        lines.append(
            f"{rec['name']} ({rec['pos']}) — team disagreement across sources: "
            f"Sleeper says {rec['team']}, ESPN says {rec['espn_team']}. "
            f"Sleeper is treated as canon here.")
        if len(lines) >= limit:
            return lines
    risers = sorted(
        (r for r in kept if not r.get("out") and r["adp"] is not None
         and r["ecr"] is not None and r["ecr"] - r["adp"] >= 40),
        key=consensus_key)
    for rec in risers:
        lines.append(
            f"{rec['name']} ({rec['team']} {rec['pos']}) — drafted well ahead of his "
            f"ranking (ADP {rec['adp']:.0f} vs consensus rank {rec['ecr']}); the room "
            f"is paying up for him.")
        if len(lines) >= limit:
            break
    return lines[:limit]


# --------------------------------------------------------------------------
# FantasyPros — optional leg, only runs when FANTASYPROS_API_KEY is set
# --------------------------------------------------------------------------

FP_NEWS_URL = "https://api.fantasypros.com/v2/json/nfl/news?limit=50"


def load_fantasypros(api_key, fixtures_dir=None):
    """Return ``(payload, status)``.

    No key is not a failure — the whole leg is optional and the vast majority
    of builds run without it, so it reports ``skipped (no key)`` and never
    lands in ``meta.degraded``.  With a key set, a failure *is* degradation:
    the user asked for this source and did not get it."""
    if not api_key:
        return None, "skipped (no key)"
    try:
        if fixtures_dir:
            path = os.path.join(fixtures_dir, "fantasypros_news.json")
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh), "ok"
        return get_json(FP_NEWS_URL, headers={
            "x-api-key": api_key,
            "accept": "application/json",
            "user-agent": "berg-sheets-data-refresh/1.0",
        }), "ok"
    except Exception as e:                       # noqa: BLE001 — soft source
        return None, f"FAILED: {e}"


def parse_fantasypros(payload):
    """Flatten whatever shape came back into ``[{headline, text, players}]``.

    Their v2 responses have moved around between ``{"news": [...]}`` and a
    bare list, and item keys differ per endpoint, so read defensively and
    keep only what we can actually use."""
    if isinstance(payload, dict):
        rows = (payload.get("news") or payload.get("items")
                or payload.get("data") or payload.get("players") or [])
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    items = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, str):
            items.append({"headline": clean_text(row, 160), "text": row, "players": []})
            continue
        if not isinstance(row, dict):
            continue
        headline = ""
        for k in ("title", "headline", "name", "player_name"):
            if row.get(k):
                headline = str(row[k])
                break
        body = ""
        for k in ("description", "text", "summary", "analysis", "body", "excerpt"):
            if row.get(k):
                body = str(row[k])
                break
        names = []
        for k in ("player_name", "player", "players", "player_names", "playerName"):
            v = row.get(k)
            if isinstance(v, str):
                names.append(v)
            elif isinstance(v, list):
                for entry in v:
                    if isinstance(entry, str):
                        names.append(entry)
                    elif isinstance(entry, dict):
                        for kk in ("name", "player_name", "full_name"):
                            if entry.get(kk):
                                names.append(str(entry[kk]))
                                break
        if not headline and not body:
            continue
        items.append({
            "headline": clean_text(headline or body, 160),
            "text": f"{headline} {body}".strip(),
            "players": names,
        })
    return items


def apply_fantasypros(recs, items, report):
    """Corroborate OUT from FantasyPros headlines; return the headline list.

    Only season-ending language counts (``FP_OUT_KEYWORDS``) and it has to
    land on a name that is actually in the pool — a headline is a weaker
    signal than an injury status, so it gets the strictest gate."""
    by_norm = {}
    for rec in recs.values():
        by_norm.setdefault(norm_name(rec["name"]), []).append(rec)
    flagged = []
    for item in items:
        low = item["text"].lower()
        if not any(kw in low for kw in FP_OUT_KEYWORDS):
            continue
        hits = []
        for name in item["players"]:
            hits.extend(by_norm.get(norm_name(name), []))
        if not hits:
            for norm, group in by_norm.items():
                for rec in group:
                    if rec["pos"] != "DST" and rec["name"].lower() in low:
                        hits.append(rec)
        for rec in hits:
            if not rec.get("fp_out"):
                flagged.append(f"{rec['name']} ({rec['pos']}): {item['headline']}")
            rec["fp_out"] = True
            rec["fp_note"] = rec["fp_note"] or item["headline"]
    report["fp_items"] = len(items)
    report["fp_out_flagged"] = sorted(flagged)
    return [it["headline"] for it in items if it["headline"]]


# --------------------------------------------------------------------------
# validation gate
# --------------------------------------------------------------------------

class ValidationError(Exception):
    pass


def validate(data, min_players, sanity_names):
    players = data["players"]
    if len(players) < min_players:
        raise ValidationError(
            f"only {len(players)} players built, minimum is {min_players}")

    seen = set()
    for p in players:
        for field in ("name", "pos", "team", "aav", "pts", "src", "note"):
            if field not in p:
                raise ValidationError(f"{p.get('name')!r}: missing field {field}")
        if p["pos"] not in POSITIONS:
            raise ValidationError(f"{p['name']!r}: bad position {p['pos']!r}")
        if not isinstance(p["aav"], int) or p["aav"] < 1:
            raise ValidationError(f"{p['name']!r}: bad aav {p['aav']!r}")
        if not isinstance(p["pts"], (int, float)) or p["pts"] < 0:
            raise ValidationError(f"{p['name']!r}: bad pts {p['pts']!r}")
        if p.get("stats") is not None:
            for k in p["stats"]:
                if k not in STAT_KEYS:
                    raise ValidationError(f"{p['name']!r}: unknown stat key {k!r}")
        # the app reads `out` as a boolean data default; a stray string or 0/1
        # would flow straight into freshPlayer() and mean something else there
        if "out" in p and not isinstance(p["out"], bool):
            raise ValidationError(f"{p['name']!r}: out must be a bool, got {p['out']!r}")
        # adp2 (superflex ADP) is optional, but when present the app sorts on
        # it — a string would sort lexicographically and scramble the board
        if "adp2" in p:
            if isinstance(p["adp2"], bool) or \
                    not isinstance(p["adp2"], (int, float)) or p["adp2"] <= 0:
                raise ValidationError(
                    f"{p['name']!r}: adp2 must be a positive number, got {p['adp2']!r}")
        pid = (p["name"] + "|" + p["pos"]).lower()
        if pid in seen:
            raise ValidationError(f"duplicate playerId {pid!r}")
        seen.add(pid)

    for want in sanity_names:
        if want.lower() not in seen:
            raise ValidationError(f"sanity check failed: {want} missing from pool")

    if not data["meta"].get("asOf"):
        raise ValidationError("meta.asOf missing")


# --------------------------------------------------------------------------
# splice
# --------------------------------------------------------------------------

def encode(data):
    blob = json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=False)
    if "\n" in blob or "\r" in blob:
        raise ValidationError("encoded data contains a newline")
    if "</script" in blob.lower():
        raise ValidationError("encoded data would close the <script> tag")
    return blob


def splice(html, blob):
    i = html.find(DATA_START)
    j = html.find(DATA_END)
    if i < 0 or j < 0 or j < i:
        raise ValidationError("data markers not found in index.html")
    out = html[:i + len(DATA_START)] + blob + html[j:]
    # re-parse what we just wrote before anyone gets to see it
    a = out.find(DATA_START) + len(DATA_START)
    b = out.find(DATA_END)
    json.loads(out[a:b])
    if out.count("\n") != html.count("\n"):
        raise ValidationError("splice changed the line count of index.html")
    return out


def read_bundle(html):
    a = html.find(DATA_START)
    b = html.find(DATA_END)
    if a < 0 or b < 0:
        raise ValidationError("data markers not found")
    return json.loads(html[a + len(DATA_START):b])


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def render_report(data, status, report):
    meta = data["meta"]
    L = []
    A = L.append
    A("# Data build report")
    A("")
    A(f"- Built: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    A(f"- Season: {report.get('season')}")
    A(f"- Players in bundle: **{len(data['players'])}**")
    A(f"- News lines: {len(data['news'])}")
    if meta.get("degraded"):
        A(f"- **Degraded sources:** {', '.join(meta['degraded'])}")
    A("")
    A("## Source status")
    A("")
    A("| Source | Status |")
    A("|---|---|")
    for k, v in status.items():
        A(f"| {k} | {v} |")
    A("")
    A("## Counts")
    A("")
    A(f"- Sleeper players DB entries: {report.get('sleeper_players_count')}")
    A(f"- Sleeper projection rows: {report.get('sleeper_projection_rows')}")
    A(f"- Dropped (no stats, no ADP): {report.get('sleeper_dropped_no_signal')}")
    A(f"- ESPN matched / added: {report.get('espn_matched')} / {report.get('espn_added')}")
    A(f"- FFC matched / added: {report.get('ffc_matched')} / {report.get('ffc_added')}")
    A(f"- Backfilled from the Sleeper players DB: {report.get('sleeper_backfilled')} "
      f"({report.get('sleeper_backfilled_teams')} team corrections)")
    A(f"- Players marked OUT: {report.get('out_count')}")
    A(f"- Carrying a superflex (2QB) ADP: {report.get('adp2_count')}"
      f" (of which QB: {report.get('adp2_qb_count')})")
    A(f"- FantasyPros headlines parsed: {report.get('fp_items', 0)}")
    A(f"- Pool before cutoff: {report.get('cutoff_pool')} → kept {report.get('cutoff_kept')}")
    A("")
    A("### Position breakdown")
    A("")
    counts = {}
    for p in data["players"]:
        counts[p["pos"]] = counts.get(p["pos"], 0) + 1
    for pos in POSITIONS:
        A(f"- {pos}: {counts.get(pos, 0)}")
    A("")
    A("## Auction values")
    A("")
    A(f"- Replacement points: {report.get('aav_replacement')}")
    A(f"- $/VORP scale: {report.get('aav_scale')} (calibration factor {report.get('aav_calibration')})")
    A(f"- ESPN-priced players: {report.get('aav_espn_priced')}")
    A(f"- Mean abs error of the VORP model vs ESPN prices: {report.get('aav_mae_vs_espn')}")
    A("")

    def section(title, items, cap=40):
        A(f"## {title} ({len(items)})")
        A("")
        if not items:
            A("_none_")
        for line in items[:cap]:
            A(f"- {line}")
        if len(items) > cap:
            A(f"- …and {len(items) - cap} more")
        A("")

    section("Marked OUT (excluded from recommendations)", report.get("out_players") or [])
    section("Teamless season-enders dropped (retired-player DB residue)",
            report.get("dropped_teamless_out") or [])
    section("D/ST opening-month schedule (softest slate first)",
            report.get("dst_schedule") or [])
    section("Injury disagreements (Sleeper vs ESPN)",
            report.get("injury_disagreements") or [])
    if report.get("fp_out_flagged"):
        section("FantasyPros OUT corroboration", report["fp_out_flagged"])
    section("Team disagreements", report.get("team_mismatches") or [])
    section("Projection splits", report.get("projection_splits") or [])
    section("ESPN rows not matched and not added", report.get("espn_unmatched") or [])
    section("FFC rows with no Sleeper match", report.get("ffc_unmatched") or [])
    A("---")
    A("")
    A(FFC_ATTRIBUTION)
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# top level
# --------------------------------------------------------------------------

def build(season, fixtures_dir=None, as_of=None, fp_key=None):
    report = {"season": season}
    raw, status = load_sources(season, fixtures_dir)

    recs, sleeper_by_key = ingest_sleeper(raw, report)
    ingest_espn(raw, recs, report)
    ingest_ffc(raw, recs, report)
    # ESPN/FFC-added rows never saw the players DB — join them back before
    # anything reads injuries, or a dropped projection hides a torn ACL
    backfill_from_sleeper(recs, sleeper_by_key, report)
    ingest_byes(raw, recs)
    resolve_teams(recs, report)
    blend_projections(recs, report)
    blend_ranks(recs)
    compute_aav(recs, report)

    fp_payload, fp_status = load_fantasypros(fp_key, fixtures_dir)
    status["fantasypros"] = fp_status
    fp_headlines = []
    if fp_payload is not None:
        fp_headlines = apply_fantasypros(recs, parse_fantasypros(fp_payload), report)
    # Sleeper's DB keeps long-retired players parked on "Injured Reserve"
    # forever (Adam Vinatieri was 'out for the season' in the second live
    # build's briefing). A season-ender with no team isn't a draftable player
    # or news — he's database residue. Dropped before flag_injuries so the
    # report's OUT count matches what actually ships.
    ghosts = {k: r for k, r in recs.items() if classify_out(r) and not r["team"]}
    for k in ghosts:
        del recs[k]
    report["dropped_teamless_out"] = sorted(
        f"{r['name']} ({r['pos']})" for r in ghosts.values())

    flag_injuries(recs, report)
    annotate_dst_schedules(recs, raw.get("espn_byes"), report)

    kept = apply_cutoff(recs, report)
    kept.sort(key=lambda r: (-r["aav"], consensus_key(r), r["name"]))

    # "skipped" is not "degraded" — an optional leg nobody enabled is normal
    degraded = [k for k, v in status.items()
                if v != "ok" and not str(v).startswith("skipped")]
    sources = list(SOURCE_LINKS)
    if fp_status == "ok":
        sources.append(FP_SOURCE_LINK)
    data = {
        "meta": {
            "asOf": as_of or date.today().isoformat(),
            "format": "PPR, 12-team, $200 budget",
            "built": "scripts/build_data.py",
            "sources": sources,
            "attribution": FFC_ATTRIBUTION,
            "degraded": degraded,
        },
        "news": build_news(kept, fp_items=fp_headlines),
        "players": [to_player(r) for r in kept],
    }
    with_adp2 = [p for p in data["players"] if p.get("adp2") is not None]
    report["adp2_count"] = len(with_adp2)
    report["adp2_qb_count"] = len([p for p in with_adp2 if p["pos"] == "QB"])
    return data, status, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--index", default=os.path.join(here, "index.html"),
                    help="index.html to splice (default: repo root)")
    ap.add_argument("--report", default=os.path.join(here, "DATA_REPORT.md"),
                    help="path for the build report")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--fixtures-dir", default=None,
                    help="read committed fixture JSONs instead of the network")
    ap.add_argument("--as-of", default=None, help="override meta.asOf (ISO date)")
    ap.add_argument("--min-players", type=int, default=450,
                    help="abort if fewer players than this survive the build")
    ap.add_argument("--sanity-names", default=None,
                    help="comma-separated 'Name|POS' that must be present "
                         "(default: a built-in list of consensus stars)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and validate but write nothing")
    ap.add_argument("--fp-key", default=None,
                    help="FantasyPros API key (defaults to $FANTASYPROS_API_KEY; "
                         "with neither, the FantasyPros leg is skipped)")
    args = ap.parse_args(argv)

    sanity = ([s.strip() for s in args.sanity_names.split(",") if s.strip()]
              if args.sanity_names is not None else DEFAULT_SANITY_NAMES)

    fp_key = args.fp_key or os.environ.get("FANTASYPROS_API_KEY") or None

    try:
        data, status, report = build(args.season, args.fixtures_dir, args.as_of, fp_key)
        validate(data, args.min_players, sanity)
        blob = encode(data)
        with open(args.index, "r", encoding="utf-8") as fh:
            html = fh.read()
        out = splice(html, blob)
    except (SourceError, ValidationError) as e:
        print(f"build_data: ABORT — {e}", file=sys.stderr)
        return 1

    md = render_report(data, status, report)
    if args.dry_run:
        print(md)
        print(f"build_data: dry run OK — {len(data['players'])} players, "
              f"{len(blob)} bytes of JSON", file=sys.stderr)
        return 0

    with open(args.index, "w", encoding="utf-8") as fh:
        fh.write(out)
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"build_data: wrote {len(data['players'])} players to {args.index} "
          f"({len(blob)} bytes); report at {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
