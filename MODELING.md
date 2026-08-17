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
   receives the extra slot and taking the best variant. A superflex slot is
   enumerated the same way, one level up: each open superflex seat goes to either
   QB demand or the FLEX pool (§2.6).

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

### 2.3 Live auction inflation (keeper-aware)

As picks come in, the app tracks `(money actually spent) / (expected value of players
drafted)`. When the room overpays early, less money chases the remaining talent, so
remaining values deflate — and vice versa. Adjusted value =
`intrinsic value × (remaining money / remaining expected value)`. This is the
standard auction-inflation correction and is recomputed on every pick.

**Keepers enter this calculation as already-spent money against already-gone talent.**
That is where most of the edge lives in a keeper league: kept players are typically
held below market, so the money still in the room chases a thinner pool and every
remaining player's true price rises. Entering the league's full keeper slate before
the draft is therefore the single highest-value input the model takes.

A **house rule cap** overrides the market for positions you refuse to pay for — by
default DST is capped at $1, which clamps its adjusted price, its max-bid advice, and
its treatment inside every solver. Freed dollars flow to positions where scarcity is
real.

### 2.3b Positional scarcity (tier cliffs)

For each undrafted player the app reports the share of that position's market value
still on the board **below** him — what remains once he and every pricier undrafted
player at his position are gone. This is deliberately *cumulative* rather than
marginal: a per-player "value remaining if only he is drafted" figure rises as prices
fall, which inverts on a value-sorted board and hides the thing that matters. The
cumulative form descends monotonically to zero, and the size of each step down *is*
the tier cliff at that position.

### 2.4 Risk-adjusted objective

Where floor/ceiling (or stdev) columns are provided, the optimizer maximizes
`mean + λ·(ceiling − mean)` for λ > 0 (upside hunting) or `mean − |λ|·(mean − floor)`
for λ < 0 (floor protection), with λ exposed as a risk-appetite slider. Without
distribution columns, λ falls back to a position-volatility heuristic. This is a
tractable stand-in for full stochastic programming — see §3.

### 2.4b Monte Carlo roster outlook (evaluation layer)

Maximizing a sum of point estimates cannot see two things that matter: **bench option
value** (you start your best lineup each week, so a volatile bench player is worth more
than his mean) and **roster-level risk shape** (two rosters projecting the same total
can be a safe band or a boom/bust spread).

The app therefore simulates ~1,200 seasons of your picks plus the optimizer's plan at
**weekly resolution**, selecting the best legal lineup each week, with per-position
volatility and per-week availability risk (weekly means are rescaled so the season
expectation still matches the projection — misses add variance, not double-counted
drag). It reports floor (10th) / median / ceiling (90th), and a *what-if* variant
prices winning a nominated player at a given bid.

Two deliberate constraints: the simulation is an **evaluation layer only** — it never
runs inside the bidding loop, so max bids and completion stay instant — and its inputs
are position-level variance assumptions, so the honest use is comparing roster *shape*,
not adjudicating ±20-point differences.

### 2.4c Strategy Lab (constrained solves)

Classic build philosophies are modeled as *constraints on the same exact solver*, not
as separate heuristics — which makes "what does this philosophy cost me?" a precise
question with a numeric answer (the gap to the unconstrained optimum).

- **Auction:** price-tier constraints. Positions are partitioned into tiers by price so
  no player is double-counted; stud requirements can span positions (Stars & Scrubs,
  BBQ); rank-exclusion constraints support builds defined by what they refuse to buy
  (Greasy Spoon skips the top-15 entirely); players you already own credit a build's
  requirements.
- **Snake:** canonical round rules (no RB before round 6 for Zero RB, QB from round 8
  or 11, etc.) applied to the marginal-value plan, relaxing gracefully when the pool
  can't satisfy them.

Definitions are taken from the published strategy literature rather than invented, and
thresholds scale with league budget. Greasy Spoon additionally computes a live
**market-type read** — classifying the room by how top-15 players are actually selling
against value — because that classification is the first decision its own author asks
you to make.

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
  caught up to. The bundled dataset's briefing is regenerated by each nightly build
  from Sleeper's live injury designations and cross-source team disagreements, rather
  than the hand-written prose it used to carry (which went stale within weeks).
- **Max-bid advisor:** for any nominated player, the app computes the largest price
  at which forcing that player into the optimal roster still beats the best roster
  without them (read directly off the completion DP table at every price point —
  effectively a marginal-value curve). That number — not the AAV — is what should
  discipline your bidding in the room.

### 2.5b The injury layer (auto-OUT)

An injury designation was decorative until this layer existed: it landed in the note
text and nothing read it, so a player with a season-ending injury kept his projection,
his ADP and his place in the recommendations. The failure was not subtle — a receiver
who had already been ruled out for the year was being suggested at his pre-injury draft
position, because his projection row had been dropped and he re-entered the pool through
ADP alone, on a path that never consulted the injury data at all.

**Sources.** Sleeper's player database (`injury_status`, `injury_body_part`,
`injury_notes`, roster `status`), ESPN's `kona_player_info` (`injuryStatus`, `injured`),
and optionally FantasyPros news headlines when a `FANTASYPROS_API_KEY` is configured.
Rows that entered the pool from ESPN or FFC are joined back to Sleeper's player database
by normalized name + position before anything is classified, so an added row carries the
same injury data a projected row does.

**Classification.** One boolean, deliberately conservative — a player is OUT when any
source says the season is over for him:

| Ruled OUT | Not ruled OUT (note only) |
|---|---|
| Sleeper `IR`, `Out`, `DNR`, `Sus` | Sleeper `PUP`, `Questionable`, `Doubtful`, `COV`, `NA` |
| Sleeper roster status `Injured Reserve` | ESPN `DAY_TO_DAY`, `QUESTIONABLE`, `DOUBTFUL` |
| ESPN `INJURY_RESERVE`, `OUT`, `SUSPENSION` | ESPN `injured: true` on its own |
| FantasyPros season-ending headline matched to a pool name | any other headline |

PUP is the interesting exclusion: a PUP player is expected back, often by week 5, and
auto-benching him would cost more than the injury does. The asymmetry is the point — a
missed OUT costs one bad recommendation the user can see and reject; a false OUT silently
removes a draftable player from every calculation. Where Sleeper and ESPN disagree, the
disagreement is recorded in `DATA_REPORT.md` rather than resolved silently.

**Effect.** Classified players ship as `out: true` in the bundle and are excluded from
the optimizer, max bids, snake plans, nomination ideas and keeper verdicts (a keeper who
is out is a toss-back at any price, not a surplus calculation). The generated briefing is
tiered by severity — season-enders with body part first, then optional FantasyPros
headlines, then week-to-week statuses, then team disagreements and ADP risers — because a
flat list put "Questionable" and "torn ACL" in the same undifferentiated pile.

**Override semantics.** The data's flag is a *default*, not a verdict. Each pool row
carries `outData` (what the data says) alongside `out` (what the app acts on). They move
together until the user disagrees; from then on the user's choice is stored as an explicit
override and re-applied over every later build and live refresh, in both directions — so
un-checking a player you have reason to believe will play sticks, and so does marking
someone out that no feed has caught up to yet.

### 2.6 Superflex (SF / 2QB) leagues

A superflex slot may be filled by QB/RB/WR/TE. It is one line in a league's settings and
it changes more of this model than any other single setting, so it is handled explicitly
rather than approximated as an extra FLEX.

**Exactness is preserved by enumeration, not by a new DP dimension.** A superflex seat is
either a quarterback or an ordinary flex, so the solver enumerates the split: for
`s_qb = 0 … S` (of `S` open superflex slots), it solves with QB demand raised by `s_qb`
and the FLEX pool raised by `S − s_qb`, then takes the best total. Every variant is a
problem the existing DP already solves exactly, so the result stays provably optimal;
the cost is `S + 1` solver passes (two in the standard one-superflex league, ~300 ms
worst case including max bids). The same enumeration runs inside the max-bid
completions — if it did not, a quarterback's max bid would be computed against a roster
shape the optimizer would never build, and the bid and the plan would contradict each
other.

**Replacement level counts superflex as QB demand.** This is the industry-standard
assumption and it is what actually happens in these rooms: a superflex seat is filled by
a quarterback whenever one is available. A 12-team league with QB + SFLEX therefore
starts 24 quarterbacks, and replacement moves from ~QB13 to ~QB25 — a swing of 50-60
projected points that flows straight into VORP, fair value and positional scarcity. The
remaining flex slots keep their existing RB/WR/TE allocation.

**Draft ranks switch to the 2QB board.** Superflex rooms take quarterbacks two to four
rounds earlier than their 1QB ADP implies, so with a superflex slot the availability
model reads `adp2` (Sleeper's `adp_2qb`, ingested by the nightly build) in preference to
ordinary ADP, falling back for anyone the feed has no 2QB rank for. Without this the
plan would confidently wait on quarterbacks who are already gone.

**A deliberate asymmetry between the pipeline and the app.** The nightly build's
replacement ranks — and therefore the bundled `aav` — stay 1QB-based, because one bundle
serves every league and the majority are 1QB. The app re-derives replacement level, VORP
and fair value from *your* settings on every recompute, which is where superflex belongs;
the market half of the blended value (`aav`) simply remains a 1QB market read. In a
superflex league, expect model value to sit above market value at quarterback — that gap
is the edge the format offers, not an error.

**Everything downstream follows.** Roster assignment fills dedicated slots, then FLEX,
then superflex (most restrictive first, which is optimal because every FLEX-eligible
position is also superflex-eligible); the snake planner gains a superflex *starter* tier,
so a second quarterback competes at full value while the bench-QB cap still prevents
hoarding a third; and the Monte Carlo lineup builder seats FLEX first and superflex from
what remains, which is what lets QB2 contribute weekly points. With no superflex slot
every one of these paths short-circuits to its previous behavior.

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

1. Hit **↻ Refresh data** for a live pull of ranks, projections, ADP and injury flags.
   The bundled pool is rebuilt nightly, so it should already be close; if you trust your
   own sheet more, export current projections + auction values (e.g., a FantasyPros cheat
   sheet CSV) and import them in the Data tab — later builds will fill in ADP, bye and
   ranks around your numbers without overwriting them.
2. Set your league's exact budget, roster slots, scoring, and draft type in Settings.
3. In keeper leagues, enter the **entire league's** keepers before draft day and check
   the "Who should I keep?" verdicts on your own candidates. Then look at Adj$ versus
   AAV — that gap is your league's real price list.
4. Apply boosts/fades for late-breaking news; toggle OUT for injured players.
5. Skim the Strategy Lab: the gap between each build and the unconstrained optimum
   tells you which philosophies are cheap in *this* market before you're on the clock.
6. On draft day, connect league sync (or log picks manually), nominate from the app's
   suggestions, and treat the max-bid number as your discipline line.
7. After the draft, export the draft log JSON and copy the recap for a post-mortem
   against the optimizer's counterfactual best roster.

## 5. Known limitations

Stated plainly, because they bound how much weight the outputs deserve:

- **The bundled dataset is now rebuilt nightly, but it is still assembled, not
  authored.** It was a hand-curated July 2026 snapshot of 190 players with ~19 sourced
  dollar values; `scripts/build_data.py` now rebuilds it every night from Sleeper
  projections, ESPN auction values and Fantasy Football Calculator ADP, cross-validating
  the sources and reporting every disagreement in `DATA_REPORT.md`. That fixes the
  staleness and the coverage, and it means stat-level projections and real ADP now exist
  for the whole pool — but where ESPN has no price the dollar value is still model-derived
  from VORP, and the projections are consumed from public sources rather than produced
  here (§3). Importing your own consensus before your draft remains a legitimate move,
  and the app will not overwrite it if you do.
- **A degraded build ships anyway.** If ESPN or FFC is unreachable the build proceeds
  without them and says so in `meta.degraded`, which the Data tab surfaces. In that state
  auction values lean harder on the VORP model. Only a Sleeper outage aborts the build
  outright and leaves the previous day's data live.
- **The injury layer is only as current as the feeds, and only handles "out for the
  season."** It reads designations, not reporting: a player whose injury broke after the
  last nightly build is not marked until the next one (the in-app ↻ refresh pulls the
  same statuses on demand). PUP and week-to-week designations are deliberately left to
  you (§2.5b), and nothing here estimates *how much* an injury lowers a projection —
  a player is either out for the season or priced as if healthy, with the boost/fade
  slider as the manual middle ground.
- **Simulation inputs are position-level, not player-level.** Floor/ceiling numbers
  inherit those assumptions; treat them as shape, not precision.
- **Snake availability is a rank model with a buffer**, not a probabilistic ADP
  distribution — it answers "likely / risky / gone," not "63.4%."
- **Nothing models opponent behavior.** Inflation is measured from what the room
  actually does, but the app doesn't predict what any particular manager will do next.
- **Projections are consumed, not produced.** Beating public expert consensus was
  explicitly out of scope (§3).
