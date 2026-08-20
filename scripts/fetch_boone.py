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
    # third-party syndication renders the list as static HTML
    "https://thepicks.com/us/news/nfl/2026-fantasy-football-full-ppr-rankings-justin-boone/",
    "https://www.aol.com/articles/2026-fantasy-football-full-ppr-155359000.html",
    "https://sports.yahoo.com/fantasy/article/2026-fantasy-football-full-ppr-rankings-justin-boones-top-300-players-155359326.html",
    "https://sports.yahoo.com/fantasy/article/2026-fantasy-football-rankings-justin-boone-top-300-players-155300098.html",
]
CAP_ARTICLES = {
    "RB": [
        "https://sports.yahoo.com/fantasy/article/fantasy-football-justin-boones-running-backs-rankings-tiers-and-salary-cap-values-154116034.html",
        "https://www.aol.com/sports/fantasy-football-justin-boones-rankings-154116242.html",
    ],
    "TE": ["https://www.aol.com/sports/fantasy-football-justin-boones-rankings-154122967.html"],
    "QB": [
        "https://sports.yahoo.com/fantasy/article/fantasy-football-justin-boones-rankings-quarterbacks-tiers-and-salary-cap-values-154113133.html",
        "https://www.aol.com/sports/fantasy-football-justin-boones-rankings-154113349.html",
    ],
    "WR": [
        "https://sports.yahoo.com/fantasy/article/fantasy-football-justin-boones-wide-receiver-rankings-tiers-and-salary-cap-values-154119352.html",
        "https://www.aol.com/sports/fantasy-football-justin-boones-rankings-154119951.html",
        "https://ca.sports.yahoo.com/news/fantasy-football-justin-boones-wide-receiver-rankings-tiers-and-salary-cap-values-154119352.html",
    ],
}

# a single article carrying values for EVERY position, split by section
# headings (user-supplied). If the values on it are only visible to Fantasy
# Ultra subscribers, the public fetch simply finds none — reported honestly,
# never worked around: no login, no paywall circumvention, ever.
CAP_ALL_PAGES = [
    "https://sports.yahoo.com/fantasy/article/fantasy-ultra-has-arrived--heres-everything-you-need-to-know-125559999.html",
]

SECTION_POS = [
    (re.compile(r"quarterback", re.I), "QB"),
    (re.compile(r"running\s*back", re.I), "RB"),
    (re.compile(r"wide\s*receiver", re.I), "WR"),
    (re.compile(r"tight\s*end", re.I), "TE"),
    (re.compile(r"kicker", re.I), "K"),
    (re.compile(r"defen[cs]e|d/?st", re.I), "DST"),
]


def parse_cap_sections(text):
    """Values article covering all positions: split on position headings and
    parse each section with its own position tag."""
    marks = []
    for pat, pos in SECTION_POS:
        m = pat.search(text)
        if m:
            marks.append((m.start(), pos))
    marks.sort()
    out = []
    for i, (start, pos) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.extend(parse_cap_values(text[start:end], pos))
    return out

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
        r"(?:\s*[,(–—-]+\s*(?:[A-Z]{2,3}\s*[,/ ]?\s*)?\(?(" + POS_RE + r")\d*\)?)?"
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


def article_year_ok(text, want="2026"):
    """These salary-cap articles carry evergreen titles; a stale mirror would
    silently feed last season's board. The FIRST year token near the top is
    the dateline; a mere '2026' in surrounding navigation must not pass —
    a 2025 article slipped through exactly that way on the fourth live run."""
    head = text[:4000]
    m = re.search(r"\b(20\d{2})\b", head)
    print(f"boone: dateline year seen: {m.group(1) if m else 'none'}")
    return bool(m) and m.group(1) == want


def derive_overall_from_values(values):
    """Boone's $200-cap values price every position on one scale, so sorting
    them is his cross-position board — the honest fallback when the top-300
    article itself is an unparseable client-rendered shell."""
    ordered = sorted(values, key=lambda v: (-v["value"], v["pos"], v["name"]))
    return [{"rank": i + 1, "name": v["name"], "pos": v["pos"]}
            for i, v in enumerate(ordered)]


def render_text(url, wait_ms=4000):
    """Load the page in headless Chromium and return the rendered body text —
    the last resort for articles whose list only exists client-side. One page
    per call, closed immediately; still a polite one-shot."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:                                       # noqa: BLE001
            pass
        page.wait_for_timeout(wait_ms)
        text = page.inner_text("body")
        browser.close()
    return text


def iframe_srcs(page):
    return re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', page, flags=re.I)


def parse_embedded_json(page):
    """Rankings living in hydration JSON inside <script> tags — the list
    Yahoo renders client-side is usually shipped as data in the raw HTML.
    Accept both key orders and a few key spellings."""
    rows = {}
    pats = [
        re.compile(r'"(?:player_?[Nn]ame|name|full[Nn]ame)"\s*:\s*"([^"]{3,40})"[^{}]{0,220}?"(?:overall_?)?rank"\s*:\s*"?(\d{1,3})"?'),
        re.compile(r'"(?:overall_?)?rank"\s*:\s*"?(\d{1,3})"?[^{}]{0,220}?"(?:player_?[Nn]ame|name|full[Nn]ame)"\s*:\s*"([^"]{3,40})"'),
    ]
    for i, pat in enumerate(pats):
        for m in pat.finditer(page):
            name, rank = (m.group(1), int(m.group(2))) if i == 0 else (m.group(2), int(m.group(1)))
            if 1 <= rank <= 300 and rank not in rows and not name.isupper():
                rows[rank] = {"rank": rank, "name": name.strip(), "pos": ""}
    return [rows[k] for k in sorted(rows)]


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
            print(f"boone: top-300 from {url}: {len(overall)} ranked rows (text)")
            if len(overall) < 150:
                got = parse_embedded_json(page)
                print(f"boone: embedded-json scan: {len(got)} ranked rows")
                if len(got) > len(overall):
                    overall = got
            if len(overall) >= 150:
                sources.append(url)
                break
            # where is the data? print embed-ish URLs from the raw page
            for eu in sorted(set(re.findall(
                    r'https://[^"\' >]*(?:embed|rankings|graphite|datawrapper|infogram)[^"\' >]*', page)))[:12]:
                print(f"boone: embed-ish url: {eu}")
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

    for url in CAP_ALL_PAGES:
        try:
            text = render_text(url, wait_ms=6000)
            if not article_year_ok(text):
                print(f"boone: REJECT {url}: not verifiably 2026")
            else:
                got = parse_cap_sections(text)
                by_pos = {}
                for v in got:
                    by_pos[v["pos"]] = by_pos.get(v["pos"], 0) + 1
                print(f"boone: ALL-page cap values from {url}: {len(got)} rows {by_pos}")
                for v in got[:6]:
                    print(f"boone:   sample: {v['name']} ({v['pos']}) ${v['value']}")
                if len(got) >= 60 and len(by_pos) >= 3:
                    values.extend(got)
                    sources.append(url)
                else:
                    idx = max(text.find("$"), 0)
                    print("boone: ALL-page sample near first $:\n" + text[max(0,idx-300):idx+900])
                    print("boone: values not freely visible or unparsed — if they are "
                          "Fantasy Ultra subscriber content, they stay out: no paywall workarounds.")
        except Exception as e:                                  # noqa: BLE001
            errors.append(f"{url}: {e}")
            print(f"boone: FAILED {url}: {e}")

    covered = {v["pos"] for v in values}
    for pos, urls in CAP_ARTICLES.items():
        if pos in covered:
            continue
        for url in urls:
            try:
                text = strip_tags(fetch(url))
                got = []
                if article_year_ok(text):
                    got = parse_cap_values(text, pos)
                if not got:
                    text = render_text(url)
                    if not article_year_ok(text):
                        errors.append(f"{url}: no 2026 dateline — stale edition?")
                        print(f"boone: REJECT {url}: not verifiably 2026")
                        continue
                    got = parse_cap_values(text, pos)
                print(f"boone: {pos} cap values from {url}: {len(got)} rows")
                if got:
                    for v in got[:3]:
                        print(f"boone:   sample {pos}: {v['name']} ${v['value']}")
                    values.extend(got)
                    sources.append(url)
                    break
                print("boone: text sample:\n" + text[:1200])
            except Exception as e:                              # noqa: BLE001
                errors.append(f"{url}: {e}")
                print(f"boone: FAILED {url}: {e}")

    if len(overall) < 150:
        for url in TOP300:
            try:
                text = render_text(url)
                got = parse_overall(text)
                print(f"boone: RENDERED {url}: {len(got)} ranked rows")
                if len(got) < 150:
                    idx = max(text.find("1."), 0)
                    print("boone: rendered text sample:\n" + text[idx:idx + 1200])
                if len(got) >= 150:
                    overall = got
                    sources.append(url + " (rendered)")
                    break
            except Exception as e:                              # noqa: BLE001
                errors.append(f"render {url}: {e}")
                print(f"boone: RENDER FAILED {url}: {e}")

    rank_basis = "top-300 article"
    pos_covered = {v["pos"] for v in values}
    if len(overall) < 150:
        if len(values) >= 120 and len(pos_covered) >= 3:
            overall = derive_overall_from_values(values)
            rank_basis = "derived from salary-cap values"
            print(f"boone: overall derived from values: {len(overall)} rows "
                  f"across {sorted(pos_covered)}")
            for row in overall[:10]:
                print(f"boone:   #{row['rank']} {row['name']} ({row['pos']})")
        else:
            print("boone: ABORT — no top-300 and not enough cap values; not writing")
            return 1
    data = {
        "meta": {
            "expert": "Justin Boone (Yahoo Sports)",
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "format": "half-PPR, 12-team, $200 salary cap",
            "sources": sources,
            "rank_basis": rank_basis,
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
