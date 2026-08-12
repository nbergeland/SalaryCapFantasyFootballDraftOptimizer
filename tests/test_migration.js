/* Bundle migration + live refresh regression suite.
 *
 * The shipped index.html still carries the old 190-player snapshot, so this
 * suite fabricates a "tomorrow's build" copy of the page (a bigger, newer
 * bundle spliced between the same markers, exactly the way scripts/build_data.py
 * does it) and drives a returning user's saved state against it.
 *
 * playwright is not a dependency of this repo (it has no npm side), so run it
 * from wherever playwright is installed:
 *
 *   NODE_PATH=/path/to/node_modules CHROMIUM=/path/to/chrome \
 *     node tests/test_migration.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO = process.env.INDEX_HTML ||
  path.join(__dirname, '..', 'index.html');
const CHROMIUM = process.env.CHROMIUM ||
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const TMP = path.join(os.tmpdir(), 'berg-idx-newbundle.html');
const START = '/*__DATA__*/', END = '/*__END_DATA__*/';

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('PASS  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra ? '  ' + JSON.stringify(extra) : '')); }
};

// ---------------------------------------------------------------- fixtures
const html = fs.readFileSync(REPO, 'utf8');
const a = html.indexOf(START) + START.length, b = html.indexOf(END);
const OLD = JSON.parse(html.slice(a, b));

// Two old players are deliberately absent from the new build: one the user has
// marked (must be carried over) and one untouched (must simply disappear).
const DROP_MARKED = OLD.players.find(p => p.name === 'Josh Allen');
const DROP_CLEAN = OLD.players.filter(p => p.pos === 'WR').slice(-1)[0];

const FILLER_TEAMS = ['ARI', 'BUF', 'DAL', 'SEA', 'KC', 'PHI', 'DET', 'SF'];
const newPlayers = OLD.players
  .filter(p => p.name !== DROP_MARKED.name && p.name !== DROP_CLEAN.name)
  .map((p, i) => Object.assign({}, p, {
    aav: Math.max(1, p.aav + (i % 3) - 1),
    src: 'sleeper+espn+ffc',
    stats: p.pos === 'QB' ? { pass_yd: 4000, pass_td: 28, int: 10, rush_yd: 300, rush_td: 3 }
      : p.pos === 'DST' || p.pos === 'K' ? undefined
        : { rush_yd: 400, rush_td: 3, rec: 60, rec_yd: 700, rec_td: 5 },
    adp: i + 1,
    ecr: i + 2,
    bye: 5 + (i % 9),
  }));
// the repo bundle predating the data pipeline lacked Michael Wilson; the real
// builds carry him — either way the synthetic bundle must have exactly one
if (!newPlayers.some(p => p.name === 'Michael Wilson'))
  newPlayers.push({
    name: 'Michael Wilson', team: 'ARI', pos: 'WR', aav: 2, pts: 159.4,
    src: 'sleeper+espn+ffc', note: '', stats: { rec: 58, rec_yd: 720, rec_td: 5 },
    adp: 140.2, ecr: 155, bye: 8,
  });
for (let i = 0; newPlayers.length < 480; i++) {
  newPlayers.push({
    name: 'Depth Guy ' + i, team: FILLER_TEAMS[i % FILLER_TEAMS.length],
    pos: ['WR', 'RB', 'TE', 'QB'][i % 4], aav: 1, pts: 120 - i * 0.1,
    src: 'sleeper (aav est)', note: '', adp: 200 + i, ecr: 210 + i, bye: 5 + (i % 9),
    stats: { rec: 20, rec_yd: 240, rec_td: 1 },
  });
}
const NEW = {
  meta: {
    asOf: '2026-08-15', format: OLD.meta.format, built: 'scripts/build_data.py',
    sources: ['https://api.sleeper.app/v1/players/nfl', 'https://fantasyfootballcalculator.com/adp'],
    attribution: 'ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com).',
    degraded: [],
  },
  news: ['Puka Nacua (LAR WR) — Sleeper injury status: Questionable.'],
  players: newPlayers,
};
fs.writeFileSync(TMP, html.slice(0, a) + JSON.stringify(NEW) + html.slice(b), 'utf8');
console.log(`new bundle: ${NEW.players.length} players, asOf ${NEW.meta.asOf}`);

// a returning user: three drafted (one a keeper), a boost, a star, a DND
const MARKS = {};
MARKS[(DROP_MARKED.name + '|' + DROP_MARKED.pos).toLowerCase()] =
  { drafted: { price: 27, mine: true, keeper: true }, boost: 0, out: false, dnd: false, star: false, nom: false };
MARKS['bijan robinson|rb'] = { drafted: { price: 64, mine: true }, boost: 0, out: false, dnd: false, star: false, nom: false };
MARKS["ja'marr chase|wr"] = { drafted: { price: 58, mine: false }, boost: 0, out: false, dnd: false, star: false, nom: false };
MARKS['puka nacua|wr'] = { drafted: null, boost: 15, out: false, dnd: false, star: true, nom: false };
MARKS['trey mcbride|te'] = { drafted: null, boost: 0, out: false, dnd: true, star: false, nom: true };

function savedState(poolMeta, poolTransform) {
  const pool = OLD.players.map(p => Object.assign({}, p, {
    stats: null, floor: null, ceil: null, adp: null, ecr: null, bye: null,
    dnd: false, star: false, nom: false,
  })).map(poolTransform || (x => x));
  return {
    v: 2, activeId: 'lg-test', poolMeta,
    leagues: [{
      id: 'lg-test', name: 'My league', settings: null,
      log: [
        { id: (DROP_MARKED.name + '|' + DROP_MARKED.pos).toLowerCase(), name: DROP_MARKED.name, pos: DROP_MARKED.pos, price: 27, mine: true, n: 1 },
        { id: 'bijan robinson|rb', name: 'Bijan Robinson', pos: 'RB', price: 64, mine: true, n: 2 },
        { id: "ja'marr chase|wr", name: "Ja'Marr Chase", pos: 'WR', price: 58, mine: false, n: 3 },
      ],
      kpCands: [{ id: 'bijan robinson|rb', name: 'Bijan Robinson', pos: 'RB', price: 64 }],
      marks: MARKS,
    }],
    pool,
  };
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROMIUM });

  async function boot(state) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
    page.on('console', m => {
      if (m.type() === 'error' && !/Failed to load resource/.test(m.text()))
        errs.push('CONSOLE: ' + m.text());
    });
    await page.goto('file://' + TMP);
    await page.evaluate(s => {
      localStorage.clear();
      localStorage.setItem('sc-draft-companion-v2', JSON.stringify(s));
    }, state);
    await page.reload();
    await page.waitForTimeout(1200);
    return { ctx, page, errs };
  }

  // ================================================================= (1) adopt
  console.log('\n--- scenario 1: saved bundled pool meets a newer bundle ---');
  {
    const { ctx, page, errs } = await boot(savedState({
      valuesAsOf: OLD.meta.asOf, valuesSrc: 'bundled snapshot', ranksAsOf: null,
    }));

    const r = await page.evaluate(() => {
      const A = window.APP, S = A.S;
      const byId = id => S.players.find(p => A.playerId(p) === id) || null;
      return {
        size: S.players.length,
        oldSize: 190,
        poolMeta: JSON.parse(JSON.stringify(S.poolMeta)),
        migration: S.migration && S.migration.mode,
        carried: S.migration && S.migration.carried,
        michaelWilson: byId('michael wilson|wr'),
        keeper: byId('josh allen|qb'),
        bijan: byId('bijan robinson|rb'),
        chase: byId("ja'marr chase|wr"),
        puka: byId('puka nacua|wr'),
        mcbride: byId('trey mcbride|te'),
        droppedClean: byId('depth guy 0|wr') ? 'n/a' : null,
        log: S.log.map(l => l.id),
        kpCands: (S.kpCands || []).map(k => k.id || k.name),
        statsCount: S.players.filter(p => p.stats).length,
        adpCount: S.players.filter(p => p.adp != null).length,
        byeCount: S.players.filter(p => p.bye != null).length,
      };
    });

    ok('pool grew past 450', r.size >= 450, { size: r.size });
    ok('adopt path taken', r.migration === 'adopt', r.migration);
    ok('Michael Wilson is in the pool', !!r.michaelWilson);
    ok('Michael Wilson has team + pos', r.michaelWilson &&
      r.michaelWilson.team === 'ARI' && r.michaelWilson.pos === 'WR');
    ok('stats arrived for most of the pool', r.statsCount > 400, { statsCount: r.statsCount });
    ok('adp arrived for most of the pool', r.adpCount > 400, { adpCount: r.adpCount });
    ok('bye arrived for most of the pool', r.byeCount > 400, { byeCount: r.byeCount });

    ok('drafted keeper survived a name the new bundle dropped',
      !!r.keeper && !!r.keeper.drafted && r.keeper.drafted.keeper === true, r.keeper && r.keeper.drafted);
    ok('carried-over count reported', r.carried === 1, { carried: r.carried });
    ok('drafted (mine) preserved', r.bijan && r.bijan.drafted &&
      r.bijan.drafted.price === 64 && r.bijan.drafted.mine === true, r.bijan && r.bijan.drafted);
    ok('drafted (rival) preserved', r.chase && r.chase.drafted &&
      r.chase.drafted.price === 58 && r.chase.drafted.mine === false, r.chase && r.chase.drafted);
    ok('boost + star preserved', r.puka && r.puka.boost === 15 && r.puka.star === true,
      r.puka && { boost: r.puka.boost, star: r.puka.star });
    ok('dnd + nom preserved', r.mcbride && r.mcbride.dnd === true && r.mcbride.nom === true,
      r.mcbride && { dnd: r.mcbride.dnd, nom: r.mcbride.nom });
    ok('draft log intact (3 entries)', r.log.length === 3, r.log);
    ok('every log entry still resolves to a pooled player', await page.evaluate(() =>
      window.APP.S.log.every(l => window.APP.S.players.some(p => window.APP.playerId(p) === l.id))));
    ok('keeper candidates intact', r.kpCands.length === 1, r.kpCands);

    ok('poolMeta.valuesAsOf advanced', r.poolMeta.valuesAsOf === '2026-08-15', r.poolMeta);
    ok('poolMeta.valuesSrc still bundled', r.poolMeta.valuesSrc === 'bundled snapshot');
    ok('poolMeta.bundleMergedAsOf stamped', r.poolMeta.bundleMergedAsOf === '2026-08-15');

    // the migration must be persisted, and must not run a second time
    await page.reload();
    await page.waitForTimeout(1200);
    const again = await page.evaluate(() => ({
      size: window.APP.S.players.length,
      migration: window.APP.S.migration,
      drafted: window.APP.S.players.filter(p => p.drafted).length,
    }));
    ok('migration persisted across reload', again.size >= 450, again);
    ok('migration is idempotent (no second run)', again.migration === null, again.migration);
    ok('drafted picks still there after reload', again.drafted === 3, again);

    // the header + data tab must own up to the new pool
    await page.locator('nav.tabs button[data-tab="data"]').click();
    await page.waitForTimeout(300);
    const meta = await page.locator('#dataMeta').textContent();
    const srcs = await page.locator('#dataSources').textContent();
    ok('data tab reports the new pool size', meta.includes(String(again.size)), meta.slice(0, 120));
    ok('data tab shows provenance', /dollar values come straight from a source/.test(meta));
    ok('FFC attribution rendered', /Fantasy Football Calculator/.test(srcs), srcs.slice(0, 120));

    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  // ============================================================== (2) enrich
  console.log('\n--- scenario 2: imported values must survive the merge ---');
  {
    const { ctx, page, errs } = await boot(savedState(
      { valuesAsOf: '2026-08-01', valuesSrc: 'imported file', ranksAsOf: null },
      p => Object.assign({}, p, { aav: 99, pts: 111, src: 'my sheet' })));

    const r = await page.evaluate(() => {
      const A = window.APP, S = A.S;
      const byId = id => S.players.find(p => A.playerId(p) === id) || null;
      const mine = S.players.filter(p => p.src === 'my sheet');
      return {
        size: S.players.length,
        migration: S.migration,
        poolMeta: JSON.parse(JSON.stringify(S.poolMeta)),
        importedUntouched: mine.every(p => p.aav === 99 && p.pts === 111),
        importedCount: mine.length,
        importedEnriched: mine.filter(p => p.adp != null && p.bye != null).length,
        importedGotStats: mine.filter(p => p.stats).length,
        michaelWilson: byId('michael wilson|wr'),
        bijan: byId('bijan robinson|rb'),
        puka: byId('puka nacua|wr'),
      };
    });

    ok('enrich path taken', r.migration && r.migration.mode === 'enrich', r.migration);
    ok('pool grew by appending the bundle', r.size >= 450, { size: r.size });
    ok('imported aav/pts untouched', r.importedUntouched === true,
      { count: r.importedCount, bijan: r.bijan && { aav: r.bijan.aav, pts: r.bijan.pts } });
    ok('imported rows enriched with adp + bye', r.importedEnriched > 150,
      { enriched: r.importedEnriched, of: r.importedCount });
    ok('imported rows given stats they lacked', r.importedGotStats > 150,
      { stats: r.importedGotStats });
    ok('Michael Wilson appended', !!r.michaelWilson);
    ok('marks survived the enrich path', r.puka && r.puka.boost === 15 && r.puka.star === true);
    ok('valuesSrc still says imported', r.poolMeta.valuesSrc === 'imported file', r.poolMeta);
    ok('valuesAsOf not overwritten by the bundle', r.poolMeta.valuesAsOf === '2026-08-01', r.poolMeta);
    ok('bundleMergedAsOf stamped', r.poolMeta.bundleMergedAsOf === '2026-08-15', r.poolMeta);

    await page.reload();
    await page.waitForTimeout(1200);
    const again = await page.evaluate(() => ({
      migration: window.APP.S.migration,
      size: window.APP.S.players.length,
      stillMine: window.APP.S.players.filter(p => p.aav === 99 && p.pts === 111).length,
    }));
    ok('enrich is idempotent', again.migration === null, again.migration);
    ok('no duplicate append on reload', again.size === r.size, again);
    ok('imported values still intact after reload', again.stillMine === r.importedCount, again);

    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  // ================================================ (3) reload-bundle button
  console.log('\n--- scenario 3: "Reload bundled data" two-click confirm ---');
  {
    const { ctx, page, errs } = await boot(savedState(
      { valuesAsOf: '2026-08-01', valuesSrc: 'imported file', ranksAsOf: null },
      p => Object.assign({}, p, { aav: 99, pts: 111, src: 'my sheet' })));

    await page.locator('nav.tabs button[data-tab="data"]').click();
    await page.waitForTimeout(300);
    const btn = page.locator('#reloadBundleBtn');
    ok('button present in Data & News', await btn.count() === 1);

    const before = await page.evaluate(() => window.APP.S.players.filter(p => p.aav === 99).length);
    await btn.click();                              // first click only arms it
    await page.waitForTimeout(200);
    ok('first click arms rather than acts', /Sure\?/.test(await btn.textContent()));
    const mid = await page.evaluate(() => window.APP.S.players.filter(p => p.aav === 99).length);
    ok('nothing replaced on the first click', mid === before, { before, mid });

    await btn.click();                              // second click commits
    await page.waitForTimeout(800);
    const after = await page.evaluate(() => ({
      label: document.querySelector('#reloadBundleBtn').textContent,
      imported: window.APP.S.players.filter(p => p.aav === 99).length,
      size: window.APP.S.players.length,
      valuesSrc: window.APP.S.poolMeta.valuesSrc,
      drafted: window.APP.S.players.filter(p => p.drafted).length,
      puka: window.APP.S.players.find(p => window.APP.playerId(p) === 'puka nacua|wr'),
    }));
    ok('button label reset after acting', after.label === 'Reload bundled data', after.label);
    // exactly one survivor is correct: the drafted keeper the new bundle no
    // longer lists is carried over verbatim, imported price and all
    ok('imported values replaced by the bundle', after.imported === 1, after);
    ok('pool is the bundle', after.size >= 450, after);
    ok('valuesSrc back to bundled snapshot', after.valuesSrc === 'bundled snapshot', after);
    ok('draft survived the forced reload', after.drafted === 3, after);
    ok('marks survived the forced reload', after.puka && after.puka.boost === 15 && after.puka.star === true);

    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  // ============================================== (4) live ↻ refresh sources
  console.log('\n--- scenario 4: ↻ refresh blends three sources independently ---');
  {
    const { ctx, page, errs } = await boot(savedState({
      valuesAsOf: OLD.meta.asOf, valuesSrc: 'bundled snapshot', ranksAsOf: null,
    }));

    await ctx.route('**/api.sleeper.app/v1/players/nfl', r => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        1: { full_name: "Ja'Marr Chase", position: 'WR', team: 'CIN', search_rank: 1 },
        2: { full_name: 'Michael Wilson', position: 'WR', team: 'ARI', search_rank: 168, injury_status: 'Questionable' },
      }),
    }));
    await ctx.route('**/api.sleeper.com/projections/**', r => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify([
        {
          player_id: '9227', team: 'ARI',
          player: { first_name: 'Michael', last_name: 'Wilson', position: 'WR', team: 'ARI' },
          stats: { rec: 66, rec_yd: 815, rec_td: 6, pts_ppr: 181.5, adp_ppr: 121.0 },
        },
        {
          player_id: '99991', team: 'TB',
          player: { first_name: 'Rookie', last_name: 'Newname', position: 'WR', team: 'TB' },
          stats: { rec: 70, rec_yd: 900, rec_td: 6, pts_ppr: 196.0, adp_ppr: 92.0 },
        },
        {
          player_id: '99992', team: 'NYJ',
          player: { first_name: 'Way', last_name: 'Toodeep', position: 'WR', team: 'NYJ' },
          stats: { rec: 5, rec_yd: 60, pts_ppr: 12.0, adp_ppr: 460.0 },
        },
      ]),
    }));
    await ctx.route('**/fantasyfootballcalculator.com/**', r => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        players: [{ name: 'Michael Wilson', position: 'WR', team: 'ARI', adp: 131.0, bye: 8 }],
      }),
    }));

    await page.locator('#refreshBtn').click();
    await page.waitForTimeout(2500);

    const r = await page.evaluate(() => {
      const S = window.APP.S;
      const mw = S.players.find(p => window.APP.playerId(p) === 'michael wilson|wr');
      return {
        mw, poolMeta: JSON.parse(JSON.stringify(S.poolMeta)),
        newcomer: S.players.find(p => p.name === 'Rookie Newname') || null,
        toodeep: S.players.find(p => p.name === 'Way Toodeep') || null,
        toast: (document.querySelector('#toast') || {}).textContent || '',
      };
    });
    ok('projection pts applied to a bundled player', r.mw && r.mw.pts === 181.5, r.mw && r.mw.pts);
    ok('projection stats applied', r.mw && r.mw.stats && r.mw.stats.rec === 66, r.mw && r.mw.stats);
    ok('adp is the blend of Sleeper and FFC', r.mw && r.mw.adp === 126, r.mw && r.mw.adp);
    ok('FFC bye applied', r.mw && r.mw.bye === 8, r.mw && r.mw.bye);
    ok('injury note applied from the players pull', r.mw && /Questionable/.test(r.mw.note || ''), r.mw && r.mw.note);
    ok('missing draftable player appended at $1', r.newcomer && r.newcomer.aav === 1 &&
      r.newcomer.src === 'sleeper live', r.newcomer);
    ok('undraftable ADP not appended', r.toodeep === null || r.toodeep === undefined);
    ok('liveRefreshedAsOf stamped', !!r.poolMeta.liveRefreshedAsOf, r.poolMeta);
    ok('ranksAsOf stamped', !!r.poolMeta.ranksAsOf, r.poolMeta);
    ok('button re-enabled', await page.locator('#refreshBtn').isEnabled());

    // one source down must not cost the others
    await ctx.unroute('**/fantasyfootballcalculator.com/**');
    await ctx.route('**/fantasyfootballcalculator.com/**', r => r.abort());
    await page.locator('#refreshBtn').click();
    await page.waitForTimeout(2500);
    const partial = await page.evaluate(() =>
      (document.querySelector('#toast') || {}).textContent || '');
    ok('partial failure reported per-source', /unavailable/.test(partial) && /Refreshed/.test(partial), partial);
    ok('button re-enabled after partial failure', await page.locator('#refreshBtn').isEnabled());

    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  // ====================================================== (5) suffix renames
  // The data builds carry Sleeper-canonical names, which drop Jr./III/'
  // suffixes the old curated pool kept. A drafted "Marvin Harrison Jr." must
  // become the bundle's "Marvin Harrison" — mark, log entry and all — not a
  // duplicate row sitting next to him.
  console.log('\n--- scenario 5: marks and logs follow a suffix rename ---');
  {
    const renamedOld = 'Michael Wilson Jr.';           // old pool spelling
    const state = savedState(
      { valuesAsOf: OLD.meta.asOf, valuesSrc: 'bundled snapshot', ranksAsOf: null },
      p => p.name === 'Michael Wilson' ? Object.assign({}, p, { name: renamedOld }) : p);
    // …but our synthetic saved pool may not contain Michael Wilson (old bundles
    // predate him) — ensure the old row exists, marked and drafted
    if (!state.pool.some(p => p.name === renamedOld))
      state.pool.push({ name: renamedOld, team: 'ARI', pos: 'WR', aav: 2, pts: 140,
        src: 'est', note: '', stats: null, floor: null, ceil: null, adp: null,
        ecr: null, bye: null, dnd: false, star: false, nom: false });
    state.leagues[0].marks[renamedOld.toLowerCase() + '|wr'] =
      { drafted: { price: 7, mine: true }, boost: 5, out: false, dnd: false, star: true, nom: false };
    state.leagues[0].log.push({ id: renamedOld.toLowerCase() + '|wr', name: renamedOld,
      pos: 'WR', price: 7, mine: true, n: 4 });

    const { ctx, page, errs } = await boot(state);
    const r = await page.evaluate(() => {
      const A = window.APP, S = A.S;
      return {
        renamedCount: S.migration && S.migration.renamed,
        dupes: S.players.filter(p => /michael wilson/i.test(p.name)).map(p => p.name),
        mw: S.players.find(p => A.playerId(p) === 'michael wilson|wr') || null,
        logIds: S.log.map(l => l.id),
        logResolves: S.log.every(l => S.players.some(p => A.playerId(p) === l.id)),
      };
    });
    ok('rename detected and counted', r.renamedCount >= 1, r.renamedCount);
    ok('no duplicate row for the renamed player', r.dupes.length === 1, r.dupes);
    ok('drafted state followed the rename', r.mw && r.mw.drafted && r.mw.drafted.price === 7,
      r.mw && r.mw.drafted);
    ok('boost + star followed the rename', r.mw && r.mw.boost === 5 && r.mw.star === true,
      r.mw && { boost: r.mw.boost, star: r.mw.star });
    ok('log id remapped to the new spelling', r.logIds.includes('michael wilson|wr'), r.logIds);
    ok('every log entry resolves after remap', r.logResolves, r.logIds);
    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exit(1);
  console.log('MIGRATION TESTS PASSED');
})();
