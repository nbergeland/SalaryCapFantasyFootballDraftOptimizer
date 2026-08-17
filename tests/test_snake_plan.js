/* Snake plan quality suite.
 *
 * Two failures of the one-pick-lookahead greedy this pins down, both reported
 * from real use of the deployed app:
 *
 *   "QB in round 2" — one-round dropoff makes every position look urgent the
 *   round before its tier breaks, even when you would happily fill that slot
 *   in round 8. The correct opportunity cost is against the quarterback you
 *   would actually end up with, which only a rollout can see.
 *
 *   "many TE" — a second and third tight end were scored against the TE tier
 *   cliff, but a flex/bench tight end's real alternative is the best RB/WR/TE
 *   who could take that same seat.
 *
 * Everything here runs on the real bundled pool, so the assertions are about
 * plan SHAPE (when the first quarterback goes, how many tight ends, where the
 * kicker lands) rather than specific players, which change nightly.
 *
 *   NODE_PATH=/path/to/node_modules CHROMIUM=/path/to/chrome \
 *     node tests/test_snake_plan.js
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

(async () => {
  const browser = await chromium.launch({ executablePath: CHROMIUM });
  const page = await browser.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
  page.on('console', m => {
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text()))
      errs.push('CONSOLE: ' + m.text());
  });
  await page.goto('file://' + INDEX);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForTimeout(1200);

  // the plan the plain greedy would have produced, for the no-regression check
  const install = () => page.evaluate(() => {
    window.T = {
      greedy(rule) {
        const A = window.APP;
        const cur = A.currentOverallPick(), T = A.S.settings.teams;
        const st = A.snakePlanState();
        const picks = A.myPickNumbers().filter(n => n >= cur).slice(0, A.snakeSlotsLeft(st));
        A.snakeGreedyFill(st, picks, 0, cur, T, rule || null);
        return st.plan;
      },
      shape(plan) {
        const A = window.APP, T = A.S.settings.teams;
        const round = n => Math.ceil(n / T);
        const starters = plan.filter(s => s.role !== 'BN');
        const qb = plan.filter(s => s.r.p.pos === 'QB');
        return {
          len: plan.length,
          picks: plan.map(s => `R${round(s.n)} ${s.role} ${s.r.p.pos}`),
          firstQBround: qb.length ? round(qb[0].n) : null,
          qb: qb.length,
          starterQB: qb.filter(s => s.role !== 'BN').length,
          te: plan.filter(s => s.r.p.pos === 'TE').length,
          lastTwo: plan.slice(-2).map(s => s.r.p.pos).sort().join(),
          kdRounds: plan.filter(s => s.r.p.pos === 'K' || s.r.p.pos === 'DST')
            .map(s => round(s.n)),
          starterPts: Math.round(starters.reduce((a, s) => a + s.r.rpts, 0)),
          value: Math.round(A.snakePlanValue(plan)),
        };
      },
    };
  });
  await install();

  // ===================================================== 1QB, three draft slots
  console.log('\n--- a 1QB league from three draft slots ---');
  for (const slot of [1, 6, 12]) {
    const r = await page.evaluate(s => {
      const A = window.APP;
      A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = s;
      A.S.settings.slots.SFLEX = 0;
      const t0 = performance.now();
      A.recompute();
      const ms = performance.now() - t0;
      return {
        rollout: window.T.shape(A.R.sol.plan),
        greedy: window.T.shape(window.T.greedy()),
        ms: Math.round(ms),
      };
    }, slot);
    const R = r.rollout;
    ok(`slot ${slot}: no quarterback before round 3`, R.firstQBround >= 3,
      { firstQBround: R.firstQBround, picks: R.picks });
    ok(`slot ${slot}: a quarterback is still drafted in the startable range`,
      R.firstQBround !== null && R.firstQBround <= 10, R.firstQBround);
    ok(`slot ${slot}: at most two tight ends on the whole roster`, R.te <= 2,
      { te: R.te, picks: R.picks });
    ok(`slot ${slot}: at most two quarterbacks`, R.qb <= 2, { qb: R.qb, picks: R.picks });
    ok(`slot ${slot}: exactly one quarterback starts`, R.starterQB === 1, R.starterQB);
    ok(`slot ${slot}: K and DST are the last two picks`, R.lastTwo === 'DST,K', R.picks);
    // the rollout always has the greedy's own move among its candidates, so it
    // cannot come out behind on its own objective
    ok(`slot ${slot}: the rollout never loses to the plain greedy`,
      R.value >= r.greedy.value, { rollout: R.value, greedy: r.greedy.value });
    ok(`slot ${slot}: starters are no worse than the greedy's`,
      R.starterPts >= r.greedy.starterPts,
      { rollout: R.starterPts, greedy: r.greedy.starterPts });
    ok(`slot ${slot}: the whole recompute stays interactive`, r.ms < 400, r.ms);
  }

  // ================================================================= superflex
  console.log('\n--- the same board in a superflex league ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      // realistic 2QB board (24 starting quarterbacks in a 12-team room)
      const qbs = A.S.players.filter(p => p.pos === 'QB' && !p.out)
        .sort((a, b) => b.pts - a.pts);
      qbs.forEach((p, i) => { p.adp2 = +(8 + 4.7 * i).toFixed(1); });
      for (const p of A.S.players)
        if (p.pos !== 'QB' && p.adp != null) p.adp2 = +(p.adp * 1.3).toFixed(1);
      A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = 1;
      const out = {};
      for (const sf of [0, 1]) {
        A.S.settings.slots.SFLEX = sf;
        A.recompute();
        out['sf' + sf] = window.T.shape(A.R.sol.plan);
      }
      return out;
    });
    ok('superflex starts two quarterbacks', r.sf1.starterQB === 2, r.sf1.picks);
    ok('superflex still stops at three quarterbacks total', r.sf1.qb <= 3, r.sf1.picks);
    ok('superflex pulls the first quarterback forward',
      r.sf1.firstQBround < r.sf0.firstQBround,
      { sf: r.sf1.firstQBround, one: r.sf0.firstQBround });
    ok('superflex does not stack tight ends either', r.sf1.te <= 2, r.sf1.picks);
    ok('K and DST still go last in superflex', r.sf1.lastTwo === 'DST,K', r.sf1.picks);
  }

  // ============================================================== mid-draft
  console.log('\n--- resuming mid-draft with a quarterback and a tight end owned ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.slots.SFLEX = 0;
      A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = 6;
      A.recompute();
      // I own the QB1 and TE1 of the pool, plus a couple of picks elsewhere;
      // 40 other players are off the board
      const pool = A.M.rows.slice().sort((a, b) => b.rpts - a.rpts).map(r => r.p);
      const mine = [];
      for (const pos of ['QB', 'TE', 'RB', 'WR']) {
        const p = pool.find(p => p.pos === pos && !p.drafted);
        A.draftPlayer(p, 1, true); mine.push(p.name);
      }
      let gone = 0;
      for (const p of pool) {
        if (gone >= 40) break;
        if (p.drafted) continue;
        A.draftPlayer(p, 1, false); gone++;
      }
      A.recompute();
      const shape = window.T.shape(A.R.sol.plan);
      const owned = A.S.players.filter(p => p.drafted && p.drafted.mine);
      return {
        shape, mine,
        totalQB: owned.filter(p => p.pos === 'QB').length + shape.qb,
        totalTE: owned.filter(p => p.pos === 'TE').length + shape.te,
      };
    });
    ok('no third quarterback once one is owned', r.totalQB <= 2,
      { totalQB: r.totalQB, picks: r.shape.picks });
    ok('no third tight end once one is owned', r.totalTE <= 2,
      { totalTE: r.totalTE, picks: r.shape.picks });
    ok('K and DST are still deferred to the end', r.shape.lastTwo === 'DST,K',
      r.shape.picks);
  }

  // =========================================================== Strategy Lab
  console.log('\n--- Strategy Lab snake builds obey their rules and stay quick ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = 6;
      A.S.settings.slots.SFLEX = 0;
      for (const p of A.S.players) p.drafted = null;
      A.S.log = []; A.recompute();
      const T = A.S.settings.teams, out = {};
      const t0 = performance.now();
      for (const key of ['zeroRB', 'heroRB', 'waitQB', 'qb5', 'eliteTE', 'robustRB', 'wrHeavy', 'balanced']) {
        const sol = A.solveStrategySnake(key);
        out[key] = {
          rounds: sol.plan.map(s => `R${Math.ceil(s.n / T)}${s.r.p.pos}`),
          relaxed: sol.relaxed,
          te: sol.plan.filter(s => s.r.p.pos === 'TE').length,
        };
      }
      out.ms = Math.round(performance.now() - t0);
      return out;
    });
    ok('Zero RB drafts no running back before round 6',
      !r.zeroRB.rounds.some(x => /^R[1-5]RB$/.test(x)), r.zeroRB.rounds);
    ok('Wait on QB drafts no quarterback before round 8',
      !r.waitQB.rounds.some(x => /^R[1-7]QB$/.test(x)), r.waitQB.rounds);
    ok('$5 QB waits until round 11',
      !r.qb5.rounds.some(x => /^R([1-9]|10)QB$/.test(x)), r.qb5.rounds);
    ok('Hero RB takes its running back in round 1',
      r.heroRB.rounds[0] === 'R1RB', r.heroRB.rounds);
    ok('Elite TE gets its tight end by round 3',
      r.eliteTE.rounds.slice(0, 3).some(x => /TE$/.test(x)), r.eliteTE.rounds);
    ok('no build stacks tight ends',
      Object.keys(r).filter(k => k !== 'ms').every(k => r[k].te <= 2),
      Object.fromEntries(Object.keys(r).filter(k => k !== 'ms').map(k => [k, r[k].te])));
    ok('eight builds solve fast enough for the live panel', r.ms < 400, r.ms);
  }

  ok('no page errors', errs.length === 0, errs);
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exit(1);
  console.log('SNAKE PLAN TESTS PASSED');
})();
