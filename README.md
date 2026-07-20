# Salary Cap Fantasy Football Draft Optimizer

A live draft companion for salary-cap (auction) fantasy football leagues. It combines
exact roster optimization with value-over-replacement pricing, expert-consensus data,
live auction-inflation tracking, and a max-bid advisor — and re-optimizes your best
possible roster **after every pick** of your draft.

## ⚡ Quick start — the web app

Open **[`index.html`](index.html)** in any browser (double-click it, or serve the repo
with GitHub Pages). No install, no backend — everything runs locally and your draft
state persists in the browser.

Run it next to your draft room:

1. **Settings** → your league's budget, teams, roster slots (incl. FLEX/bench) and
   scoring (PPR / half / standard / custom).
2. **Data & News** → the bundled dataset is a July 2026 consensus snapshot (values,
   projections, offseason news). The week of your draft, export a fresh cheat-sheet
   CSV (FantasyPros, ESPN, RotoWire, …) and import it — columns are auto-detected,
   and multiple sources can be blended. Apply per-player boosts/fades for late news.
3. **Draft** → every nomination: type the name, click the row, read the one number
   that matters — **Max bid**. Every sale: record who won it and for how much.
   Budget, inflation, adjusted values, max bids, and the optimal completion of your
   roster all recompute instantly (~100 ms for a full re-solve).

Feature highlights:

- **Exact optimizer** — a dynamic program equivalent to integer linear programming,
  provably optimal for your remaining slots/budget, re-solved live.
- **Max-bid advisor** — the largest price at which winning a player still beats the
  best roster you could build without them. Bid to it, never past it.
- **Live inflation** — tracks money actually leaving the room vs expected values and
  re-prices every remaining player (the classic auction-inflation correction).
- **VORP dollar model** — replacement-level-based intrinsic values, blendable with
  market AAV.
- **Risk appetite dial** — tilt the objective toward ceilings (league-winner hunting)
  or floors.
- **Nomination ideas** — expensive players you don't want, to drain rival budgets.
- **Draft log with undo, JSON export/import, CSV export**, dark/light theme.

## 📓 Python engine & notebook

The same math is available offline for analysis:

- [`optimizer.py`](optimizer.py) — PuLP/CBC integer-programming engine: FLEX support,
  correct multi-lineup generation via no-good cuts, custom scoring recomputed from
  stat-level projections, VORP + fair-value dollars, `max_bid()` advisor, and
  mid-draft re-optimization (`locked` / `excluded`).
- [`DraftOptimizer.ipynb`](DraftOptimizer.ipynb) — executed walkthrough of the engine
  on the bundled data.

```bash
pip install -r requirements.txt
jupyter notebook DraftOptimizer.ipynb
```

## 📐 Modeling

**[`MODELING.md`](MODELING.md)** evaluates the original approach and documents the
upgraded methodology. Short version: the original binary-ILP formulation was the
*right* choice for lineup selection and is retained; what needed replacing was
everything around it — a crashing multi-lineup constraint, deterministic stale
projections, static pre-draft prices, no replacement-level reasoning, and no way to
adapt mid-draft. The upgrade adds VORP valuation, consensus blending, risk
adjustment, live inflation, and per-pick re-optimization, with the web app's DP
solver producing solutions identical to the ILP in milliseconds.

## 🗂 Repository map

| File | Purpose |
|---|---|
| `index.html` | The live draft companion web app (self-contained, bundled 2026 data) |
| `optimizer.py` | Python optimization engine (PuLP) |
| `DraftOptimizer.ipynb` | Executed reference notebook |
| `MODELING.md` | Modeling evaluation & methodology |
| `auc_values_ALL.xlsx` | Legacy 2022 player sheet (used by the notebook demo) |
| `NU_MSDS460_FFBSalaryCapOptimizer.ipynb` | Legacy notebook (kept for history; superseded — its multi-lineup loop has a known crash) |
| `playerLists\*.xlsx`, `*.png` | Legacy outputs and diagrams |

## 🔄 Keeping data current for your season

The bundled dataset (190 players, PPR, 12-team, $200) was compiled 2026-07-20 from
expert-consensus sources with 2026 offseason news baked into values and notes. Values
marked `est` are curve-based estimates; `sourced` are published figures. Projections
and prices move all summer — **always import a fresh CSV the week of your draft**,
then fine-tune with boosts/fades as camp news breaks.

## Legacy overview

The original project was a single Jupyter notebook (`NU_MSDS460_FFBSalaryCapOptimizer.ipynb`)
that solved a one-shot lineup ILP from an Excel sheet — see
[deepwiki overview](https://deepwiki.com/nbergeland/SalaryCapFantasyFootballDraftOptimizer#overview).
