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
  next pick, take-now urgency (points lost by waiting), and a round-by-round plan.

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

- **Refresh ranks/news** — one click pulls Sleeper's free public player feed for live
  consensus ranks, team changes, and injury flags.
- **Import CSV or Excel** — FantasyPros cheat-sheet exports (100+ expert ECR) drop in
  as-is; ECR, ADP, Bye, and stat-level columns are auto-detected, and the legacy
  `auc_values_ALL.xlsx` format imports unchanged. Multiple sources can be blended by
  weight, and stat columns enable exact rescoring under your league's settings.
- **Boost/fade and OUT toggles** for news the projections haven't caught up to.
- The bundled dataset is a **July 2026 consensus snapshot** (190 players, mostly
  estimated dollar values, with offseason news annotations). The header warns when it
  goes stale — **always import fresh data the week of your draft.**

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
| `index.html` | The entire app — self-contained, bundled 2026 data |
| `.github/workflows/pages.yml` | Auto-deploys the app to GitHub Pages on every push to `main` |
| `optimizer.py` | Python optimization engine (PuLP) |
| `DraftOptimizer.ipynb` | Executed reference notebook |
| `MODELING.md` | Modeling evaluation & methodology |
| `auc_values_ALL.xlsx` | Legacy player sheet (still imports directly) |
| `NU_MSDS460_FFBSalaryCapOptimizer.ipynb` | Original notebook, kept for history (superseded) |

## Origins

This began as a single Jupyter notebook that solved a one-shot lineup ILP from an Excel
sheet — see the [deepwiki overview](https://deepwiki.com/nbergeland/SalaryCapFantasyFootballDraftOptimizer#overview)
of that original version.
