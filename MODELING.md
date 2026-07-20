# Modeling Evaluation & Methodology

This document evaluates the original optimization approach used in this project and
describes the upgraded modeling that now powers the draft companion web app and the
rebuilt notebook.

## 1. Was the original modeling a decent option?

**Short answer: yes — binary integer linear programming (ILP) was the right choice
for the lineup-selection problem, and it remains the core of the upgraded system.
The weaknesses were not in the choice of optimizer but in everything around it.**

### What the original model got right

The original notebook formulated roster selection as a 0/1 integer program via PuLP:

- **Decision variables:** one binary variable per player (selected / not selected)
- **Objective:** maximize the sum of projected fantasy points of selected players
- **Constraints:** exact position counts, total salary ≤ cap

This is the canonical formulation for salary-cap lineup construction (it is a
multi-dimensional knapsack), and it is *exact*: at this problem size (~450 players,
~10 roster slots, integer budget ≤ 200) a solver finds the provably optimal lineup in
milliseconds. Heuristics (greedy, genetic algorithms) would be strictly worse choices
here — they trade away optimality guarantees for speed the problem doesn't need.

### Where it fell short

1. **A crashing bug in multi-lineup generation.** The loop that generates alternative
   lineups constrained the *objective* (`rewards <= total_score - 0.01`) using a
   `total_score` variable that is a `list` on first use — the notebook dies with
   `TypeError: unsupported operand type(s) for -: 'list' and 'float'`. Beyond the bug,
   constraining the objective value is the wrong mechanism: it forbids equally-scored
   *different* lineups and depends on fragile `eval()`-based score recovery. The
   canonical technique is a **no-good cut**: after each solve, add
   `sum(selected vars) <= N - 1`, which excludes exactly the previous roster and
   nothing else.

2. **Deterministic single-point projections.** Fantasy point outcomes are extremely
   noisy (season-level projection RMSE for skill players is on the order of 40–60 PPR
   points). Optimizing a single mean projection ignores risk posture entirely — a
   cash-game-style "safe floor" roster and a league-winning "ceiling" roster are
   different optimization problems.

3. **Static, exogenous prices.** The `Value` column was a pre-draft auction estimate.
   In a live salary-cap draft, realized prices deviate immediately — early
   overpayment deflates later prices and vice versa. A lineup optimized before the
   draft is stale after the first nomination. The original tool had no way to
   re-optimize mid-draft, no tracking of the money actually leaving the room, and no
   inflation adjustment.

4. **No replacement-level reasoning.** Raw projected points make QBs look like the
   most valuable assets in football. Position constraints partially mask this inside
   the ILP, but any *bid advice* derived from raw points is distorted. Value over
   replacement (VORP) is the standard correction and was absent.

5. **Incomplete roster model.** No FLEX slot, no team defense (the dataset itself
   contains no DST rows), no bench, and no reserve budget for bench spots — all of
   which materially change optimal bidding in real leagues.

6. **Stale data, single source.** One vintage of one provider's projections
   (2022 season), with no way to blend sources, apply news adjustments, or rescore
   stat-level projections under different league scoring.

### Verdict

| Aspect | Original | Assessment |
|---|---|---|
| Optimization framework (ILP / knapsack) | PuLP CBC, exact | **Keep** — correct and optimal |
| Multi-lineup generation | Objective cut (buggy) | **Replace** with no-good cuts |
| Projections | Single stale point estimate | **Replace** with consensus blend + rescoring + risk adjustment |
| Prices | Static pre-draft values | **Replace** with live prices + inflation model |
| Valuation | Raw points | **Add** VORP-based dollar valuation |
| Draft-time usability | Pre-draft notebook run | **Replace** with live re-optimizing web app |

## 2. The upgraded modeling

### 2.1 Exact optimization, re-solved live

The web app re-solves the roster problem *after every pick* in the draft. To make
that instant in a browser it uses a **dynamic-programming formulation that is
mathematically equivalent to the ILP** for this constraint structure:

1. For each position `p` with remaining required count `n_p`, build a knapsack table
   `T_p[j][c]` = max risk-adjusted points achievable choosing exactly `j` available
   players of position `p` at total cost `≤ c` (budget is integer dollars).
2. Combine position tables by convolution over the remaining budget:
   `C[c] = max over splits (C[c − c′] + T_p[n_p][c′])`.
3. FLEX is handled exactly by enumerating which eligible position (RB/WR/TE)
   receives the extra slot and taking the best variant.

Because position groups are disjoint and constraints are "exactly n per group +
shared budget," this DP explores the full feasible set — the result is provably
optimal, identical to the PuLP solution, and computes in a few milliseconds, which
is what makes *live* re-optimization and interactive bid advice possible. The
rebuilt notebook keeps the PuLP ILP (with fixed no-good cuts) as the offline
reference implementation, and the test suite cross-validates the two engines
against each other.

State that feeds each re-solve:

- Your drafted players are **locked in at the price you actually paid** (they fill
  their primary slot first, overflowing to FLEX, then bench).
- Players drafted by other teams are **removed from the pool**.
- Your remaining budget is reduced by actual spend, minus a **bench reserve**
  ($1 by default per unfilled bench slot, configurable).

### 2.2 Value over replacement (VORP) dollar valuation

Replacement level for each position is the projected score of the last starter-quality
player in your league (league size × starters at that position, FLEX allocated by
historical share). Each player's VORP is `points − replacement(pos)`, and the
**intrinsic dollar value** distributes the league's total discretionary cap
(total budgets − $1 × total roster spots) proportionally to positive VORP. The app
lets you blend intrinsic value with market AAV (consensus auction values) via a
slider, since market prices carry real information about how the room will bid.

### 2.3 Live auction inflation

As picks come in, the app tracks `(money actually spent) / (expected value of players
drafted)`. When the room overpays early, less money chases the remaining talent, so
remaining values deflate — and vice versa. Adjusted value =
`intrinsic value × (remaining money / remaining expected value)`. This is the
standard auction-inflation correction and is recomputed on every pick.

### 2.4 Risk-adjusted objective

Where floor/ceiling (or stdev) columns are provided, the optimizer maximizes
`mean + λ·(ceiling − mean)` for λ > 0 (upside hunting) or `mean − |λ|·(mean − floor)`
for λ < 0 (floor protection), with λ exposed as a risk-appetite slider. Without
distribution columns, λ falls back to a position-volatility heuristic. This is a
tractable stand-in for full stochastic programming — see §3.

### 2.5 Consensus, news, and season fine-tuning

- **Custom scoring:** when stat-level projections are present (pass/rush/rec yards,
  TDs, receptions, INTs), points are recomputed from your league's scoring settings
  (PPR / half / standard presets or fully custom) rather than trusting a provider's
  scoring assumptions.
- **Consensus blending:** import any number of projection sources as CSV; each
  import can *merge* (weighted-average points, latest AAV) or *replace*. This is
  how you fold in FantasyPros ECR/projections, ESPN, RotoWire, etc. right before
  your draft.
- **News adjustments:** per-player boost/fade percentage and an OUT toggle let you
  encode camp news, injuries, holdouts, and role changes the projections haven't
  caught up to. The bundled 2026 dataset ships with news annotations current as of
  July 2026.
- **Max-bid advisor:** for any nominated player, the app computes the largest price
  at which forcing that player into the optimal roster still beats the best roster
  without them (read directly off the completion DP table at every price point —
  effectively a marginal-value curve). That number — not the AAV — is what should
  discipline your bidding in the room.

## 3. Alternatives considered (and why they weren't chosen)

- **Full stochastic programming / Monte Carlo roster simulation.** The theoretically
  right objective is maximizing P(win league), which depends on the joint
  distribution of scores. It requires distributional inputs users rarely have,
  and per-solve costs that fight live-draft latency. The λ-risk objective captures
  most of the practical benefit; the architecture leaves room to add simulation
  later.
- **Training our own ML projection model.** Projections are a commodity: public
  expert-consensus aggregates are the benchmark that individual models struggle to
  beat, and they are updated daily with news we cannot observe from historical data
  alone. Consuming and *blending* consensus (plus user-applied news adjustments) is
  a better use of modeling effort than competing with it.
- **Heuristic optimizers (greedy, simulated annealing, GA).** Unnecessary — the
  exact problem is small. Optimality matters here because bid advice derives from
  *differences* between optimal solutions, which heuristic noise would corrupt.

## 4. Practical guidance for your season

1. A week before your draft, export current projections + auction values
   (e.g., FantasyPros cheat sheet CSV) and import them in the app's Data tab.
2. Set your league's exact budget, roster slots, and scoring in Settings.
3. Apply boosts/fades for late-breaking news; toggle OUT for injured players.
4. On draft day, run the app beside your draft room: log every pick with its price,
   nominate from the app's suggestions, and treat the max-bid number as your
   discipline line.
5. After the draft, export the draft log JSON for a post-mortem against the
   optimizer's counterfactual best roster.
