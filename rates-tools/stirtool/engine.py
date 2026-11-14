"""Background engine: polls Sierra, refreshes public data, refits the curve and builds the state
that the web page and the strip display."""
import datetime as dt
import threading
import time
import traceback

import numpy as np

from . import calendar_us as cal
from . import model as mdl
from . import scenario as scn
from . import sierra, sources

POLL_S = 0.25
STALE_S = 600           # a quote older than this (vs the newest tick in the strip) is flagged


def _f(v, nd=6):
    return None if v is None else round(float(v), nd)


def _age_weight(age_s):
    if age_s is None:
        return 0.05
    if age_s <= 120:
        return 1.0
    if age_s <= 600:
        return 0.5
    if age_s <= 1800:
        return 0.25
    return 0.1


class Engine:
    def __init__(self, data_dir, chartbook):
        self.feed = sierra.SierraFeed(data_dir, chartbook)
        self.data_dir, self.chartbook = data_dir, chartbook
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.version = 0
        self.state = {'status': 'starting'}
        self.scenario = {'mode': 'whole', 'fade': 0.6, 'edits': {}}     # edits: {meeting iso: bp}
        self.focus = {}                                                    # speaker id -> meeting iso
        self.model = None
        self.fix = None
        self.meetings = []
        self.speakers = []
        self.info = {}
        self.errors = {}
        self._settle_cache = {}
        self._theta = None
        self._stop = threading.Event()

    # ---- control from the web page ---------------------------------------------------
    def set_scenario(self, mode=None, fade=None, set_edits=None, reset=False):
        with self.lock:
            if reset:
                self.scenario['edits'] = {}
            if mode in scn.MODES:
                self.scenario['mode'] = mode
            if fade is not None:
                self.scenario['fade'] = min(max(float(fade), 0.0), 1.0)
            for k, v in (set_edits or {}).items():
                if v is None:
                    self.scenario['edits'].pop(k, None)
                else:
                    self.scenario['edits'][k] = float(v)
            self._recompute()

    def speaker_action(self, body):
        with self.lock:
            act = body.get('action')
            if act == 'focus':
                self.focus[body['id']] = body.get('meeting')
            elif act == 'add':
                rows = sources.manual_speakers()
                when = dt.datetime.fromisoformat(body['when_et'])
                rows.append({'id': f'manual-{int(time.time() * 1000)}', 'speaker': body['speaker'].strip(),
                             'kind': body.get('kind') or 'Speech', 'topic': body.get('topic', ''), 'where': '',
                             'when_et': when.isoformat(timespec='minutes'), 'time_known': True, 'source': 'added by you'})
                sources.save_manual_speakers(rows)
            elif act == 'remove':
                sources.save_manual_speakers([r for r in sources.manual_speakers() if r['id'] != body.get('id')])
            self._refresh_speakers(force=True)
            self._recompute()

    # ---- loop --------------------------------------------------------------------------
    def start(self):
        threading.Thread(target=self._run, name='engine', daemon=True).start()

    def stop(self):
        self._stop.set()

    def _guard(self, name, fn):
        try:
            fn()
            self.errors.pop(name, None)
        except Exception as exc:
            self.errors[name] = f'{type(exc).__name__}: {exc}'
            traceback.print_exc()

    def _refresh_fixings(self):
        fx = sources.fixings()
        self.info['fixings'] = fx['info']
        if not self.fix or fx['effr'] != self.fix['effr'] or fx['sofr'] != self.fix['sofr']:
            self.fix = fx
            self.model = None

    def _refresh_meetings(self):
        meetings, info = sources.fomc_meetings(dt.date.today())
        self.info['fomc'] = info
        if meetings != self.meetings:
            self.meetings = meetings
            self.model = None

    def _refresh_speakers(self, force=False):
        if force:
            rows, info = sources.speakers(cal.now_utc())
        else:
            rows, info = sources.speakers(cal.now_utc())
        self.speakers, self.info['speakers'] = rows, info

    def _run(self):
        sierra.background_io()
        due = {'discover': 0, 'fix': 0, 'fomc': 0, 'spk': 0, 'tick': 0}
        last_td = None
        while not self._stop.is_set():
            now = time.time()
            with self.lock:
                if now >= due['discover']:
                    self._guard('sierra', lambda: self.feed.discover() and setattr(self, 'model', None))
                    due['discover'] = now + 20
                if now >= due['fix']:
                    self._guard('fixings', self._refresh_fixings)
                    due['fix'] = now + 300
                if now >= due['fomc']:
                    self._guard('fomc', self._refresh_meetings)
                    due['fomc'] = now + 3600
                if now >= due['spk']:
                    self._guard('speakers', self._refresh_speakers)
                    due['spk'] = now + 900
                changed = False
                try:
                    changed = self.feed.poll()
                except Exception as exc:
                    self.errors['sierra'] = str(exc)
                td = cal.trade_date(cal.now_utc())
                if changed or self.model is None or td != last_td or now >= due['tick']:
                    last_td = td
                    self._guard('model', self._recompute)
                    due['tick'] = now + 2
            self._stop.wait(POLL_S)

    # ---- computation -------------------------------------------------------------------
    def _ensure_model(self, today):
        if self.model is not None and self.model.today == today:
            return
        if not self.fix or not self.meetings or not self.feed.symbols:
            raise RuntimeError('waiting for data (fixings, FOMC dates or Sierra contracts)')
        contracts = sorted((mdl.parse_symbol(s) for s in self.feed.symbols), key=lambda c: (c.product != 'ZQ', c.start))
        contracts = [c for c in contracts if c.end > today]
        self.model = mdl.Model(contracts, self.meetings, self.fix['effr'], self.fix['sofr'], today)
        self._settle_cache.clear()
        self._theta = None

    def _settlement_fit(self, prev):
        key = (prev, self.model.last_effr, len(self.model.contracts))
        if key not in self._settle_cache:
            settle = {}
            for c in self.model.contracts:
                px, src = self.feed.settlement(c.symbol, prev)
                settle[c.symbol] = (px, src)
            prices = {s: v[0] for s, v in settle.items() if v[0] is not None}
            fit = self.model.fit(prices) if len(prices) >= 3 else None
            self._settle_cache = {key: (settle, fit)}
        return self._settle_cache[key]

    def _recompute(self):
        now = cal.now_utc()
        today = cal.to_et(now).date()
        td = cal.trade_date(now)
        prev = cal.prev_weekday(td)
        self._ensure_model(today)
        m = self.model
        quotes = self.feed.quotes()
        feed_time = max((q.last_time for q in quotes.values() if q.last_time), default=None)
        open_now = cal.globex_open(now)

        current, weights, ages = {}, {}, {}
        for c in m.contracts:
            q = quotes.get(c.symbol)
            if q and q.mid is not None:
                current[c.symbol] = q.mid
                age = (feed_time - q.last_time).total_seconds() if q.last_time and feed_time else None
                ages[c.symbol] = age
                weights[c.symbol] = _age_weight(age)
        settle, fit_settle = self._settlement_fit(prev)
        fit_now = m.fit(current, weights, start=self._theta) if len(current) >= 3 else fit_settle
        if fit_now is None:
            raise RuntimeError('not enough prices to fit the curve')
        self._theta = np.concatenate([fit_now.x, [fit_now.sp]])

        # scenario
        idx = {mt['date'].isoformat(): k for k, mt in enumerate(m.meetings)}
        sc = self.scenario
        edits = {idx[d]: v for d, v in sc['edits'].items() if d in idx}
        x_new = scn.apply_edits(fit_now.x, edits, sc['mode'], sc['fade'])
        rep = scn.reprice(m, fit_now, current, x_new, today)
        lags = scn.lag(fit_now, fit_settle, m, today) if fit_settle else {}

        cum_now = np.cumsum(fit_now.x)
        cum_set = np.cumsum(fit_settle.x) if fit_settle else None
        cum_new = np.cumsum(x_new)
        meetings = []
        for k, mt in enumerate(m.meetings):
            meetings.append({'date': mt['date'].isoformat(), 'assumed': mt['assumed'],
                             'move_bp': _f(fit_now.x[k], 3), 'priced_bp': _f(cum_now[k], 3),
                             'settle_bp': _f(cum_set[k], 3) if cum_set is not None else None,
                             'change_bp': _f(cum_now[k] - cum_set[k], 3) if cum_set is not None else None,
                             'scenario_bp': _f(cum_new[k], 3), 'edited': mt['date'].isoformat() in sc['edits'],
                             'effr_after': _f(m.base + cum_now[k] / 100, 4)})

        contracts = []
        for c in m.contracts:
            q = quotes.get(c.symbol)
            tick = mdl.tick_size(c, today)
            st_px, st_src = settle.get(c.symbol, (None, None))
            mid = current.get(c.symbol)
            age = ages.get(c.symbol)
            r = rep[c.symbol]
            lg = lags.get(c.symbol)
            contracts.append({
                'symbol': c.symbol, 'product': c.product, 'label': c.label,
                'period': [c.start.isoformat(), c.end.isoformat()],
                'bid': _f(q.bid if q else None), 'ask': _f(q.ask if q else None), 'last': _f(q.last if q else None),
                'mid': _f(mid), 'last_time': q.last_time.isoformat() if q and q.last_time else None,
                'age_s': _f(age, 1), 'stale': age is None or age > STALE_S, 'volume': q.volume if q else 0,
                'has_ticks': self.feed.has_ticks(c.symbol),
                'settle': _f(st_px), 'settle_source': st_src,
                'chg_ticks': _f((mid - st_px) / tick, 2) if mid is not None and st_px is not None else None,
                'fair': _f(fit_now.fair[c.symbol]), 'resid_bp': _f(fit_now.resid.get(c.symbol), 3),
                'lag_ticks': _f(lg['ticks'], 2) if lg else None, 'lag_bp': _f(lg['bp'], 3) if lg else None,
                'tick': tick, 'tick_value': r['tick_value'],
                'target': _f(r['target']), 'target_exact': _f(r['target_exact']),
                'scn_ticks': _f(r['ticks'], 2), 'scn_bp': _f(r['move_bp'], 3), 'scn_usd': _f(r['usd_per_lot'], 2)})

        # speakers and their ladders (one ladder per focus meeting)
        spk, ladders = [], {}
        for s in self.speakers:
            when = dt.datetime.fromisoformat(s['when_et']).date()
            default = next((mt['date'].isoformat() for mt in m.meetings if mt['date'] >= when), None)
            focus = self.focus.get(s['id']) or default
            if focus in idx and focus not in ladders:
                ladders[focus] = scn.ladder(m, fit_now, current, idx[focus], sc['mode'], sc['fade'], today)
            spk.append({**s, 'focus_meeting': focus})
        for lad in ladders.values():
            for col in lad['outcomes']:
                col['contracts'] = {s: {'target': _f(v['target']), 'ticks': _f(v['ticks'], 2)}
                                    for s, v in col['contracts'].items()}
                col['path_bp'] = [_f(v, 2) for v in col['path_bp']]

        fx = self.fix
        status = 'closed' if not open_now else ('live' if feed_time and (now - feed_time).total_seconds() < 120 else 'quiet')
        self.state = {
            'version': self.version + 1, 'now_utc': now.isoformat(), 'today': today.isoformat(),
            'trade_date': td.isoformat(), 'prev_trade_date': prev.isoformat(), 'globex_open': open_now,
            'feed': {'status': status, 'last_tick_utc': feed_time.isoformat() if feed_time else None,
                     'age_s': _f((now - feed_time).total_seconds(), 1) if feed_time else None,
                     'data_dir': self.data_dir, 'chartbook': self.chartbook},
            'rates': {'effr': m.base, 'effr_date': m.last_effr.isoformat(),
                      'sofr': fx['sofr'][m.last_sofr], 'sofr_date': m.last_sofr.isoformat(),
                      'target': list(fx['target']), 'spread_bp': _f(fit_now.sp, 3),
                      'spread_prior_bp': _f(m.spread_prior, 3)},
            'meetings': meetings, 'contracts': contracts,
            'scenario': {**sc, 'active': bool(sc['edits'])},
            'speakers': spk, 'ladders': ladders,
            'sources': self.info, 'errors': dict(self.errors),
        }
        self.version += 1
        self.changed.notify_all()

    def snapshot(self):
        with self.lock:
            return self.state, self.version
