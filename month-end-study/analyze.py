"""Statistics for the month-end close study: reads output/events.csv and paths.npz from extract.py.

For each product x reference time (UK close, London 4pm fix, US close) x window (30 min
before, 30 min after) it tests whether the month-end move is consistently one way, and
compares it with the same window on every other weekday. Writes output/summary.json.
"""
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from extract import CFDS, MARKETS, STANDINS, Settings

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'output'
EUREX = {'FESX', 'FDAX', 'FESB', 'FGBS', 'FGBM', 'FGBL', 'FGBX', 'FOAT', 'FBTP'}
THIN = 0.10  # windows with under 10% of the product's usual activity are dropped as stale
MIN_MONTHS = 12  # a test needs at least a year of month-ends to get a verdict
# Equal-weight average of the CME currency futures on each day two or more were recorded.
# Every one is quoted in dollars per unit of foreign currency, so up means a weaker dollar.
BASKET, BASKET_MEMBERS = 'FXB', ('6E', '6B', '6A', '6J', '6S', '6C')


def add_basket(rows, groups, path_of):
    by = {}
    for r in rows:
        if r['root'] in BASKET_MEMBERS and not r['thin']:
            by.setdefault((r['date'], r['session']), []).append(r)
    for (day, session), members in sorted(by.items()):
        if len(members) < 2:
            continue
        b = dict(members[0], root=BASKET, contract='basket', standin=0, note='', thin=False,
                 multiplier=float('nan'), pre_pts=None, post_pts=None,
                 activity=sum(r['activity'] for r in members))
        for w in ('pre', 'post'):
            vals = [r[w] for r in members if r[w] is not None]
            b[w] = float(np.mean(vals)) if len(vals) >= 2 else None
            b['vol_' + w] = sum(r['vol_' + w] for r in members)
            b['n_' + w] = sum(r['n_' + w] for r in members)
        mtd = [r['mtd'] for r in members if r['mtd'] is not None]
        b['mtd'] = float(np.mean(mtd)) if b['monthend'] and len(mtd) == len(members) else None
        # Basket "price" path: the members' paths rebased to 1 and averaged, high/low from that path.
        normed = [path_of[k] / path_of[k][0] for k in (f"{r['root']}|{day}|{session}" for r in members)
                  if k in path_of and np.isfinite(path_of[k]).all() and path_of[k][0] > 0]
        if len(normed) >= 2:
            p = np.mean(normed, axis=0)
            path_of[f'{BASKET}|{day}|{session}'] = p
            b.update(p_start=p[0], p_close=p[30], p_end=p[60], pre_hi=p[:31].max(), pre_lo=p[:31].min(),
                     post_hi=p[30:].max(), post_lo=p[30:].min())
        else:
            b.update(p_start=float('nan'), p_close=float('nan'), p_end=float('nan'), pre_hi=float('nan'),
                     pre_lo=float('nan'), post_hi=float('nan'), post_lo=float('nan'))
        rows.append(b)
        groups.setdefault((BASKET, session), []).append(b)


# ---------------------------------------------------------------- distributions

def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > 1e-300 else 1e-300)
            c = 1 + aa / c
            c = c if abs(c) > 1e-300 else 1e-300
            h *= d * c
        if abs(d * c - 1) < 3e-14:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b


def t_pvalue(t, df):
    """Two-sided p-value of Student's t."""
    if not np.isfinite(t) or df <= 0:
        return float('nan')
    return _betai(df / 2, 0.5, df / (df + t * t))


def sign_pvalue(up, down):
    """Two-sided exact sign test."""
    n = up + down
    if n == 0:
        return float('nan')
    k = min(up, down)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def one_sample(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return dict(n=n, mean=float(x.mean()) if n else None, t=None, p=None)
    sd = x.std(ddof=1)
    t = x.mean() / (sd / math.sqrt(n)) if sd > 0 else float('nan')
    return dict(n=n, mean=float(x.mean()), median=float(np.median(x)), std=float(sd), t=float(t), p=t_pvalue(t, n - 1))


def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return None, None
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    if va + vb == 0:
        return None, None
    t = (a.mean() - b.mean()) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return float(t), t_pvalue(t, df)


def bh(pvalues):
    """Benjamini-Hochberg q-values (None stays None)."""
    idx = [i for i, p in enumerate(pvalues) if p is not None and np.isfinite(p)]
    order = sorted(idx, key=lambda i: pvalues[i])
    q = [None] * len(pvalues)
    running = 1.0
    for rank in range(len(order), 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * len(order) / rank)
        q[i] = running
    return q


def fix_scale(rows):
    """Some recordings store real prices where their Symbol Settings imply scaled ones (6AH26 holds
    0.6666, not 6666). Rescale each row's multiplier by the power of ten that brings its price in
    line with its product's median, so points and ticks come out right. Returns stay unaffected."""
    def price(r):
        p = num(r['p_close'])
        return p if np.isfinite(p) and p > 0 else num(r['p_start'])
    by = {}
    for r in rows:
        p = price(r)
        if np.isfinite(p) and p > 0:
            by.setdefault(r['root'], []).append(p * num(r['multiplier']))
    typical = {root: np.median(v) for root, v in by.items()}
    for r in rows:
        p, m = price(r), num(r['multiplier'])
        if r['root'] in typical and np.isfinite(p) and p > 0:
            r['multiplier'] = m * 10.0 ** round(math.log10(typical[r['root']] / (p * m)))
        else:
            r['multiplier'] = m


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float('nan')
    return f


def clean(v, digits=3):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else round(float(v), digits)
    return v


# ---------------------------------------------------------------- main

def main():
    rows = list(csv.DictReader(open(OUT / 'events.csv', newline='')))
    coverage = json.loads((OUT / 'coverage.json').read_text())
    archive = np.load(OUT / 'paths.npz')
    path_of = {k: p for k, p in zip(archive['key'].tolist(), archive['path'])}
    settings = Settings(Path(r'C:\SierraChart\Data'))

    fix_scale(rows)
    for r in rows:
        for k in ('p_start', 'p_close', 'p_end', 'mtd_ref', 'multiplier', 'vol_pre', 'vol_post',
                  'pre_hi', 'pre_lo', 'post_hi', 'post_lo'):
            r[k] = num(r[k])
        for k in ('n_pre', 'n_post', 'monthend', 'standin'):
            r[k] = int(r[k])
        r['activity'] = r['n_pre'] + r['n_post']
        ok_pre = r['n_pre'] > 0 and np.isfinite(r['p_start']) and np.isfinite(r['p_close'])
        ok_post = r['n_post'] > 0 and np.isfinite(r['p_close']) and np.isfinite(r['p_end'])
        r['pre'] = (r['p_close'] / r['p_start'] - 1) * 1e4 if ok_pre else None
        r['post'] = (r['p_end'] / r['p_close'] - 1) * 1e4 if ok_post else None
        r['pre_pts'] = (r['p_close'] - r['p_start']) * r['multiplier'] if ok_pre else None
        r['post_pts'] = (r['p_end'] - r['p_close']) * r['multiplier'] if ok_post else None
        r['mtd'] = (r['p_start'] / r['mtd_ref'] - 1) * 1e4 if r['monthend'] and np.isfinite(r['mtd_ref']) \
            and np.isfinite(r['p_start']) else None

    # Drop stale windows: far less activity than the product's typical day at that time.
    groups = {}
    for r in rows:
        groups.setdefault((r['root'], r['session']), []).append(r)
    for key, items in groups.items():
        typical = np.median([r['activity'] for r in items])
        for r in items:
            r['thin'] = r['activity'] < THIN * typical
            if r['thin']:
                r['pre'] = r['post'] = None

    add_basket(rows, groups, path_of)
    names = {m[0]: (m[1], m[2]) for m in MARKETS} | {c[0]: (c[1], c[2]) for c in CFDS}
    names[BASKET] = ('Currency basket vs USD (6E 6B 6A 6J 6S 6C)', 'Currencies')
    cfd_roots = {c[0] for c in CFDS}

    def tick_spec(root):
        if root in cfd_roots:
            conf = settings.lookup(root + '.scid')
        else:
            used = {r['contract'][:-3] for r in groups.get((root, 'US'), []) + groups.get((root, 'UK'), [])}
            base = root if root in used or not used else sorted(used)[0]
            conf = settings.lookup(f'{base}Z26-EUREX.scid' if root in EUREX else f'{base}Z26_FUT_CME.scid')
            if base != root:
                conf = dict(conf, standin=base)
        tick = num(conf.get('tick-size'))
        value = num(conf.get('currency-value-per-tick'))
        return dict(tick=tick if np.isfinite(tick) and tick > 0 else None,
                    tick_value=value if np.isfinite(value) else None,
                    currency=conf.get('currency') or ('EUR' if root in EUREX else 'USD'),
                    spec_from=conf.get('standin'))

    # ES month-to-date at each month-end, for the equity-rebalancing conditional.
    es_mtd = {(r['date'], r['session']): r['mtd'] for r in groups.get(('ES', 'US'), []) + groups.get(('ES', 'UK'), [])
              + groups.get(('ES', 'FIX'), []) if r['monthend'] and r['mtd'] is not None}

    stats = []
    for (root, session), items in sorted(groups.items()):
        me = sorted([r for r in items if r['monthend']], key=lambda r: r['date'])
        base = [r for r in items if not r['monthend']]
        spec = tick_spec(root)
        for window in ('pre', 'post'):
            x = [r[window] for r in me if r[window] is not None]
            if len(x) < 3:
                continue
            xb = np.array([r[window] for r in base if r[window] is not None])
            s = one_sample(x)
            up, down = sum(v > 0 for v in x), sum(v < 0 for v in x)
            pts = [r[window + '_pts'] for r in me if r[window] is not None]
            sb = one_sample(xb) if len(xb) > 1 else dict(n=len(xb), mean=None, std=None)
            wt, wp = welch(x, xb)
            # Volatility-adjusted: each month-end divided by the spread of nearby normal days.
            dates_b = np.array([np.datetime64(r['date']) for r in base if r[window] is not None])
            z = []
            for r in me:
                if r[window] is None:
                    continue
                near = np.abs((dates_b - np.datetime64(r['date'])).astype(int)) <= 90
                if near.sum() >= 15:
                    sd = xb[near].std(ddof=1)
                    if sd > 0:
                        z.append(r[window] / sd)
            sz = one_sample(z) if len(z) > 2 else dict(t=None, mean=None)
            # Conditionals: aligned with the product's own month so far, and with the S&P's.
            own = [(r[window] * np.sign(r['mtd'])) for r in me if r[window] is not None and r['mtd']]
            es = [(r[window] * np.sign(es_mtd[(r['date'], session)])) for r in me
                  if r[window] is not None and es_mtd.get((r['date'], session))]
            so, se = one_sample(own) if len(own) > 2 else {}, one_sample(es) if len(es) > 2 else {}
            half = len(x) // 2
            h1, h2 = x[:half], x[half:]
            vol_key = 'vol_' + window if root not in cfd_roots else 'n_' + window
            vme = np.median([r[vol_key] for r in me if r[window] is not None])
            vb = np.median([r[vol_key] for r in base if r[window] is not None]) if len(xb) else float('nan')
            tick = spec['tick']
            pts = [v for v in pts if v is not None]
            mean_pts = float(np.mean(pts)) if pts else float('nan')
            stats.append(dict(
                root=root, session=session, window=window, n=s['n'], mean=s['mean'], median=s.get('median'),
                std=s.get('std'), t=s.get('t'), p=s.get('p'), up=up, down=down,
                hit=up / (up + down) if up + down else None, p_sign=sign_pvalue(up, down),
                mean_pts=mean_pts, mean_ticks=mean_pts / tick if tick else None,
                mean_value=mean_pts / tick * spec['tick_value'] if tick and spec['tick_value'] else None,
                base_n=sb['n'], base_mean=sb.get('mean'), base_std=sb.get('std'),
                base_hit=float((xb > 0).sum() / max(1, (xb != 0).sum())) if len(xb) else None,
                welch_t=wt, welch_p=wp, z_mean=sz.get('mean'), z_t=sz.get('t'),
                vol_ratio=float(vme / vb) if vb and np.isfinite(vb) and vb > 0 else None,
                own_n=so.get('n'), own_mean=so.get('mean'), own_t=so.get('t'), own_p=so.get('p'),
                own_hit=float(np.mean(np.array(own) > 0)) if len(own) > 2 else None,
                es_n=se.get('n'), es_mean=se.get('mean'), es_t=se.get('t'), es_p=se.get('p'),
                es_hit=float(np.mean(np.array(es) > 0)) if len(es) > 2 else None,
                h1_n=len(h1), h1_mean=float(np.mean(h1)) if h1 else None,
                h1_hit=float(np.mean(np.array(h1) > 0)) if h1 else None,
                h2_n=len(h2), h2_mean=float(np.mean(h2)) if h2 else None,
                h2_hit=float(np.mean(np.array(h2) > 0)) if h2 else None,
                last12_mean=float(np.mean(x[-12:])), last12_hit=float(np.mean(np.array(x[-12:]) > 0)),
                **{k: spec[k] for k in ('tick', 'tick_value', 'currency', 'spec_from')}))

    eligible = [s['p'] if s['n'] >= MIN_MONTHS else None for s in stats]
    for s, q, qw in zip(stats, bh(eligible), bh([s['welch_p'] if s['n'] >= MIN_MONTHS else None for s in stats])):
        s['q'], s['q_welch'] = q, qw

    # Average minute paths, month-end vs normal days, in bp from close-30m.
    paths = {}
    for (root, session), items in groups.items():
        out = {}
        for label, pick in (('me', 1), ('base', 0)):
            arr = []
            for r in items:
                if r['monthend'] != pick or r['thin']:
                    continue
                p = path_of.get(f"{root}|{r['date']}|{session}")
                if p is not None and np.isfinite(p).all() and p[0] > 0:
                    arr.append((p / p[0] - 1) * 1e4)
            if arr:
                out[label] = [round(float(v), 2) for v in np.mean(arr, axis=0)]
                out[label + '_n'] = len(arr)
        if out:
            paths[f'{root}|{session}'] = out

    events = [dict(root=r['root'], date=r['date'], session=r['session'], contract=r['contract'],
                   standin=r['standin'], note=r['note'], close_utc=r['close_utc'],
                   pre=clean(r['pre'], 2), post=clean(r['post'], 2), mtd=clean(r['mtd'], 1),
                   pre_pts=clean(r['pre_pts'], 6), post_pts=clean(r['post_pts'], 6),
                   pre_hi=clean((r['pre_hi'] / r['p_start'] - 1) * 1e4, 2) if r['pre'] is not None else None,
                   pre_lo=clean((r['pre_lo'] / r['p_start'] - 1) * 1e4, 2) if r['pre'] is not None else None,
                   post_hi=clean((r['post_hi'] / r['p_close'] - 1) * 1e4, 2) if r['post'] is not None else None,
                   post_lo=clean((r['post_lo'] / r['p_close'] - 1) * 1e4, 2) if r['post'] is not None else None,
                   price=clean(r['p_close'] * r['multiplier'], 6))
              for r in rows if r['monthend']]

    roots = []
    basket_days = sorted({r['date'] for r in groups.get((BASKET, 'FIX'), [])})
    for c in coverage['roots'] + [dict(root=BASKET, status='ok', first=basket_days[0] if basket_days else None,
                                       last=basket_days[-1] if basket_days else None,
                                       roots_used=list(BASKET_MEMBERS))]:
        root = c['root']
        n = {s: len([e for e in events if e['root'] == root and e['session'] == s and e['pre'] is not None])
             for s in ('UK', 'FIX', 'US')}
        roots.append(dict(root=root, name=names[root][0], sector=names[root][1], status=c['status'],
                          cfd=root in cfd_roots, first=c.get('first'), last=c.get('last'),
                          roots_used=c.get('roots_used', []), standins=STANDINS.get(root, []), n=n))

    summary = dict(generated=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                   extracted=coverage['generated'], roots=roots,
                   stats=[{k: clean(v, 5) for k, v in s.items()} for s in stats], paths=paths, events=events)
    (OUT / 'summary.json').write_text(json.dumps(summary, separators=(',', ':')))
    export_dashboard(stats, events, paths, roots, names)
    print(f'{len(stats)} tests, {len(events)} month-end events')
    top = sorted([s for s in stats if s['n'] >= 8 and s['t'] is not None and np.isfinite(s['t'])],
                 key=lambda s: -abs(s['t']))[:40]
    print(f"{'root':6}{'sess':5}{'win':5}{'n':>4}{'mean':>8}{'hit':>6}{'t':>7}{'p':>8}{'q':>7}"
          f"{'base':>7}{'wP':>8}{'ztt':>6}{'vol':>6}{'h1':>7}{'h2':>7}{'ticks':>7}")
    for s in top:
        print(f"{s['root']:6}{s['session']:5}{s['window']:5}{s['n']:>4}{s['mean']:>8.2f}{s['hit'] or 0:>6.0%}"
              f"{s['t']:>7.2f}{s['p']:>8.4f}{s['q'] or 1:>7.3f}{s['base_mean'] or 0:>7.2f}{s['welch_p'] or 1:>8.4f}"
              f"{s['z_t'] or 0:>6.2f}{s['vol_ratio'] or 0:>6.2f}{s['h1_mean'] or 0:>7.2f}{s['h2_mean'] or 0:>7.2f}"
              f"{s['mean_ticks'] or 0:>7.1f}")


SESSION_LABEL = {'UK': 'UK close 16:30 London', 'FIX': 'London 4pm fix', 'US': 'US close 16:00 New York'}
WINDOW_LABEL = {'pre': '30 min before', 'post': '30 min after'}


def verdict(s):
    """Strong: survives the false-discovery cut, beats normal days and holds in both halves."""
    if s['n'] < MIN_MONTHS or s['p'] is None or not np.isfinite(s['p']):
        return 'Too few months'
    agree = s['h1_mean'] is not None and s['h2_mean'] is not None and np.sign(s['h1_mean']) == np.sign(s['h2_mean'])
    beats = s['welch_p'] is not None and s['welch_p'] < 0.05
    if s['q'] is not None and s['q'] < 0.10 and agree and beats:
        return 'Strong'
    if s['p'] < 0.05 and agree and beats:
        return 'Promising'
    if s['p'] < 0.10 or (s['p_sign'] is not None and s['p_sign'] < 0.10):
        return 'Weak'
    return 'No edge'


def export_dashboard(stats, events, paths, roots, names):
    """Row files for the dashboard: one per table it draws."""
    out = OUT / 'dash'
    out.mkdir(exist_ok=True)
    rank = {'Strong': 0, 'Promising': 1, 'Weak': 2, 'No edge': 3, 'Too few months': 4}
    rows = []
    for s in stats:
        v = verdict(s)
        rows.append({'id': f"{s['root']}|{s['session']}|{s['window']}", 'root': s['root'],
                     'name': names[s['root']][0], 'sector': names[s['root']][1],
                     'session': s['session'], 'window': s['window'],
                     'reference': SESSION_LABEL[s['session']], 'when': WINDOW_LABEL[s['window']],
                     'verdict': v, 'verdict_rank': rank[v],
                     'direction': 'Up' if (s['mean'] or 0) > 0 else 'Down',
                     'halves_agree': bool(s['h1_mean'] is not None and s['h2_mean'] is not None
                                          and np.sign(s['h1_mean']) == np.sign(s['h2_mean'])),
                     **{k: clean(s[k], 5) for k in (
                         'n', 'mean', 'median', 'std', 't', 'p', 'q', 'up', 'down', 'hit', 'p_sign',
                         'mean_pts', 'mean_ticks', 'mean_value', 'currency', 'base_n', 'base_mean', 'base_std',
                         'base_hit', 'welch_t', 'welch_p', 'q_welch', 'z_t', 'vol_ratio', 'own_n', 'own_mean',
                         'own_t', 'own_p', 'own_hit', 'es_n', 'es_mean', 'es_t', 'es_p', 'es_hit', 'h1_n',
                         'h1_mean', 'h1_hit', 'h2_n', 'h2_mean', 'h2_hit', 'last12_mean', 'last12_hit', 'tick')}})
    rows.sort(key=lambda r: (r['verdict_rank'], -abs(r['t'] or 0)))
    (out / 'stats.json').write_text(json.dumps(rows, separators=(',', ':')))
    ev = [dict(id=f"{e['root']}|{e['session']}|{e['date']}", **e) for e in events
          if e['pre'] is not None or e['post'] is not None]
    (out / 'events.json').write_text(json.dumps(ev, separators=(',', ':')))
    long = []
    for key, p in paths.items():
        root, session = key.split('|')
        for kind, label in (('me', 'Month-end'), ('base', 'Normal days')):
            if kind in p:
                long += [dict(id=f'{key}|{kind}|{i - 30}', series=key, root=root, session=session, kind=label,
                              minute=i - 30, bps=v, days=p[kind + '_n']) for i, v in enumerate(p[kind])]
    (out / 'paths.json').write_text(json.dumps(long, separators=(',', ':')))
    cov = [dict(root=r['root'], name=r['name'], sector=r['sector'], status=r['status'],
                kind='CFD' if r['cfd'] else 'Future', first=r['first'], last=r['last'],
                months_uk=r['n']['UK'], months_fix=r['n']['FIX'], months_us=r['n']['US'],
                contracts=', '.join(r['roots_used']) or '—') for r in roots]
    (out / 'coverage.json').write_text(json.dumps(cov, separators=(',', ':')))
    print('dashboard files:', {p.name: p.stat().st_size for p in out.iterdir()})


if __name__ == '__main__':
    main()
