'use strict';

// Reads data/state.json (written by watch.ps1) twice a second and shows the
// newest results PDF the moment it lands.

const STATE_URL = 'data/state.json';
const POLL_MS = 500;
const STALE_MS = 45000;          // no heartbeat for this long = watcher not running
const TITLE = 'Auction Watch';

const $ = (id) => document.getElementById(id);
const etTime = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit', second: '2-digit' });
const etHm = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' });
const etDay = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', month: 'short', day: 'numeric' });
const localTime = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const localHm = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });

let state = null;
let lastOk = 0;
let seen = null;          // result ids already present when the page loaded (no alert for those)
let pinnedId = null;      // a result picked from the menu; null = follow the newest
let shownId = null;       // result currently in the PDF frame
let alertId = null;
let stripKey = '';
let historyKey = '';

const asList = (v) => (Array.isArray(v) ? v : (v ? [v] : []));
const dayOf = (r) => etDay.format(new Date(r.closeUtc || (r.date + 'T17:00:00Z')));

function span(ms) {
  let s = Math.max(0, Math.round(ms / 1000));
  const d = Math.floor(s / 86400); s -= d * 86400;
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s -= m * 60;
  const p = (n) => String(n).padStart(2, '0');
  return d > 0 ? `${d}d ${p(h)}h ${p(m)}m` : `${p(h)}:${p(m)}:${p(s)}`;
}

/* ---------- sound + notifications ---------- */

let audio = null;

async function enableSound() {
  try {
    if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
    if (audio.state === 'suspended') await audio.resume();
    tone(660, 0, 0.12);
  } catch (e) { /* no audio */ }
  if ('Notification' in window && Notification.permission === 'default') {
    try { await Notification.requestPermission(); } catch (e) { /* ignore */ }
  }
  updateSoundBtn();
}

function soundOn() { return !!audio && audio.state === 'running'; }

function updateSoundBtn() {
  const b = $('soundBtn');
  b.textContent = soundOn() ? 'Sound on' : 'Enable sound';
  b.classList.toggle('on', soundOn());
}

function tone(freq, at, dur) {
  if (!soundOn()) return;
  const t = audio.currentTime + at;
  const o = audio.createOscillator();
  const g = audio.createGain();
  o.type = 'sine';
  o.frequency.value = freq;
  o.connect(g); g.connect(audio.destination);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.start(t); o.stop(t + dur + 0.05);
}

function chime() { tone(880, 0, 0.25); tone(1175, 0.18, 0.25); tone(1568, 0.36, 0.5); }

/* ---------- alert ---------- */

let chimeTimer = null;
let titleTimer = null;

function fireAlert(r) {
  alertId = r.id;
  document.body.classList.add('alerting');
  chime();
  let n = 1;
  clearInterval(chimeTimer);
  chimeTimer = setInterval(() => { if (++n > 3) clearInterval(chimeTimer); else chime(); }, 1500);

  clearInterval(titleTimer);
  let on = false;
  titleTimer = setInterval(() => { document.title = (on = !on) ? `● RESULTS OUT — ${r.desc}` : TITLE; }, 800);

  if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
    try {
      const note = new Notification('Auction results out', { body: `${r.desc}  ·  CUSIP ${r.cusip}`, tag: 'aw-' + r.id, requireInteraction: true });
      note.onclick = () => { window.focus(); note.close(); };
    } catch (e) { /* ignore */ }
  }
  stripKey = '';
}

function ack() {
  if (!document.body.classList.contains('alerting')) return;
  document.body.classList.remove('alerting');
  clearInterval(chimeTimer);
  clearInterval(titleTimer);
  document.title = TITLE;
  alertId = null;
  stripKey = '';
  if (state) render();
}

/* ---------- rendering ---------- */

function metric(k, v, big) {
  const d = document.createElement('div');
  d.className = 'metric' + (big ? ' big' : '');
  const a = document.createElement('div'); a.className = 'k'; a.textContent = k;
  const b = document.createElement('div'); b.className = 'v'; b.textContent = v;
  d.append(a, b);
  return d;
}

function showResult(r) {
  const frame = $('pdf');
  if (!r) {
    $('strip').hidden = true;
    $('empty').hidden = false;      // overlay covers the (blank) frame
    if (shownId) { frame.src = 'about:blank'; shownId = null; }
    return;
  }
  if (r.id !== shownId) {
    frame.src = r.pdf + '#navpanes=0&view=FitH';
    shownId = r.id;
  }
  $('empty').hidden = true;
  $('strip').hidden = false;

  const key = JSON.stringify(r) + '|' + alertId;
  if (key === stripKey) return;
  stripKey = key;

  const tag = $('tag');
  const isAlert = r.id === alertId;
  tag.textContent = isAlert ? 'JUST OUT' : (r.isNew ? 'NEW' : 'PREVIOUS');
  tag.className = 'tag' + (r.isNew ? ' new' : '');

  $('title').textContent = r.desc;
  let sub = `CUSIP ${r.cusip} · auction ${dayOf(r)}`;
  if (r.detectedUtc) {
    const d = new Date(r.detectedUtc);
    sub += ` · got it ${etTime.format(d)} ET / ${localTime.format(d)} local`;
    if (r.closeUtc) sub += ` (${span(d - new Date(r.closeUtc))} after close)`;
  }
  $('sub').textContent = sub;

  const m = r.summary;
  const box = $('metrics');
  box.replaceChildren();
  if (m) {
    box.append(metric(m.label, m.high ? m.high + '%' : '—', true));
    box.append(metric('Allotted at high', m.allotted ? m.allotted + '%' : '—'));
    if (m.median || m.low) box.append(metric('Median / low', `${m.median} / ${m.low}`));
    if (m.investRate) box.append(metric('Invest. rate', m.investRate + '%'));
    box.append(metric('Bid-to-cover', m.btc || '—', true));
    if (m.indirect) {
      box.append(metric('Indirect', m.indirect + '%'));
      box.append(metric('Direct', m.direct + '%'));
      box.append(metric('Dealers', m.dealers + '%'));
    }
    if (m.offering) box.append(metric('Size', m.offering));
  } else {
    box.append(metric('Numbers', 'loading…'));
  }

  $('openLocal').href = r.pdf;
  $('openWeb').href = r.url;
}

function renderHistory(list, current) {
  const sel = $('history');
  const key = list.map((r) => r.id + (r.isNew ? '*' : '')).join(',');
  if (key !== historyKey) {
    historyKey = key;
    sel.replaceChildren();
    for (const r of list) {
      const o = document.createElement('option');
      o.value = r.id;
      o.textContent = `${r.desc} — ${dayOf(r)}${r.isNew ? '' : ' (previous)'}`;
      sel.append(o);
    }
  }
  sel.hidden = list.length < 2;
  if (current) sel.value = current.id;
}

function renderStatus() {
  const now = Date.now();
  $('clockEt').textContent = etTime.format(now) + ' ET';
  $('clockLocal').textContent = localTime.format(now) + ' local';

  let cls = 'wait';
  let text = 'Connecting…';
  const hb = state ? Date.parse(state.heartbeat) : NaN;
  const s = state && state.session;

  if (!state || !lastOk || !(now - hb < STALE_MS)) {
    cls = 'off';
    text = 'Watcher not running — double-click the Auction Watch icon on your desktop';
  } else {
    switch (state.phase) {
      case 'countdown':
        text = s ? `Waiting · polling starts in ${span(Date.parse(s.fastStartUtc) - now)}` : 'Waiting';
        break;
      case 'polling': {
        cls = 'live';
        text = 'Polling TreasuryDirect';
        if (state.poll && state.poll.file) text += ` · ${state.poll.file}: ${state.poll.status}`;
        if (s) {
          const c = Date.parse(s.closeUtc);
          text += now < c ? ` · close in ${span(c - now)}` : ` · +${span(now - c)} after close`;
        }
        break;
      }
      case 'found': cls = 'found'; text = state.message || 'Results out'; break;
      case 'error': case 'gaveup': cls = 'warn'; text = state.message; break;
      default: text = state.message || state.phase;
    }
  }
  const pill = $('pill');
  pill.className = 'pill ' + cls;
  $('pillText').textContent = text;

  // the auction being waited for
  const next = $('next');
  next.replaceChildren();
  if (s && state.phase !== 'done' && !(cls === 'off')) {
    const targets = asList(s.targets);
    const close = new Date(s.closeUtc);
    const b = document.createElement('b');
    b.textContent = targets.map((t) => t.desc + (t.offering ? ` (${t.offering})` : '')).join(', ');
    next.append('Next: ', b, ` · ${etDay.format(close)} · closes ${etHm.format(close)} ET (${localHm.format(close)} local)`);
  }

  // empty-state text when there is no PDF yet
  if (!$('empty').hidden) {
    if (cls === 'off') {
      $('emptyTitle').textContent = 'Watcher not running';
      $('emptyText').textContent = 'Double-click the Auction Watch icon on your desktop. This page reconnects by itself.';
    } else {
      $('emptyTitle').textContent = 'Waiting for the results PDF';
      $('emptyText').textContent = s
        ? `${asList(s.targets).map((t) => t.desc).join(', ')} closes ${etHm.format(new Date(s.closeUtc))} ET. The PDF appears here the moment TreasuryDirect posts it.`
        : 'It will appear here the moment TreasuryDirect posts it.';
    }
  }
}

function render() {
  const list = asList(state && state.results);
  if (seen === null) seen = new Set(list.map((r) => r.id));
  const latest = list[0];
  if (latest && latest.isNew && !seen.has(latest.id)) {
    pinnedId = null;                      // jump to the new one
    fireAlert(latest);
  }
  list.forEach((r) => seen.add(r.id));

  const current = (pinnedId && list.find((r) => r.id === pinnedId)) || latest;
  showResult(current);
  renderHistory(list, current);
  renderStatus();
}

async function poll() {
  try {
    const res = await fetch(STATE_URL + '?_=' + Date.now(), { cache: 'no-store' });
    if (res.ok) {
      state = await res.json();
      lastOk = Date.now();
      render();
    }
  } catch (e) { /* watcher not running */ }
  setTimeout(poll, POLL_MS);
}

/* ---------- wire up ---------- */

$('soundBtn').addEventListener('click', enableSound);
$('ackBtn').addEventListener('click', ack);
document.addEventListener('keydown', ack);
$('history').addEventListener('change', (e) => {
  const list = asList(state && state.results);
  pinnedId = (list[0] && e.target.value === list[0].id) ? null : e.target.value;
  render();
});
setInterval(renderStatus, 250);
updateSoundBtn();
renderStatus();
poll();
