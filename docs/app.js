'use strict';

/* ============================ config ============================ */
const TARGET_URL  = 'https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/BBPA_20260910174000.pdf';
const NOT_BEFORE  = '2026-09-10';          // ignore any BBPA file dated before this (YYYY-MM-DD)
const FANOUT_DAYS = 2;                      // also try filenames this many days later
const EXTRA_TIMES = ['174000', '184000', '164000'];
const POLL_MS     = 20000;
const PDFJS_WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

if (window.pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;

/* ============================ state ============================ */
const $ = (id) => document.getElementById(id);
let workerUrl = '';
let audioCtx = null, soundEnabled = false, beepTimer = null, titleTimer = null;
let lastKey = null, acknowledged = false, previewMode = false;
let checkCount = 0;

/* ============================ worker URL setup ============================ */
function loadWorkerUrl() {
  try { workerUrl = (localStorage.getItem('bw_worker') || '').trim(); } catch (e) { workerUrl = ''; }
  return workerUrl;
}
function showSetup(msg) {
  document.body.className = 'waiting';
  $('setup').hidden = false; $('waiting').hidden = true; $('alert').hidden = true;
  $('workerInput').value = workerUrl || '';
  if (msg) { $('workerErr').hidden = false; $('workerErr').textContent = msg; }
}
function saveWorkerUrl() {
  let v = $('workerInput').value.trim().replace(/\/+$/, '');
  if (!/^https:\/\/[^ ]+\.workers\.dev/i.test(v) && !/^https:\/\//i.test(v)) {
    return showSetup('That doesn’t look like a URL. It should start with https:// and usually ends in .workers.dev');
  }
  workerUrl = v;
  try { localStorage.setItem('bw_worker', v); } catch (e) {}
  $('setup').hidden = true;
  startWatching();
}

/* ============================ candidate URLs ============================ */
function pad(n) { return String(n).padStart(2, '0'); }
function ymd(d) { return d.getUTCFullYear() + pad(d.getUTCMonth() + 1) + pad(d.getUTCDate()); }
function parseBBPA(url) {
  const m = url.match(/BBPA_(\d{4})(\d{2})(\d{2})(\d{6})\.pdf/i);
  if (!m) return null;
  return { date: new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])), time: m[4] };
}
function fileDate(url) { const p = parseBBPA(url); return p ? p.date : null; }

const FLOOR = (function () {
  if (NOT_BEFORE) { const d = new Date(NOT_BEFORE + 'T00:00:00Z'); if (!isNaN(d)) return d; }
  return fileDate(TARGET_URL);
})();

function candidateUrls() {
  const list = [TARGET_URL];
  const base = parseBBPA(TARGET_URL);
  if (!base) return list;
  const start = (FLOOR && FLOOR > base.date) ? new Date(FLOOR) : new Date(base.date);
  const times = [...new Set([base.time, ...EXTRA_TIMES])];
  for (let d = 0; d <= FANOUT_DAYS; d++) {
    const day = new Date(start); day.setUTCDate(day.getUTCDate() + d);
    if (FLOOR && day < FLOOR) continue;
    const s = ymd(day), yr = day.getUTCFullYear();
    for (const t of times) {
      const name = `BBPA_${s}${t}.pdf`;
      list.push(`https://www.treasurydirect.gov/instit/annceresult/press/preanre/${yr}/${name}`);
      list.push(`https://fiscaldata.treasury.gov/static-data/published-reports/buybacks/preliminary/${name}`);
    }
  }
  return [...new Set(list)];
}
const CANDIDATES = candidateUrls();

/* ============================ PDF parsing ============================ */
function amountValue(s) { return parseInt(s.replace(/[^\d]/g, ''), 10) || 0; }

function pickAmount(flat) {
  const red = flat.search(/Redeemed/i);
  if (red >= 0) {
    const tail = flat.slice(red);
    const mm = tail.match(/\$[\d,]{6,}/g) || [];
    for (const a of mm) { const v = amountValue(a); if (v >= 10000000) return v; }
  }
  let best = 0;
  for (const a of (flat.match(/\$[\d,]{6,}/g) || [])) { const v = amountValue(a); if (v >= 10000000 && v > best) best = v; }
  return best;
}
function fmtShort(n) {
  if (n >= 1e9) return '$' + (n / 1e9).toFixed(n % 1e9 ? 1 : 0).replace(/\.0$/, '') + 'B';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(n % 1e6 ? 1 : 0).replace(/\.0$/, '') + 'M';
  return '$' + n;
}
function fmtFull(n) { return '$' + n.toLocaleString('en-US'); }
function tierFor(n) {
  if (n >= 10e9) return { name: 'HUGE  ( >= $10B )', color: '#b91c1c' };
  if (n >= 5e9)  return { name: 'XL  ( $5B - $10B )', color: '#ef4444' };
  if (n >= 3e9)  return { name: 'LARGE  ( $3B - $5B )', color: '#f59e0b' };
  if (n >= 1e9)  return { name: 'NORMAL  ( $1B - $3B )', color: '#22c55e' };
  return { name: 'SMALL  ( < $1B )', color: '#3b82f6' };
}

async function parsePdf(buf, url) {
  const res = {
    detectedAt: new Date().toISOString(), pdfUrl: url,
    operationType: null, headlineAmount: null, headlineAmountText: null,
    headlineAmountShort: null, tier: null, tierColor: null,
    maturityRange: null, operationDate: null, parsed: false
  };
  let flat = '';
  try {
    const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(buf) }).promise;
    const nPages = Math.min(pdf.numPages, 2);
    for (let p = 1; p <= nPages; p++) {
      const tc = await (await pdf.getPage(p)).getTextContent();
      flat += ' ' + tc.items.map((i) => i.str).join(' ');
    }
  } catch (e) {
    res.error = 'pdf parse failed: ' + e;
    return res;
  }
  flat = flat.replace(/\s+/g, ' ').trim();

  if (/TREASURY\s+TIPS\s+BUYBACK/i.test(flat)) res.operationType = 'TIPS buyback';
  else if (/TREASURY\s+DEBT\s+BUYBACK/i.test(flat)) res.operationType = 'Nominal coupon buyback';
  else if (/BUYBACK/i.test(flat)) res.operationType = 'Treasury buyback';

  const mr = flat.match(/(\d{2}\/\d{2}\/\d{4})\s*-\s*(\d{2}\/\d{2}\/\d{4})/);
  if (mr) res.maturityRange = mr[1] + ' - ' + mr[2];

  const months = 'January|February|March|April|May|June|July|August|September|October|November|December';
  const md = flat.match(new RegExp('\\$[\\d,]{7,}\\s+((?:' + months + ')\\s+\\d{1,2},\\s+\\d{4})'));
  if (md) res.operationDate = md[1];
  else { const m2 = flat.match(new RegExp('(?:' + months + ')\\s+\\d{1,2},\\s+\\d{4}')); if (m2) res.operationDate = m2[0]; }

  const amt = pickAmount(flat);
  if (amt > 0) {
    const t = tierFor(amt);
    res.headlineAmount = amt;
    res.headlineAmountText = fmtFull(amt);
    res.headlineAmountShort = fmtShort(amt);
    res.tier = t.name;
    res.tierColor = t.color;
    res.parsed = true;
  }
  return res;
}

/* ============================ polling ============================ */
async function checkOne(url, headOnly) {
  const q = workerUrl + '/?url=' + encodeURIComponent(url) + (headOnly ? '&head=1' : '');
  const res = await fetch(q, { cache: 'no-store' });
  const up = parseInt(res.headers.get('X-Upstream-Status') || res.status, 10);
  return { res, status: up };
}

async function poll() {
  if (previewMode) { setTimeout(poll, POLL_MS); return; }
  checkCount++;
  let hit = null, lastStatus = null, err = null;
  try {
    for (const url of CANDIDATES) {
      let r;
      try { r = await checkOne(url, true); } catch (e) { err = String(e); continue; }
      if (url === TARGET_URL) lastStatus = r.status;
      if (r.status >= 200 && r.status < 400) {
        const fd = fileDate(url);
        if (FLOOR && fd && fd < FLOOR) continue;
        hit = url; break;
      }
    }
  } catch (e) { err = String(e); }

  if (hit) {
    try {
      const full = await checkOne(hit, false);
      const buf = await full.res.arrayBuffer();
      const result = await parsePdf(buf, hit);
      renderFound(result);
    } catch (e) {
      renderWaiting({ status: 'error', lastError: 'found ' + hit + ' but could not read it: ' + e });
      setTimeout(poll, POLL_MS);
      return;
    }
    return; // stop polling; found
  }

  renderWaiting({
    status: err ? 'error' : 'waiting',
    httpStatus: lastStatus,
    lastError: err
  });
  setTimeout(poll, POLL_MS);
}

function startWatching() {
  checkCount = 0;
  renderWaiting({ status: 'starting' });
  poll();
}

/* ============================ rendering ============================ */
function fmtTime(iso) { const d = new Date(iso || Date.now()); return isNaN(d) ? '--' : d.toLocaleTimeString(); }

function renderWaiting(s) {
  if (document.body.classList.contains('found')) return;
  document.body.className = 'waiting';
  $('setup').hidden = true; $('waiting').hidden = false; $('alert').hidden = true;
  $('checkCount').textContent = checkCount;
  $('lastCheck').textContent = fmtTime();
  $('httpStatus').textContent = (s && s.httpStatus != null) ? s.httpStatus : '—';
  $('targetUrl').textContent = TARGET_URL;
  $('targetUrl').href = TARGET_URL;
  if (s && s.status === 'error') $('statusLine').textContent = 'Problem: ' + (s.lastError || 'unknown') + ' — still retrying…';
  else if (s && s.status === 'starting') $('statusLine').textContent = 'Starting…';
  else $('statusLine').textContent = 'Not published yet. Still watching…';
}

function renderFound(r) {
  const isNew = (r.detectedAt || 'found') !== lastKey;
  if (isNew) { acknowledged = false; lastKey = r.detectedAt || 'found'; }
  document.body.className = acknowledged ? 'found ack' : 'found';
  document.documentElement.style.setProperty('--tier', r.tierColor || '#22c55e');
  $('setup').hidden = true; $('waiting').hidden = true; $('alert').hidden = false;

  $('bigAmount').textContent = r.headlineAmountShort || r.headlineAmountText || 'PUBLISHED';
  $('fullAmount').textContent =
    (r.headlineAmountText && r.headlineAmountText !== r.headlineAmountShort) ? r.headlineAmountText : '';
  $('opType').textContent = r.operationType || 'Treasury buyback';
  $('tier').textContent = r.tier || '';
  $('maturity').textContent = r.maturityRange ? ('Maturity range · ' + r.maturityRange) : '';
  $('opDate').textContent = r.operationDate ? ('Operation date · ' + r.operationDate) : '';
  $('detectedAt').textContent = r.detectedAt ? ('Detected ' + fmtTime(r.detectedAt)) : '';
  $('parseNote').hidden = !!r.parsed;
  $('pdfLink').href = r.pdfUrl || '#';

  if (isNew) fireAlert(r);
}

/* ============================ alert fx ============================ */
async function enableAlerts() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') await audioCtx.resume();
    soundEnabled = true;
    blip(660, 0.09, 0.18);
  } catch (e) {}
  if ('Notification' in window && Notification.permission === 'default') {
    try { await Notification.requestPermission(); } catch (e) {}
  }
  updateEnableBtn();
}
function updateEnableBtn() {
  const b = $('enableBtn');
  const n = ('Notification' in window) ? Notification.permission : 'unsupported';
  if (soundEnabled && n === 'granted') { b.textContent = '✓ Sound + notifications on'; b.classList.add('on'); }
  else if (soundEnabled) { b.textContent = '✓ Sound on — click again to allow notifications'; b.classList.remove('on'); }
  else { b.textContent = '🔔 Enable sound + notifications'; b.classList.remove('on'); }
}
function blip(freq, dur, gain) {
  if (!soundEnabled || !audioCtx) return;
  const o = audioCtx.createOscillator(), g = audioCtx.createGain();
  o.type = 'square'; o.frequency.value = freq;
  o.connect(g); g.connect(audioCtx.destination);
  const t = audioCtx.currentTime;
  g.gain.setValueAtTime(gain || 0.2, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + (dur || 0.15));
  o.start(t); o.stop(t + (dur || 0.15) + 0.02);
}
function startBeeping() {
  if (beepTimer) return;
  const salvo = () => { blip(880, 0.13, 0.25); setTimeout(() => blip(1175, 0.13, 0.25), 170); };
  salvo(); beepTimer = setInterval(salvo, 1200);
}
function stopBeeping() { if (beepTimer) { clearInterval(beepTimer); beepTimer = null; } }
function flashTitle(txt) {
  if (titleTimer) clearInterval(titleTimer);
  let on = false;
  titleTimer = setInterval(() => { document.title = on ? 'Buyback Watch' : ('🟢 ' + txt + ' — BUYBACK'); on = !on; }, 900);
}
function fireAlert(r) {
  const short = r.headlineAmountShort || 'PUBLISHED';
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      const nt = new Notification('Treasury buyback announced', {
        body: (r.headlineAmountText || 'Published') +
              (r.operationType ? ('  ·  ' + r.operationType) : '') +
              (r.maturityRange ? ('\n' + r.maturityRange) : ''),
        tag: 'buyback-' + (r.detectedAt || ''), requireInteraction: true
      });
      nt.onclick = () => { window.focus(); nt.close(); };
    } catch (e) {}
  }
  startBeeping();
  flashTitle(short);
}
function acknowledge() {
  acknowledged = true; previewMode = false;
  stopBeeping();
  if (titleTimer) { clearInterval(titleTimer); titleTimer = null; }
  document.title = 'Buyback Watch';
  document.body.classList.add('ack');
  if (!lastKey) startWatching();
}

/* ============================ wire up ============================ */
$('workerSave').addEventListener('click', saveWorkerUrl);
$('workerInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') saveWorkerUrl(); });
$('enableBtn').addEventListener('click', enableAlerts);
$('ackBtn').addEventListener('click', acknowledge);
$('resetWorker').addEventListener('click', () => { showSetup(''); });
$('testBtn').addEventListener('click', () => {
  lastKey = null; acknowledged = false; previewMode = true;
  renderFound({
    detectedAt: new Date().toISOString(),
    headlineAmount: 12500000000, headlineAmountText: '$12,500,000,000', headlineAmountShort: '$12.5B',
    operationType: 'Nominal coupon buyback — PREVIEW', tier: 'HUGE  ( >= $10B )', tierColor: '#b91c1c',
    maturityRange: '10/15/2026 - 08/31/2028', operationDate: '(preview)', pdfUrl: '#', parsed: true
  });
});

updateEnableBtn();
if (loadWorkerUrl()) startWatching();
else showSetup('');
