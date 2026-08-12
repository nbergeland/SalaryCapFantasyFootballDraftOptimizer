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
Sleeper projections api.sleeper.com/projections/nfl/YYYY season stat projections, pts_ppr, adp_ppr
FFC ADP            fantasyfootballcalculator.com        real-draft ADP (attribution requested)
ESPN kona          lm-api-reads.fantasy.espn.com        auction values, PPR ranks, 2nd projection
ESPN pro teams     lm-api-reads.fantasy.espn.com        bye weeks

Outage policy: if either Sleeper source fails the build aborts and nothing is
written (yesterday's data stays live).  ESPN/FFC are degradable — the build
proceeds and records the loss in ``meta.degraded`` and in DATA_REPORT.md.

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
from datetime import date, datetime, timezone

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

DATA_START = "/*__DATA__*/"
DATA_END = "/*__END_DATA__*/"

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]

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

FFC_ATTRIBUTION = "ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com)."


# --------------------------------------------------------------------------
# normalization — byte-for-byte mirrors of the JS helpers in index.html
# --------------------------------------------------------------------------

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")
_NON_ALPHA_RE = re.compile(r"[^a-z]")


def norm_name(s) -> str:
    """Mirror of normName() in index.html (~line 2555)."""
    return _NON_ALPHA_RE.sub("", _SUFFIX_RE.sub("", str(s).lower()))


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
             f"{season}/segments/0/leagues/leaguedefaults/3?view=kona_player_info",
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


def index_sleeper_players(players_db):
    """id -> record, plus a key -> record index."""
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
               "search_rank": pl.get("search_rank"), "injury": pl.get("injury_status")}
        by_id[str(pid)] = rec
        by_key.setdefault(pkey(name, pos, team), rec)
    return by_id, by_key


def new_record(name, pos, team):
    return {
        "name": name, "pos": pos, "team": team,
        "stats": None, "sleeper_pts": None, "sleeper_adp": None,
        "search_rank": None, "injury": None,
        "espn_rank": None, "espn_aav": None, "espn_pts": None, "espn_team": "",
        "ffc_adp": None, "ffc_team": "",
        "bye": None, "sources": set(), "flags": [],
    }


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

        if not stats and adp is None and pos not in ("K", "DST"):
            dropped += 1                            # no signal at all — skip
            continue

        key = pkey(name, pos, team)
        rec = recs.get(key) or new_record(name, pos, team)
        rec["stats"] = stats or None
        rec["sleeper_pts"] = round(float(pts), 1) if pts is not None else None
        rec["sleeper_adp"] = round(float(adp), 1) if adp is not None else None
        rec["sources"].add("sleeper")
        if db:
            rec["search_rank"] = db.get("search_rank")
            rec["injury"] = db.get("injury")
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
        elif rec["espn_rank"] is not None or rec["adp"] is not None:
            keep.add(id(rec))
    kept = [r for r in ordered if id(r) in keep]
    report["cutoff_pool"] = len(recs)
    report["cutoff_kept"] = len(kept)
    return kept


def provenance(rec):
    order = [s for s in ("sleeper", "espn", "ffc") if s in rec["sources"]]
    base = "+".join(order) or "unknown"
    return base if rec["aav_src"] == "espn" else base + " (aav est)"


def build_note(rec):
    bits = list(rec["flags"])
    if rec["injury"]:
        bits.append(f"Sleeper: {rec['injury']}")
    return " · ".join(bits)


def to_player(rec):
    p = {
        "name": rec["name"], "team": rec["team"], "pos": rec["pos"],
        "aav": int(rec["aav"]), "pts": rec["pts"], "src": provenance(rec),
        "note": build_note(rec),
    }
    if rec["stats"]:
        p["stats"] = rec["stats"]
    if rec["adp"] is not None:
        p["adp"] = rec["adp"]
    if rec["ecr"] is not None:
        p["ecr"] = rec["ecr"]
    if rec["bye"]:
        p["bye"] = rec["bye"]
    return p


def build_news(kept, limit=25):
    """The old hand-written prose rots within weeks; generate the briefing from
    what Sleeper actually reports today instead."""
    lines = []
    injured = sorted((r for r in kept if r["injury"]), key=consensus_key)
    for rec in injured:
        lines.append(
            f"{rec['name']} ({rec['team'] or 'FA'} {rec['pos']}) — Sleeper injury status: "
            f"{rec['injury']}. Verify game-day status before you draft.")
        if len(lines) >= limit:
            return lines
    moved = sorted(
        (r for r in kept
         if r["espn_team"] and r["team"] and r["espn_team"] != r["team"]),
        key=consensus_key)
    for rec in moved:
        lines.append(
            f"{rec['name']} ({rec['pos']}) — team disagreement across sources: "
            f"Sleeper says {rec['team']}, ESPN says {rec['espn_team']}. "
            f"Sleeper is treated as canon here.")
        if len(lines) >= limit:
            return lines
    risers = sorted(
        (r for r in kept if r["adp"] is not None and r["ecr"] is not None
         and r["ecr"] - r["adp"] >= 40), key=consensus_key)
    for rec in risers:
        lines.append(
            f"{rec['name']} ({rec['team']} {rec['pos']}) — drafted well ahead of his "
            f"ranking (ADP {rec['adp']:.0f} vs consensus rank {rec['ecr']}); the room "
            f"is paying up for him.")
        if len(lines) >= limit:
            break
    return lines[:limit]


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

def build(season, fixtures_dir=None, as_of=None):
    report = {"season": season}
    raw, status = load_sources(season, fixtures_dir)

    recs, _sleeper_by_key = ingest_sleeper(raw, report)
    ingest_espn(raw, recs, report)
    ingest_ffc(raw, recs, report)
    ingest_byes(raw, recs)
    resolve_teams(recs, report)
    blend_projections(recs, report)
    blend_ranks(recs)
    compute_aav(recs, report)
    kept = apply_cutoff(recs, report)
    kept.sort(key=lambda r: (-r["aav"], consensus_key(r), r["name"]))

    degraded = [k for k, v in status.items() if v != "ok"]
    data = {
        "meta": {
            "asOf": as_of or date.today().isoformat(),
            "format": "PPR, 12-team, $200 budget",
            "built": "scripts/build_data.py",
            "sources": list(SOURCE_LINKS),
            "attribution": FFC_ATTRIBUTION,
            "degraded": degraded,
        },
        "news": build_news(kept),
        "players": [to_player(r) for r in kept],
    }
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
    args = ap.parse_args(argv)

    sanity = ([s.strip() for s in args.sanity_names.split(",") if s.strip()]
              if args.sanity_names is not None else DEFAULT_SANITY_NAMES)

    try:
        data, status, report = build(args.season, args.fixtures_dir, args.as_of)
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
