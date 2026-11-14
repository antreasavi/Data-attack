"""Check that the STIR contracts in a Sierra Chart chartbook can be read, and how fresh they are.

Read-only: files are opened with full sharing at background I/O priority, so
Sierra keeps writing them normally. Nothing in the Sierra folders is changed.

Usage:
    python -I rates-tools/sierra_check.py                      # STERS chartbook, instance 5
    python -I rates-tools/sierra_check.py --chartbook "X .Cht" --data-dir C:/SierraChart/Data
"""
import argparse
import ctypes
import datetime as dt
import glob
import msvcrt
import os
import re
import struct
import zlib

DEFAULT_DIR = r'C:\SierraChart\SierraChartInstance_5\Data'
DEFAULT_BOOK = 'STERS .Cht'
PRICE_SCALE = 0.01          # Sierra stores ZQ/SR3 prices x100 (real-time multiplier 0.01)
SCID_HEADER = 56
SCID_RECORD = struct.Struct('<q4f4I')   # time(us since 1899-12-30 UTC), O, H=ask, L=bid, C=last, trades, vol, bidvol, askvol
EPOCH = dt.datetime(1899, 12, 30, tzinfo=dt.timezone.utc)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
k32.GetCurrentThread.restype = ctypes.c_void_p
k32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]


def open_shared(path):
    """Open read-only with FILE_SHARE_READ|WRITE|DELETE so Sierra is never blocked."""
    h = k32.CreateFileW(path, 0x80000000, 0x7, None, 3, 0x80, None)
    if h in (None, ctypes.c_void_p(-1).value):
        raise OSError(ctypes.get_last_error(), 'CreateFileW failed', path)
    return os.fdopen(msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY), 'rb')


def chartbook_symbols(path):
    raw = open_shared(path).read()
    data = zlib.decompress(raw[5:]) if raw[:4] == b'ZLib' else raw
    found = re.findall(rb'\\((?:ZQ|SR3|SR1)[A-Z]\d{2}_FUT_CME)\.(dly|scid)', data)
    out = {}
    for sym, kind in found:
        out.setdefault(sym.decode(), set()).add(kind.decode())
    return out


def last_daily(path):
    with open_shared(path) as f:
        f.seek(max(0, os.path.getsize(path) - 400))
        rows = [r for r in f.read().decode('ascii', 'replace').splitlines() if r[:2] == '20']
    if not rows:
        return None
    p = [x.strip() for x in rows[-1].split(',')]
    return p[0], float(p[4]) * PRICE_SCALE, int(float(p[5]))


def last_tick(path):
    size = os.path.getsize(path)
    n = (size - SCID_HEADER) // SCID_RECORD.size
    if n <= 0:
        return None
    with open_shared(path) as f:
        f.seek(SCID_HEADER + (n - 1) * SCID_RECORD.size)
        t, o, ask, bid, last, trades, vol, bv, av = SCID_RECORD.unpack(f.read(SCID_RECORD.size))
    when = EPOCH + dt.timedelta(microseconds=t)
    return when, bid * PRICE_SCALE, ask * PRICE_SCALE, last * PRICE_SCALE, n


def globex_open(now):
    """CME Globex: Sun 17:00 CT to Fri 16:00 CT, daily halt 16:00-17:00 CT (CT = UTC-6 in winter, -5 in summer)."""
    ct = now - dt.timedelta(hours=6 if not (3 < now.month < 11) else 5)
    wd, hm = ct.weekday(), ct.hour * 60 + ct.minute
    if wd == 5 or (wd == 6 and hm < 17 * 60) or (wd == 4 and hm >= 16 * 60):
        return False
    return not (16 * 60 <= hm < 17 * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default=DEFAULT_DIR)
    ap.add_argument('--chartbook', default=DEFAULT_BOOK)
    a = ap.parse_args()
    k32.SetThreadPriority(k32.GetCurrentThread(), 0x00010000)   # THREAD_MODE_BACKGROUND_BEGIN

    book = os.path.join(a.data_dir, a.chartbook)
    syms = chartbook_symbols(book) if os.path.exists(book) else {}
    if not syms:
        syms = {os.path.basename(p).split('.')[0]: set() for p in glob.glob(os.path.join(a.data_dir, '*_FUT_CME.*'))
                if re.match(r'(ZQ|SR3|SR1)[A-Z]\d{2}_', os.path.basename(p))}
    now = dt.datetime.now(dt.timezone.utc)
    live_market = globex_open(now)
    print(f'chartbook: {book}  ({len(syms)} contracts)   now {now:%a %Y-%m-%d %H:%M:%S} UTC   Globex {"OPEN" if live_market else "CLOSED"}')
    print(f'{"contract":<16}{"chart":<7}{"daily close":>12}  {"date":<11}{"tick file":<10}{"bid":>9}{"ask":>9}{"last":>9}  {"last tick (UTC)":<20}{"age":>8}  status')
    order = sorted(syms, key=lambda s: (s[:3] != 'ZQ' and s[:2] == 'ZQ', s.split('_')[0][:-3], s[-10:-8], 'FGHJKMNQUVXZ'.index(s.split('_')[0][-3])))
    order = sorted(syms, key=lambda s: (0 if s.startswith('ZQ') else 1, int(s.split('_')[0][-2:]), 'FGHJKMNQUVXZ'.index(s.split('_')[0][-3])))
    for s in order:
        kinds = '/'.join(sorted(syms[s])) or '-'
        dly = os.path.join(a.data_dir, s + '.dly')
        scid = os.path.join(a.data_dir, s + '.scid')
        d = last_daily(dly) if os.path.exists(dly) else None
        dcol = f'{d[1]:>12.4f}  {d[0]:<11}' if d else f'{"-":>12}  {"-":<11}'
        if os.path.exists(scid):
            t = last_tick(scid)
            age = (now - t[0]).total_seconds()
            status = 'LIVE' if age < 300 else ('stale' if live_market else 'ok (market closed)')
            print(f'{s:<16}{kinds:<7}{dcol}{"yes":<10}{t[1]:>9.4f}{t[2]:>9.4f}{t[3]:>9.4f}  {t[0]:%m-%d %H:%M:%S}{"":<6}{age:>7.0f}s  {status}')
        else:
            print(f'{s:<16}{kinds:<7}{dcol}{"MISSING":<10}{"":>27}  {"":<20}{"":>8}  no live bid/ask: needs an intraday chart')


if __name__ == '__main__':
    main()
