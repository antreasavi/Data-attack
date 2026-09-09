'use strict';

const STATE_URL = 'data/state.json';
const POLL_MS = 3000;

const $ = (id) => document.getElementById(id);

let audioCtx = null;
let soundEnabled = false;
let beepTimer = null;
let titleTimer = null;
let lastKey = null;       // result.detectedAt we have already alerted on
let acknowledged = false;
let previewMode = false;  // "Preview alert" was clicked — freeze polling until acknowledged

/* ---------- sound + notifications ---------- */
async function enableAlerts() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === 'suspended') await audioCtx.resume();
    soundEnabled = true;
    blip(660, 0.09, 0.18);
  } catch (e) { /* ignore */ }

  if ('Notification' in window && Notification.permission === 'default') {
    try { await Notification.requestPermission(); } catch (e) { /* ignore */ }
  }
  updateEnableBtn();
}

function updateEnableBtn() {
  const b = $('enableBtn');
  const notif = ('Notification' in window) ? Notification.permission : 'unsupported';
  if (soundEnabled && notif === 'granted') {
    b.textContent = '✓ Sound + notifications on';
    b.classList.add('on');
  } else if (soundEnabled) {
    b.textContent = '✓ Sound on — click again to allow notifications';
    b.classList.remove('on');
  } else {
    b.textContent = '🔔 Enable sound + notifications';
    b.classList.remove('on');
  }
}

function blip(freq, dur, gain) {
  if (!soundEnabled || !audioCtx) return;
  const o = audioCtx.createOscillator();
  const g = audioCtx.createGain();
  o.type = 'square';
  o.frequency.value = freq;
  o.connect(g); g.connect(audioCtx.destination);
  const t = audioCtx.currentTime;
  g.gain.setValueAtTime(gain || 0.2, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + (dur || 0.15));
  o.start(t);
  o.stop(t + (dur || 0.15) + 0.02);
}

function startBeeping() {
  if (beepTimer) return;
  const salvo = () => { blip(880, 0.13, 0.25); setTimeout(() => blip(1175, 0.13, 0.25), 170); };
  salvo();
  beepTimer = setInterval(salvo, 1200);
}
function stopBeeping() {
  if (beepTimer) { clearInterval(beepTimer); beepTimer = null; }
}

function flashTitle(txt) {
  if (titleTimer) clearInterval(titleTimer);
  let on = false;
  titleTimer = setInterval(() => {
    document.title = on ? 'Buyback Watch' : ('🟢 ' + txt + ' — BUYBACK');
    on = !on;
  }, 900);
}

/* ---------- rendering ---------- */
function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? '—' : d.toLocaleTimeString();
}

function showWaiting(s) {
  document.body.className = 'waiting';
  $('waiting').hidden = false;
  $('alert').hidden = true;
  $('checkCount').textContent = (s && s.checkCount != null) ? s.checkCount : 0;
  $('lastCheck').textContent = fmtTime(s && s.checkedAt);
  $('httpStatus').textContent = (s && s.httpStatus != null) ? s.httpStatus : '—';

  const url = (s && s.url) || '';
  const a = $('targetUrl');
  a.textContent = url;
  a.href = url || '#';

  if (s && s.status === 'error') {
    $('statusLine').textContent = 'Connection problem: ' + (s.lastError || 'unknown') + ' — still retrying…';
  } else if (s) {
    $('statusLine').textContent = 'Not published yet. Still watching…';
  } else {
    $('statusLine').textContent = 'Waiting for the watcher to start…';
  }
}

function showAlert(s) {
  const r = s.result || {};
  document.body.className = acknowledged ? 'found ack' : 'found';
  document.documentElement.style.setProperty('--tier', r.tierColor || '#22c55e');
  $('waiting').hidden = true;
  $('alert').hidden = false;

  $('bigAmount').textContent = r.headlineAmountShort || r.headlineAmountText || 'PUBLISHED';
  $('fullAmount').textContent =
    (r.headlineAmountText && r.headlineAmountText !== r.headlineAmountShort) ? r.headlineAmountText : '';
  $('opType').textContent = r.operationType || 'Treasury buyback';
  $('tier').textContent = r.tier || '';
  $('maturity').textContent = r.maturityRange ? ('Maturity range · ' + r.maturityRange) : '';
  $('opDate').textContent = r.operationDate ? ('Operation date · ' + r.operationDate) : '';
  $('detectedAt').textContent = r.detectedAt ? ('Detected ' + fmtTime(r.detectedAt)) : '';
  $('parseNote').hidden = !!r.parsed;

  const link = $('pdfLink');
  link.href = r.pdfUrl || r.localPdf || '#';
}

function fireAlert(s) {
  const r = s.result || {};
  const short = r.headlineAmountShort || 'PUBLISHED';
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      const n = new Notification('Treasury buyback announced', {
        body: (r.headlineAmountText || 'Published') +
              (r.operationType ? ('  ·  ' + r.operationType) : '') +
              (r.maturityRange ? ('\n' + r.maturityRange) : ''),
        tag: 'buyback-' + (r.detectedAt || ''),
        requireInteraction: true
      });
      n.onclick = () => { window.focus(); n.close(); };
    } catch (e) { /* ignore */ }
  }
  startBeeping();
  flashTitle(short);
}

function acknowledge() {
  acknowledged = true;
  previewMode = false;
  stopBeeping();
  if (titleTimer) { clearInterval(titleTimer); titleTimer = null; }
  document.title = 'Buyback Watch';
  document.body.classList.add('ack');
}

function render(s) {
  if (s && s.found && s.result) {
    const key = s.result.detectedAt || 'found';
    const isNew = key !== lastKey;
    if (isNew) acknowledged = false;   // a fresh announcement re-arms the flash
    showAlert(s);
    if (isNew) {
      lastKey = key;
      fireAlert(s);
    }
  } else {
    showWaiting(s);
  }
}

async function poll() {
  if (previewMode) { setTimeout(poll, POLL_MS); return; }
  try {
    const res = await fetch(STATE_URL + '?_=' + Date.now(), { cache: 'no-store' });
    if (res.ok) {
      render(await res.json());
    } else {
      showWaiting(null);
    }
  } catch (e) {
    showWaiting(null);
  }
  setTimeout(poll, POLL_MS);
}

/* ---------- wire up ---------- */
$('enableBtn').addEventListener('click', enableAlerts);
$('ackBtn').addEventListener('click', acknowledge);
$('testBtn').addEventListener('click', () => {
  lastKey = null;
  acknowledged = false;
  previewMode = true;
  render({
    found: true,
    result: {
      detectedAt: new Date().toISOString(),
      headlineAmount: 12500000000,
      headlineAmountText: '$12,500,000,000',
      headlineAmountShort: '$12.5B',
      operationType: 'Nominal coupon buyback — PREVIEW',
      tier: 'HUGE  ( >= $10B )',
      tierColor: '#b91c1c',
      maturityRange: '10/15/2026 - 08/31/2028',
      operationDate: '(preview)',
      pdfUrl: '#',
      parsed: true
    }
  });
});

updateEnableBtn();
poll();
