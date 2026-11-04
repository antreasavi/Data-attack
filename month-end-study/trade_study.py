"""Trade plans for the Promising month-end tests: a second check, entry/exit timing and tick stops.

Needs the extract.py output (with minute highs and lows) and `python analyze.py`
(output/dash/stats.json). `python trade_study.py [events folder]` reads output/ by default. For each Promising test it:

1. re-derives the month-end move from the minute data and checks it against random sets of
   normal days, a bootstrap interval, the median and the mean without its largest month;
2. simulates every entry and exit on a 5-minute grid across the hour around the reference
   time, in the test's direction, with stop-losses from 3 to 60 ticks and with none, after costs;
3. picks the plan that made the most per tick risked (smoothed over neighbouring plans so one
   lucky cell can't win) and checks that choice out of sample by leaving each month out in turn.

Writes output/trade/plans.json, grid.json and trades.json.
"""
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from analyze import BASKET, BASKET_MEMBERS, THIN, clean, fix_scale
from extract import LON, NY, Settings

HERE = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'output'
TRADE = HERE / 'output' / 'trade'
COMMISSION = 4.50      # assumed $ per round turn
SLIPPAGE_TICKS = 1.0   # assumed ticks lost per round turn (crossing the spread)
STEP = 5
READ_MIN = 1.0         # ticks a trade after costs, with no stop, for a test to count as still paying
STOPS = [3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, None]
BASKET_STOPS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, None]   # bp
REF = {'FIX': (LON, 16, 0, 'London'), 'UK': (LON, 16, 30, 'London'), 'US': (NY, 16, 0, 'New York')}
rng = np.random.default_rng(7)


def clock(session, minute):
    zone, hh, mm, city = REF[session]
    t = datetime(2026, 1, 15, hh, mm) + timedelta(minutes=minute)
    return f"{t:%H:%M} {city}"


def load():
    rows = list(csv.DictReader(open(SOURCE / 'events.csv', newline='')))
    fix_scale(rows)
    z = np.load(SOURCE / 'paths.npz')
    index = {k: i for i, k in enumerate(z['key'].tolist())}
    groups = {}
    for r in rows:
        r['activity'] = int(r['n_pre']) + int(r['n_post'])
        groups.setdefault((r['root'], r['session']), []).append(r)
    for items in groups.values():
        typical = np.median([r['activity'] for r in items])
        for r in items:
            r['thin'] = r['activity'] < THIN * typical
    return groups, z['path'], z['high'], z['low'], index


def series(groups, path, high, low, index, root, session, monthend):
    """Per-day arrays: price at each minute (61) and each minute's high/low (60), gaps filled."""
    out = []
    for r in groups.get((root, session), []):
        if int(r['monthend']) != monthend or r['thin']:
            continue
        i = index.get(f"{root}|{r['date']}|{session}")
        if i is None:
            continue
        c = path[i]
        hi = np.where(np.isnan(high[i]), c[1:], high[i])
        lo = np.where(np.isnan(low[i]), c[1:], low[i])
        out.append(dict(date=r['date'], c=c, hi=hi, lo=lo, contract=r['contract'], mult=float(r['multiplier'])))
    return sorted(out, key=lambda e: e['date'])


def basket(groups, path, high, low, index, session, monthend, specs):
    by = {}
    for root in BASKET_MEMBERS:
        for e in series(groups, path, high, low, index, root, session, monthend):
            if np.isfinite(e['c']).all() and e['c'][0] > 0:
                by.setdefault(e['date'], []).append((root, e))
    out = []
    for day, members in sorted(by.items()):
        if len(members) < 2:
            continue
        p0 = [e['c'][0] for _, e in members]
        c = np.mean([e['c'] / b for (_, e), b in zip(members, p0)], axis=0) * 1e4
        hi = np.mean([e['hi'] / b for (_, e), b in zip(members, p0)], axis=0) * 1e4
        lo = np.mean([e['lo'] / b for (_, e), b in zip(members, p0)], axis=0) * 1e4
        cost = np.mean([specs[root]['cost_ticks'] * specs[root]['tick'] / (e['c'][0] * e['mult']) * 1e4 for root, e in members])
        out.append(dict(date=day, c=c, hi=hi, lo=lo, contract='basket', mult=1.0, cost=cost))
    return out


def window_returns(events, window):
    a, b = (0, 30) if window == 'pre' else (30, 60)
    return np.array([(e['c'][b] / e['c'][a] - 1) * 1e4 for e in events
                     if np.isfinite(e['c'][a]) and np.isfinite(e['c'][b]) and e['c'][a] > 0])


def second_check(me, base, window, direction):
    """Does the month-end move survive checks that don't assume a bell curve?"""
    r = window_returns(me, window)
    rb = window_returns(base, window)
    n = len(r)
    boot = rng.choice(r, (10000, n)).mean(axis=1)
    null = rng.choice(rb, (20000, n)).mean(axis=1)
    perm_p = (np.sum(direction * null >= direction * r.mean()) + 1) / (len(null) + 1)
    trim = np.sort(r)[int(n * 0.1): n - int(n * 0.1)]
    ex_max = np.delete(r, np.argmax(np.abs(r)))
    years = {}
    for e, v in zip([e for e in me if np.isfinite(e['c'][0 if window == 'pre' else 30])
                     and np.isfinite(e['c'][30 if window == 'pre' else 60])], r):
        years.setdefault(e['date'][:4], []).append(v)
    good_years = sum(direction * np.mean(v) > 0 for v in years.values())
    lo, hi = np.percentile(boot, [2.5, 97.5])
    checks = [perm_p < 0.05, direction * lo > 0, direction * np.median(r) > 0, direction * ex_max.mean() > 0,
              good_years >= len(years) / 2]
    verdict = 'Confirmed' if all(checks) else 'Partly' if sum(checks) >= 3 else 'Not confirmed'
    return dict(n=n, mean_bp=r.mean(), median_bp=float(np.median(r)), trimmed_bp=trim.mean(),
                ex_max_bp=ex_max.mean(), ci_lo=lo, ci_hi=hi, perm_p=perm_p, base_n=len(rb),
                years_good=int(good_years), years=len(years), check=verdict, checks_passed=int(sum(checks)))


def simulate(events, direction, tick, cost, stops):
    """Net P&L in ticks for every (entry, exit, stop) plan and every month-end: P[plan, month].
    `tick` is in display units; each month converts it with its own recording's multiplier."""
    events = [e for e in events if np.isfinite(e['c']).all()]
    c = np.array([e['c'] for e in events])
    hi = np.array([e['hi'] for e in events])
    lo = np.array([e['lo'] for e in events])
    costs = np.array([e.get('cost', cost) for e in events])
    tick = tick / np.array([e['mult'] for e in events])
    plans, rows, mae_rows = [], [], []
    for en in range(0, 60, STEP):
        for ex in range(en + STEP, 61, STEP):
            gross = direction * (c[:, ex] - c[:, en]) / tick
            if direction > 0:
                mae = (c[:, en] - lo[:, en:ex].min(axis=1)) / tick
            else:
                mae = (hi[:, en:ex].max(axis=1) - c[:, en]) / tick
            mae = np.maximum(mae, 0)
            for s in stops:
                pnl = gross if s is None else np.where(mae >= s, -float(s), gross)
                plans.append((en, ex, s))
                rows.append(pnl - costs)
                mae_rows.append(mae)
    return events, plans, np.array(rows), np.array(mae_rows)


def pick_stop(plans, mean, stops, en, ex):
    """At a fixed entry and exit, the stop with the most P&L per tick risked, averaged with the next
    tighter and looser stop so a single lucky level can't win."""
    keyed = {s: k for k, (a, b, s) in enumerate(plans) if a == en and b == ex}
    sized = [s for s in stops if s is not None]
    ratio = np.array([mean[keyed[s]] / s for s in sized])
    smooth = np.array([ratio[max(0, i - 1):i + 2].mean() for i in range(len(sized))])
    i = int(np.argmax(smooth))
    return keyed[sized[i]] if mean[keyed[sized[i]]] > 0 else keyed[None]


def choose(plans, P, stops, mask=None, timing=None):
    """Timing first (the entry and exit with the best average without a stop), then the stop.
    With `timing` given, only the stop is chosen."""
    mean = (P if mask is None else P[:, mask]).mean(axis=1)
    if timing is None:
        free = [k for k, (a, b, s) in enumerate(plans) if s is None]
        k = max(free, key=lambda k: mean[k])
        timing = plans[k][:2]
    return pick_stop(plans, mean, stops, *timing)


def describe(P, mae, k, tick_value):
    x = P[k]
    wins, losses = x[x > 0], x[x <= 0]
    return dict(net_ticks=x.mean(), net_value=x.mean() * tick_value if tick_value else None, win=float((x > 0).mean()),
                avg_win=wins.mean() if len(wins) else None, avg_loss=losses.mean() if len(losses) else None,
                pf=wins.sum() / -losses.sum() if losses.sum() < 0 else None, worst=x.min(), best=x.max(),
                t=x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 and x.std() > 0 else None,
                mae_p50=float(np.percentile(mae[k], 50)), mae_p80=float(np.percentile(mae[k], 80)),
                mae_p90=float(np.percentile(mae[k], 90)))


def main():
    stats = json.loads((HERE / 'output' / 'dash' / 'stats.json').read_text())
    tests = [s for s in stats if s['verdict'] == 'Promising']
    groups, path, high, low, index = load()
    data = Path(r'C:\SierraChart\Data')
    settings = Settings(data)
    specs = {}
    for root in set(BASKET_MEMBERS) | {s['root'] for s in tests if s['root'] != BASKET}:
        conf = settings.lookup(min(data.glob(f'{root}Z26[-_]*.scid')).name)
        mult = float(conf.get('real-time-multiplier') or 1)
        tick, value = float(conf['tick-size']), float(conf['currency-value-per-tick'])
        specs[root] = dict(tick=tick, tick_value=value, mult=mult, tick_stored=tick / mult,
                           cost_ticks=SLIPPAGE_TICKS + COMMISSION / value)
    plans_out, grid_out, trades_out = [], [], []
    for s in tests:
        root, session, window = s['root'], s['session'], s['window']
        direction = 1 if s['mean'] > 0 else -1
        if root == BASKET:
            me = basket(groups, path, high, low, index, session, 1, specs)
            base = basket(groups, path, high, low, index, session, 0, specs)
            tick, tick_value, cost, stops, unit = 1.0, None, None, BASKET_STOPS, 'bp'
        else:
            me = series(groups, path, high, low, index, root, session, 1)
            base = series(groups, path, high, low, index, root, session, 0)
            sp = specs[root]
            tick, tick_value, cost, stops, unit = sp['tick'], sp['tick_value'], sp['cost_ticks'], STOPS, 'ticks'
        check = second_check(me, base, window, direction)
        events, plans, P, mae = simulate(me, direction, tick, cost, stops)
        n = len(events)
        simple_en, simple_ex = (0, 30) if window == 'pre' else (30, 60)
        k_simple = plans.index((simple_en, simple_ex, None))
        k_best = choose(plans, P, stops)
        k_win = choose(plans, P, stops, timing=(simple_en, simple_ex))
        k_max = int(np.argmax(P.mean(axis=1)))
        # Out of sample: choose on every other month, score the month left out.
        oos, oos_win = [], []
        for i in range(n):
            mask = np.ones(n, bool)
            mask[i] = False
            oos.append(P[choose(plans, P, stops, mask), i])
            oos_win.append(P[choose(plans, P, stops, mask, timing=(simple_en, simple_ex)), i])
        oos, oos_win = np.array(oos), np.array(oos_win)
        half = None
        if n >= 60:
            first = np.arange(n) < n // 2
            k_half = choose(plans, P, stops, first)
            half = dict(entry=plans[k_half][0] - 30, exit=plans[k_half][1] - 30, stop=plans[k_half][2],
                        later_net=P[k_half, ~first].mean(), later_win=float((P[k_half, ~first] > 0).mean()),
                        later_n=int((~first).sum()), later_from=events[n // 2]['date'])
        best = describe(P, mae, k_best, tick_value)
        simple = describe(P, mae, k_simple, tick_value)
        wplan = describe(P, mae, k_win, tick_value)
        wstop = plans[k_win][2]
        en, ex, stop = plans[k_best]
        row = dict(id=s['id'], root=root, name=s['name'], session=session, window=window, reference=s['reference'],
                   when=s['when'], direction='Long' if direction > 0 else 'Short', unit=unit, months=n,
                   tick=specs.get(root, {}).get('tick'), tick_value=tick_value,
                   cost=cost if cost is not None else float(np.mean([e['cost'] for e in events])),
                   **{f'chk_{k}': v for k, v in check.items()},
                   simple_net=simple['net_ticks'], simple_value=simple['net_value'], simple_win=simple['win'],
                   simple_worst=simple['worst'], mae_p50=simple['mae_p50'], mae_p80=simple['mae_p80'],
                   mae_p90=simple['mae_p90'],
                   w_entry_clock=clock(session, simple_en - 30), w_exit_clock=clock(session, simple_ex - 30),
                   w_stop=wstop, w_net=wplan['net_ticks'], w_value=wplan['net_value'], w_win=wplan['win'],
                   w_pf=wplan['pf'], w_worst=wplan['worst'], w_avg_win=wplan['avg_win'], w_avg_loss=wplan['avg_loss'],
                   w_per_risk=wplan['net_ticks'] / wstop if wstop else None,
                   w_oos_net=oos_win.mean(), w_oos_win=float((oos_win > 0).mean()),
                   simple_last12=P[k_simple, -12:].mean(), w_last12=P[k_win, -12:].mean(),
                   plan_last12=P[k_best, -12:].mean(),
                   entry_min=None if en is None else en - 30, exit_min=None if ex is None else ex - 30, stop=stop,
                   entry_clock=None if en is None else clock(session, en - 30),
                   exit_clock=None if ex is None else clock(session, ex - 30),
                   **{f'plan_{k}': v for k, v in best.items()},
                   per_risk=best.get('net_ticks') / stop if stop else None,
                   oos_net=oos.mean(), oos_win=float((oos > 0).mean()),
                   oos_value=oos.mean() * tick_value if tick_value else None,
                   max_entry=plans[k_max][0] - 30, max_exit=plans[k_max][1] - 30, max_stop=plans[k_max][2],
                   max_net=P[k_max].mean(),
                   half_entry=half and half['entry'], half_exit=half and half['exit'], half_stop=half and half['stop'],
                   half_net=half and half['later_net'], half_win=half and half['later_win'],
                   half_n=half and half['later_n'], half_from=half and half['later_from'])
        row['read'] = ('Basket, not one contract' if root == BASKET else 'Too small after costs' if row['simple_net'] < READ_MIN
                       else 'Faded lately' if row['simple_last12'] < 0 else 'Holds up')
        row.update(commission=COMMISSION, slippage=SLIPPAGE_TICKS, step=STEP, read_min=READ_MIN, currency=s.get('currency'))
        plans_out.append({k: clean(v, 9 if k == 'tick' else 4) if isinstance(v, (float, np.floating)) else
                          (int(v) if isinstance(v, np.integer) else v) for k, v in row.items()})
        means, wins = P.mean(axis=1), (P > 0).mean(axis=1)
        for k, (a, b, st) in enumerate(plans):
            grid_out.append(dict(id=f"{s['id']}|{a - 30}|{b - 30}|{st or 0}", test=s['id'], entry_min=a - 30,
                                 exit_min=b - 30, stop=st or 0, net=round(float(means[k]), 3),
                                 win=round(float(wins[k]), 3)))
        if k_best is not None:
            for e, v, m in zip(events, P[k_best], mae[k_best]):
                trades_out.append(dict(id=f"{s['id']}|{e['date']}", test=s['id'], date=e['date'],
                                       contract=e['contract'], net=round(float(v), 3), mae=round(float(m), 2),
                                       stopped=bool(stop is not None and m >= stop)))
        print(f"{s['id']:14} {row['direction']:5} n={n:3} check={check['check']:13} perm_p={check['perm_p']:.4f} "
              f"CI=[{check['ci_lo']:+.1f},{check['ci_hi']:+.1f}] med={check['median_bp']:+.1f} exmax={check['ex_max_bp']:+.1f} "
              f"yrs={check['years_good']}/{check['years']} | simple {simple['net_ticks']:+.2f}{unit[0]} win {simple['win']:.0%} "
              f"mae50/80/90 {simple['mae_p50']:.0f}/{simple['mae_p80']:.0f}/{simple['mae_p90']:.0f} | "
              f"window stop {wstop} net {wplan['net_ticks']:+.2f} win {wplan['win']:.0%} worst {wplan['worst']:.0f} "
              f"OOS {oos_win.mean():+.2f} L12 {P[k_simple, -12:].mean():+.2f}/{P[k_win, -12:].mean():+.2f} | plan {row['entry_clock']}->{row['exit_clock']} stop {stop} net {best.get('net_ticks', 0):+.2f} "
              f"win {best.get('win', 0):.0%} pf {best.get('pf') or 0:.2f} | OOS {oos.mean():+.2f} win {(oos > 0).mean():.0%}"
              + (f" | half->later {half['later_net']:+.2f} ({half['entry']},{half['exit']},{half['stop']})" if half else ''))
    TRADE.mkdir(parents=True, exist_ok=True)
    for name, data in (('plans', plans_out), ('grid', grid_out), ('trades', trades_out)):
        (TRADE / f'{name}.json').write_text(json.dumps(data, separators=(',', ':')))
    print({p.name: p.stat().st_size for p in TRADE.glob('*.json')})


if __name__ == '__main__':
    main()
