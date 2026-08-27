# Data build report

- Built: 2026-08-27T19:51:36+00:00
- Season: 2026
- Players in bundle: **615**
- News lines: 25

## Source status

| Source | Status |
|---|---|
| sleeper_players | ok |
| sleeper_projections | ok |
| ffc_adp | ok |
| espn_kona | ok |
| espn_byes | ok |
| boone | ok (278 ranks, 0 values, 7d old) |
| fantasypros | skipped (no key) |

## Counts

- Sleeper players DB entries: 4388
- Sleeper projection rows: 3303
- Dropped (no stats, no ADP): 2356
- ESPN matched / added: 636 / 0
- FFC matched / added: 266 / 1
- Backfilled from the Sleeper players DB: 37 (0 team corrections)
- Players marked OUT: 11
- Carrying a superflex (2QB) ADP: 343 (of which QB: 46)
- FantasyPros headlines parsed: 0
- Pool before cutoff: 871 → kept 615

### Position breakdown

- QB: 61
- RB: 131
- WR: 206
- TE: 94
- K: 91
- DST: 32

## Auction values

- Replacement points: {'DST': 91.9, 'QB': 291.5, 'WR': 169.9, 'RB': 168.8, 'TE': 156.0, 'K': 116.2}
- $/VORP scale: 0.4067 (calibration factor 0.9346)
- ESPN-priced players: 96
- Sleeper-priced players: 0 (auction keys seen in the feed: none)
- Mean abs error of the VORP model vs ESPN prices: 5.67

## Marked OUT (excluded from recommendations) (11)

- Brandon Aiyuk (SF WR): sleeper injury_status=DNR, espn injuryStatus=OUT
- Jack Stoll (CLE TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Jake Bobo (SEA WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Jaren Kanak (TEN TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Jayden Higgins (HOU WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Jeshaun Jones (MIN WR): sleeper injury_status=Sus, espn injuryStatus=SUSPENSION
- John Michael Gyllenborg (KC TE): sleeper injury_status=IR
- Julian Hill (NE TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Ricky Pearsall (SF WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Trey Benson (ARI RB): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Xavier Weaver (ARI WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE

## Teamless season-enders dropped (retired-player DB residue) (2)

- Adam Vinatieri (K)
- Stephen Hauschka (K)

## D/ST opening-month schedule (softest slate first) (32)

- Chiefs D/ST: avg opponent offense rank 24.2 (vs DEN, IND, MIA, LV) — season proj 91
- Falcons D/ST: avg opponent offense rank 22.8 (vs PIT, CAR, GB, NO) — season proj 78
- Raiders D/ST: avg opponent offense rank 21.2 (vs MIA, LAC, NO, KC) — season proj 62
- Lions D/ST: avg opponent offense rank 21.0 (vs NO, BUF, NYJ, CAR) — season proj 104
- Ravens D/ST: avg opponent offense rank 20.2 (vs IND, NO, DAL, TEN) — season proj 106
- 49ers D/ST: avg opponent offense rank 19.8 (vs LAR, MIA, ARI, DEN) — season proj 81
- Cowboys D/ST: avg opponent offense rank 19.8 (vs NYG, WAS, BAL, HOU) — season proj 76
- Bengals D/ST: avg opponent offense rank 19.8 (vs TB, HOU, PIT, JAX) — season proj 72
- Chargers D/ST: avg opponent offense rank 19.5 (vs ARI, LV, BUF, SEA) — season proj 81
- Browns D/ST: avg opponent offense rank 19.5 (vs JAX, TB, CAR, PIT) — season proj 72
- Vikings D/ST: avg opponent offense rank 18.0 (vs GB, CHI, TB, MIA) — season proj 104
- Titans D/ST: avg opponent offense rank 17.8 (vs NYJ, PHI, NYG, BAL) — season proj 71
- Patriots D/ST: avg opponent offense rank 17.2 (vs SEA, PIT, JAX, BUF) — season proj 96
- Eagles D/ST: avg opponent offense rank 17.0 (vs WAS, TEN, CHI, LAR) — season proj 98
- Bears D/ST: avg opponent offense rank 16.8 (vs CAR, MIN, PHI, NYJ) — season proj 87
- Seahawks D/ST: avg opponent offense rank 16.5 (vs NE, ARI, WAS, LAC) — season proj 110
- Packers D/ST: avg opponent offense rank 16.5 (vs MIN, NYJ, ATL, TB) — season proj 92
- Colts D/ST: avg opponent offense rank 15.8 (vs BAL, KC, HOU, WAS) — season proj 95
- Panthers D/ST: avg opponent offense rank 15.8 (vs CHI, ATL, CLE, DET) — season proj 69
- Giants D/ST: avg opponent offense rank 15.5 (vs DAL, LAR, TEN, ARI) — season proj 93
- Cardinals D/ST: avg opponent offense rank 15.5 (vs LAC, SEA, SF, NYG) — season proj 79
- Jaguars D/ST: avg opponent offense rank 14.8 (vs CLE, DEN, NE, CIN) — season proj 90
- Steelers D/ST: avg opponent offense rank 14.5 (vs ATL, NE, CIN, CLE) — season proj 106
- Buccaneers D/ST: avg opponent offense rank 14.2 (vs CIN, CLE, MIN, GB) — season proj 91
- Saints D/ST: avg opponent offense rank 14.2 (vs DET, BAL, LV, ATL) — season proj 71
- Jets D/ST: avg opponent offense rank 14.0 (vs TEN, GB, DET, CHI) — season proj 78
- Commanders D/ST: avg opponent offense rank 13.0 (vs PHI, DAL, SEA, IND) — season proj 71
- Rams D/ST: avg opponent offense rank 12.8 (vs SF, NYG, DEN, PHI) — season proj 99
- Dolphins D/ST: avg opponent offense rank 12.5 (vs LV, SF, KC, MIN) — season proj 69
- Bills D/ST: avg opponent offense rank 11.5 (vs HOU, DET, LAC, NE) — season proj 90
- Broncos D/ST: avg opponent offense rank 8.8 (vs KC, JAX, LAR, SF) — season proj 110
- Texans D/ST: avg opponent offense rank 7.8 (vs BUF, CIN, IND, DAL) — season proj 114


- Boone matched: 268 ranks, 0 salary-cap values
## Boone rows with no pool match (10)

- Days of Fantasy (rank 29)
- E. All Jr. (rank 265)
- J. Williams (rank 43)
- J. Williams (rank 50)
- K. Allen (rank 162)
- K. Allen (rank 198)
- M. Washington (rank 157)
- M. Washington Jr. (rank 153)
- N. Whittington (rank 297)
- R. White (rank 114)

## Injury disagreements (Sleeper vs ESPN) (5)

- Isaac Guerendo (RB): sleeper=PUP/Active espn=OUT
- Luke Musgrave (TE): sleeper=PUP/Active espn=OUT
- Tip Reiman (TE): sleeper=PUP/Active espn=OUT
- Tyrell Shavers (WR): sleeper=PUP/Active espn=OUT
- Zach Charbonnet (RB): sleeper=PUP/Active espn=OUT

## Team disagreements (0)

_none_

## Projection splits (183)

- Steelers D/ST (DST): sleeper=88.0 espn=132.7
- Jets D/ST (DST): sleeper=64.0 espn=99.8
- Broncos D/ST (DST): sleeper=96.0 espn=130.1
- Cardinals D/ST (DST): sleeper=66.0 espn=97.7
- Kendre Miller (RB): sleeper=5.6 espn=80.6
- Zach Charbonnet (RB): sleeper=67.2 espn=137.0
- Keaton Mitchell (RB): sleeper=96.9 espn=27.5
- DeMario Douglas (WR): sleeper=80.4 espn=141.7
- Marvin Mims (WR): sleeper=69.9 espn=149.1
- Parker Washington (WR): sleeper=212.4 espn=44.4
- Dontayvion Wicks (WR): sleeper=70.4 espn=20.5
- Darnell Washington (TE): sleeper=85.1 espn=13.5
- Anthony Richardson (QB): sleeper=21.3 espn=70.4
- Tank Bigsby (RB): sleeper=65.2 espn=109.7
- KaVontae Turpin (WR): sleeper=71.5 espn=104.2
- Cameron Dicker (K): sleeper=106.0 espn=143.9
- Jaylen Warren (RB): sleeper=170.6 espn=250.2
- Isiah Pacheco (RB): sleeper=53.6 espn=213.8
- Jalen Nailor (WR): sleeper=130.6 espn=23.9
- Christian Watson (WR): sleeper=207.6 espn=50.0
- Malik Willis (QB): sleeper=270.1 espn=2.4
- Kyren Williams (RB): sleeper=208.0 espn=284.0
- John Metchie (WR): sleeper=48.8 espn=1.2
- Alec Pierce (WR): sleeper=177.9 espn=70.9
- Zamir White (RB): sleeper=5.1 espn=64.7
- Isaiah Likely (TE): sleeper=157.3 espn=99.4
- Dameon Pierce (RB): sleeper=4.3 espn=51.5
- Jahan Dotson (WR): sleeper=71.2 espn=32.8
- Jalen Tolbert (WR): sleeper=34.2 espn=71.5
- Riley Patterson (K): sleeper=61.0 espn=29.9
- Joshua Palmer (WR): sleeper=32.6 espn=111.2
- Chuba Hubbard (RB): sleeper=147.9 espn=258.5
- Justin Fields (QB): sleeper=34.7 espn=299.3
- Dyami Brown (WR): sleeper=4.9 espn=107.3
- Tutu Atwell (WR): sleeper=10.7 espn=114.3
- Najee Harris (RB): sleeper=26.3 espn=95.0
- Nick Westbrook-Ikhine (WR): sleeper=29.5 espn=109.5
- Darnell Mooney (WR): sleeper=73.4 espn=160.8
- Jauan Jennings (WR): sleeper=105.7 espn=192.7
- Rico Dowdle (RB): sleeper=161.1 espn=84.0
- …and 143 more

## ESPN rows not matched and not added (364)

- Kene Nwangwu (NYJ RB) rank=431
- Bam Knight (ARI RB) rank=435
- Erick All Jr. (CIN TE) rank=443
- Jacob Saylors (DET RB) rank=456
- DeeJay Dallas (JAX RB) rank=457
- Josh Williams (TB RB) rank=458
- Jake Browning (TB QB) rank=482
- Sam Howell (DAL QB) rank=486
- Kyle Juszczyk (SF RB) rank=997
- Hollywood Brown (PHI WR) rank=1041
- Hunter Luepke (DAL RB) rank=1098
- Mason Tipton (NO WR) rank=1155
- Alec Ingold (LAC RB) rank=1162
- Ben Sims (MIA TE) rank=1170
- Adam Prentice (DEN RB) rank=1212
- Connor Heyward (LV RB) rank=1215
- Michael Burton (CLE RB) rank=1216
- Mitchell Tinsley (CIN WR) rank=1220
- Max Bredeson (MIN RB) rank=1224
- CJ Dippre (NE TE) rank=1237
- Kenny Pickett (CAR QB) rank=1243
- Matthew Hibner (BAL TE) rank=1257
- Justin Watson (HOU WR) rank=1262
- Andrew Beck (NYJ RB) rank=1267
- Jonathan Mingo (DAL WR) rank=1269
- Riley Nowakowski (PIT RB) rank=1276
- Drew Lock (SEA QB) rank=1280
- Reggie Gilliam (NE RB) rank=1281
- Patrick Ricard (NYG RB) rank=1290
- Braxton Berrios (NYG WR) rank=1335
- Charlie Jones (CIN WR) rank=1336
- British Brooks (HOU RB) rank=1337
- Myles Price (MIN WR) rank=1340
- Jalen Reagor (MIA WR) rank=1342
- Britain Covey (PHI WR) rank=1343
- Ihmir Smith-Marsette (ARI WR) rank=1346
- Ke'Shawn Williams (CIN WR) rank=1348
- Michael Bandy (DEN WR) rank=1356
- Mason Kinsey (TEN WR) rank=1358
- Laquon Treadwell (IND WR) rank=1362
- …and 324 more

## FFC rows with no Sleeper match (1)

- Bub Means (NO WR) adp=167.8

---

ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com).
