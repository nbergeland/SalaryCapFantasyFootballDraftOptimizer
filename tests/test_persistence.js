// Persistence suite — born from a real report: "I set up keepers for my
// league and they disappear." Every in-app path proved sound; the loss was
// browser storage eviction. These tests pin down both halves: the in-app
// paths stay sound, and the IndexedDB mirror brings state back when
// localStorage is wiped out from under the app.
// Run: INDEX_HTML=<path> NODE_PATH=<playwright dir> node test_persistence.js
const { chromium } = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path');

const REPO = process.env.INDEX_HTML ||
  require('path').join(__dirname, '..', 'index.html');
const CHROMIUM = process.env.CHROMIUM ||
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const START = '/*__DATA__*/', END = '/*__END_DATA__*/';
const html = fs.readFileSync(REPO, 'utf8');
const a = html.indexOf(START) + START.length, b = html.indexOf(END);
const CUR = JSON.parse(html.slice(a, b));

// tomorrow's bundle: same players, asOf +1 day (what the nightly cron produces)
const dayAfter = iso => { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10); };
const NEXT = { meta: Object.assign({}, CUR.meta, { asOf: dayAfter(CUR.meta.asOf) }), news: CUR.news, players: CUR.players };
const TMP_TODAY = path.join(os.tmpdir(), 'persist-today.html');
const TMP_NEXT = path.join(os.tmpdir(), 'persist-next.html');
fs.writeFileSync(TMP_TODAY, html);
fs.writeFileSync(TMP_NEXT, html.slice(0, a) + JSON.stringify(NEXT) + html.slice(b));

let pass = 0, fail = 0;
const ok = (n, v, extra) => {
  if (v) { pass++; console.log('PASS  ' + n); }
  else { fail++; console.log('FAIL  ' + n + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')); }
};

(async () => {
  const browser = await chromium.launch({ executablePath: CHROMIUM });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR: ' + e.message));

  const keeperState = () => page.evaluate(() => {
    const A = window.APP;
    return {
      keepers: A.S.players.filter(p => p.drafted && p.drafted.keeper)
        .map(p => ({ id: A.playerId(p), price: p.drafted.price, mine: p.drafted.mine })),
      kpCands: (A.S.kpCands || []).map(c => c.id),
      leagues: A.LEAGUES.list.map(l => ({ id: l.id, name: l.name, marks: Object.keys(l.marks || {}).length })),
      active: A.LEAGUES.activeId,
      lsBytes: (localStorage.getItem('sc-draft-companion-v2') || '').length,
    };
  });

  // ---- day 1: fresh user sets up keepers + candidates -------------------
  console.log('--- day 1: set up keepers ---');
  await page.goto('file://' + TMP_TODAY);
  await page.waitForTimeout(1200);
  await page.evaluate(() => { localStorage.clear(); location.reload(); });
  await page.waitForTimeout(1200);

  await page.evaluate(() => {
    const A = window.APP;
    const keep = (name, price, mine) => {
      const p = A.S.players.find(x => x.name === name);
      p.drafted = { price, mine, keeper: true };
    };
    keep('Bijan Robinson', 38, true);
    keep("Ja'Marr Chase", 45, false);
    A.S.kpCands.push({ id: 'bijan robinson|rb', cost: 38 });
    A.recompute();   // recompute -> saveState
  });
  let s1 = await keeperState();
  ok('day1: 2 keepers set', s1.keepers.length === 2, s1.keepers);
  ok('day1: candidate saved', s1.kpCands.length === 1, s1.kpCands);

  // ---- same day reload --------------------------------------------------
  await page.reload(); await page.waitForTimeout(1200);
  let s2 = await keeperState();
  ok('same-day reload: keepers persist', s2.keepers.length === 2, s2.keepers);
  ok('same-day reload: candidate persists', s2.kpCands.length === 1, s2.kpCands);

  // ---- next day: nightly build shipped a newer bundle -------------------
  console.log('--- day 2: newer bundle adopts ---');
  // carry localStorage across "origins" by copying the blob (file:// pages share origin)
  await page.goto('file://' + TMP_NEXT);
  await page.waitForTimeout(1500);
  let s3 = await keeperState();
  ok('next-day adopt: keepers persist', s3.keepers.length === 2, s3.keepers);
  ok('next-day adopt: candidate persists', s3.kpCands.length === 1, s3.kpCands);

  // ---- multi-league: add league B, flip back and forth ------------------
  console.log('--- multi-league switching ---');
  await page.evaluate(() => { window.APP.addLeague('League B', false); });
  await page.waitForTimeout(300);
  let s4 = await keeperState();
  ok('league B is empty of keepers', s4.keepers.length === 0, s4.keepers);
  await page.evaluate(() => {
    const A = window.APP;
    const first = A.LEAGUES.list[0].id;
    A.switchLeague(first);
  });
  await page.waitForTimeout(300);
  let s5 = await keeperState();
  ok('switch back: league A keepers restored', s5.keepers.length === 2, s5.keepers);
  ok('switch back: candidate restored', s5.kpCands.length === 1, s5.kpCands);

  // reload while league A active, then switch after reload
  await page.reload(); await page.waitForTimeout(1200);
  let s6 = await keeperState();
  ok('reload multi-league: keepers persist', s6.keepers.length === 2, s6.keepers);

  // ---- version skew: blob saved by the PREVIOUS app release -------------
  // (pre-injury: pool rows had no outData, marks always carried out:false)
  console.log('--- state written by the previous release ---');
  const oldBlob = await page.evaluate(() => {
    const A = window.APP;
    const raw = JSON.parse(localStorage.getItem('sc-draft-companion-v2'));
    raw.pool = raw.pool.map(({ outData, ...p }) => p);        // old pool shape
    for (const lg of raw.leagues)
      for (const k in (lg.marks || {}))
        lg.marks[k] = Object.assign({ out: false }, lg.marks[k]); // old always-out marks
    raw.poolMeta.valuesAsOf = '2026-08-10';                    // older than bundle
    return JSON.stringify(raw);
  });
  await page.evaluate(bl => { localStorage.setItem('sc-draft-companion-v2', bl); }, oldBlob);
  await page.reload(); await page.waitForTimeout(1500);
  let s7 = await keeperState();
  ok('old-release blob: keepers survive migration', s7.keepers.length === 2, s7.keepers);
  ok('old-release blob: candidate survives', s7.kpCands.length === 1, s7.kpCands);

  // ---- the eviction scenario: localStorage wiped, IDB mirror survives ---
  console.log('--- browser evicted localStorage (the Safari 7-day case) ---');
  // let the debounced mirror land first
  await page.waitForTimeout(2000);
  await page.evaluate(() => { localStorage.clear(); });
  await page.reload(); await page.waitForTimeout(2500);   // restore is async
  let s8 = await keeperState();
  ok('mirror auto-restored after localStorage wipe', s8.keepers.length === 2, s8.keepers);
  ok('candidates restored from mirror', s8.kpCands.length === 1, s8.kpCands);
  ok('both leagues restored from mirror', s8.leagues.length === 2, s8.leagues);

  // ---- full-state export / import round-trip ----------------------------
  console.log('--- export carries everything ---');
  const exported = await page.evaluate(() => JSON.parse(window.APP.buildStateBlob()));
  ok('export is the full v2 state', exported.v === 2 && Array.isArray(exported.leagues));
  ok('export contains both leagues', exported.leagues.length === 2, exported.leagues.map(l => l.name));
  const lgA = exported.leagues.find(l => Object.keys(l.marks || {}).length);
  ok('export contains keeper marks', lgA &&
    Object.values(lgA.marks).filter(m => m.drafted && m.drafted.keeper).length === 2);
  ok('export contains keeper candidates', lgA && (lgA.kpCands || []).length === 1, lgA && lgA.kpCands);

  // ---- corrupted blob: quarantined, then mirror recovers ----------------
  console.log('--- corrupted blob is quarantined, not paved over ---');
  await page.evaluate(() => {
    localStorage.setItem('sc-draft-companion-v2', '{definitely not json');
  });
  await page.reload(); await page.waitForTimeout(2500);
  const s9 = await keeperState();
  const q = await page.evaluate(() => ({
    quarantined: !!localStorage.getItem('sc-draft-companion-v2-quarantine'),
  }));
  ok('corrupt blob parked under quarantine key', q.quarantined);
  ok('mirror recovered the state anyway', s9.keepers.length === 2, s9.keepers);
  ok('no page errors across corruption', errs.length === 0, errs.slice(0, 3));

  console.log(errs.length ? '\nERRORS:\n' + errs.join('\n') : '\nno page errors');
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
