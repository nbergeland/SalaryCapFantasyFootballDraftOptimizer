#!/usr/bin/env python3
"""Pull a private ESPN league's JSON using the owner's own session cookies.

Runs on GitHub Actions with the user's espn_s2 + SWID stored as repository
secrets — the credentials live in the repo owner's encrypted secrets and are
sent only to ESPN. The output file carries the league payload plus a pulled-at
stamp and NEVER the cookies.

Environment:
    ESPN_S2, SWID        the session cookies (repo secrets); both required
    ESPN_LEAGUE_ID       the league to pull (repo variable or dispatch input)
    ESPN_SEASON          season year, default 2026

Exit codes: 0 on success or an explicit skip (no secrets — the scheduled run
must stay green on forks without setup), 1 on a real failure (bad cookies,
unknown league) so the workflow run says so.
"""
import json
import os
import sys
from datetime import datetime, timezone

VIEWS = "view=mDraftDetail&view=mTeam&view=mRoster&view=mSettings"


def league_url(league_id, season):
    return (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
            f"{season}/segments/0/leagues/{league_id}?{VIEWS}")


def cookie_header(espn_s2, swid):
    # SWID is stored with its braces on espn.com; tolerate a secret saved
    # without them
    swid = swid.strip()
    if swid and not swid.startswith("{"):
        swid = "{" + swid.strip("{}") + "}"
    return f"espn_s2={espn_s2.strip()}; SWID={swid}"


def fetch(url, cookie):
    import urllib.request
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Cookie": cookie,
        "User-Agent": "bergsheets-league-pull/1.0",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def envelope(data, league_id, season, now=None):
    return {
        "pulled": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "league_id": str(league_id),
        "season": int(season),
        "teams": len(data.get("teams") or []),
        "picks": len(((data.get("draftDetail") or {}).get("picks")) or []),
        "data": data,
    }


def main():
    espn_s2 = os.environ.get("ESPN_S2", "")
    swid = os.environ.get("SWID", "")
    league_id = os.environ.get("ESPN_LEAGUE_ID", "").strip()
    season = os.environ.get("ESPN_SEASON", "2026").strip() or "2026"
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/espn_league.json"

    if not espn_s2 or not swid:
        print("pull_espn_league: skipped — ESPN_S2 / SWID secrets are not set. "
              "Add them under Settings → Secrets and variables → Actions "
              "(values from your espn.com cookies) to enable the pull.")
        return 0
    if not league_id:
        print("pull_espn_league: FAILED — no league id. Set the repository "
              "variable ESPN_LEAGUE_ID (or pass the workflow input).",
              file=sys.stderr)
        return 1

    url = league_url(league_id, season)
    print(f"pull_espn_league: GET league {league_id}, season {season}")
    try:
        status, body = fetch(url, cookie_header(espn_s2, swid))
    except Exception as e:  # urllib raises on 4xx/5xx too
        status = getattr(e, "code", None)
        if status in (401, 403):
            print(f"pull_espn_league: FAILED — ESPN answered {status}. The "
                  "cookies were rejected: they may have expired (log out and "
                  "back into espn.com, then update the ESPN_S2 / SWID secrets) "
                  "or belong to an account that isn't in this league.",
                  file=sys.stderr)
            return 1
        if status == 404:
            print("pull_espn_league: FAILED — ESPN answered 404. Check "
                  f"ESPN_LEAGUE_ID ({league_id}) and season ({season}).",
                  file=sys.stderr)
            return 1
        print(f"pull_espn_league: FAILED — {e}", file=sys.stderr)
        return 1

    try:
        data = json.loads(body)
    except ValueError:
        print("pull_espn_league: FAILED — ESPN returned non-JSON "
              f"(status {status}).", file=sys.stderr)
        return 1
    if not isinstance(data, dict) or not data.get("teams"):
        msg = data.get("messages") if isinstance(data, dict) else None
        print(f"pull_espn_league: FAILED — no teams in the response"
              f"{' — ESPN said: ' + '; '.join(map(str, msg)) if msg else ''}.",
              file=sys.stderr)
        return 1

    env = envelope(data, league_id, season)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(env, fh, separators=(",", ":"))
    print(f"pull_espn_league: OK — {env['teams']} teams, {env['picks']} draft "
          f"picks → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
