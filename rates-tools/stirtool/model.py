"""Fed path model and ZQ / SR3 pricing.

Path: EFFR is a step function. It starts at the latest published EFFR ("base") and moves by
x_k basis points the day after FOMC meeting k. SOFR = EFFR path + a spread (bp) fitted to market.

  ZQ  = 100 - average daily EFFR over the calendar month (weekends carry the prior fixing).
  SR3 = 100 - SOFR compounded over business days from the 3rd Wednesday of the contract month
        to the 3rd Wednesday three months later, ACT/360.

Days that already have a published fixing use it; later days use the model path.
"""
import datetime as dt
from dataclasses import dataclass

import numpy as np

from . import calendar_us as cal

MONTH_CODES = 'FGHJKMNQUVXZ'
TICK_VALUE = {('ZQ', 0.0025): 10.4175, ('ZQ', 0.005): 20.835, ('SR3', 0.0025): 6.25, ('SR3', 0.005): 12.50}
BP_VALUE = {'ZQ': 41.67, 'SR3': 25.0}

# Fit settings (residuals are in bp; weight 1 = a normal live quote)
SMOOTH = 0.02          # penalty on changes in per-meeting increments (keeps far meetings sensible)
RIDGE = 1e-6
SPREAD_PRIOR_W = 0.1   # pull of the SOFR-EFFR spread toward its recent average


@dataclass(frozen=True)
class Contract:
    symbol: str
    product: str      # 'ZQ' or 'SR3'
    year: int
    month: int
    start: dt.date
    end: dt.date      # exclusive

    @property
    def label(self):
        return f'{self.product} {dt.date(self.year, self.month, 1):%b%y}'


def parse_symbol(sym):
    product = 'SR3' if sym.startswith('SR3') else 'ZQ'
    month = MONTH_CODES.index(sym[len(product)]) + 1
    year = 2000 + int(sym[len(product) + 1:])
    if product == 'ZQ':
        start = dt.date(year, month, 1)
        end = dt.date(*cal.add_months(year, month, 1), 1)
    else:
        start = cal.third_wednesday(year, month)
        end = cal.third_wednesday(*cal.add_months(year, month, 3))
    return Contract(sym, product, year, month, start, end)


def tick_size(c, today):
    """CME: the nearest expiring month trades in 0.0025, the others in 0.005."""
    if c.product == 'ZQ':
        return 0.0025 if (c.year, c.month) == (today.year, today.month) else 0.005
    y, m = cal.add_months(today.year, today.month, -3)
    while True:
        if m % 3 == 0 and cal.third_wednesday(*cal.add_months(y, m, 3)) > today:
            return 0.0025 if (c.year, c.month) == (y, m) else 0.005
        y, m = cal.add_months(y, m, 1)


def _fill_forward(fix, d):
    """Fixing in force on day d: the latest published fixing on or before d."""
    while d not in fix:
        d -= cal.ONE_DAY
    return fix[d]


class Model:
    def __init__(self, contracts, meetings, effr, sofr, today):
        self.today = today
        self.contracts = list(contracts)
        self.last_effr = max(effr)
        self.last_sofr = max(sofr)
        self.base = effr[self.last_effr]
        common = sorted(set(effr) & set(sofr))[-20:]
        self.spread_prior = float(np.mean([(sofr[d] - effr[d]) * 100 for d in common])) if common else 0.0
        horizon = max(c.end for c in self.contracts)
        self.meetings = [m for m in meetings
                         if m['date'] + cal.ONE_DAY > self.last_effr and m['date'] + cal.ONE_DAY < horizon]
        self.eff = np.array([(m['date'] + cal.ONE_DAY).toordinal() for m in self.meetings])
        self.K = len(self.meetings)
        self._legs = [self._build(c, effr, sofr) for c in self.contracts]

    def _build(self, c, effr, sofr):
        K = self.K
        if c.product == 'ZQ':
            days = [c.start + dt.timedelta(days=i) for i in range((c.end - c.start).days)]
            past = [d for d in days if d <= self.last_effr]
            fut = np.array([d.toordinal() for d in days if d > self.last_effr])
            first = min(effr)
            realized = sum(_fill_forward(effr, d) if d >= first else self.base for d in past)
            A = (fut[:, None] >= self.eff[None, :]).astype(float) if len(fut) else np.zeros((0, K))
            return {'kind': 'ZQ', 'N': len(days), 'realized': realized, 'nf': len(fut),
                    'a': A.sum(0) / len(days) / 100.0}
        bdays = cal.business_days(c.start, c.end)
        nxt = bdays[1:] + [c.end]
        n = np.array([(b - a).days for a, b in zip(bdays, nxt)], float)
        is_past = np.array([d <= self.last_sofr for d in bdays])
        first = min(sofr)
        r_past = np.array([_fill_forward(sofr, d) if d >= first else self.base for d in bdays])
        ords = np.array([d.toordinal() for d in bdays])
        A = (ords[:, None] >= self.eff[None, :]).astype(float)
        A[is_past] = 0.0
        return {'kind': 'SR3', 'D': (c.end - c.start).days, 'n': n, 'past': is_past, 'r_past': r_past, 'A': A}

    # ---- pricing -----------------------------------------------------------------
    def rates(self, x, sp):
        """Model rate (%) for every contract. x: per-meeting moves (bp), sp: SOFR-EFFR spread (bp)."""
        x = np.asarray(x, float)
        out = np.empty(len(self._legs))
        for j, L in enumerate(self._legs):
            if L['kind'] == 'ZQ':
                out[j] = (L['realized'] + L['nf'] * self.base) / L['N'] + L['a'] @ x
            else:
                r = np.where(L['past'], L['r_past'], self.base + (L['A'] @ x + sp) / 100.0)
                out[j] = (np.prod(1 + r / 100.0 * L['n'] / 360.0) - 1) * 360.0 / L['D'] * 100.0
        return out

    def prices(self, x, sp):
        return 100.0 - self.rates(x, sp)

    def jacobian(self, x, sp):
        """d rate(%) / d [x_1..x_K, sp] (parameters in bp)."""
        x = np.asarray(x, float)
        J = np.zeros((len(self._legs), self.K + 1))
        for j, L in enumerate(self._legs):
            if L['kind'] == 'ZQ':
                J[j, :self.K] = L['a']
            else:
                r = np.where(L['past'], L['r_past'], self.base + (L['A'] @ x + sp) / 100.0)
                g = 1 + r / 100.0 * L['n'] / 360.0
                prod = np.prod(g)
                w = (L['n'] / 36000.0) / g * prod * 36000.0 / L['D'] / 100.0   # d rate% / d r_i(bp)
                J[j, :self.K] = w @ L['A']
                J[j, self.K] = w[~L['past']].sum()
        return J

    # ---- fit -----------------------------------------------------------------------
    def fit(self, market, weights=None, start=None):
        """Least-squares fit of the meeting path (and spread) to market prices {symbol: price}."""
        sel = [j for j, c in enumerate(self.contracts) if market.get(c.symbol) is not None]
        M = np.array([market[self.contracts[j].symbol] for j in sel])
        w = np.sqrt(np.array([(weights or {}).get(self.contracts[j].symbol, 1.0) for j in sel]))
        K = self.K
        theta = np.zeros(K + 1) if start is None else np.array(start, float)
        if start is None:
            theta[K] = self.spread_prior
        D = np.zeros((max(K - 1, 0), K + 1))
        for k in range(1, K):
            D[k - 1, k], D[k - 1, k - 1] = 1.0, -1.0
        R = np.vstack([np.sqrt(SMOOTH) * D,
                       np.sqrt(RIDGE) * np.hstack([np.eye(K), np.zeros((K, 1))]),
                       np.sqrt(SPREAD_PRIOR_W) * np.eye(1, K + 1, K)])
        r0 = np.concatenate([np.zeros(max(K - 1, 0) + K), [np.sqrt(SPREAD_PRIOR_W) * self.spread_prior]])
        for _ in range(8):
            x, sp = theta[:K], theta[K]
            res = (100.0 - self.rates(x, sp)[sel] - M) * 100.0          # bp, model - market
            Jr = -100.0 * self.jacobian(x, sp)[sel]
            lhs = np.vstack([w[:, None] * Jr, R])
            rhs = -np.concatenate([w * res, R @ theta - r0])
            step = np.linalg.lstsq(lhs, rhs, rcond=None)[0]
            theta = theta + step
            if np.max(np.abs(step)) < 1e-7:
                break
        x, sp = theta[:K], theta[K]
        fair = self.prices(x, sp)
        resid = {self.contracts[j].symbol: (market[self.contracts[j].symbol] - fair[j]) * 100.0 for j in sel}
        return Fit(x=x, sp=sp, fair={c.symbol: fair[j] for j, c in enumerate(self.contracts)}, resid=resid)

    def cumulative(self, x):
        return np.cumsum(x)


@dataclass
class Fit:
    x: np.ndarray       # per-meeting moves, bp
    sp: float           # SOFR - EFFR spread, bp
    fair: dict          # symbol -> model price
    resid: dict         # symbol -> market - model, bp
