#!/usr/bin/env python3
"""Fetch Justin Boone's 2026 rankings (and salary-cap values) into
data/boone_2026.json, for scripts/build_data.py to blend as an expert source.

Run by .github/workflows/boone-refresh.yml on MANUAL dispatch only — this
reads editorial articles, so it is a polite one-shot pull when the user asks
for a refresh, never a recurring scraper. The dev sandbox has no egress; the
Actions runner does.

Articles (Yahoo Sports, with AOL syndication mirrors as fallback):
  - the full-PPR top-300 (overall ranks)
  - per-position "Rankings Tiers and Salary Cap Values" pieces
    (12-team, $200, half-PPR — close enough to blend, and noted in meta)

Parsing is deliberately forgiving: article markup shifts, so several row
shapes are tried and the run prints diagnostics (match counts, a text
sample on failure) to the job log for iteration without artifact plumbing.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (compatible; BergSheetsPersonal/1.0; "
      "personal fantasy tool, one-shot manual fetch)")

# AOL syndication mirrors flatten the content into static HTML; Yahoo's own
# article pages render the list with JavaScript and serve an empty shell
# (verified on the first live fetch), so the mirrors go first.
TOP300 = [
    "https://www.aol.com/articles/2026-fantasy-football-full-ppr-155359000.html",
    "https://sports.yahoo.com/fantasy/article/2026-fantasy-football-full-ppr-rankings-justin-boones-top-300-players-155359326.html",
    "https://sports.yahoo.com/fantasy/article/2026-fantasy-football-rankings-justin-boone-top-300-players-155300098.html",
]
CAP_ARTICLES = {
    "RB": ["https://www.aol.com/sports/fantasy-football-justin-boones-rankings-154116242.html"],
    "TE": ["https://www.aol.com/sports/fantasy-football-justin-boones-rankings-154122967.html"],
    # WR/QB slugs are discovered from links inside the articles above when
    # not listed here; add them explicitly once known.
    "WR": [],
    "QB": [],
}

POS_RE = r"(?:QB|RB|WR|TE|K|D/?ST|DEF)"


def fetch(url, timeout=30):
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.text


def strip_tags(page):
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<br[^>]*>|</p>|</li>|</tr>|</h\d>", "\n", page, flags=re.I)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html_mod.unescape(page)
    return re.sub(r"[ \t]+", " ", page)


def parse_overall(text):
    """Ranked rows: '12. Player Name, TEAM' / '12. Player Name (WR4) TEAM'."""
    rows = {}
    pat = re.compile(
        r"(?m)^\s*(\d{1,3})[.)]?\s+([A-Z][A-Za-z.'\- ]+?[a-z.])"
        r"(?:\s*[,(–—-]+\s*(?:[A-Z]{2,3}\s*[,/ ]\s*)?(" + POS_RE + r")\d*\)?)?"
        r"(?:\s*[,–—-]+\s*[A-Z]{2,3})?\s*$")
    for m in pat.finditer(text):
        rank = int(m.group(1))
        if 1 <= rank <= 300 and rank not in rows:
            rows[rank] = {"rank": rank, "name": m.group(2).strip(),
                          "pos": (m.group(3) or "").replace("DEF", "DST").replace("D/ST", "DST")}
    return [rows[k] for k in sorted(rows)]


def parse_cap_values(text, pos):
    """Value rows: 'Player Name — $23' / 'Player Name: $23' / 'Player Name $23'."""
    out = []
    seen = set()
    pat = re.compile(
        r"([A-Z][A-Za-z.'\- ]+?[a-z.])\s*(?:[—:–-]\s*)?\$\s*(\d{1,3})\b")
    for m in pat.finditer(text):
        name, val = m.group(1).strip(), int(m.group(2))
        if val > 200 or len(name.split()) > 4 or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append({"name": name, "pos": pos, "value": val})
    return out


def discover_links(page):
    """Companion-article URLs mentioned inside a fetched page's raw HTML."""
    urls = set()
    for m in re.finditer(
            r'https://(?:sports\.yahoo\.com|www\.aol\.com)/[^"\' >]*'
            r'(?:justin-boone|boone|fantasy-football)[^"\' >]*\.html', page):
        urls.add(m.group(0))
    return urls


def iframe_srcs(page):
    return re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', page, flags=re.I)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/boone_2026.json")
    args = ap.parse_args(argv)

    overall, values, sources, errors = [], [], [], []

    for url in TOP300:
        try:
            page = fetch(url)
            text = strip_tags(page)
            overall = parse_overall(text)
            print(f"boone: top-300 from {url}: {len(overall)} ranked rows")
            if len(overall) >= 150:
                sources.append(url)
                break
            # the ranking table may live in an embedded iframe — follow
            # same-host frames before giving up on this URL
            for src in iframe_srcs(page)[:6]:
                if not src.startswith("http"):
                    src = "https://sports.yahoo.com" + src
                try:
                    itext = strip_tags(fetch(src))
                    got = parse_overall(itext)
                    print(f"boone: iframe {src}: {len(got)} ranked rows")
                    if len(got) >= 150:
                        overall = got
                        sources.append(src)
                        break
                except Exception as ie:                        # noqa: BLE001
                    print(f"boone: iframe {src} failed: {ie}")
            if len(overall) >= 150:
                break
            errors.append(f"{url}: only {len(overall)} rows parsed")
            for disc in sorted(discover_links(page)):
                print(f"boone: raw-html link: {disc}")
            print("boone: text sample for parser iteration:\n" + text[:1500])
        except Exception as e:                                  # noqa: BLE001
            errors.append(f"{url}: {e}")
            print(f"boone: FAILED {url}: {e}")

    for pos, urls in CAP_ARTICLES.items():
        for url in urls:
            try:
                text = strip_tags(fetch(url))
                got = parse_cap_values(text, pos)
                print(f"boone: {pos} cap values from {url}: {len(got)} rows")
                if got:
                    values.extend(got)
                    sources.append(url)
                    break
                print("boone: text sample:\n" + text[:1200])
            except Exception as e:                              # noqa: BLE001
                errors.append(f"{url}: {e}")
                print(f"boone: FAILED {url}: {e}")

    if len(overall) < 150:
        print("boone: ABORT — top-300 parse below threshold; not writing")
        return 1
    data = {
        "meta": {
            "expert": "Justin Boone (Yahoo Sports)",
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "format": "half-PPR, 12-team, $200 salary cap",
            "sources": sources,
            "errors": errors,
        },
        "overall": overall,
        "values": values,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    print(f"boone: wrote {args.out}: {len(overall)} ranks, {len(values)} values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
