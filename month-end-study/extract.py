"""Read-only month-end close study over the MarketWatch symbols, straight from Sierra .scid files.

For every weekday on record it measures each product in the 30 minutes before and after
three reference times: the UK close (16:30 London), the London 4pm FX fix (16:00 London)
and the US close (16:00 New York). Month-end days are the last business day of each
month on the relevant calendar; every other weekday is kept as the baseline.

Only the hour around each reference time is read, by binary search, so whole files are
never streamed. Files are opened read-only with read/write/delete sharing and the worker
runs at background I/O priority, so Sierra keeps recording undisturbed.

    python extract.py                 # all MarketWatch roots
    python extract.py --roots 6B ES   # a subset
"""
import argparse
import csv
import ctypes
import fnmatch
import os
import re
import struct
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

UTC = timezone.utc
LON = ZoneInfo('Europe/London')
NY = ZoneInfo('America/New_York')
EPOCH = 2_209_161_600
REC = np.dtype([('dt', '<i8'), ('o', '<f4'), ('h', '<f4'), ('l', '<f4'),
                ('c', '<f4'), ('nt', '<u4'), ('tv', '<u4'), ('bv', '<u4'), ('av', '<u4')])
CONTRACT = re.compile(r'^(.+?)([FGHJKMNQUVXZ])(\d{2})(?:_FUT_CME|-(EUREX|CME|CBOT|NYMEX|COMEX))\.scid$', re.I)
HERE = Path(__file__).resolve().parent

# MarketWatch's futures list (market_data.MARKETS): root, name, sector, fallback multiplier.
MARKETS = [
    ('ES', 'S&P 500', 'Equity indices', .01), ('NQ', 'Nasdaq 100', 'Equity indices', .01),
    ('YM', 'Dow Jones', 'Equity indices', 1), ('RTY', 'Russell 2000', 'Equity indices', .01),
    ('FESX', 'Euro Stoxx 50', 'Equity indices', 1), ('FDAX', 'DAX', 'Equity indices', 1),
    ('FESB', 'Euro Stoxx Banks', 'Equity indices', 1), ('NIY', 'Nikkei 225 (JPY)', 'Equity indices', 1),
    ('ZT', '2-Year T-Note', 'Fixed income', 1), ('ZF', '5-Year T-Note', 'Fixed income', 1),
    ('ZN', '10-Year T-Note', 'Fixed income', 1), ('ZB', 'US T-Bond', 'Fixed income', 1),
    ('UB', 'Ultra T-Bond', 'Fixed income', 1), ('FGBS', 'Euro Schatz', 'Fixed income', 1),
    ('FGBM', 'Euro Bobl', 'Fixed income', 1), ('FGBL', 'Euro Bund', 'Fixed income', 1),
    ('FGBX', 'Euro Buxl', 'Fixed income', 1), ('FOAT', 'French OAT', 'Fixed income', 1),
    ('FBTP', 'Italian BTP', 'Fixed income', 1), ('SR3', '3-Month SOFR', 'Fixed income', .01),
    ('ZQ', '30-Day Fed Funds', 'Fixed income', .01), ('CL', 'WTI Crude Oil', 'Energy', .01),
    ('HO', 'Heating Oil', 'Energy', .0001), ('RB', 'RBOB Gasoline', 'Energy', .0001),
    ('NG', 'Natural Gas', 'Energy', .001), ('GC', 'Gold', 'Metals', .1),
    ('SI', 'Silver', 'Metals', .001), ('PL', 'Platinum', 'Metals', .1),
    ('HG', 'Copper', 'Metals', .0001), ('6E', 'Euro', 'Currencies', .0001),
    ('6B', 'British Pound', 'Currencies', .0001), ('6J', 'Japanese Yen', 'Currencies', .000001),
    ('6S', 'Swiss Franc', 'Currencies', .0001), ('6A', 'Australian Dollar', 'Currencies', .0001),
    ('6C', 'Canadian Dollar', 'Currencies', .0001), ('6M', 'Mexican Peso', 'Currencies', .000001),
    ('6L', 'Brazilian Real', 'Currencies', .0001), ('ZC', 'Corn', 'Agriculture', 1),
    ('ZW', 'Wheat', 'Agriculture', 1), ('ZS', 'Soybeans', 'Agriculture', 1),
    ('ZL', 'Soybean Oil', 'Agriculture', .01), ('LE', 'Live Cattle', 'Agriculture', .001),
    ('HE', 'Lean Hogs', 'Agriculture', .001), ('BTC', 'Bitcoin', 'Digital assets', 1),
]
# MarketWatch's CFDs (product_catalog.DIRECT): read directly, quote feed, no rollover.
CFDS = [('UK100', 'FTSE 100 CFD', 'Equity indices'), ('FRA40', 'CAC 40 CFD', 'Equity indices'),
        ('GER30', 'DAX CFD', 'Equity indices'), ('HKG33', 'Hang Seng CFD', 'Equity indices'),
        ('UKOIL', 'Brent Oil CFD', 'Energy'), ('USOIL', 'WTI Oil CFD', 'Energy'),
        ('XAUUSD', 'Spot Gold CFD', 'Metals')]
# Same-price contracts that fill gaps where the full-size root was not recorded
# (MarketWatch's PREFERRED does the same for M6B and MGC).
STANDINS = {'ES': ['MES'], 'NQ': ['MNQ'], 'YM': ['MYM'], 'RTY': ['M2K'], 'FDAX': ['FDXM'],
            'GC': ['MGC'], 'SI': ['SIC', 'QI'], 'CL': ['MCL'], 'NG': ['MNG'], 'HG': ['MHG'],
            '6E': ['M6E'], '6B': ['M6B'], '6J': ['M6J'], 'BTC': ['MBT'], 'ZW': ['MZW'], 'ZS': ['MZS']}
# Reference times: label, zone, regular close.
SESSIONS = {'UK': (LON, (16, 30)), 'FIX': (LON, (16, 0)), 'US': (NY, (16, 0))}
HALF = 1800
STEPS = 61  # one price per minute from close-30m to close+30m


def enter_background_mode():
    """Lower this thread's CPU and disk priority (Windows) so Sierra's own I/O comes first."""
    if os.name != 'nt':
        return False
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThread.restype = wintypes.HANDLE
    kernel.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
    return bool(kernel.SetThreadPriority(kernel.GetCurrentThread(), 0x00010000))


@contextmanager
def shared_read(path):
    """Read-only handle that lets Sierra keep reading, writing, renaming and deleting (as MarketWatch)."""
    if os.name != 'nt':
        with open(path, 'rb', buffering=0) as file:
            yield file
        return
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(Path(path).resolve()), 0x80000000, 0x1 | 0x2 | 0x4, None, 3, 0x10000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    with os.fdopen(fd, 'rb', buffering=0) as file:
        yield file


# ---------------------------------------------------------------- calendars

def easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday_of(year, month, weekday):
    nxt = date(year + month // 12, month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def observed(d):
    """NYSE rule: a Saturday holiday is observed on Friday, a Sunday one on Monday."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def us_holidays(year):
    # A Saturday New Year's Day is not observed: NYSE stays open on 31 December.
    new_year = date(year, 1, 1)
    days = {nth_weekday(year, 1, 0, 3), nth_weekday(year, 2, 0, 3),
            easter(year) - timedelta(days=2), last_weekday_of(year, 5, 0), observed(date(year, 7, 4)),
            nth_weekday(year, 9, 0, 1), nth_weekday(year, 11, 3, 4), observed(date(year, 12, 25))}
    if new_year.weekday() != 5:
        days.add(observed(new_year))
    if year >= 2022:
        days.add(observed(date(year, 6, 19)))
    days |= {date(2012, 10, 29), date(2012, 10, 30), date(2018, 12, 5), date(2025, 1, 9)}
    return days


def uk_holidays(year):
    ny = date(year, 1, 1)
    days = {ny + timedelta(days={5: 2, 6: 1}.get(ny.weekday(), 0)),
            easter(year) - timedelta(days=2), easter(year) + timedelta(days=1),
            nth_weekday(year, 5, 0, 1), last_weekday_of(year, 5, 0), last_weekday_of(year, 8, 0)}
    xmas = date(year, 12, 25)
    if xmas.weekday() == 5:
        days |= {date(year, 12, 27), date(year, 12, 28)}
    elif xmas.weekday() == 6:
        days |= {date(year, 12, 26), date(year, 12, 27)}
    elif xmas.weekday() == 4:
        days |= {xmas, date(year, 12, 28)}
    else:
        days |= {xmas, date(year, 12, 26)}
    moved = {2012: (date(2012, 5, 28), [date(2012, 6, 4), date(2012, 6, 5)]),
             2020: (date(2020, 5, 4), [date(2020, 5, 8)]),
             2022: (date(2022, 5, 30), [date(2022, 6, 2), date(2022, 6, 3), date(2022, 9, 19)]),
             2023: (None, [date(2023, 5, 8)])}
    if year in moved:
        drop, add = moved[year]
        days.discard(drop)
        days |= set(add)
    return days


_HOLIDAYS = {}


def closed(d, calendar):
    key = (calendar, d.year)
    if key not in _HOLIDAYS:
        _HOLIDAYS[key] = (us_holidays if calendar == 'US' else uk_holidays)(d.year)
    return d.weekday() >= 5 or d in _HOLIDAYS[key]


def month_end(year, month, calendar):
    d = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    while closed(d, calendar):
        d -= timedelta(days=1)
    return d


def schedule(first, last):
    """Every weekday x reference time: (day, session, close UTC, month-end?, note)."""
    items = []
    d = first
    while d <= last:
        if d.weekday() < 5:
            for session, (zone, (hh, mm)) in SESSIONS.items():
                calendar = 'US' if session == 'US' else 'UK'
                if closed(d, calendar):
                    continue
                me = d == month_end(d.year, d.month, calendar)
                note = ''
                if session == 'US':
                    thanksgiving = nth_weekday(d.year, 11, 3, 4)
                    if d == thanksgiving + timedelta(days=1) or (d.month, d.day) in {(12, 24), (7, 3)}:
                        if not me:
                            continue  # early-close days stay out of the baseline
                        hh, mm, note = 13, 0, 'early close 13:00 ET'
                elif session == 'UK':
                    if d.month == 12 and (d == month_end(d.year, 12, 'UK') or d.day == 24 or
                                          (d.day in (22, 23) and d.weekday() == 4)):
                        if not me:
                            continue
                        hh, mm, note = 12, 30, 'LSE early close 12:30'
                close = datetime(d.year, d.month, d.day, hh, mm, tzinfo=zone).timestamp()
                items.append((d, session, close, me, note))
        d += timedelta(days=1)
    return items


# ---------------------------------------------------------------- Sierra files

class Settings:
    """Symbol Settings lookup, same rule as MarketWatch: exact symbol, else the longest wildcard."""

    def __init__(self, data_dir):
        names = ('SymbolSettings.DTCSubInstance.xml', 'SymbolSettings.sc_futures_direct.dtc.trading.xml')
        config = next((p for p in (data_dir.parent / 'SymbolSettings' / n for n in names) if p.exists()), None)
        self.rules = []
        if config:
            for item in ET.parse(config).getroot().findall('settings'):
                pattern = item.findtext('symbol', '').upper().replace('#', '[0-9]')
                self.rules.append((pattern, {c.tag: c.text for c in item if c.text is not None}))

    def lookup(self, filename):
        symbol = Path(filename).stem.upper()
        for candidate in (symbol, re.sub(r'-(CME|CBOT|NYMEX|COMEX)$', '_FUT_CME', symbol)):
            exact = next((s for p, s in self.rules if p == candidate), None)
            if exact is not None:
                return exact
            matches = [(p, s) for p, s in self.rules if fnmatch.fnmatchcase(candidate, p)]
            if matches:
                return max(matches, key=lambda e: len(re.sub(r'\[[^]]*\]|[?*]', '', e[0])))[1]
        return {}


class Scid:
    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        self.cache = {}
        self.file = None

    def __enter__(self):
        self._ctx = shared_read(self.path)
        self.file = self._ctx.__enter__()
        head = self.file.read(56)
        if len(head) < 56 or head[:4] != b'SCID':
            raise ValueError(f'{self.path.name}: not an SCID file')
        self.hs, rs = struct.unpack_from('<II', head, 4)
        if rs != 40:
            raise ValueError(f'{self.path.name}: record size {rs}')
        self.n = (self.size - self.hs) // 40
        self.file.seek(self.hs)
        first = struct.unpack('<q', self.file.read(8))[0]
        self.micros = 100_000_000_000_000 < first < 100_000_000_000_000_000
        self.first, self.last = self.time(0), self.time(self.n - 1)
        return self

    def __exit__(self, *exc):
        self._ctx.__exit__(*exc)
        self.file = None

    def decode(self, raw):
        v = struct.unpack('<q' if self.micros else '<d', raw)[0]
        return v / 1e6 - EPOCH if self.micros else v * 86400 - EPOCH

    def time(self, i):
        v = self.cache.get(i)
        if v is None:
            self.file.seek(self.hs + i * 40)
            v = self.cache[i] = self.decode(self.file.read(8))
        return v

    def count_le(self, t):
        """Number of records stamped at or before t (bisect_right)."""
        lo, hi = 0, self.n
        while lo < hi:
            mid = (lo + hi) // 2
            if self.time(mid) <= t:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def records(self, i0, i1):
        i0, i1 = max(0, i0), min(self.n, i1)
        if i1 <= i0:
            return np.zeros(0, REC), np.zeros(0)
        self.file.seek(self.hs + i0 * 40)
        raw = self.file.read((i1 - i0) * 40)
        data = np.frombuffer(raw[:len(raw) // 40 * 40], dtype=REC)
        stamps = (data['dt'] if self.micros else data['dt'].view('<f8')).astype(float)
        return data, stamps / (1e6 if self.micros else 1 / 86400) - EPOCH


def valid(data, quotes):
    return np.isfinite(data['c']) & (data['c'] > 0) & ((data['tv'] > 0) | quotes)


def last_valid(sc, upto, quotes, max_age):
    """Last valid price at or before `upto`, if it is no older than max_age seconds."""
    end = sc.count_le(upto)
    for back in (200, 5000):
        data, ts = sc.records(end - back, end)
        keep = valid(data, quotes)
        if keep.any():
            j = np.flatnonzero(keep)[-1]
            return float(data['c'][j]) if upto - ts[j] <= max_age else None
        if end - back <= 0:
            break
    return None


def measure(sc, close, lo, hi, quotes):
    """Minute grid of prices and window statistics around one reference time."""
    data, ts = sc.records(lo - 200, hi)
    keep = valid(data, quotes)
    data, ts = data[keep], ts[keep]
    if not len(ts):
        return None
    start = close - HALF
    price = data['c'].astype(float)
    grid = start + 60.0 * np.arange(STEPS)
    j = np.searchsorted(ts, grid, side='right') - 1
    path = np.where(j >= 0, price[np.maximum(j, 0)], np.nan)
    # A reference print from a previous trading session is not a pre-window price.
    if j[0] < 0 or start - ts[j[0]] > 4 * 3600:
        path[0] = np.nan
    pre = (ts > start) & (ts <= close)
    post = (ts > close) & (ts <= close + HALF)
    # Highest and lowest trade inside each minute (grid[k-1], grid[k]], for stop-loss tests.
    edges = np.searchsorted(ts, grid, side='right')
    high, low = np.full(STEPS - 1, np.nan), np.full(STEPS - 1, np.nan)
    for k in range(1, STEPS):
        if edges[k] > edges[k - 1]:
            chunk = price[edges[k - 1]:edges[k]]
            high[k - 1], low[k - 1] = chunk.max(), chunk.min()
    vol = data['tv'].astype(float)
    out = dict(path=path, high=high, low=low, n_pre=int(pre.sum()), n_post=int(post.sum()),
               vol_pre=float(vol[pre].sum()), vol_post=float(vol[post].sum()))
    for key, mask in (('pre', pre), ('post', post)):
        out[key + '_hi'] = float(price[mask].max()) if mask.any() else np.nan
        out[key + '_lo'] = float(price[mask].min()) if mask.any() else np.nan
    return out


def candidates(root, data_dir, cfd):
    if cfd:
        path = data_dir / f'{root}.scid'
        return [(path, False)] if path.exists() and path.stat().st_size > 56 else []
    found, seen = [], set()
    roots = {root: False, **{s: True for s in STANDINS.get(root, [])}}
    for path in sorted(data_dir.glob('*.scid'), key=lambda p: -p.stat().st_size):
        m = CONTRACT.match(path.name)
        if not m or m[1].upper() not in roots or path.stat().st_size <= 56 + 40:
            continue
        key = (m[1].upper() + m[2].upper() + m[3], path.stat().st_size)
        if key in seen:
            continue  # "-CME" and "_FUT_CME" copies of the same recording
        seen.add(key)
        found.append((path, roots[m[1].upper()]))
    return found


def process(root, cfd, data_dir, settings, now, writer, paths_out):
    files = candidates(root, data_dir, cfd)
    if not files:
        return dict(root=root, status='no files on disk')
    quotes = cfd
    infos = []
    for path, standin in files:
        try:
            with Scid(path) as sc:
                infos.append((path, standin, sc.first, sc.last))
        except (ValueError, OSError) as error:
            print('  skip', path.name, error)
    if not infos:
        return dict(root=root, status='no readable files')
    first = datetime.fromtimestamp(min(i[2] for i in infos), UTC).date()
    last = datetime.fromtimestamp(max(i[3] for i in infos), UTC).date()
    items = [it for it in schedule(first, last) if it[2] + HALF <= now]
    # 1) Activity in each window, per candidate file, from two binary searches.
    activity = {}
    for path, standin, t0, t1 in infos:
        inside = [k for k, it in enumerate(items) if t0 <= it[2] + HALF and it[2] - HALF <= t1]
        if not inside:
            continue
        with Scid(path) as sc:
            for k in inside:
                close = items[k][2]
                lo, hi = sc.count_le(close - HALF), sc.count_le(close + HALF)
                if hi > lo:
                    activity.setdefault(k, []).append((hi - lo, standin, path, lo, hi))
    # 2) Front contract per window: the busiest full-size file, unless a stand-in is 5x busier.
    chosen = {}
    for k, options in activity.items():
        full = max((o for o in options if not o[1]), default=None)
        micro = max((o for o in options if o[1]), default=None)
        chosen[k] = full if full and (not micro or full[0] * 5 >= micro[0]) else micro
    by_file = {}
    for k, option in chosen.items():
        by_file.setdefault(option[2], []).append((k, option))
    # Previous month-end reference time per (session, month), for month-to-date moves.
    me_close = {(it[1], it[0].year, it[0].month): it[2] for it in items if it[3]}
    for d, session, close, me, note in schedule(first.replace(day=1) - timedelta(days=40), first):
        if me:
            me_close.setdefault((session, d.year, d.month), close)
    rows = 0
    for path, entries in by_file.items():
        conf = settings.lookup(path.name)
        mult = float(conf.get('real-time-multiplier', next((m[3] for m in MARKETS if m[0] == root), 1)))
        m = CONTRACT.match(path.name)
        contract = (m[1] + m[2] + m[3]).upper() if m else path.stem.upper()
        with Scid(path) as sc:
            for k, (count, standin, _, lo, hi) in sorted(entries, key=lambda e: e[0]):
                d, session, close, me, note = items[k]
                got = measure(sc, close, lo, hi, quotes)
                if got is None:
                    continue
                mtd_ref = np.nan
                if me:
                    prev = (d.replace(day=1) - timedelta(days=1))
                    ref_close = me_close.get((session, prev.year, prev.month))
                    if ref_close:
                        ref = last_valid(sc, ref_close, quotes, 3 * 86400)
                        mtd_ref = ref if ref is not None else np.nan
                path_row = got['path']
                writer.writerow(dict(
                    root=root, date=d.isoformat(), session=session, monthend=int(me), note=note,
                    close_utc=datetime.fromtimestamp(close, UTC).strftime('%Y-%m-%d %H:%M'),
                    contract=contract, standin=int(standin), multiplier=mult,
                    p_start=path_row[0], p_close=path_row[30], p_end=path_row[60], mtd_ref=mtd_ref,
                    n_pre=got['n_pre'], n_post=got['n_post'], vol_pre=got['vol_pre'], vol_post=got['vol_post'],
                    pre_hi=got['pre_hi'], pre_lo=got['pre_lo'], post_hi=got['post_hi'], post_lo=got['post_lo']))
                paths_out.append((root, d.isoformat(), session, path_row, got['high'], got['low']))
                rows += 1
    used = sorted({CONTRACT.match(p.name)[1].upper() if CONTRACT.match(p.name) else root for p in by_file})
    return dict(root=root, status='ok', first=first.isoformat(), last=last.isoformat(), rows=rows,
                files=len(by_file), roots_used=used)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-dir', default=os.environ.get('SIERRA_DATA_DIR', r'C:\SierraChart\Data'))
    parser.add_argument('--out', default=str(HERE / 'output'))
    parser.add_argument('--roots', nargs='*')
    args = parser.parse_args()
    data_dir, out = Path(args.data_dir), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print('background I/O priority:', enter_background_mode())
    settings = Settings(data_dir)
    now = time.time()
    roots = [(m[0], False) for m in MARKETS] + [(c[0], True) for c in CFDS]
    if args.roots:
        wanted = {r.upper() for r in args.roots}
        roots = [r for r in roots if r[0] in wanted]
    fields = ['root', 'date', 'session', 'monthend', 'note', 'close_utc', 'contract', 'standin', 'multiplier',
              'p_start', 'p_close', 'p_end', 'mtd_ref', 'n_pre', 'n_post', 'vol_pre', 'vol_post',
              'pre_hi', 'pre_lo', 'post_hi', 'post_lo']
    paths, report = [], []
    with open(out / 'events.csv', 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for root, cfd in roots:
            started = time.time()
            result = process(root, cfd, data_dir, settings, now, writer, paths)
            result['seconds'] = round(time.time() - started, 1)
            report.append(result)
            print(result, flush=True)
    np.savez_compressed(out / 'paths.npz', key=np.array([f'{r}|{d}|{s}' for r, d, s, *_ in paths]),
                        path=np.array([p[3] for p in paths]) if paths else np.zeros((0, STEPS)),
                        high=np.array([p[4] for p in paths]) if paths else np.zeros((0, STEPS - 1)),
                        low=np.array([p[5] for p in paths]) if paths else np.zeros((0, STEPS - 1)))
    import json
    (out / 'coverage.json').write_text(json.dumps(dict(generated=datetime.now(UTC).isoformat(timespec='seconds'),
                                                       roots=report), indent=1))


if __name__ == '__main__':
    main()
