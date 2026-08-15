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
const TMP_INJ = path.join(os.tmpdir(), 'berg-idx-injury.html');
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

// The repo bundle's asOf advances with every real data build, so synthetic
// "newer" bundles must be dated relative to it — a hardcoded date silently
// stops being newer the day a real build catches up to it (which is exactly
// what happened when the first injury build landed with today's date).
const dayAfter = (iso, n) => {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
const ASOF_NEW = dayAfter(OLD.meta.asOf, 1);
const ASOF_NEWER = dayAfter(OLD.meta.asOf, 2);

// Two old players are deliberately absent from the new build: one the user has
// marked (must be carried over) and one untouched (must simply disappear).
const DROP_MARKED = OLD.players.find(p => p.name === 'Josh Allen');
const DROP_CLEAN = OLD.players.filter(p => p.pos === 'WR').slice(-1)[0];

const FILLER_TEAMS = ['ARI', 'BUF', 'DAL', 'SEA', 'KC', 'PHI', 'DET', 'SF'];
const newPlayers = OLD.players
  .filter(p => p.name !== DROP_MARKED.name && p.name !== DROP_CLEAN.name)
  // strip the real bundle's own out flags — each scenario plants exactly the
  // OUT population it wants to reason about
  .map(({ out, outData, ...p }) => p)
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
    asOf: ASOF_NEW, format: OLD.meta.format, built: 'scripts/build_data.py',
    sources: ['https://api.sleeper.app/v1/players/nfl', 'https://fantasyfootballcalculator.com/adp'],
    attribution: 'ADP data courtesy of Fantasy Football Calculator (fantasyfootballcalculator.com).',
    degraded: [],
  },
  news: ['Puka Nacua (LAR WR) — Sleeper injury status: Questionable.'],
  players: newPlayers,
};
const writeBundle = (file, bundle) =>
  fs.writeFileSync(file, html.slice(0, a) + JSON.stringify(bundle) + html.slice(b), 'utf8');
writeBundle(TMP, NEW);
console.log(`new bundle: ${NEW.players.length} players, asOf ${NEW.meta.asOf}`);

// ---- the injury bundle: same build, plus players the data rules out --------
// Both are cheap at their price and would otherwise be recommended, which is
// exactly the Ricky Pearsall failure this feature exists to stop.
const INJ_STAR = {
  name: 'Injured Star', team: 'SF', pos: 'WR', aav: 55, pts: 305, out: true,
  src: 'sleeper+espn+ffc', note: 'Sleeper: IR (Knee) — placed on IR in August',
  stats: { rec: 92, rec_yd: 1240, rec_td: 9 }, adp: 12, ecr: 12, bye: 9,
};
const INJ_OVERRIDE = {
  name: 'Override Guy', team: 'KC', pos: 'WR', aav: 30, pts: 250, out: true,
  src: 'sleeper+espn+ffc', note: 'Sleeper: Out (Hamstring)',
  stats: { rec: 78, rec_yd: 980, rec_td: 7 }, adp: 40, ecr: 40, bye: 6,
};
const INJ_FRESH = {
  name: 'Fresh Casualty', team: 'DET', pos: 'RB', aav: 25, pts: 230, out: true,
  src: 'sleeper+espn+ffc', note: 'Sleeper: Out (Achilles)',
  stats: { rush_yd: 900, rush_td: 8, rec: 30, rec_yd: 250, rec_td: 1 },
  adp: 44, ecr: 44, bye: 7,
};
const injuryBundle = (asOf, players) => ({
  meta: Object.assign({}, NEW.meta, { asOf }),
  news: [`Injured Star (SF WR) — out for the season (Knee). Status IR; he is marked OUT here.`],
  players,
});
const INJ_FIRST = injuryBundle(ASOF_NEW,
  NEW.players.concat([INJ_STAR, INJ_OVERRIDE]));
const INJ_SECOND = injuryBundle(ASOF_NEWER,
  NEW.players.concat([INJ_STAR, INJ_OVERRIDE, INJ_FRESH]));

// a returning user: three drafted (one a keeper), a boost, a star, a DND
const MARKS = {};
MARKS[(DROP_MARKED.name + '|' + DROP_MARKED.pos).toLowerCase()] =
  { drafted: { price: 27, mine: true, keeper: true }, boost: 0, out: false, dnd: false, star: false, nom: false };
MARKS['bijan robinson|rb'] = { drafted: { price: 64, mine: true }, boost: 0, out: false, dnd: false, star: false, nom: false };
MARKS["ja'marr chase|wr"] = { drafted: { price: 58, mine: false }, boost: 0, out: false, dnd: false, star: false, nom: false };
MARKS['puka nacua|wr'] = { drafted: null, boost: 15, out: false, dnd: false, star: true, nom: false };
MARKS['trey mcbride|te'] = { drafted: null, boost: 0, out: false, dnd: true, star: false, nom: true };

function savedState(poolMeta, poolTransform) {
  const pool = OLD.players.map(({ out, outData, ...p }) => Object.assign({}, p, {
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

  async function boot(state, file) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));
    page.on('console', m => {
      if (m.type() === 'error' && !/Failed to load resource/.test(m.text()))
        errs.push('CONSOLE: ' + m.text());
    });
    await page.goto('file://' + (file || TMP));
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

    ok('poolMeta.valuesAsOf advanced', r.poolMeta.valuesAsOf === ASOF_NEW, r.poolMeta);
    ok('poolMeta.valuesSrc still bundled', r.poolMeta.valuesSrc === 'bundled snapshot');
    ok('poolMeta.bundleMergedAsOf stamped', r.poolMeta.bundleMergedAsOf === ASOF_NEW);

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
    ok('bundleMergedAsOf stamped', r.poolMeta.bundleMergedAsOf === ASOF_NEW, r.poolMeta);

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

  // ================================================ (6) data-supplied OUT
  // The bundle now ships out:true for anyone ruled out for the season. It has
  // to reach the recommendations, be visible on the board, and still lose to
  // the user when the user disagrees — including across the next build.
  console.log('\n--- scenario 6: bundled OUT flags, and the user overruling them ---');
  {
    writeBundle(TMP_INJ, INJ_FIRST);
    const state = savedState({
      valuesAsOf: OLD.meta.asOf, valuesSrc: 'bundled snapshot', ranksAsOf: null,
    });
    state.leagues[0].marks = JSON.parse(JSON.stringify(MARKS));
    // a returning user who already overruled a previous build: his saved pool
    // row carries the data default, his mark carries the disagreement
    state.pool.push({
      name: 'Override Guy', team: 'KC', pos: 'WR', aav: 30, pts: 250,
      src: 'sleeper+espn+ffc', note: 'Sleeper: Out (Hamstring)', outData: true,
      stats: null, floor: null, ceil: null, adp: null, ecr: null, bye: null,
      dnd: false, star: false, nom: false,
    });
    state.leagues[0].marks['override guy|wr'] =
      { drafted: null, boost: 0, out: false, dnd: false, star: false, nom: false };

    const { ctx, page, errs } = await boot(state, TMP_INJ);
    const r = await page.evaluate(() => {
      const A = window.APP, S = A.S, R = A.R;
      const byId = id => S.players.find(p => A.playerId(p) === id) || null;
      const inOpt = id => !!(R.sol && R.sol.chosen.some(x => A.playerId(x.p) === id));
      return {
        star: byId('injured star|wr'), over: byId('override guy|wr'),
        starInOpt: inOpt('injured star|wr'), overInOpt: inOpt('override guy|wr'),
        starBid: R.bids.has('injured star|wr'), overBid: R.bids.has('override guy|wr'),
        outCount: S.players.filter(p => p.out).length,
      };
    });
    ok('bundled out:true reaches the pool', r.star && r.star.out === true, r.star);
    ok('bundled OUT is recorded as the data default',
      r.star && r.star.outData === true, r.star && r.star.outData);
    ok('an OUT player is never in the optimal roster', r.starInOpt === false);
    ok('an OUT player gets no max bid', r.starBid === false);
    ok('a saved out:false overrules the bundle', r.over && r.over.out === false,
      r.over && { out: r.over.out, outData: r.over.outData });
    ok('the overruled player keeps the data default for later builds',
      r.over && r.over.outData === true);
    ok('the overruled player is back in the market', r.overBid === true);
    ok('only the flagged player is out', r.outCount === 1, { outCount: r.outCount });

    // the board has to show it, not just the model
    await page.fill('#search', 'Injured Star');
    await page.waitForTimeout(300);
    const row = page.locator('#pool tbody tr').first();
    ok('OUT row is dimmed/struck through',
      ((await row.getAttribute('class')) || '').includes('outrow'),
      await row.getAttribute('class'));
    ok('OUT pill rendered on the row', /OUT/.test(await row.innerHTML()));

    // snake mode plans around him too
    const snakeHasStar = await page.evaluate(() => {
      const A = window.APP;
      A.S.settings.mode = 'snake'; A.recompute();
      const has = !!(A.R.sol && A.R.sol.plan &&
        A.R.sol.plan.some(s => A.playerId(s.r.p) === 'injured star|wr'));
      A.S.settings.mode = 'auction'; A.recompute();
      return has;
    });
    ok('an OUT player is never in the snake plan', snakeHasStar === false);

    // …and the keeper advisor stops pricing him like a healthy player
    const keeper = await page.evaluate(() => {
      const A = window.APP;
      A.S.kpCands = [{ id: 'injured star|wr', name: 'Injured Star', pos: 'WR', cost: 5 }];
      A.recompute();
      const row = A.keeperAdvice()[0];
      return row && { out: !!row.out, keep: !!row.keep, label: row.label };
    });
    ok('keeper advisor calls an OUT keeper a toss-back',
      keeper && keeper.out === true && keeper.keep === false, keeper);
    await page.evaluate(() => { window.APP.S.kpCands = []; window.APP.recompute(); });

    // the user overrules the data through the block bar
    await page.fill('#search', 'Injured Star');
    await page.waitForTimeout(300);
    await page.locator('#pool tbody tr button[data-act="sel"]').first().click();
    await page.waitForTimeout(300);
    ok('block bar has an OUT toggle', await page.locator('#blockOut').count() === 1);
    ok('block bar reports the OUT state',
      /marked OUT/.test(await page.locator('#blockOut').textContent()));
    await page.locator('#blockOut').click();
    await page.waitForTimeout(400);
    const afterClick = await page.evaluate(() => {
      const A = window.APP;
      const p = A.S.players.find(x => A.playerId(x) === 'injured star|wr');
      return { out: p.out, outData: p.outData,
        mark: A.captureMarks()['injured star|wr'],
        bid: A.R.bids.has('injured star|wr') };
    });
    ok('block-bar toggle clears OUT', afterClick.out === false, afterClick);
    ok('the override is stored as a mark',
      afterClick.mark && afterClick.mark.out === false, afterClick.mark);
    ok('un-marked player rejoins the market', afterClick.bid === true);

    await page.reload();
    await page.waitForTimeout(1200);
    const afterReload = await page.evaluate(() => {
      const A = window.APP;
      const p = A.S.players.find(x => A.playerId(x) === 'injured star|wr');
      return { out: p.out, outData: p.outData, migration: A.S.migration };
    });
    ok('override survives a reload', afterReload.out === false, afterReload);
    ok('data default still remembered after reload', afterReload.outData === true);

    // …and survives the *next* nightly build, which still says he is out
    writeBundle(TMP_INJ, INJ_SECOND);
    await page.reload();
    await page.waitForTimeout(1400);
    const afterBuild = await page.evaluate(() => {
      const A = window.APP, S = A.S;
      const byId = id => S.players.find(p => A.playerId(p) === id) || null;
      return {
        migration: S.migration && S.migration.mode,
        star: byId('injured star|wr'), fresh: byId('fresh casualty|rb'),
        over: byId('override guy|wr'),
        asOf: S.poolMeta.valuesAsOf,
      };
    });
    ok('the next build was adopted', afterBuild.migration === 'adopt', afterBuild.migration);
    ok('poolMeta advanced to the new build', afterBuild.asOf === ASOF_NEWER, afterBuild.asOf);
    ok('override survives re-migration', afterBuild.star && afterBuild.star.out === false,
      afterBuild.star && { out: afterBuild.star.out, outData: afterBuild.star.outData });
    ok('a newly ruled-out player arrives OUT',
      afterBuild.fresh && afterBuild.fresh.out === true && afterBuild.fresh.outData === true,
      afterBuild.fresh);
    ok('the other override also survives', afterBuild.over && afterBuild.over.out === false);

    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  // ======================================== (7) live refresh injury handling
  console.log('\n--- scenario 7: ↻ refresh auto-marks OUT and replaces stale notes ---');
  {
    const state = savedState(
      { valuesAsOf: OLD.meta.asOf, valuesSrc: 'bundled snapshot', ranksAsOf: null },
      // a three-week-old status that the append-only refresh could never clear
      p => p.name === 'Michael Wilson'
        ? Object.assign({}, p, { note: 'projection split: Sleeper 180 vs ESPN 140 · Sleeper: Questionable (Ankle)' })
        : p.name === 'Puka Nacua'
          ? Object.assign({}, p, { note: 'Sleeper: Doubtful (Knee)' }) : p);
    state.leagues[0].marks = JSON.parse(JSON.stringify(MARKS));
    // the user says Trey McBride is unavailable; Sleeper will say he is fine
    state.leagues[0].marks['trey mcbride|te'] =
      { drafted: null, boost: 0, out: true, dnd: true, star: false, nom: true };

    const { ctx, page, errs } = await boot(state);
    await ctx.route('**/api.sleeper.app/v1/players/nfl', r => r.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        1: {
          full_name: 'Michael Wilson', position: 'WR', team: 'ARI', search_rank: 168,
          injury_status: 'IR', injury_body_part: 'Knee', status: 'Injured Reserve',
          injury_notes: 'Placed on IR after surgery.\nOut for the season.',
        },
        2: { full_name: 'Puka Nacua', position: 'WR', team: 'LAR', search_rank: 7 },
        3: { full_name: 'Trey McBride', position: 'TE', team: 'ARI', search_rank: 14 },
        4: {
          full_name: 'Bijan Robinson', position: 'RB', team: 'ATL', search_rank: 1,
          injury_status: 'PUP', injury_body_part: 'Hamstring',
        },
      }),
    }));
    await ctx.route('**/api.sleeper.com/projections/**',
      r => r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));
    await ctx.route('**/fantasyfootballcalculator.com/**', r => r.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({ players: [] }),
    }));

    await page.locator('#refreshBtn').click();
    await page.waitForTimeout(2500);

    const r = await page.evaluate(() => {
      const A = window.APP, S = A.S;
      const byId = id => S.players.find(p => A.playerId(p) === id) || null;
      return {
        mw: byId('michael wilson|wr'), puka: byId('puka nacua|wr'),
        mcbride: byId('trey mcbride|te'), bijan: byId('bijan robinson|rb'),
        mwBid: A.R.bids.has('michael wilson|wr'),
        toast: (document.querySelector('#toast') || {}).textContent || '',
        marks: A.captureMarks(),
      };
    });
    ok('IR status auto-marks the player OUT', r.mw && r.mw.out === true && r.mw.outData === true,
      r.mw && { out: r.mw.out, outData: r.mw.outData });
    ok('auto-OUT player leaves the market', r.mwBid === false);
    ok('the stale Sleeper note is replaced, not stacked',
      r.mw && /Sleeper: IR \(Knee\)/.test(r.mw.note) && !/Questionable/.test(r.mw.note),
      r.mw && r.mw.note);
    ok('the note keeps its non-Sleeper segments',
      r.mw && /projection split/.test(r.mw.note), r.mw && r.mw.note);
    ok('injury notes are flattened to one line',
      r.mw && !/\n/.test(r.mw.note) && /Out for the season/.test(r.mw.note), r.mw && r.mw.note);
    ok('a cleared status removes the stale segment',
      r.puka && !/Sleeper:/.test(r.puka.note || ''), r.puka && r.puka.note);
    ok('PUP is never auto-marked OUT', r.bijan && r.bijan.out === false,
      r.bijan && { out: r.bijan.out, note: r.bijan.note });
    ok('PUP still shows up as a note', r.bijan && /Sleeper: PUP \(Hamstring\)/.test(r.bijan.note),
      r.bijan && r.bijan.note);
    ok("a user's own OUT is not cleared by a healthy report",
      r.mcbride && r.mcbride.out === true && r.mcbride.outData === false, r.mcbride);
    ok("the user's OUT stays stored as an override",
      r.marks['trey mcbride|te'] && r.marks['trey mcbride|te'].out === true,
      r.marks['trey mcbride|te']);
    ok('an auto-OUT needs no mark of its own',
      !r.marks['michael wilson|wr'] || !('out' in r.marks['michael wilson|wr']),
      r.marks['michael wilson|wr']);
    ok('the refresh says how many players it marked OUT',
      /auto-marked OUT/.test(r.toast), r.toast);

    await page.reload();
    await page.waitForTimeout(1200);
    const again = await page.evaluate(() => {
      const A = window.APP;
      const byId = id => A.S.players.find(p => A.playerId(p) === id) || null;
      return { mw: byId('michael wilson|wr'), mcbride: byId('trey mcbride|te') };
    });
    // the live refresh writes outData onto the pool, which saveState keeps
    ok('auto-OUT survives a reload', again.mw && again.mw.out === true, again.mw);
    ok("the user's OUT survives a reload", again.mcbride && again.mcbride.out === true);

    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  // ============================== (8) injuries reach an imported pool too
  // An imported sheet's dollar values are the user's own work and stay put,
  // but an injury is a fact his sheet does not have — the enrich path has to
  // carry the OUT flag and the note across without touching his numbers.
  console.log('\n--- scenario 8: the enrich path carries injuries into an imported pool ---');
  {
    writeBundle(TMP_INJ, INJ_SECOND);
    const state = savedState(
      { valuesAsOf: '2026-08-01', valuesSrc: 'imported file', ranksAsOf: null },
      p => Object.assign({}, p, { aav: 99, pts: 111, src: 'my sheet' }));
    state.pool.push({
      name: 'Injured Star', team: 'SF', pos: 'WR', aav: 99, pts: 111,
      src: 'my sheet', note: 'my own note', stats: null, floor: null, ceil: null,
      adp: null, ecr: null, bye: null, dnd: false, star: false, nom: false,
    });

    const { ctx, page, errs } = await boot(state, TMP_INJ);
    const r = await page.evaluate(() => {
      const A = window.APP, S = A.S;
      const byId = id => S.players.find(p => A.playerId(p) === id) || null;
      return {
        migration: S.migration && S.migration.mode,
        star: byId('injured star|wr'), fresh: byId('fresh casualty|rb'),
        bid: A.R.bids.has('injured star|wr'),
      };
    });
    ok('enrich path taken', r.migration === 'enrich', r.migration);
    ok('imported values still untouched', r.star && r.star.aav === 99 && r.star.pts === 111,
      r.star && { aav: r.star.aav, pts: r.star.pts });
    ok('the bundle OUT reaches an imported row',
      r.star && r.star.out === true && r.star.outData === true, r.star);
    ok('the imported row keeps its own note and gains the injury',
      r.star && /my own note/.test(r.star.note) && /Sleeper: IR \(Knee\)/.test(r.star.note),
      r.star && r.star.note);
    ok('an OUT import is out of the market', r.bid === false);
    ok('an appended OUT player arrives out', r.fresh && r.fresh.out === true, r.fresh);
    ok('no page errors', errs.length === 0, errs);
    await ctx.close();
  }

  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail) process.exit(1);
  console.log('MIGRATION TESTS PASSED');
})();
