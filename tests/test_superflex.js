/* Superflex (SF / 2QB) league suite.
 *
 * Superflex is not a cosmetic slot: it doubles quarterback demand, moves the
 * position's replacement level by a dozen ranks, reorders the draft board and
 * puts a second QB in the optimal roster. These tests pin down all of that on
 * the real bundled pool, and — just as important — pin down that a league
 * WITHOUT a superflex slot behaves exactly as it did before the feature.
 *
 * The shipped bundle does not carry adp2 (superflex ADP) until the first data
 * build after the pipeline change, so the snake scenario seeds a plausible 2QB
 * board onto the pool in-page rather than depending on the bundle for it.
 *
 * playwright is not a dependency of this repo (it has no npm side), so run it
 * from wherever playwright is installed:
 *
 *   NODE_PATH=/path/to/node_modules CHROMIUM=/path/to/chrome \
 *     node tests/test_superflex.js
 */
const { chromium } = require('playwright');
const path = require('path');

const INDEX = process.env.INDEX_HTML || path.join(__dirname, '..', 'index.html');
const CHROMIUM = process.env.CHROMIUM ||
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('PASS  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); }
};

// a superflex league on Sleeper: SUPER_FLEX alongside an ordinary FLEX
const SL = {
  'user/sfuser': { user_id: 'U9', display_name: 'sfuser' },
  'user/U9/leagues/nfl/2026': [{ league_id: 'L9', name: 'Superflex League', total_rosters: 12 }],
  'league/L9': {
    league_id: 'L9', name: 'Superflex League', total_rosters: 12,
    roster_positions: ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'SUPER_FLEX',
      'K', 'DEF', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN'],
    scoring_settings: { rec: 1, pass_td: 4, pass_int: -2, pass_yd: 0.04, rush_yd: 0.1, rush_td: 6 },
  },
  'league/L9/users': [{ user_id: 'U9', display_name: 'sfuser' }],
  'league/L9/drafts': [{ draft_id: 'D9', status: 'pre_draft', type: 'snake', settings: {} }],
  'draft/D9/picks': [],
};

(async () => {
  const browser = await chromium.launch({ executablePath: CHROMIUM });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  page.on('console', m => {
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text()))
      errs.push('CONSOLE: ' + m.text());
  });
  await ctx.route('https://api.sleeper.app/v1/**', route => {
    const key = route.request().url().replace('https://api.sleeper.app/v1/', '');
    const body = SL[key];
    route.fulfill({
      status: body ? 200 : 404, contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify(body ?? { error: 'not found ' + key }),
    });
  });

  const reset = async () => {
    await page.goto('file://' + INDEX);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForTimeout(1200);
  };

  // ============================================================ (1) auction
  // In superflex economics a second quarterback is essentially always worth a
  // starting slot — the optimizer has to find that on its own, and its max
  // bids have to agree with the roster it proposes.
  console.log('\n--- scenario 1: SFLEX:1 auction on the real bundle ---');
  {
    await reset();
    const r = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.slots.SFLEX = 1;
      A.recompute();
      const shape = () => ({
        total: +A.R.sol.total.toFixed(4),
        roster: A.R.sol.chosen.map(r => A.playerId(r.p) + '@' + r.adj).sort(),
      });
      const first = shape();
      A.recompute();
      const second = shape();
      const qbs = A.R.sol.chosen.filter(r => r.p.pos === 'QB')
        .sort((a, b) => b.rpts - a.rpts);
      return {
        first, second,
        nQB: qbs.length,
        qbs: qbs.map(r => ({ name: r.p.name, adj: r.adj, bid: A.R.bids.get(A.playerId(r.p)) })),
        rosterSize: A.R.sol.chosen.length,
        slotsFilled: Object.values(A.S.settings.slots).reduce((a, b) => a + b, 0),
      };
    });
    ok('optimal roster seats two quarterbacks', r.nQB === 2, r.qbs);
    ok('the roster fills exactly the starting slots (SFLEX included)',
      r.rosterSize === r.slotsFilled, { rosterSize: r.rosterSize, slots: r.slotsFilled });
    ok('QB2 carries a real max bid', r.qbs.length === 2 && r.qbs[1].bid > 0, r.qbs);
    ok('max bid is at least what the plan pays for him',
      r.qbs.length === 2 && r.qbs[1].bid >= r.qbs[1].adj, r.qbs);
    ok('solver is idempotent across recomputes',
      JSON.stringify(r.first) === JSON.stringify(r.second), r);

    // buying at the max bid must not break the completion: the enumeration
    // used for max bids and the one used for the roster have to be the same
    const after = await page.evaluate(() => {
      const A = window.APP;
      const step = () => {
        const qb = A.R.sol.chosen.filter(r => r.p.pos === 'QB')
          .sort((a, b) => a.rpts - b.rpts)[0];       // cheapest planned QB first
        if (!qb) return null;
        A.draftPlayer(qb.p, A.R.bids.get(A.playerId(qb.p)), true);
        const a = A.myRosterAssignment();
        return {
          bought: qb.p.name,
          feasible: !!A.R.sol,
          qbSeat: a.starters.QB.length,
          sflexSeat: a.sflex.map(p => p.pos),
          planQB: A.R.sol ? A.R.sol.chosen.filter(r => r.p.pos === 'QB').length : null,
        };
      };
      return [step(), step()];
    });
    ok('buying QB2 at his max bid leaves a feasible roster', after[0].feasible, after[0]);
    ok('one QB bought fills the dedicated slot, superflex still shopping',
      after[0].qbSeat === 1 && after[0].sflexSeat.length === 0 && after[0].planQB === 1,
      after[0]);
    ok('the second QB is seated in the superflex slot',
      after[1].sflexSeat.length === 1 && after[1].sflexSeat[0] === 'QB', after[1]);
    ok('with both seats filled the completion stops shopping for QBs',
      after[1].planQB === 0, after[1]);
  }

  // ============================================================= (2) SFLEX:0
  // A 1QB league must behave exactly as it did before superflex existed.
  console.log('\n--- scenario 2: SFLEX:0 is unchanged behavior ---');
  {
    await reset();
    const r = await page.evaluate(() => {
      const A = window.APP;
      const shape = () => ({
        total: +A.R.sol.total.toFixed(4),
        roster: A.R.sol.chosen.map(r => A.playerId(r.p) + '@' + r.adj).sort(),
        repl: JSON.parse(JSON.stringify(A.M.repl)),
        bids: [...A.R.bids.entries()].sort().map(([k, v]) => k + '=' + v).join(','),
      });
      const before = shape();
      const qbByPts = A.M.rows.filter(r => r.p.pos === 'QB' && !r.p.out)
        .sort((a, b) => b.pts0 - a.pts0);
      const replRank = n => qbByPts[n - 1].pts0;
      A.S.settings.slots.SFLEX = 1; A.recompute();
      const sfRepl = A.M.repl.QB, sfIsSF = A.isSF();
      A.S.settings.slots.SFLEX = 0; A.recompute();
      const after = shape();
      return {
        same: JSON.stringify(before) === JSON.stringify(after),
        oneQB: { repl: before.repl.QB, want: replRank(12) },
        superflex: { repl: sfRepl, want: replRank(24), isSF: sfIsSF },
        isSFoff: A.isSF(),
      };
    });
    ok('turning superflex on and off again restores the 1QB solve exactly',
      r.same, r);
    ok('1QB replacement level is the 12th quarterback',
      r.oneQB.repl === r.oneQB.want, r.oneQB);
    ok('superflex replacement level drops to the 24th quarterback',
      r.superflex.repl === r.superflex.want, r.superflex);
    ok('superflex replacement is materially lower than 1QB',
      r.superflex.repl < r.oneQB.repl - 20, { sf: r.superflex.repl, one: r.oneQB.repl });
    ok('isSF() tracks the slot', r.superflex.isSF === true && r.isSFoff === false, r);
  }

  // =============================================================== (3) snake
  // The 2QB board is the whole game in an SF snake draft: quarterbacks leave
  // rounds earlier than their 1QB ADP suggests, and the plan has to see it.
  console.log('\n--- scenario 3: SFLEX:1 snake plan on a seeded 2QB board ---');
  {
    await reset();
    const r = await page.evaluate(() => {
      const A = window.APP;
      // a realistic 12-team superflex board: 24 quarterbacks are starters, so
      // QB1 goes around pick 8 and QB24 is gone by pick ~120. Everyone else
      // slides ~30% to make room for them.
      const qbs = A.S.players.filter(p => p.pos === 'QB' && !p.out)
        .sort((a, b) => b.pts - a.pts);
      qbs.forEach((p, i) => { p.adp2 = +(8 + 4.7 * i).toFixed(1); });
      for (const p of A.S.players)
        if (p.pos !== 'QB' && p.adp != null) p.adp2 = +(p.adp * 1.3).toFixed(1);
      A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = 1;
      const run = sflex => {
        A.S.settings.slots.SFLEX = sflex;
        A.recompute();
        const plan = A.R.sol.plan;
        const qbSteps = plan.filter(s => s.r.p.pos === 'QB');
        return {
          len: plan.length,
          roles: plan.map(s => `${s.n}:${s.role}:${s.r.p.pos}`),
          starterQB: qbSteps.filter(s => s.role !== 'BN').length,
          starterRoles: qbSteps.filter(s => s.role !== 'BN').map(s => s.role).sort(),
          benchQB: qbSteps.filter(s => s.role === 'BN').length,
          firstQB: qbSteps.length ? qbSteps[0].n : null,
          firstBenchQB: qbSteps.filter(s => s.role === 'BN').map(s => s.n)[0] ?? null,
          lastTwo: plan.slice(-2).map(s => s.r.p.pos),
          topQBmrank: A.M.rows.filter(r => r.p.pos === 'QB')
            .sort((a, b) => a.mrank - b.mrank)[0].mrank,
        };
      };
      const sf = run(1), one = run(0);
      return { sf, one, picks: A.S.settings.teams };
    });
    ok('exactly two quarterbacks start (QB + SFLEX)',
      r.sf.starterQB === 2 && JSON.stringify(r.sf.starterRoles) === '["QB","SFLEX"]',
      r.sf.starterRoles);
    ok('at most one quarterback is planned for the bench',
      r.sf.benchQB <= 1, r.sf);
    ok('no bench quarterback is taken before both starters',
      r.sf.firstBenchQB === null || r.sf.firstBenchQB > r.sf.firstQB, r.sf);
    ok('the 2QB board is what ranks the room in superflex',
      r.sf.topQBmrank <= 10, r.sf.topQBmrank);
    ok('a 1QB league still ranks off ordinary ADP',
      r.one.topQBmrank > 20, r.one.topQBmrank);
    ok('superflex drafts its first quarterback earlier than a 1QB league',
      r.sf.firstQB <= r.one.firstQB - r.picks, { sf: r.sf.firstQB, one: r.one.firstQB });
    ok('the first quarterback goes inside the first third of the draft',
      r.sf.firstQB <= r.picks * (r.sf.len / 3), { firstQB: r.sf.firstQB, len: r.sf.len });
    ok('the superflex plan covers one more slot than the 1QB plan',
      r.sf.len === r.one.len + 1, { sf: r.sf.len, one: r.one.len });
    ok('K and DST still go with the last two picks',
      r.sf.lastTwo.sort().join() === 'DST,K', r.sf.lastTwo);
  }

  // ================================================================ (4) sync
  console.log('\n--- scenario 4: Sleeper imports SUPER_FLEX as its own slot ---');
  {
    await reset();
    await page.click('nav.tabs button[data-tab="data"]');
    await page.fill('#slUser', 'sfuser');
    await page.click('#slFind');
    await page.waitForTimeout(400);
    await page.click('#slLoad');
    await page.waitForTimeout(600);
    const r = await page.evaluate(() => ({
      slots: JSON.parse(JSON.stringify(window.APP.S.settings.slots)),
      bench: window.APP.S.settings.bench,
      mode: window.APP.S.settings.mode,
      form: +document.querySelector('#s_SFLEX').value,
      isSF: window.APP.isSF(),
    }));
    ok('SUPER_FLEX lands in slots.SFLEX', r.slots.SFLEX === 1, r.slots);
    ok('the ordinary FLEX count is not inflated by it', r.slots.FLEX === 1, r.slots);
    ok('the rest of the lineup imports as before',
      r.slots.QB === 1 && r.slots.RB === 2 && r.slots.WR === 2 && r.slots.TE === 1 &&
      r.slots.K === 1 && r.slots.DST === 1 && r.bench === 6, r.slots);
    ok('the Settings form shows the imported superflex slot', r.form === 1, r.form);
    ok('the app knows it is a superflex league', r.isSF === true);

    // ESPN calls the same slot OP (lineup slot id 7)
    const espn = await page.evaluate(() => {
      const A = window.APP;
      A.SYNC.es.settingsApplied = false;
      A.espnIngest({
        teams: [{ id: 1, name: 'Mine', roster: { entries: [] } }],
        settings: {
          draftSettings: { type: 'AUCTION', auctionBudget: 200 },
          rosterSettings: { lineupSlotCounts: { 0: 1, 2: 2, 4: 2, 6: 1, 7: 1, 23: 1, 16: 1, 17: 1, 20: 6 } },
        },
        draftDetail: { picks: [] },
      }, false);
      A.espnApply({});
      return JSON.parse(JSON.stringify(A.S.settings.slots));
    });
    ok('ESPN slot 7 (OP) imports as superflex', espn.SFLEX === 1, espn);
    ok('ESPN slot 23 still imports as FLEX', espn.FLEX === 1, espn);
  }

  // ======================================================== (5) Monte Carlo
  // The weekly best-lineup builder is what turns a rostered QB2 into points.
  // Without the SFLEX pass he sits on the bench every week and the sim cannot
  // tell him apart from a scrub.
  console.log('\n--- scenario 5: Monte Carlo seats QB2 in the superflex slot ---');
  {
    await reset();
    const r = await page.evaluate(() => {
      const A = window.APP;
      const slots = { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SFLEX: 1, K: 1, DST: 1 };
      const oneQB = { ...slots, SFLEX: 0 };
      const base = [
        { pos: 'RB', pts: 280 }, { pos: 'RB', pts: 240 }, { pos: 'RB', pts: 190 },
        { pos: 'WR', pts: 270 }, { pos: 'WR', pts: 230 }, { pos: 'WR', pts: 200 },
        { pos: 'TE', pts: 180 }, { pos: 'K', pts: 130 }, { pos: 'DST', pts: 120 },
        { pos: 'QB', pts: 380 },
      ];
      const withQB2 = base.concat([{ pos: 'QB', pts: 330 }]);
      const withScrub = base.concat([{ pos: 'WR', pts: 90 }]);
      const r = {
        sfQB2: A.simulateRoster(withQB2, slots, 1500),
        sfScrub: A.simulateRoster(withScrub, slots, 1500),
        oneQB2: A.simulateRoster(withQB2, oneQB, 1500),
        oneScrub: A.simulateRoster(withScrub, oneQB, 1500),
      };
      r.sfGain = r.sfQB2.p50 - r.sfScrub.p50;
      r.oneGain = r.oneQB2.p50 - r.oneScrub.p50;
      return r;
    });
    ok('a superflex roster is worth more with a real QB2 than with a scrub',
      r.sfQB2.p50 > r.sfScrub.p50, { qb2: r.sfQB2, scrub: r.sfScrub });
    ok('the gain is the size of a starting quarterback, not noise',
      r.sfQB2.p50 - r.sfScrub.p50 > 100, { qb2: r.sfQB2.p50, scrub: r.sfScrub.p50 });
    ok('the floor rises too (QB2 also covers the QB1 bye/miss weeks)',
      r.sfQB2.p10 > r.sfScrub.p10, { qb2: r.sfQB2, scrub: r.sfScrub });
    // in a 1QB league the same QB2 is bench insurance — worth something (he
    // covers QB1's miss weeks and wins the odd hindsight week) but nothing
    // like a starting slot
    ok('a superflex QB2 is worth several times what a 1QB backup is worth',
      r.sfGain > 4 * r.oneGain, { sf: r.sfGain, one: r.oneGain });
    ok('the superflex lineup outscores the 1QB lineup on the same roster',
      r.sfQB2.p50 > r.oneQB2.p50 + 100, { sf: r.sfQB2.p50, one: r.oneQB2.p50 });
  }

  // ============================================================= (6) adp2
  // The bundle only gains adp2 with the first data build after the pipeline
  // change, so the plumbing that carries it has to be tested on its own.
  console.log('\n--- scenario 6: the superflex ADP field survives every path ---');
  {
    await reset();
    await ctx.route('**/api.sleeper.com/projections/**', route => route.fulfill({
      status: 200, contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify([
        {
          player_id: '4984', team: 'BUF',
          player: { first_name: 'Josh', last_name: 'Allen', position: 'QB', team: 'BUF' },
          stats: { pass_yd: 4100, pass_td: 32, pts_ppr: 395.4, adp_ppr: 22.5, adp_2qb: 5.5 },
        },
        {
          player_id: '4881', team: 'BAL',
          player: { first_name: 'Lamar', last_name: 'Jackson', position: 'QB', team: 'BAL' },
          stats: { pass_yd: 3800, pass_td: 30, pts_ppr: 378.1, adp_ppr: 26.0, adp_2qb: 999.0 },
        },
      ]),
    }));
    const r = await page.evaluate(async () => {
      const A = window.APP;
      const fresh = A.freshPlayer({ name: 'Test Guy', pos: 'QB', aav: 5, pts: 200, adp2: 12.3 });
      const bare = A.freshPlayer({ name: 'Bare Guy', pos: 'QB', aav: 5, pts: 200 });
      const by = n => A.S.players.find(p => p.name === n) || null;
      const lamarBefore = by('Lamar Jackson') ? by('Lamar Jackson').adp2 : null;
      const res = await A.refreshProjections();
      return {
        fresh: fresh.adp2, bare: bare.adp2, updated: res.updated,
        allen: by('Josh Allen') && by('Josh Allen').adp2,
        lamarBefore,
        lamar: by('Lamar Jackson') && by('Lamar Jackson').adp2,
      };
    });
    ok('freshPlayer carries adp2 through', r.fresh === 12.3, r);
    ok('a player with no 2QB rank gets null, not undefined', r.bare === null, r);
    ok('the live refresh applies adp_2qb', r.allen === 5.5, r);
    // a 999-style placeholder in the live feed means "no current signal",
    // not "his rank vanished" — whatever value the bundle supplied must
    // survive it untouched. (When this test was written the bundle carried
    // no adp2, so "left alone" and "nulled" were indistinguishable; the
    // real nightly builds ship adp2 now.)
    ok('placeholder 2QB ADP leaves the stored value alone',
      r.lamar === r.lamarBefore, r);
    await ctx.unroute('**/api.sleeper.com/projections/**');
  }

  // ============================================================ settings I/O
  console.log('\n--- settings round-trip ---');
  {
    await reset();
    const r = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.slots.SFLEX = 2;
      A.settingsToForm();
      const shown = +document.querySelector('#s_SFLEX').value;
      document.querySelector('#s_SFLEX').value = '1';
      A.formToSettings();
      return { shown, read: A.S.settings.slots.SFLEX, def: A.LEAGUES.list.length };
    });
    ok('settingsToForm shows the superflex count', r.shown === 2, r);
    ok('formToSettings reads it back', r.read === 1, r);
    const saved = await page.evaluate(async () => {
      const A = window.APP;
      A.S.settings.slots.SFLEX = 1; A.recompute();
      await new Promise(r => setTimeout(r, 100));
      location.reload();
    }).catch(() => null);
    await page.waitForTimeout(1500);
    const persisted = await page.evaluate(() => window.APP.S.settings.slots.SFLEX);
    ok('the superflex slot survives a reload', persisted === 1, { persisted, saved });
  }

  ok('no page errors', errs.length === 0, errs);
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exit(1);
  console.log('SUPERFLEX TESTS PASSED');
})();
