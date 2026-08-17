# BERG SHEETS — Fantasy Football Draft Optimizer

**▶ Live app: https://nbergeland.github.io/SalaryCapFantasyFootballDraftOptimizer/**

A live draft companion for **salary-cap (auction) and snake** fantasy football leagues.
It re-solves your optimal roster after every pick, tells you the most you should bid on
the player currently nominated, tracks how the room's money is moving, and compares the
classic draft philosophies side by side — all in a single static page with no backend.

## ⚡ Quick start

Open the [live app](https://nbergeland.github.io/SalaryCapFantasyFootballDraftOptimizer/)
(or `index.html` from a clone). Everything runs locally in your browser; your draft state
persists there and is never shared.

### Where your state lives (and why it can't just vanish)

Draft state — leagues, keepers, candidates, marks, logs — is saved in the browser on
every change, **twice**: localStorage (primary) plus an IndexedDB mirror keeping the
last 8 hourly snapshots. If the browser ever wipes localStorage (Safari deletes site
data after 7 days without a visit; "clear browsing data" does too), the app
auto-restores from the mirror on the next open. An unreadable save is quarantined for
recovery, never overwritten. The Data & News tab shows storage health: last save time,
durable-storage grant, and mirror status.

State is still **per browser, per device**. To move it or keep an offline copy,
**Export draft** in the header writes every league to a file that **Import** restores
exactly. On Safari/iPhone, export after entering keepers — belt and suspenders.

1. **Settings** — draft type (auction/snake), teams, budget, roster slots, scoring, and
   your snake draft slot.
2. **Data & News** — import fresh projections/values, enter keepers, and connect your
   league.
3. **Draft** — work the board: search a nominated player, read **Max bid**, record the
   sale (or let league sync do it), and watch every number re-solve.

## 🔌 Pair it with your real draft

| Platform | How it works | Hands-free? |
|---|---|---|
| **Sleeper** | Enter your username → pick your league → **Auto-sync every 5s**. Pulls roster slots, budget, scoring, draft type, and your draft slot, then every pick and price as they happen. No login needed — Sleeper's API is public. | ✅ fully |
| **ESPN** | Drag the generated **📡 BERG ESPN bridge** bookmarklet to your bookmarks bar. On draft day, click it once on a logged-in ESPN tab — it streams picks and bid amounts to the app every 12s. | ✅ after one click |
| **Yahoo** | Drag the **📡 BERG Yahoo bridge** bookmarklet, then click it in the draft room with the **Draft Results** panel visible — results stream over every 8s. | ✅ after one click |

Manual entry is always available and takes about three seconds per sale. Bridges require
the hosted site (bookmarklets can't target `file://` pages). **Do a mock-draft dry run
before the real thing.**

## 🧠 What it computes

- **Max bid** — the largest price at which winning a player still beats the best roster
  you could build without them. The discipline line: bid to it, never past it.
- **Optimal completion** — the best way to finish your starters with the money and slots
  you have left, re-solved after every pick (~150 ms).
- **Adj$** — each player's true price in *your* room: model value blended with market
  AAV, corrected for live auction inflation (money left ÷ value left), which keepers
  push upward.
- **PS (positional scarcity)** — the share of a position's market value left *below* a
  player, once he and everyone pricier there is gone. Descends down the board; the size
  of each drop is the tier cliff.
- **Budget ledger** — spend vs. model value with an over/under pace verdict, per-player
  paid-vs-value deltas, and a warning when even the optimal roster can't spend your
  remaining money.
- **Roster outlook (Monte Carlo)** — 1,200 simulated seasons at weekly resolution,
  starting your best lineup each week, so boom/bust bench depth is priced properly.
  Reports floor (10th) / median / ceiling (90th). A **"sim if won"** line shows how
  winning the nominated player at the entered price moves your median and floor.
- **Snake mode** — market/ADP rank, expected round, an availability call against your
  next pick, take-now urgency (points lost by waiting), and a round-by-round plan. The
  plan prices each pick against the player who would actually fill that *slot* later —
  pooled across the positions the slot accepts — and rolls each candidate out to a
  finished roster before committing, which is what keeps it from reaching for a
  quarterback in round 2 or stacking tight ends it will never start.
- **Superflex (SF / 2QB)** — set **Superflex** to 1 in Settings (Sleeper's `SUPER_FLEX`
  and ESPN's `OP` import it for you) and the whole quarterback market reprices. Four
  things change at once: replacement level drops from QB12 to QB24, so QB VORP, fair
  value and scarcity all shift; the draft board switches to 2QB ADP, because
  quarterbacks leave two to four rounds earlier in SF; the optimizer starts seating a
  second QB and prices a max bid for him; and the weekly lineup sim plays him. A league
  without a superflex slot is untouched by all of it.

## 🎯 Strategy Lab

Toggle any combination of eleven build archetypes and each renders a full starting
lineup, its projected points, spend, Monte Carlo range, and sourced when-to-use / risk
notes — recomputed live, so mid-draft you can ask "is Zero RB still on the table from
here?" The main optimizer stays unconstrained as the baseline to compare against.

In auction these are price-tier constraints; in snake they're canonical round rules.
Definitions follow the published strategy literature (FootballAbsurdity, FantasyPros,
Footballguys, FantasyLife, FantasyLabs) and scale to your league's budget:

| Build | Auction rule | Snake rule |
|---|---|---|
| **Greasy Spoon** | Skip top-15 ranked players entirely; QB ≤ $5 | — |
| **BBQ** | Two studs ~$115 combined; then RB/WR ≤ $20, TE ≤ $15, QB ≤ $8 | — |
| **Stars & Scrubs** | 3 elites at $35+; everyone else $1–5 | — |
| **Balanced** | Nobody over ~$42 | best available |
| **Hero RB** | One RB $40+; other RBs ≤ $15 | RB in R1, resume R7+ |
| **Zero RB** | Every RB ≤ $12 | no RB rounds 1–5 |
| **Robust RB** | Two RBs at $35+ | 2 RBs by R3 |
| **WR Heavy** | Two WRs at $35+ | 3 WRs by R3 |
| **$5 QB** | QB ≤ $5 | QB from R11 |
| **Wait on QB** | QB ≤ $12 (5–7% of budget) | QB from R8 |
| **Elite TE** | One TE at $20+ | TE by R3 |

**Greasy Spoon** also reads the room live: it classifies your auction as Hoovler's
Type A / B / C from how top-15 players are actually selling versus value, and tells you
whether bargains should crash in later or whether skipping the stars will cost you.

## 🔄 Keeping the data sharp

The bundled player pool is **rebuilt every night** by
[`scripts/build_data.py`](scripts/build_data.py), run from
[`.github/workflows/data-refresh.yml`](.github/workflows/data-refresh.yml) at 09:20 UTC
and spliced straight into `index.html`, which then redeploys through the usual Pages
workflow. Each build writes [`DATA_REPORT.md`](DATA_REPORT.md) — per-source status,
unmatched rows, cross-source team disagreements, projection splits, and how well the
auction model tracks ESPN's prices.

| Source | Contributes |
|---|---|
| Sleeper players | roster, teams, injury status + body part + notes, search rank |
| Sleeper projections | stat-level season projections, PPR points, ADP, superflex (2QB) ADP |
| Fantasy Football Calculator | ADP from real mock drafts |
| ESPN (`kona_player_info`) | auction values, PPR ranks, a second projection, injury status |
| ESPN pro teams | bye weeks |
| FantasyPros news *(optional)* | headlines, and corroboration for season-ending injuries |

Sleeper is required: if either Sleeper call fails the build aborts and yesterday's data
stays live. ESPN and FFC are degradable — the build proceeds and flags itself in the app.
Nothing is written until the whole bundle clears a validation gate (minimum player count,
per-record schema, no duplicate IDs, a sanity list of consensus stars).

*ADP data courtesy of [Fantasy Football Calculator](https://fantasyfootballcalculator.com).*

### Injuries: who gets marked OUT, and who doesn't

Every build classifies each player and ships `out: true` for anyone who is done for the
season, so they never reach a recommendation, a max bid, a snake plan or a keeper verdict.
A player is auto-marked OUT when **Sleeper** reports `IR`, `Out`, `DNR` or `Sus` (or a
roster status of *Injured Reserve*), when **ESPN** reports `INJURY_RESERVE`, `OUT` or
`SUSPENSION`, or when an active FantasyPros headline reports a season-ending injury for
someone in the pool.

**PUP, Questionable and Doubtful are deliberately never auto-marked.** Those players come
back, and a false OUT costs you a draftable player. They get a note (with body part and
Sleeper's own injury note) and a line in the briefing instead.

You always have the last word: un-check **OUT** on the Data tab, or hit **🚑 OUT** on the
block bar, and that override survives every later build and live refresh — in both
directions. Rows that entered the pool from ESPN or FFC are joined back to Sleeper's
player database first, which is what fixes the case that motivated this: a player whose
projection was dropped, who re-entered on ADP alone, and who was recommended at his
pre-injury draft position because nothing in the pipeline knew he was hurt.

The generated briefing is ordered by severity rather than by ADP: season-enders first
(with body part), then FantasyPros headlines, then week-to-week statuses, then
cross-source team disagreements and ADP risers — each tier capped so one kind of news
cannot crowd out the rest.

### Optional: FantasyPros

FantasyPros' free personal API tier needs a key you request from them. It is entirely
optional — with no key the leg is skipped silently and is *not* counted as a degraded
source. To turn it on: request a key, then add it as the repository secret
`FANTASYPROS_API_KEY` (Settings → Secrets and variables → Actions). The next nightly
build picks it up automatically — no code change — and starts adding `FP:` headlines to
the briefing plus a second opinion on season-ending injuries. Locally:
`FANTASYPROS_API_KEY=... python3 scripts/build_data.py` (or `--fp-key`).

In the app itself:

- **↻ Refresh data** — a live pull from the two CORS-open sources: Sleeper's player feed
  (ranks, team changes, injuries), Sleeper's season projections (points, stat lines,
  ADP), and Fantasy Football Calculator's ADP, blended with Sleeper's. Draftable players
  your pool is missing are appended at $1; the nightly build is what prices them properly.
  Each source is independent, so one being down costs you only that source. Season-ending
  statuses are auto-marked OUT here too (and the count is reported), stale injury notes
  are replaced rather than piled up, and your own OUT decisions are left alone.
- **Reload bundled data** (Data & News) — force the pool back to the dataset built into
  the page. Your draft, keepers, boosts and OUT/DND/★ marks are re-applied afterwards.
- **Import CSV or Excel** — FantasyPros cheat-sheet exports (100+ expert ECR) drop in
  as-is; ECR, ADP, Bye, and stat-level columns are auto-detected, and the legacy
  `auc_values_ALL.xlsx` format imports unchanged. Multiple sources can be blended by
  weight, and stat columns enable exact rescoring under your league's settings. Imported
  values are treated as yours: later nightly builds fill in ADP, bye and ranks around
  them but never overwrite your dollar values or projections.
- **Boost/fade and OUT toggles** for news the projections haven't caught up to. OUT
  arrives pre-checked for season-ending injuries; un-checking one is an override that
  sticks.

The header still warns when values go stale, and importing a fresh sheet the week of your
draft is still the surest thing you can do.

## 🏆 Keepers

Enter every kept player league-wide before the draft (Keepers card, the roster card's
shortcut, or the block bar's keeper checkbox). Keepers fill rosters and consume budgets
without advancing the pick counter — and because kept players are usually below market,
the remaining pool inflates, which the Adj$ column prices in automatically.

**"Who should I keep?"** ranks your keeper candidates by surplus — what they'd cost in
this draft versus their keeper price (or, in snake, market round versus the round you'd
forfeit) — with KEEP / bubble / toss-back verdicts under your league's keeper limit and
one-click lock-in.

## 📓 Python engine & notebook

The same math offline, for analysis:

- [`optimizer.py`](optimizer.py) — PuLP/CBC integer-programming engine: FLEX support,
  multi-lineup generation via no-good cuts, custom scoring from stat-level projections,
  VORP and fair-value dollars, `max_bid()`, and mid-draft re-optimization.
- [`DraftOptimizer.ipynb`](DraftOptimizer.ipynb) — executed walkthrough.

```bash
pip install -r requirements.txt
jupyter notebook DraftOptimizer.ipynb
```

The data builder is plain-stdlib Python and its tests need no network:

```bash
python3 -m unittest discover -s tests
python3 scripts/build_data.py --fixtures-dir tests/fixtures --dry-run
```

## 📐 Modeling

**[`MODELING.md`](MODELING.md)** evaluates the original approach and documents the
methodology. Short version: the original binary-ILP formulation was the *right* choice
for lineup selection and is retained; what needed replacing was everything around it —
a crashing multi-lineup constraint, stale deterministic projections, static pre-draft
prices, no replacement-level reasoning, and no way to adapt mid-draft.

The web app solves an exact dynamic program equivalent to that ILP, which is what makes
live re-optimization and instant max-bid advice possible. Monte Carlo sits on top as an
*evaluation* layer only — it never runs inside the bidding loop.

## 🗂 Repository map

| File | Purpose |
|---|---|
| `index.html` | The entire app — self-contained, with the player pool spliced in between `/*__DATA__*/` markers |
| `scripts/build_data.py` | Nightly data builder: fetches, cross-validates and splices the player pool |
| `.github/workflows/data-refresh.yml` | Runs the builder daily at 09:20 UTC and commits the result |
| `.github/workflows/pages.yml` | Auto-deploys the app to GitHub Pages on every push to `main` |
| `DATA_REPORT.md` | Written by each data build — source status, disagreements, calibration |
| `tests/test_build_data.py` | Builder unit tests (stdlib `unittest`, offline via fixtures) |
| `tests/fixtures/` | Schema-faithful slices of the six upstream payloads (injury cases included) |
| `tests/test_migration.js` | Playwright suite for bundle migration, injuries and the live refresh |
| `tests/test_persistence.js` | Playwright suite for keeper/draft state survival across storage eviction |
| `tests/test_superflex.js` | Playwright suite for superflex leagues (optimizer, ranks, sync, sim) |
| `tests/test_snake_plan.js` | Playwright suite for snake plan shape (QB timing, TE stacking, K/DST last) |
| `.nojekyll` | Lets Pages serve straight from a branch — see below |
| `optimizer.py` | Python optimization engine (PuLP) |
| `DraftOptimizer.ipynb` | Executed reference notebook |
| `MODELING.md` | Modeling evaluation & methodology |
| `auc_values_ALL.xlsx` | Legacy player sheet (still imports directly) |
| `NU_MSDS460_FFBSalaryCapOptimizer.ipynb` | Original notebook, kept for history (superseded) |

### If a deploy gets stuck

Occasionally an Actions job is queued but never assigned a runner — `runner_id: 0`,
zero billable time, no logs — and errors out ~15 minutes later. It's intermittent and
unrelated to this repo's code; two identical dispatches seconds apart can behave
differently. **Re-run the workflow** (Actions → *Deploy BERG SHEETS to GitHub Pages* →
*Run workflow*) and it normally picks up a runner.

If it won't budge on draft day, bypass Actions entirely: **Settings → Pages → Source →
Deploy from a branch → `main` / `/ (root)`**. `index.html` is fully self-contained and
needs no build step, so GitHub serves it directly off its own infrastructure with no
runner involved. `.nojekyll` is committed so this works immediately.

## Origins

This began as a single Jupyter notebook that solved a one-shot lineup ILP from an Excel
sheet — see the [deepwiki overview](https://deepwiki.com/nbergeland/SalaryCapFantasyFootballDraftOptimizer#overview)
of that original version.
