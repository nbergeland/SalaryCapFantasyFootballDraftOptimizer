# Data build report

- Built: 2026-09-29T15:53:34+00:00
- Season: 2026
- Players in bundle: **657**
- News lines: 25

## Source status

| Source | Status |
|---|---|
| sleeper_players | ok |
| sleeper_projections | ok |
| ffc_adp | ok |
| espn_kona | ok |
| espn_byes | ok |
| boone | ok (278 ranks, 0 values, 40d old - STALE, re-run the boone-refresh workflow) |
| fantasypros | skipped (no key) |

## Counts

- Sleeper players DB entries: 4390
- Sleeper projection rows: 3305
- Dropped (no stats, no ADP): 2233
- ESPN matched / added: 645 / 1
- FFC matched / added: 29 / 0
- Backfilled from the Sleeper players DB: 41 (0 team corrections)
- Players marked OUT: 100
- Carrying a superflex (2QB) ADP: 338 (of which QB: 45)
- FantasyPros headlines parsed: 0
- Pool before cutoff: 989 → kept 657

### Position breakdown

- QB: 64
- RB: 155
- WR: 237
- TE: 104
- K: 65
- DST: 32

## Auction values

- Replacement points: {'DST': 91.9, 'QB': 291.5, 'WR': 173.4, 'RB': 168.7, 'TE': 156.0, 'K': 116.2}
- $/VORP scale: 0.4316 (calibration factor 0.9443)
- ESPN-priced players: 96
- Sleeper-priced players: 0 (auction keys seen in the feed: none)
- Mean abs error of the VORP model vs ESPN prices: 6.18

## Marked OUT (excluded from recommendations) (100)

- A.J. Brown (NE WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Adam Randall (BAL RB): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Adonai Mitchell (NYJ WR): sleeper injury_status=Out, espn injuryStatus=OUT
- Alec Pierce (IND WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Andrei Iosivas (CIN WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Arian Smith (NYJ WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Ashton Dulin (IND WR): sleeper injury_status=Out, espn injuryStatus=OUT
- Baker Mayfield (TB QB): sleeper injury_status=Out, espn injuryStatus=OUT
- Barion Brown (NO WR): sleeper injury_status=Out, espn injuryStatus=OUT
- Ben Yurosek (MIN TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Blake Grupe (NYJ K): sleeper injury_status=Out
- Brandon Aiyuk (SF WR): sleeper injury_status=DNR, espn injuryStatus=OUT
- Breece Hall (NYJ RB): sleeper injury_status=Out
- Brenen Thompson (LAC WR): sleeper injury_status=Out, espn injuryStatus=OUT
- Brevin Jordan (HOU TE): sleeper injury_status=Out
- CJ Daniels (LAR WR): sleeper injury_status=Out
- Caleb Douglas (MIA WR): sleeper injury_status=Out, espn injuryStatus=OUT
- Caleb Williams (CHI QB): sleeper injury_status=Out, espn injuryStatus=OUT
- Carson Beck (ARI QB): sleeper injury_status=Out
- Charlie Kolar (LAC TE): sleeper injury_status=Out, espn injuryStatus=OUT
- Chig Okonkwo (WAS TE): sleeper injury_status=Out, espn injuryStatus=OUT
- Christian Kirk (SF WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Colbie Young (CIN WR): sleeper injury_status=Out, espn injuryStatus=OUT
- DJ Giddens (IND RB): sleeper injury_status=Out
- Dalevon Campbell (LAC WR): espn injuryStatus=INJURY_RESERVE
- Dallas Goedert (PHI TE): sleeper injury_status=Out, espn injuryStatus=OUT
- Darius Slayton (IND WR): sleeper injury_status=Out
- David Njoku (LAC TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- David Sills (TB WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- De'Von Achane (MIA RB): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- De'Zhaun Stribling (SF WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Demarcus Robinson (SF WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Devin Singletary (NYG RB): sleeper injury_status=Out
- Dillon Gabriel (CLE QB): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Dont'e Thornton (LV WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Drew Allar (PIT QB): sleeper injury_status=Out
- Dylan Sampson (CLE RB): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Eli Raridon (NE TE): sleeper injury_status=Out, espn injuryStatus=OUT
- Eli Stowers (PHI TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Elijah Sarratt (BAL WR): sleeper injury_status=Out
- …and 60 more

## Teamless season-enders dropped (retired-player DB residue) (7)

- Adam Vinatieri (K)
- Benjamin Watson (TE)
- Joe Mixon (RB)
- Nick Keizer (TE)
- Stephen Hauschka (K)
- Tyreek Hill (WR)
- Vance McDonald (TE)

## D/ST opening-month schedule (softest slate first) (32)

- Bears D/ST: avg opponent offense rank 23.0 (vs CAR, MIN, PHI, NYJ) — season proj 87
- Eagles D/ST: avg opponent offense rank 22.5 (vs WAS, TEN, CHI, LAR) — season proj 98
- Falcons D/ST: avg opponent offense rank 22.5 (vs PIT, CAR, GB, NO) — season proj 78
- Lions D/ST: avg opponent offense rank 22.2 (vs NO, BUF, NYJ, CAR) — season proj 104
- Vikings D/ST: avg opponent offense rank 22.0 (vs GB, CHI, TB, MIA) — season proj 104
- Cowboys D/ST: avg opponent offense rank 22.0 (vs NYG, WAS, BAL, HOU) — season proj 76
- 49ers D/ST: avg opponent offense rank 20.0 (vs LAR, MIA, ARI, DEN) — season proj 81
- Packers D/ST: avg opponent offense rank 20.0 (vs MIN, NYJ, ATL, TB) — season proj 92
- Chiefs D/ST: avg opponent offense rank 19.8 (vs DEN, IND, MIA, LV) — season proj 91
- Seahawks D/ST: avg opponent offense rank 18.8 (vs NE, ARI, WAS, LAC) — season proj 110
- Raiders D/ST: avg opponent offense rank 18.8 (vs MIA, LAC, NO, KC) — season proj 62
- Titans D/ST: avg opponent offense rank 18.5 (vs NYJ, PHI, NYG, BAL) — season proj 71
- Browns D/ST: avg opponent offense rank 18.0 (vs JAX, TB, CAR, PIT) — season proj 72
- Bengals D/ST: avg opponent offense rank 17.8 (vs TB, HOU, PIT, JAX) — season proj 72
- Buccaneers D/ST: avg opponent offense rank 17.0 (vs CIN, CLE, MIN, GB) — season proj 91
- Colts D/ST: avg opponent offense rank 17.0 (vs BAL, KC, HOU, WAS) — season proj 95
- Ravens D/ST: avg opponent offense rank 16.2 (vs IND, NO, DAL, TEN) — season proj 106
- Dolphins D/ST: avg opponent offense rank 15.5 (vs LV, SF, KC, MIN) — season proj 69
- Panthers D/ST: avg opponent offense rank 15.5 (vs CHI, ATL, CLE, DET) — season proj 69
- Giants D/ST: avg opponent offense rank 15.0 (vs DAL, LAR, TEN, ARI) — season proj 93
- Cardinals D/ST: avg opponent offense rank 15.0 (vs LAC, SEA, SF, NYG) — season proj 79
- Chargers D/ST: avg opponent offense rank 14.5 (vs ARI, LV, BUF, SEA) — season proj 81
- Rams D/ST: avg opponent offense rank 14.2 (vs SF, NYG, DEN, PHI) — season proj 99
- Jets D/ST: avg opponent offense rank 14.0 (vs TEN, GB, DET, CHI) — season proj 78
- Jaguars D/ST: avg opponent offense rank 13.8 (vs CLE, DEN, NE, CIN) — season proj 90
- Steelers D/ST: avg opponent offense rank 13.5 (vs ATL, NE, CIN, CLE) — season proj 106
- Bills D/ST: avg opponent offense rank 13.0 (vs HOU, DET, LAC, NE) — season proj 90
- Commanders D/ST: avg opponent offense rank 11.0 (vs PHI, DAL, SEA, IND) — season proj 71
- Patriots D/ST: avg opponent offense rank 10.8 (vs SEA, PIT, JAX, BUF) — season proj 96
- Broncos D/ST: avg opponent offense rank 10.5 (vs KC, JAX, LAR, SF) — season proj 110
- Saints D/ST: avg opponent offense rank 9.5 (vs DET, BAL, LV, ATL) — season proj 71
- Texans D/ST: avg opponent offense rank 6.2 (vs BUF, CIN, IND, DAL) — season proj 114


- Boone matched: 262 ranks, 0 salary-cap values
## Boone rows with no pool match (16)

- Days of Fantasy (rank 29)
- E. All Jr. (rank 265)
- J. Ferguson (rank 178)
- J. Johnson (rank 159)
- J. Williams (rank 43)
- J. Williams (rank 50)
- J. Wright (rank 223)
- K. Allen (rank 162)
- K. Allen (rank 198)
- K. Coleman (rank 266)
- M. Davis (rank 282)
- M. Washington (rank 157)
- M. Washington Jr. (rank 153)
- N. Whittington (rank 297)
- R. White (rank 114)
- T. Etienne (rank 279)

## Injury disagreements (Sleeper vs ESPN) (35)

- Blake Grupe (K): sleeper=Out/Active espn=ACTIVE
- Breece Hall (RB): sleeper=Out/Active espn=QUESTIONABLE
- Brevin Jordan (TE): sleeper=Out/Active espn=ACTIVE
- CJ Daniels (WR): sleeper=Out/Active espn=ACTIVE
- Carson Beck (QB): sleeper=Out/Active espn=ACTIVE
- DJ Giddens (RB): sleeper=Out/Active espn=ACTIVE
- Dalevon Campbell (WR): sleeper=Questionable/Inactive espn=INJURY_RESERVE
- Darius Slayton (WR): sleeper=Out/Active espn=ACTIVE
- Devin Singletary (RB): sleeper=Out/Active espn=ACTIVE
- Drew Allar (QB): sleeper=Out/Active espn=ACTIVE
- Elijah Sarratt (WR): sleeper=Out/Active espn=ACTIVE
- Emari Demercado (RB): sleeper=Out/Active espn=ACTIVE
- Isaac Guerendo (RB): sleeper=PUP/Active espn=OUT
- J.J. McCarthy (QB): sleeper=Out/Active espn=ACTIVE
- Ja'Tavion Sanders (TE): sleeper=Out/Active espn=ACTIVE
- Jack Endries (TE): sleeper=Out/Active espn=ACTIVE
- Jalen Coker (WR): sleeper=Out/Active espn=QUESTIONABLE
- Jalen Milroe (QB): sleeper=Out/Active espn=ACTIVE
- Joe Royer (TE): sleeper=PUP/Active espn=OUT
- Justin Jefferson (WR): sleeper=Out/Active espn=QUESTIONABLE
- Kylen Granson (TE): sleeper=Out/Active espn=ACTIVE
- Lil'Jordan Humphrey (WR): sleeper=Out/Active espn=ACTIVE
- Michael Carter (RB): sleeper=Out/Active espn=ACTIVE
- Mike Evans (WR): sleeper=Out/Active espn=QUESTIONABLE
- Reggie Virgil (WR): sleeper=Out/Active espn=ACTIVE
- Riley Leonard (QB): sleeper=Out/Active espn=ACTIVE
- Skyler Bell (WR): sleeper=Out/Active espn=ACTIVE
- Taylen Green (QB): sleeper=Out/Active espn=ACTIVE
- Tip Reiman (TE): sleeper=PUP/Active espn=OUT
- Tutu Atwell (WR): sleeper=Out/Active espn=ACTIVE
- Ty Simpson (QB): sleeper=Out/Active espn=ACTIVE
- Tyler Conklin (TE): sleeper=Out/Active espn=ACTIVE
- Tyrell Shavers (WR): sleeper=PUP/Active espn=OUT
- Will Howard (QB): sleeper=Out/Active espn=ACTIVE
- Zach Charbonnet (RB): sleeper=PUP/Active espn=OUT

## Team disagreements (0)

_none_

## Projection splits (181)

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
- …and 141 more

## ESPN rows not matched and not added (354)

- Malik Davis (DAL RB) rank=329
- Kene Nwangwu (NYJ RB) rank=408
- Bam Knight (ARI RB) rank=433
- Eli Heidenreich (PIT RB) rank=445
- Erick All Jr. (CIN TE) rank=449
- Riley Nowakowski (PIT RB) rank=461
- Jalon Daniels (TB QB) rank=481
- Sam Howell (DAL QB) rank=487
- Kyle Juszczyk (SF RB) rank=1002
- Hollywood Brown (PHI WR) rank=1047
- Hunter Luepke (DAL RB) rank=1096
- Laquon Treadwell (IND WR) rank=1153
- Alec Ingold (LAC RB) rank=1162
- Tay Martin (DET WR) rank=1182
- Adam Prentice (DEN RB) rank=1203
- Michael Burton (CLE RB) rank=1208
- Kenny Pickett (CAR QB) rank=1233
- Matthew Hibner (BAL TE) rank=1245
- Andrew Beck (NYJ RB) rank=1252
- Jonathan Mingo (DAL WR) rank=1253
- Hunter Long (ARI TE) rank=1255
- Johnny Mundt (PHI TE) rank=1259
- Carsen Ryan (CLE TE) rank=1261
- Kyle McCord (MIA QB) rank=1266
- Drew Lock (SEA QB) rank=1268
- Patrick Ricard (NYG RB) rank=1273
- Corey Kiner (NE RB) rank=1294
- Braxton Berrios (NYG WR) rank=1318
- Ke'Shawn Williams (CIN WR) rank=1322
- Myles Price (MIN WR) rank=1323
- Cooper Rush (ATL QB) rank=1328
- Gunner Olszewski (NYG WR) rank=1341
- AJ Dillon (CAR RB) rank=1343
- Trey Sermon (ATL RB) rank=1345
- Elijah Moore (PHI WR) rank=1346
- Zach Wilson (NO QB) rank=1347
- Simi Fehoko (ARI WR) rank=1352
- Sam Ehlinger (DEN QB) rank=1353
- D.J. Montgomery (IND WR) rank=1355
- Calvin Austin III (NYG WR) rank=1359
- …and 314 more

## FFC rows with no Sleeper match (0)

_none_

---

ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com).
