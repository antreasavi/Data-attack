"""Scenarios, speaker ladders and the lagging-contract measure.

A scenario sets the total move priced by a meeting (bp vs today's EFFR), e.g. "Dec +50".
How the meetings after it react depends on the mode:
  whole : the change carries through every later meeting (parallel shift from that meeting on)
  pull  : later meetings keep their pricing (end rate unchanged); they are only moved as far as
          needed to stay on the right side of the new level (a hike pulled forward, not added)
  fade  : later meetings move by change x fade^(meetings later)
Target price = current market mid + model price change, so each contract keeps its own basis.
"""
import numpy as np

from .model import BP_VALUE, TICK_VALUE, tick_size

MODES = ('whole', 'pull', 'fade')
LADDER_OUTCOMES = (-25, 0, 25, 50, 75, 100)


def apply_edits(x, edits, mode='whole', fade=0.6):
    """edits: {meeting index: target cumulative bp}. Returns new per-meeting moves."""
    C = np.cumsum(np.asarray(x, float))
    for k in sorted(edits):
        target = float(edits[k])
        d = target - C[k]
        if mode == 'pull':
            # Timing only: later meetings keep their pricing (end rate unchanged). A later meeting is
            # moved only if it sat on the same side as the move and the new level now passes it
            # (a hike pulled into this meeting / a cut pulled in), so the path never reverses.
            old = C[k]
            C[k] = target
            later = C[k + 1:]
            if d > 0:
                C[k + 1:] = np.where(later >= old, np.maximum(later, target), later)
            elif d < 0:
                C[k + 1:] = np.where(later <= old, np.minimum(later, target), later)
        elif mode == 'fade':
            C[k:] += d * fade ** np.arange(len(C) - k)
        else:
            C[k:] += d
    return np.diff(np.concatenate([[0.0], C]))


def reprice(model, fit, current, x_new, today):
    """Per contract: current price, scenario target and ticks to target."""
    base = model.prices(fit.x, fit.sp)
    new = model.prices(x_new, fit.sp)
    out = {}
    for j, c in enumerate(model.contracts):
        tick = tick_size(c, today)
        cur = current.get(c.symbol)
        cur = base[j] if cur is None else cur
        move = new[j] - base[j]
        target = cur + move
        out[c.symbol] = {'current': cur, 'target': round(target / tick) * tick, 'target_exact': target,
                         'move_bp': move * 100, 'ticks': move / tick,
                         'usd_per_lot': move * 100 * BP_VALUE[c.product], 'tick': tick,
                         'tick_value': TICK_VALUE[(c.product, tick)]}
    return out


def ladder(model, fit, current, k, mode, fade, today, outcomes=LADDER_OUTCOMES):
    """Target price of every contract for each outcome at meeting k."""
    cols = []
    cum_now = float(np.cumsum(fit.x)[k])
    for o in outcomes:
        x_new = apply_edits(fit.x, {k: o}, mode, fade)
        cols.append({'outcome_bp': o, 'contracts': reprice(model, fit, current, x_new, today),
                     'path_bp': np.cumsum(x_new).tolist()})
    return {'meeting': model.meetings[k]['date'].isoformat(), 'priced_now_bp': cum_now, 'mode': mode,
            'fade': fade, 'outcomes': cols}


def lag(fit_now, fit_settle, model, today):
    """How far each contract has moved away from the fitted curve since settlement (ticks).
    Positive = price above where the rest of the strip says (rich); negative = below (cheap).
    Each contract's usual gap to the curve cancels because it is measured at both times."""
    out = {}
    for c in model.contracts:
        a, b = fit_now.resid.get(c.symbol), fit_settle.resid.get(c.symbol) if fit_settle else None
        if a is None or b is None:
            continue
        bp = a - b
        out[c.symbol] = {'bp': bp, 'ticks': bp / 100 / tick_size(c, today), 'resid_now_bp': a, 'resid_settle_bp': b}
    return out
