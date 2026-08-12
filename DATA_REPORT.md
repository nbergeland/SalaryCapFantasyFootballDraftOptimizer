# Data build report

- Built: 2026-08-12T01:37:05+00:00
- Season: 2026
- Players in bundle: **3219**
- News lines: 25
- **Degraded sources:** espn_kona

## Source status

| Source | Status |
|---|---|
| sleeper_players | ok |
| sleeper_projections | ok |
| ffc_adp | ok |
| espn_kona | FAILED: https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/leaguedefaults/3?view=kona_player_info: 404 Client Error:  for url: https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/leaguedefaults/3?view=kona_player_info |
| espn_byes | ok |

## Counts

- Sleeper players DB entries: 4385
- Sleeper projection rows: 3301
- Dropped (no stats, no ADP): 0
- ESPN matched / added: None / None
- FFC matched / added: 255 / 1
- Pool before cutoff: 3219 → kept 3219

### Position breakdown

- QB: 355
- RB: 672
- WR: 1362
- TE: 644
- K: 154
- DST: 32

## Auction values

- Replacement points: {'DST': 86.0, 'QB': 295.5, 'WR': 170.9, 'RB': 161.1, 'TE': 161.0, 'K': 103.0}
- $/VORP scale: 0.4757 (calibration factor 1.0)
- ESPN-priced players: 0
- Mean abs error of the VORP model vs ESPN prices: None

## Team disagreements (0)

_none_

## Projection splits (0)

_none_

## ESPN rows not matched and not added (0)

_none_

## FFC rows with no Sleeper match (1)

- Eddy Piñeiro (SF K) adp=156.9

---

ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com).
