"""US calendar helpers: holidays, business days, IMM dates and US time zones.

Time zones are computed from the US DST rule directly, so this works on Windows
without the tzdata package.
"""
import datetime as dt
from functools import lru_cache

UTC = dt.timezone.utc
ONE_DAY = dt.timedelta(days=1)


def nth_weekday(year, month, weekday, n):
    """n-th given weekday (Mon=0) of a month; n=-1 means the last one."""
    if n > 0:
        first = dt.date(year, month, 1)
        return first + dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - ONE_DAY
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def third_wednesday(year, month):
    return nth_weekday(year, month, 2, 3)


def add_months(year, month, k):
    idx = year * 12 + (month - 1) + k
    return idx // 12, idx % 12 + 1


def easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def _observed(d):
    if d.weekday() == 5:
        return d - ONE_DAY
    if d.weekday() == 6:
        return d + ONE_DAY
    return d


@lru_cache(maxsize=None)
def holidays(year):
    """US government-securities (SIFMA-style) full holidays. Approximate: used only for day weights."""
    h = {
        nth_weekday(year, 1, 0, 3),          # MLK
        nth_weekday(year, 2, 0, 3),          # Presidents
        easter(year) - 2 * ONE_DAY,          # Good Friday
        nth_weekday(year, 5, 0, -1),         # Memorial
        _observed(dt.date(year, 6, 19)),     # Juneteenth
        _observed(dt.date(year, 7, 4)),      # Independence
        nth_weekday(year, 9, 0, 1),          # Labor
        nth_weekday(year, 10, 0, 2),         # Columbus
        _observed(dt.date(year, 11, 11)),    # Veterans
        nth_weekday(year, 11, 3, 4),         # Thanksgiving
        _observed(dt.date(year, 12, 25)),    # Christmas
    }
    ny = dt.date(year, 1, 1)
    if ny.weekday() == 6:
        h.add(ny + ONE_DAY)
    elif ny.weekday() < 5:
        h.add(ny)
    return frozenset(h)


def is_business_day(d):
    return d.weekday() < 5 and d not in holidays(d.year)


def business_days(start, end):
    """Business days in [start, end)."""
    out, d = [], start
    while d < end:
        if is_business_day(d):
            out.append(d)
        d += ONE_DAY
    return out


def next_business_day(d):
    d += ONE_DAY
    while not is_business_day(d):
        d += ONE_DAY
    return d


# ---- time zones -------------------------------------------------------------------

def _is_dst(utc_dt, std_offset_h):
    """US DST: 2nd Sunday of March 02:00 local to 1st Sunday of November 02:00 local."""
    local_std = utc_dt.astimezone(UTC).replace(tzinfo=None) + dt.timedelta(hours=std_offset_h)
    y = local_std.year
    start = dt.datetime.combine(nth_weekday(y, 3, 6, 2), dt.time(2))
    end = dt.datetime.combine(nth_weekday(y, 11, 6, 1), dt.time(1))   # 02:00 DST == 01:00 standard
    return start <= local_std < end


def _zone(utc_dt, std_offset_h):
    off = std_offset_h + (1 if _is_dst(utc_dt, std_offset_h) else 0)
    return dt.timezone(dt.timedelta(hours=off))


def to_et(utc_dt):
    return utc_dt.astimezone(_zone(utc_dt, -5))


def to_ct(utc_dt):
    return utc_dt.astimezone(_zone(utc_dt, -6))


def local_to_utc(naive, std_offset_h):
    """Naive local wall-clock time (ET: -5, CT: -6) to aware UTC."""
    guess = (naive - dt.timedelta(hours=std_offset_h)).replace(tzinfo=UTC)
    off = std_offset_h + (1 if _is_dst(guess, std_offset_h) else 0)
    return (naive - dt.timedelta(hours=off)).replace(tzinfo=UTC)


def now_utc():
    return dt.datetime.now(UTC)


# ---- CME trade dates ----------------------------------------------------------------

def trade_date(utc_dt):
    """CME Globex trade date: the session that opens 17:00 CT belongs to the next weekday."""
    ct = to_ct(utc_dt)
    d = ct.date()
    if ct.hour >= 17:
        d += ONE_DAY
    while d.weekday() >= 5:
        d += ONE_DAY
    return d


def prev_weekday(d):
    d -= ONE_DAY
    while d.weekday() >= 5:
        d -= ONE_DAY
    return d


def session_bounds(td):
    """UTC [start, end) of the Globex session for trade date td (17:00 CT the day before to 16:00 CT).
    Monday's session opens Sunday 17:00 CT."""
    start = local_to_utc(dt.datetime.combine(td - ONE_DAY, dt.time(17)), -6)
    end = local_to_utc(dt.datetime.combine(td, dt.time(16)), -6)
    return start, end


def globex_open(utc_dt):
    start, end = session_bounds(trade_date(utc_dt))
    return start <= utc_dt < end
