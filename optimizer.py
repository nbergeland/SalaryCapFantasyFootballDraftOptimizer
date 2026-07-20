"""Salary-cap fantasy football draft optimizer.

Exact 0/1 integer-programming lineup optimization (PuLP/CBC) with:
  - FLEX slot support (RB/WR/TE eligible)
  - correct multi-lineup generation via no-good cuts
  - custom scoring recomputed from stat-level projections
  - value-over-replacement (VORP) dollar valuation
  - a max-bid advisor for live salary-cap (auction) drafts

This module is the offline reference engine; the web app (index.html) implements
an equivalent dynamic program in the browser for live re-optimization. See
MODELING.md for the methodology and the evaluation of the original approach.
"""

from dataclasses import dataclass, field

import pandas as pd
import pulp

# Points per unit of each stat column, keyed by the column names used in
# auc_values_ALL.xlsx (pass yds/TD/INT, rush att/yds/TD, receptions, rec yds/TD).
SCORING_PRESETS = {
    "ppr": {"p_yd": 0.04, "TD": 4, "INT": -2, "r_yd": 0.1, "r_td": 6,
            "rec": 1.0, "rec_yd": 0.1, "rec_tds": 6},
    "half_ppr": {"p_yd": 0.04, "TD": 4, "INT": -2, "r_yd": 0.1, "r_td": 6,
                 "rec": 0.5, "rec_yd": 0.1, "rec_tds": 6},
    "standard": {"p_yd": 0.04, "TD": 4, "INT": -2, "r_yd": 0.1, "r_td": 6,
                 "rec": 0.0, "rec_yd": 0.1, "rec_tds": 6},
}

FLEX_ELIGIBLE = ("RB", "WR", "TE")


@dataclass
class LeagueSettings:
    salary_cap: int = 200
    teams: int = 12
    # Starting slots; FLEX picks the best extra RB/WR/TE.
    slots: dict = field(default_factory=lambda: {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "Def": 1})
    bench_spots: int = 6
    bench_reserve_per_spot: int = 1

    @property
    def optimizer_budget(self) -> int:
        return self.salary_cap - self.bench_spots * self.bench_reserve_per_spot


def load_players(path: str, scoring: str | dict | None = None) -> pd.DataFrame:
    """Load a player sheet (Excel/CSV) and optionally rescore from stat columns."""
    df = pd.read_excel(path) if str(path).endswith((".xlsx", ".xls")) else pd.read_csv(path)
    df = df.dropna(subset=["Name", "Pos"]).copy()
    df["Value"] = df["Value"].clip(lower=1)  # $1 minimum bid, negative values are data noise
    if scoring is not None:
        # Only skill positions have stat-level projection columns; K/Def keep
        # the sheet's point projections.
        df["Pts"] = df["Pts"].astype(float)
        skill = df["Pos"].isin(["QB", "RB", "WR", "TE"])
        df.loc[skill, "Pts"] = recompute_points(df[skill], scoring)
    return df.reset_index(drop=True)


def recompute_points(df: pd.DataFrame, scoring: str | dict) -> pd.Series:
    """Recompute fantasy points from stat-level projection columns."""
    weights = SCORING_PRESETS[scoring] if isinstance(scoring, str) else scoring
    pts = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        if col in df.columns:
            pts += pd.to_numeric(df[col], errors="coerce").fillna(0) * w
    return pts.round(1)


def replacement_levels(df: pd.DataFrame, league: LeagueSettings) -> dict:
    """Projected points of the last starter-quality player at each position.

    FLEX starters are allocated to RB/WR/TE in proportion to how many of each
    position clear the non-flex starter cutoffs (a standard approximation).
    """
    slots = league.slots
    starters = {p: slots.get(p, 0) * league.teams for p in df["Pos"].unique()}
    flex_total = slots.get("FLEX", 0) * league.teams
    if flex_total:
        pool = {p: df[df.Pos == p].nlargest(starters[p] + flex_total, "Pts")["Pts"]
                for p in FLEX_ELIGIBLE if p in starters}
        # Next-best players beyond each position's own starters compete for flex.
        overflow = pd.concat(
            [s.iloc[starters[p]:] for p, s in pool.items()]).nlargest(flex_total)
        for p, s in pool.items():
            starters[p] += int(overflow.isin(s.iloc[starters[p]:]).sum())
    levels = {}
    for pos, n in starters.items():
        pos_pts = df[df.Pos == pos]["Pts"].nlargest(max(n, 1))
        levels[pos] = float(pos_pts.iloc[-1]) if len(pos_pts) >= n and n > 0 else 0.0
    return levels


def add_vorp(df: pd.DataFrame, league: LeagueSettings) -> pd.DataFrame:
    """Attach VORP and an intrinsic auction dollar value to each player."""
    df = df.copy()
    levels = replacement_levels(df, league)
    df["VORP"] = (df["Pts"] - df["Pos"].map(levels)).round(1)
    roster_size = sum(league.slots.values()) + league.bench_spots
    discretionary = league.teams * (league.salary_cap - roster_size)
    positive = df["VORP"].clip(lower=0)
    df["FairValue"] = (1 + discretionary * positive / positive.sum()).round(0).astype(int)
    return df


def _solve(prob: pulp.LpProblem) -> None:
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Solver returned {pulp.LpStatus[status]} — "
                           "check that the pool can fill every slot under the cap.")


def _build_problem(df, league, budget, locked, excluded):
    prob = pulp.LpProblem("lineup", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in df.index}
    prob += pulp.lpSum(df.at[i, "Pts"] * x[i] for i in df.index)
    prob += pulp.lpSum(df.at[i, "Value"] * x[i] for i in df.index) <= budget

    slots = league.slots
    flex_n = slots.get("FLEX", 0)
    present = set(df["Pos"].unique())
    total = 0
    for pos, n in slots.items():
        if pos == "FLEX":
            continue
        if pos not in present:
            continue  # e.g. sheet has no Def rows — skip the slot rather than fail
        idx = df.index[df.Pos == pos]
        op = ">=" if pos in FLEX_ELIGIBLE and flex_n else "=="
        expr = pulp.lpSum(x[i] for i in idx)
        prob += (expr >= n) if op == ">=" else (expr == n)
        total += n
    if flex_n and present & set(FLEX_ELIGIBLE):
        total += flex_n
    prob += pulp.lpSum(x.values()) == total

    for i in locked:
        prob += x[i] == 1
    for i in excluded:
        prob += x[i] == 0
    return prob, x


def optimize_lineups(df: pd.DataFrame, league: LeagueSettings | None = None,
                     n_lineups: int = 1, budget: int | None = None,
                     locked: list | None = None,
                     excluded: list | None = None) -> list[dict]:
    """Return the top-n distinct optimal lineups.

    Alternatives are generated with no-good cuts (each solved roster is excluded
    by `sum(chosen vars) <= roster_size - 1`), which is the correct replacement
    for the original notebook's buggy objective-value constraint.
    """
    league = league or LeagueSettings()
    budget = league.optimizer_budget if budget is None else budget
    prob, x = _build_problem(df, league, budget, locked or [], excluded or [])

    lineups = []
    for _ in range(n_lineups):
        _solve(prob)
        chosen = [i for i in df.index if x[i].value() == 1]
        roster = df.loc[chosen].sort_values(["Pos", "Pts"], ascending=[True, False])
        lineups.append({
            "players": roster[["Name", "Team", "Pos", "Value", "Pts"]],
            "total_pts": round(float(roster["Pts"].sum()), 1),
            "total_cost": int(roster["Value"].sum()),
        })
        prob += pulp.lpSum(x[i] for i in chosen) <= len(chosen) - 1  # no-good cut
    return lineups


def max_bid(df: pd.DataFrame, player_name: str,
            league: LeagueSettings | None = None,
            budget: int | None = None,
            excluded: list | None = None) -> dict:
    """Largest price at which winning `player_name` still beats passing on them.

    Bid up to this number; past it, letting the player go is optimal.
    """
    league = league or LeagueSettings()
    budget = league.optimizer_budget if budget is None else budget
    matches = df.index[df.Name == player_name]
    if len(matches) == 0:
        raise KeyError(f"player not found: {player_name}")
    i = matches[0]

    best_without = optimize_lineups(df, league, budget=budget,
                                    excluded=[i, *(excluded or [])])[0]["total_pts"]
    lo, hi, best_price = 0, budget, None
    trial = df.copy()
    while lo <= hi:  # optimal-with-forced-inclusion is non-increasing in price
        mid = (lo + hi) // 2
        trial.at[i, "Value"] = max(mid, 1)
        with_p = optimize_lineups(trial, league, budget=budget, locked=[i],
                                  excluded=excluded or [])[0]["total_pts"]
        if with_p >= best_without:
            best_price, lo = mid, mid + 1
        else:
            hi = mid - 1
    return {"player": player_name, "max_bid": best_price,
            "lineup_pts_without": best_without}
