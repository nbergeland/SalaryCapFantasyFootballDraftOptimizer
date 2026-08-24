/* End-to-end bridge pipeline: postMessage an ESPN league payload into the
 * receiver exactly as the bookmarklet does — teams populate, picking my team
 * applies picks live, a second message lands incremental picks, settings
 * import once, and the private-league 401 fallback path spotlights. */
const { chromium } = require('playwright');
const path = require('path');

const INDEX = process.env.INDEX_HTML ||
  path.join(__dirname, '..', 'index.html');
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
  await page.goto('file://' + INDEX);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForTimeout(1200);

  const r = await page.evaluate(() => {
    const A = window.APP;
    A.S.settings.mode = 'auction';
    A.recompute();
    // build an ESPN league payload from real pool players (ES_POS: QB=1,RB=2,WR=3,TE=4)
    const posId = { QB: 1, RB: 2, WR: 3, TE: 4 };
    const pick = (pos, i) => A.M.rows.filter(x => x.p.pos === pos && !x.p.out)
      .sort((a, b) => b.rpts - a.rpts)[i].p;
    const roster = names => ({ entries: names.map((p, i) => ({
      playerPoolEntry: { player: { id: 1000 + posId[p.pos] * 100 + i * 10 +
        (p.name.length % 10), fullName: p.name, defaultPositionId: posId[p.pos] } } })) });
    const t1 = [pick('RB', 0), pick('WR', 0)];
    const t2 = [pick('RB', 1), pick('WR', 1)];
    // stable ids
    let nid = 5000; const idOf = new Map();
    const entry = p => { if (!idOf.has(p)) idOf.set(p, ++nid);
      return { playerPoolEntry: { player: { id: idOf.get(p), fullName: p.name,
        defaultPositionId: posId[p.pos] } } }; };
    const payload = {
      settings: { draftSettings: { type: 'AUCTION', auctionBudget: 200 },
        rosterSettings: { lineupSlotCounts: { 0: 1, 2: 2, 4: 2, 6: 1, 23: 1, 7: 0, 17: 1, 16: 1, 20: 6 } } },
      teams: [
        { id: 1, name: 'Berg Dynasty', roster: { entries: t1.map(entry) } },
        { id: 2, name: 'Rival Sharks', roster: { entries: t2.map(entry) } },
      ],
      draftDetail: { picks: [
        { playerId: idOf.get(t1[0]), teamId: 1, bidAmount: 55 },
        { playerId: idOf.get(t1[1]), teamId: 1, bidAmount: 48 },
        { playerId: idOf.get(t2[0]), teamId: 2, bidAmount: 52 },
      ] },
    };
    window.postMessage({ bergsheets: 'espn', data: payload }, '*');
    return new Promise(res => setTimeout(() => {
      const sel = document.getElementById('esMyTeam');
      const teams = [...sel.options].map(o => o.textContent);
      const statusBefore = document.getElementById('esStatus').textContent;
      // choose my team → pending picks apply
      sel.value = '1'; sel.dispatchEvent(new Event('change'));
      setTimeout(() => {
        const drafted1 = A.S.players.filter(p => p.drafted);
        const mine1 = drafted1.filter(p => p.drafted.mine).map(p => p.name);
        const by1 = drafted1.map(p => p.drafted.by);
        // second bridge message: one more rival pick arrives
        payload.teams[1].roster.entries.push(entry(t2[1]));
        payload.draftDetail.picks.push({ playerId: idOf.get(t2[1]), teamId: 2, bidAmount: 44 });
        window.postMessage({ bergsheets: 'espn', data: payload }, '*');
        setTimeout(() => {
          const drafted2 = A.S.players.filter(p => p.drafted);
          const status = document.getElementById('esStatus').textContent;
          const review = A.reviewData();
          res({
            teams, statusBefore,
            applied1: drafted1.length, mine1, by1,
            applied2: drafted2.length,
            budget: A.S.settings.cap, slots: { ...A.S.settings.slots },
            price: drafted2.find(p => p.name === (t2[1] || {}).name)?.drafted?.price,
            status,
            reviewTeams: review ? review.ranked.map(t => t.label).sort() : [],
          });
        }, 300);
      }, 300);
    }, 300));
  });

  ok('bridge payload populates the team picker',
    r.teams.join('|').includes('Berg Dynasty') && r.teams.join('|').includes('Rival Sharks'), r.teams);
  ok('waits for a team pick before applying', /Select your team/.test(r.statusBefore), r.statusBefore);
  ok('choosing my team applies all seen picks', r.applied1 === 3, r.applied1);
  ok('my picks are mine', r.mine1.length === 2, r.mine1);
  ok('rival picks carry the team name', r.by1.filter(b => b === 'Rival Sharks').length >= 1, r.by1);
  ok('a later bridge message lands only the new pick', r.applied2 === 4, r.applied2);
  ok('auction price rides along', r.price === 44, r.price);
  ok('league settings imported once (budget 200, 2 RB)',
    r.budget === 200 && r.slots.RB === 2, { budget: r.budget, slots: r.slots });
  ok('status shows the live-sync stamp', /Live sync ✓/.test(r.status), r.status);
  ok('review then buckets by ESPN team names',
    r.reviewTeams.includes('You') && r.reviewTeams.includes('Rival Sharks'), r.reviewTeams);

  // multi-tab rebroadcast: a payload arriving on the BroadcastChannel (as
  // rebroadcast by whichever window the bookmarklet targeted) applies here too
  const bc = await page.evaluate(() => {
    const A = window.APP;
    for (const p of A.S.players) p.drafted = null;
    A.S.log = []; A.recompute();
    const posId = { QB: 1, RB: 2, WR: 3, TE: 4 };
    const p1 = A.M.rows.filter(x => x.p.pos === 'RB' && !x.p.out)
      .sort((a, b) => b.rpts - a.rpts)[0].p;
    const payload = {
      teams: [{ id: 1, name: 'BC Team', roster: { entries: [{ playerPoolEntry:
        { player: { id: 7001, fullName: p1.name, defaultPositionId: posId[p1.pos] } } }] } }],
      draftDetail: { picks: [{ playerId: 7001, teamId: 1, bidAmount: 31 }] },
    };
    return new Promise(res => {
      try { new BroadcastChannel('bergsheets-bridge').postMessage(
        { bergsheets: 'espn', data: payload }); }
      catch (e) { res({ bcUnsupported: true }); return; }
      setTimeout(() => {
        const sel = document.getElementById('esMyTeam');
        sel.value = '1'; sel.dispatchEvent(new Event('change'));
        setTimeout(() => res({
          teams: [...sel.options].map(o => o.textContent),
          applied: A.S.players.filter(p => p.drafted).length,
        }), 250);
      }, 250);
    });
  });
  if (bc.bcUnsupported) ok('BroadcastChannel unsupported here — skipped', true);
  else {
    ok('a channel payload populates this tab too', bc.teams.includes('BC Team'), bc.teams);
    ok('and its picks apply here', bc.applied === 1, bc.applied);
  }

  // the no-bookmark console variant
  const nb = await page.evaluate(() => ({
    fn: typeof window.APP.bridgeScript === 'function',
    // file:// can't build the hosted script — it must refuse, not crash
    nullOffline: window.APP.bridgeScript('espn') === null,
    button: !!document.getElementById('esBridgeCopy'),
  }));
  ok('bridgeScript exists and refuses off the hosted site', nb.fn && nb.nullOffline, nb);
  ok('the copy-console button is present', nb.button);

  // the 401 spotlight path (fetch stubbed to a private-league answer)
  const s = await page.evaluate(async () => {
    document.getElementById('esLeague').value = '30578399';
    const orig = window.fetch;
    window.fetch = () => Promise.resolve({ ok: false, status: 401 });
    const out = await window.APP.espnFetchNow();
    window.fetch = orig;
    return { out, status: document.getElementById('esStatus').textContent };
  });
  ok('a 401 explains both real fixes', /Viewable to Public/.test(s.status) &&
    /bridge/.test(s.status), s.status.slice(0, 120));
  ok('espnFetchNow reports failure honestly', s.out === false);

  ok('no page errors', errs.length === 0, errs);
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exit(1);
  console.log('BRIDGE PIPELINE TESTS PASSED');
})();
