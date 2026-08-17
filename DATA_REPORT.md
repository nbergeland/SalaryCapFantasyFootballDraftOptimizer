# Data build report

- Built: 2026-08-17T09:58:17+00:00
- Season: 2026
- Players in bundle: **609**
- News lines: 25

## Source status

| Source | Status |
|---|---|
| sleeper_players | ok |
| sleeper_projections | ok |
| ffc_adp | ok |
| espn_kona | ok |
| espn_byes | ok |
| fantasypros | skipped (no key) |

## Counts

- Sleeper players DB entries: 4385
- Sleeper projection rows: 3300
- Dropped (no stats, no ADP): 2373
- ESPN matched / added: 631 / 0
- FFC matched / added: 259 / 0
- Backfilled from the Sleeper players DB: 36 (0 team corrections)
- Players marked OUT: 7
- FantasyPros headlines parsed: 0
- Pool before cutoff: 850 → kept 609

### Position breakdown

- QB: 69
- RB: 130
- WR: 190
- TE: 94
- K: 94
- DST: 32

## Auction values

- Replacement points: {'DST': 91.9, 'QB': 291.1, 'WR': 173.3, 'RB': 168.8, 'TE': 156.0, 'K': 116.2}
- $/VORP scale: 0.4158 (calibration factor 0.9354)
- ESPN-priced players: 100
- Mean abs error of the VORP model vs ESPN prices: 5.61

## Marked OUT (excluded from recommendations) (7)

- Brandon Aiyuk (SF WR): sleeper injury_status=DNR, espn injuryStatus=OUT
- Jaren Kanak (TEN TE): sleeper injury_status=IR
- Jeremiah Webb (NE WR): sleeper injury_status=IR
- John Michael Gyllenborg (KC TE): sleeper injury_status=IR
- Julian Hill (NE TE): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Ricky Pearsall (SF WR): sleeper injury_status=IR, espn injuryStatus=INJURY_RESERVE
- Zane Gonzalez (MIA K): sleeper injury_status=IR

## Teamless season-enders dropped (retired-player DB residue) (2)

- Adam Vinatieri (K)
- Stephen Hauschka (K)

## Injury disagreements (Sleeper vs ESPN) (9)

- Alec Pierce (WR): sleeper=PUP/Active espn=OUT
- Chris Bell (WR): sleeper=PUP/Active espn=OUT
- George Kittle (TE): sleeper=PUP/Active espn=OUT
- Isaac Guerendo (RB): sleeper=PUP/Active espn=OUT
- Jaren Kanak (TE): sleeper=IR/Inactive espn=ACTIVE
- Luke Musgrave (TE): sleeper=PUP/Active espn=OUT
- Tip Reiman (TE): sleeper=PUP/Active espn=OUT
- Tyrell Shavers (WR): sleeper=PUP/Active espn=OUT
- Zach Charbonnet (RB): sleeper=PUP/Active espn=OUT

## Team disagreements (0)

_none_

## Projection splits (185)

- Steelers D/ST (DST): sleeper=88.0 espn=132.7
- Jets D/ST (DST): sleeper=64.0 espn=99.8
- Broncos D/ST (DST): sleeper=96.0 espn=130.1
- Cardinals D/ST (DST): sleeper=66.0 espn=97.7
- Kendre Miller (RB): sleeper=5.6 espn=80.6
- Zach Charbonnet (RB): sleeper=67.2 espn=137.0
- Keaton Mitchell (RB): sleeper=96.9 espn=27.5
- DeMario Douglas (WR): sleeper=68.8 espn=141.7
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
- Jerome Ford (RB): sleeper=26.3 espn=109.3
- Alec Pierce (WR): sleeper=177.9 espn=70.9
- Zamir White (RB): sleeper=5.1 espn=64.7
- Tyler Allgeier (RB): sleeper=69.4 espn=104.8
- Isaiah Likely (TE): sleeper=157.3 espn=99.4
- Calvin Austin (WR): sleeper=54.8 espn=107.5
- Jahan Dotson (WR): sleeper=71.2 espn=32.8
- Jalen Tolbert (WR): sleeper=34.2 espn=71.5
- Joshua Palmer (WR): sleeper=32.6 espn=111.2
- Chuba Hubbard (RB): sleeper=147.9 espn=258.5
- Justin Fields (QB): sleeper=34.7 espn=299.3
- Dyami Brown (WR): sleeper=4.9 espn=107.3
- Tutu Atwell (WR): sleeper=10.7 espn=114.3
- Najee Harris (RB): sleeper=26.3 espn=95.0
- Nick Westbrook-Ikhine (WR): sleeper=26.7 espn=109.5
- Darnell Mooney (WR): sleeper=58.6 espn=160.8
- Jauan Jennings (WR): sleeper=105.7 espn=192.7
- …and 145 more

## ESPN rows not matched and not added (369)

- Kene Nwangwu (NYJ RB) rank=431
- Bam Knight (ARI RB) rank=435
- Erick All Jr. (CIN TE) rank=443
- Jacob Saylors (DET RB) rank=456
- DeeJay Dallas (JAX RB) rank=457
- Josh Williams (TB RB) rank=458
- Jake Browning (TB QB) rank=482
- Sam Howell (DAL QB) rank=486
- Kyle Juszczyk (SF RB) rank=994
- Hollywood Brown (PHI WR) rank=1041
- Hunter Luepke (DAL RB) rank=1097
- Alec Ingold (LAC RB) rank=1160
- Adam Prentice (DEN RB) rank=1209
- Connor Heyward (LV RB) rank=1212
- Michael Burton (CLE RB) rank=1213
- Mitchell Tinsley (CIN WR) rank=1218
- Max Bredeson (MIN RB) rank=1221
- CJ Dippre (NE TE) rank=1237
- Kenny Pickett (CAR QB) rank=1242
- Matthew Hibner (BAL TE) rank=1255
- Justin Watson (HOU WR) rank=1260
- Andrew Beck (NYJ RB) rank=1265
- Jonathan Mingo (DAL WR) rank=1266
- Johnny Mundt (PHI TE) rank=1271
- Riley Nowakowski (PIT RB) rank=1274
- Brycen Tremayne (CAR WR) rank=1277
- Drew Lock (SEA QB) rank=1278
- Reggie Gilliam (NE RB) rank=1279
- Patrick Ricard (NYG RB) rank=1288
- Jalen Reagor (MIA WR) rank=1316
- Braxton Berrios (NYG WR) rank=1336
- Charlie Jones (CIN WR) rank=1337
- British Brooks (HOU RB) rank=1338
- Myles Price (MIN WR) rank=1342
- Britain Covey (PHI WR) rank=1344
- Ke'Shawn Williams (CIN WR) rank=1347
- Mason Tipton (NO WR) rank=1350
- Michael Bandy (DEN WR) rank=1357
- Jeshaun Jones (MIN WR) rank=1358
- Mason Kinsey (TEN WR) rank=1359
- …and 329 more

## FFC rows with no Sleeper match (0)

_none_

---

ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com).
