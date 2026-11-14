"""Live quotes from Sierra Chart's own data files. Read-only.

Sierra writes one 40-byte record per trade to <symbol>.scid while an intraday chart
for that symbol is open. In those tick records High = ask, Low = bid, Close = last.
Settlements come from <symbol>.dly (its daily close is the 14:00 CT settlement); if the
daily file has no row for the wanted day, a 14:00 CT reference is derived from ticks.

Files are opened with full sharing at background I/O priority so Sierra is never blocked.
"""
import ctypes
import datetime as dt
import glob
import msvcrt
import os
import re
import struct
import threading
import zlib

from . import calendar_us as cal

SCID_HEADER = 56
REC = struct.Struct('<q4f4I')        # time(us since 1899-12-30 UTC), O, H, L, C, trades, volume, bidvol, askvol
EPOCH = dt.datetime(1899, 12, 30, tzinfo=dt.timezone.utc)
SYMBOL_RE = re.compile(r'((?:ZQ|SR3)[FGHJKMNQUVXZ]\d{2})_FUT_CME')

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_k32.CreateFileW.restype = ctypes.c_void_p
_k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                             ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
_k32.GetCurrentThread.restype = ctypes.c_void_p
_k32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
_INVALID = ctypes.c_void_p(-1).value


def background_io():
    """Mark the calling thread as background I/O priority (call once per reader thread)."""
    _k32.SetThreadPriority(_k32.GetCurrentThread(), 0x00010000)


def open_shared(path):
    h = _k32.CreateFileW(path, 0x80000000, 0x7, None, 3, 0x80, None)   # GENERIC_READ, share R/W/D, OPEN_EXISTING
    if h in (None, _INVALID):
        raise OSError(ctypes.get_last_error(), 'cannot open', path)
    return os.fdopen(msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY), 'rb')


def to_time(us):
    return EPOCH + dt.timedelta(microseconds=us)


def to_us(t):
    return int((t - EPOCH).total_seconds() * 1_000_000)


def is_tick(o):
    """Tick records carry bid/ask: Open is 0 or one of Sierra's sub-trade markers (~ -1.999e37)."""
    return o == 0.0 or o < -1e30


class Quote:
    __slots__ = ('symbol', 'bid', 'ask', 'last', 'last_size', 'last_time', 'volume', 'high', 'low', 'trades')

    def __init__(self, symbol):
        self.symbol = symbol
        self.bid = self.ask = self.last = self.high = self.low = None
        self.last_size = self.volume = self.trades = 0
        self.last_time = None

    @property
    def mid(self):
        if self.bid and self.ask and self.ask >= self.bid:
            return (self.bid + self.ask) / 2
        return self.last

    def as_dict(self):
        return {'bid': self.bid, 'ask': self.ask, 'last': self.last, 'mid': self.mid, 'last_size': self.last_size,
                'last_time': self.last_time.isoformat() if self.last_time else None,
                'volume': self.volume, 'high': self.high, 'low': self.low, 'trades': self.trades}


class _Tail:
    """Incremental reader for one .scid file, tracking the current Globex session."""

    def __init__(self, symbol, path, scale):
        self.symbol, self.path, self.scale = symbol, path, scale
        self.quote = Quote(symbol)
        self.n_read = None          # records consumed
        self.session = None         # trade date being accumulated

    def _count(self):
        return max(0, (os.path.getsize(self.path) - SCID_HEADER) // REC.size)

    def _find(self, f, n, t_us):
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            f.seek(SCID_HEADER + mid * REC.size)
            if REC.unpack(f.read(REC.size))[0] < t_us:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def poll(self, now_td):
        """Read new records. Returns True if the quote changed."""
        if not os.path.exists(self.path):
            return False
        n = self._count()
        if self.n_read is not None and n == self.n_read and self.session == now_td:
            return False
        with open_shared(self.path) as f:
            if self.n_read is None or n < self.n_read or self.session != now_td:
                # (re)start: begin at this session's open, but always keep the latest quote
                start, _ = cal.session_bounds(now_td)
                first = self._find(f, n, to_us(start))
                self.quote = Quote(self.symbol)
                self.session = now_td
                if first >= n and n > 0:        # no trades yet this session: seed from the last record
                    first = n - 1
                    seed_only = True
                else:
                    seed_only = False
            else:
                first, seed_only = self.n_read, False
            f.seek(SCID_HEADER + first * REC.size)
            data = f.read((n - first) * REC.size)
        self._apply(data, seed_only)
        self.n_read = n
        return True

    def _apply(self, data, seed_only):
        q, s = self.quote, self.scale
        for t, o, h, l, c, trades, vol, bv, av in REC.iter_unpack(data):
            if is_tick(o):
                if h > 0:
                    q.ask = h * s
                if l > 0:
                    q.bid = l * s
            price = c * s
            q.last, q.last_size, q.last_time = price, vol, to_time(t)
            if seed_only:
                continue
            q.volume += vol
            q.trades += 1
            q.high = price if q.high is None else max(q.high, price)
            q.low = price if q.low is None else min(q.low, price)

    def reference_at(self, td, ct_time=dt.time(14)):
        """~settlement for trade date td: VWAP of trades in the minute before 14:00 CT,
        else the mid at 14:00 CT. Rounded to 0.0025."""
        if not os.path.exists(self.path):
            return None
        t_end = cal.local_to_utc(dt.datetime.combine(td, ct_time), -6)
        t_beg = t_end - dt.timedelta(minutes=1)
        with open_shared(self.path) as f:
            n = self._count()
            i_end = self._find(f, n, to_us(t_end))
            i_beg = self._find(f, n, to_us(t_end - dt.timedelta(hours=2)))
            f.seek(SCID_HEADER + i_beg * REC.size)
            recs = list(REC.iter_unpack(f.read((i_end - i_beg) * REC.size)))
        if not recs:
            return None
        win = [r for r in recs if r[0] >= to_us(t_beg)]
        if win and sum(r[6] for r in win) > 0:
            px = sum(r[4] * r[6] for r in win) / sum(r[6] for r in win) * self.scale
        else:
            last = recs[-1]
            px = ((last[2] + last[3]) / 2 if is_tick(last[1]) and last[2] > 0 and last[3] > 0 else last[4]) * self.scale
        return round(px / 0.0025) * 0.0025


class SierraFeed:
    def __init__(self, data_dir, chartbook, scale=0.01):
        self.data_dir, self.chartbook, self.scale = data_dir, chartbook, scale
        self.tails = {}
        self._dly_cache = {}
        self.lock = threading.Lock()
        self.discover()

    # -- contracts ------------------------------------------------------------------
    def discover(self):
        """Contracts in the chartbook (re-read so contracts added in Sierra appear automatically)."""
        syms = []
        book = os.path.join(self.data_dir, self.chartbook)
        try:
            raw = open_shared(book).read()
            data = zlib.decompress(raw[5:]) if raw[:4] == b'ZLib' else raw
            syms = SYMBOL_RE.findall(data.decode('latin-1'))
        except (OSError, zlib.error):
            pass
        if not syms:
            syms = [SYMBOL_RE.match(os.path.basename(p)).group(1)
                    for p in glob.glob(os.path.join(self.data_dir, '*_FUT_CME.scid'))
                    if SYMBOL_RE.match(os.path.basename(p))]
        syms = list(dict.fromkeys(syms))
        changed = set(syms) != set(self.tails)
        with self.lock:
            for s in syms:
                if s not in self.tails:
                    self.tails[s] = _Tail(s, os.path.join(self.data_dir, s + '_FUT_CME.scid'), self.scale)
            for s in list(self.tails):
                if s not in syms:
                    del self.tails[s]
        return changed

    @property
    def symbols(self):
        return list(self.tails)

    # -- quotes ---------------------------------------------------------------------
    def poll(self, now=None):
        td = cal.trade_date(now or cal.now_utc())
        changed = False
        with self.lock:
            for t in self.tails.values():
                try:
                    changed |= t.poll(td)
                except OSError:
                    pass
        return changed

    def quotes(self):
        with self.lock:
            return {s: t.quote for s, t in self.tails.items()}

    def has_ticks(self, symbol):
        t = self.tails.get(symbol)
        return bool(t and os.path.exists(t.path))

    # -- settlements ----------------------------------------------------------------
    def _daily(self, symbol):
        path = os.path.join(self.data_dir, symbol + '_FUT_CME.dly')
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return {}
        hit = self._dly_cache.get(symbol)
        if hit and hit[0] == mtime:
            return hit[1]
        rows = {}
        with open_shared(path) as f:
            for line in f.read().decode('ascii', 'replace').splitlines()[1:]:
                p = [x.strip() for x in line.split(',')]
                if len(p) >= 5:
                    try:
                        rows[dt.date(*map(int, p[0].split('/')))] = float(p[4]) * self.scale
                    except ValueError:
                        pass
        self._dly_cache[symbol] = (mtime, rows)
        return rows

    def settlement(self, symbol, td):
        """(price, source) for trade date td."""
        px = self._daily(symbol).get(td)
        if px is not None:
            return px, 'settlement'
        t = self.tails.get(symbol)
        ref = t.reference_at(td) if t else None
        return (ref, '2pm CT ref') if ref is not None else (None, None)
