/* Hard positional caps + post-draft league review + next-pick options +
 * ESPN league-ID sync wiring.
 *
 * The caps sections pin the "one QB/TE/K/DST, ever" rule at every surface
 * (completion, max bids, snake plan) including the superflex exception;
 * the review sections reconstruct rosters from snake pick order and from
 * synced-league team labels; the next-picks sections check that three
 * distinct, full-plan-scored options come back in both modes.
 *
 *   NODE_PATH=/path/to/node_modules CHROMIUM=/path/to/chrome \
 *     node tests/test_caps_review.js
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

  // ---------------- auction: hard caps ----------------
  console.log('\n--- auction hard caps ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.mode = 'auction'; A.S.settings.slots.SFLEX = 0;
      A.recompute();
      const cap = { QB: A.posCap('QB'), TE: A.posCap('TE'), K: A.posCap('K'),
        DST: A.posCap('DST'), RB: A.posCap('RB') };
      // buy the top TE and top QB at market
      const byPos = pos => A.M.rows.filter(x => x.p.pos === pos && !x.p.drafted && !x.p.out)
        .sort((a, b) => b.rpts - a.rpts);
      const te1 = byPos('TE')[0], qb1 = byPos('QB')[0];
      A.draftPlayer(te1.p, Math.max(1, Math.round(te1.adj)), true);
      A.draftPlayer(qb1.p, Math.max(1, Math.round(qb1.adj)), true);
      const chosen = A.R.sol ? A.R.sol.chosen.map(x => x.p.pos) : [];
      const teBids = byPos('TE').slice(0, 12).map(x => A.R.bids.get(A.playerId(x.p)) ?? null);
      const qbBids = byPos('QB').slice(0, 12).map(x => A.R.bids.get(A.playerId(x.p)) ?? null);
      const rbBids = byPos('RB').slice(0, 5).map(x => A.R.bids.get(A.playerId(x.p)) ?? null);
      return { cap, chosen, teBids, qbBids, rbBids,
        teInPlan: chosen.filter(p => p === 'TE').length,
        qbInPlan: chosen.filter(p => p === 'QB').length };
    });
    ok('caps are 1 for QB/TE/K/DST, unlimited RB',
      r.cap.QB === 1 && r.cap.TE === 1 && r.cap.K === 1 && r.cap.DST === 1 &&
      r.cap.RB === Infinity || r.cap.RB === null, r.cap);
    ok('optimal completion adds no second TE', r.teInPlan === 0, r.chosen);
    ok('optimal completion adds no second QB', r.qbInPlan === 0, r.chosen);
    ok('every remaining TE is a $0 pass', r.teBids.every(b => b === 0), r.teBids);
    ok('every remaining QB is a $0 pass', r.qbBids.every(b => b === 0), r.qbBids);
    ok('RBs still get real bids', r.rbBids.some(b => b > 0), r.rbBids);
  }

  // ---------------- superflex exception ----------------
  console.log('\n--- superflex: second QB still allowed ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      for (const p of A.S.players) p.drafted = null;
      A.S.log = [];
      A.S.settings.slots.SFLEX = 1;
      A.recompute();
      const cap = A.posCap('QB');
      const byPos = pos => A.M.rows.filter(x => x.p.pos === pos && !x.p.drafted && !x.p.out)
        .sort((a, b) => b.rpts - a.rpts);
      const qb1 = byPos('QB')[0];
      A.draftPlayer(qb1.p, Math.max(1, Math.round(qb1.adj)), true);
      const qbBids = byPos('QB').slice(0, 8).map(x => A.R.bids.get(A.playerId(x.p)) ?? null);
      // now buy a second QB — the third must be a pass
      const qb2 = byPos('QB')[0];
      A.draftPlayer(qb2.p, Math.max(1, Math.round(qb2.adj)), true);
      const qb3Bids = byPos('QB').slice(0, 8).map(x => A.R.bids.get(A.playerId(x.p)) ?? null);
      A.S.settings.slots.SFLEX = 0;
      for (const p of A.S.players) p.drafted = null;
      A.S.log = []; A.recompute();
      return { cap, qbBids, qb3Bids };
    });
    ok('superflex QB cap is 2', r.cap === 2, r.cap);
    ok('a second QB still gets bids in superflex', r.qbBids.some(b => b > 0), r.qbBids);
    ok('a third QB is a pass even in superflex', r.qb3Bids.every(b => b === 0), r.qb3Bids);
  }

  // ---------------- snake review: teams from pick order ----------------
  console.log('\n--- snake draft + league review ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = 3;
      A.recompute();
      const T = A.S.settings.teams;
      const rounds = Object.values(A.S.settings.slots).reduce((a, b) => a + b, 0)
        + A.S.settings.bench;
      const total = T * rounds;
      // script a full snake draft straight off the projections board
      const board = A.M.rows.slice().sort((a, b) => b.rpts - a.rpts).map(x => x.p);
      let bi = 0;
      const my = new Set(A.myPickNumbers());
      for (let n = 1; n <= total && bi < board.length; n++) {
        while (bi < board.length && board[bi].drafted) bi++;
        if (bi >= board.length) break;
        A.applyPick(board[bi], 1, my.has(n));
      }
      A.recompute();
      const d = A.reviewData();
      return {
        teams: d ? d.ranked.length : 0,
        labels: d ? d.ranked.map(t => t.label).slice(0, 4) : [],
        meRank: d && d.me ? d.me.rank : null,
        meStarters: d && d.me ? d.me.starters : 0,
        simOk: d ? d.ranked.every(t => t.sim && t.sim.p50 > 0 &&
          t.sim.p10 <= t.sim.p50 && t.sim.p50 <= t.sim.p90) : false,
        pooled: d ? !!d.pooled : null,
      };
    });
    ok('review finds every snake team', r.teams === 12, r.teams);
    ok('my team is ranked', r.meRank >= 1 && r.meRank <= 12, r.meRank);
    ok('rosters simulate (p10<=p50<=p90)', r.simOk);
    ok('slot labels name the rivals', r.labels.some(l => /^Slot \d+$/.test(l)), r.labels);
    ok('nothing pooled in a snake review', r.pooled === false, r.pooled);
    ok('my starters project > 0', r.meStarters > 0, r.meStarters);
  }

  // ---------------- review renders ----------------
  {
    const r = await page.evaluate(() => {
      window.APP.showTab('review');
      const el = document.getElementById('review');
      return { html: el ? el.innerHTML.slice(0, 200) : null,
        hasTable: !!el.querySelector('table'),
        hasRank: /ranks\s*#\d+/.test(el.textContent) };
    });
    ok('review tab renders a standings table', r.hasTable, r.html);
    ok('review names my rank', r.hasRank, r.html);
  }

  // ---------------- auction attribution via applyExternalPicks(by) ----------------
  console.log('\n--- synced auction review with team names ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      for (const p of A.S.players) p.drafted = null;
      A.S.log = []; A.S.settings.mode = 'auction';
      A.recompute();
      const board = A.M.rows.slice().sort((a, b) => b.rpts - a.rpts);
      const names = ['Berg', 'Riva1', 'Riva2', 'Riva3'];
      const picks = board.slice(0, 40).map((x, i) => ({
        name: x.p.name, pos: x.p.pos, team: x.p.team,
        price: Math.max(1, Math.round(x.adj)),
        mine: i % 4 === 0, by: names[i % 4],
      }));
      const res = A.applyExternalPicks(picks);
      const d = A.reviewData();
      return {
        applied: res.applied,
        teams: d ? d.ranked.map(t => t.label).sort() : [],
        meLabel: d && d.me ? d.me.label : null,
        deals: d ? d.deals.length : 0,
        logBy: A.S.log.slice(0, 4).map(e => e.by),
      };
    });
    ok('external picks applied', r.applied >= 30, r.applied);
    ok('review buckets by platform team name',
      r.teams.length === 4 && r.teams.includes('You') && r.teams.includes('Riva2'), r.teams);
    ok('my picks land on "You"', r.meLabel === 'You', r.meLabel);
    ok('log entries carry the by label', r.logBy.every(b => typeof b === 'string'), r.logBy);
  }

  // ---------------- suggested next picks ----------------
  console.log('\n--- suggested next picks (3 options) ---');
  {
    const r = await page.evaluate(() => {
      const A = window.APP;
      // auction: fresh board, the plan's top targets
      for (const p of A.S.players) p.drafted = null;
      A.S.log = []; A.S.settings.mode = 'auction';
      A.recompute();
      const au = A.auctionNextOptions(3).map(o => ({ pos: o.r.p.pos, bid: o.bid }));
      const auHtml = (document.getElementById('nextPicks') || {}).innerHTML || '';
      // snake: fresh board, three scored options
      for (const p of A.S.players) p.drafted = null;
      A.S.log = []; A.S.settings.mode = 'snake'; A.S.settings.snakeSlot = 5;
      A.recompute();
      const sn = A.snakeNextOptions(3).map(o => ({ pos: o.r.p.pos, role: o.role,
        lose: o.lose, val: Math.round(o.val) }));
      const snHtml = (document.getElementById('nextPicks') || {}).innerHTML || '';
      return { au, sn, auHad3: au.length === 3, snHad3: sn.length === 3,
        snSorted: sn.every((o, i) => i === 0 ? o.lose === 0 : o.lose >= sn[i - 1].lose),
        snDistinct: new Set(sn.map(o => o.pos + o.role)).size >= 2,
        rendered: /plan/.test(snHtml) };
    });
    ok('auction offers 3 targets', r.auHad3, r.au);
    ok('snake offers 3 options', r.snHad3, r.sn);
    ok('options are ranked by full-plan value', r.snSorted, r.sn);
    ok('options are genuinely different lines', r.snDistinct, r.sn);
    ok('the panel renders with a plan badge', r.rendered);
  }

  // ---------------- ESPN wiring exists ----------------
  {
    const r = await page.evaluate(() => ({
      hasConnect: !!document.getElementById('esConnect'),
      hasAuto: !!document.getElementById('esAuto'),
      fn: typeof window.APP.espnFetchNow === 'function' &&
          typeof window.APP.espnAutoToggle === 'function',
      urlOk: (() => { document.getElementById('esLeague').value = '123456';
        return window.APP.espnUrl().includes('/leagues/123456?view=mDraftDetail'); })(),
    }));
    ok('ESPN connect + auto-sync buttons exist', r.hasConnect && r.hasAuto, r);
    ok('espnFetchNow/espnAutoToggle are wired', r.fn);
    ok('espnUrl builds from the league id', r.urlOk);
  }

  ok('no page errors', errs.length === 0, errs);
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exit(1);
  console.log('CAPS+REVIEW+ESPN TESTS PASSED');
})();
