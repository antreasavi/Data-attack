"""Public data: NY Fed EFFR/SOFR fixings, FOMC meeting dates, Fed speaker calendar.

Everything is cached under %LOCALAPPDATA%\\StirTool so a site outage never blanks the tool;
each result says whether it came from a fresh download or the cache.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.request
import zlib

from . import calendar_us as cal

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) StirTool/1.0'
EFFR_URL = 'https://markets.newyorkfed.org/api/rates/unsecured/effr/last/120.json'
SOFR_URL = 'https://markets.newyorkfed.org/api/rates/secured/sofr/last/120.json'
FOMC_URL = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
FED_CAL_URL = 'https://www.federalreserve.gov/json/calendar.json'
MONTHS = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                      'September', 'October', 'November', 'December'], 1)}

# Used only if both the FOMC page and the cache are unavailable.
FALLBACK_FOMC = ['2026-12-09', '2027-01-27', '2027-03-17', '2027-04-28', '2027-06-09', '2027-07-28',
                 '2027-09-15', '2027-10-27', '2027-11-17']


def cache_dir():
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    p = os.path.join(base, 'StirTool')
    os.makedirs(p, exist_ok=True)
    return p


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8-sig', 'replace')


def _cached(name, max_age_s, fetch):
    """Return (value, info). Uses the cache if it is fresh, else fetches; falls back to stale cache on error."""
    path = os.path.join(cache_dir(), name)
    cached = None
    try:
        with open(path, encoding='utf-8') as f:
            cached = json.load(f)
    except (OSError, ValueError):
        pass
    now = cal.now_utc()
    if cached:
        age = (now - dt.datetime.fromisoformat(cached['fetched_at'])).total_seconds()
        if 0 <= age < max_age_s:
            return cached['value'], {'source': 'cache', 'fetched_at': cached['fetched_at']}
    try:
        value = fetch()
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'fetched_at': now.isoformat(), 'value': value}, f)
        os.replace(tmp, path)
        return value, {'source': 'live', 'fetched_at': now.isoformat()}
    except Exception as exc:  # network or parse failure: keep the last good copy
        if cached:
            return cached['value'], {'source': 'stale cache', 'fetched_at': cached['fetched_at'], 'error': str(exc)}
        raise


# ---- NY Fed fixings -------------------------------------------------------------------

def _fixings(url):
    rows = json.loads(_get(url)).get('refRates', [])
    out = {r['effectiveDate']: float(r['percentRate']) for r in rows if r.get('percentRate') is not None}
    meta = {}
    if rows and rows[0].get('targetRateFrom') is not None:
        meta = {'target_from': rows[0]['targetRateFrom'], 'target_to': rows[0]['targetRateTo']}
    return {'fixings': out, 'meta': meta}


def fixings():
    """{'effr': {date: %}, 'sofr': {...}, 'target': (from, to), 'info': {...}}"""
    effr, i1 = _cached('effr.json', 1800, lambda: _fixings(EFFR_URL))
    sofr, i2 = _cached('sofr.json', 1800, lambda: _fixings(SOFR_URL))
    to_d = lambda d: {dt.date.fromisoformat(k): v for k, v in d.items()}
    return {'effr': to_d(effr['fixings']), 'sofr': to_d(sofr['fixings']),
            'target': (effr['meta'].get('target_from'), effr['meta'].get('target_to')),
            'info': {'effr': i1, 'sofr': i2}}


# ---- FOMC dates -----------------------------------------------------------------------

def parse_fomc(page, years):
    out = []
    for year in years:
        start = page.find(f'{year} FOMC Meetings')
        if start < 0:
            continue
        end = page.find('FOMC Meetings', start + 10)
        seg = page[start: end if end > 0 else len(page)]
        for month_text, day_text in re.findall(
                r'fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', seg, re.S):
            nums = re.findall(r'\d+', day_text)
            names = [n for n in month_text.strip().split('/') if n in MONTHS]
            if not nums or not names:
                continue
            day = int(nums[-1])
            month = MONTHS[names[-1]] if len(names) > 1 and int(nums[0]) > day else MONTHS[names[0]]
            try:
                out.append(dt.date(year, month, day).isoformat())
            except ValueError:
                pass
    return sorted(set(out))


def fomc_meetings(today):
    """Decision dates (second day of each meeting). Years not yet published are projected
    from the last published year (+364 days, same weekday) and flagged as assumed."""
    years = (today.year, today.year + 1, today.year + 2)
    try:
        dates, info = _cached('fomc.json', 86400, lambda: parse_fomc(_get(FOMC_URL), years))
    except Exception as exc:
        dates, info = FALLBACK_FOMC, {'source': 'built-in fallback', 'error': str(exc)}
    if not dates:
        dates, info = FALLBACK_FOMC, {'source': 'built-in fallback'}
    meetings = [{'date': dt.date.fromisoformat(d), 'assumed': False} for d in dates]
    last_year = max(m['date'].year for m in meetings)
    template = [m['date'] for m in meetings if m['date'].year == last_year]
    for year in range(last_year + 1, today.year + 3):
        shift = dt.timedelta(days=364 * (year - last_year))
        for d in template:
            meetings.append({'date': d + shift, 'assumed': True})
    return sorted(meetings, key=lambda m: m['date']), info


# ---- Fed speakers -----------------------------------------------------------------------

def _parse_time(text):
    m = re.match(r'\s*(\d{1,2}):(\d{2})\s*([ap])\.?m', text or '', re.I)
    if not m:
        return None
    h, mi = int(m.group(1)) % 12, int(m.group(2))
    return dt.time(h + (12 if m.group(3).lower() == 'p' else 0), mi)


def parse_fed_calendar(text):
    events = json.loads(text).get('events', [])
    out = []
    for e in events:
        if e.get('type') not in ('Speeches', 'Testimony'):
            continue
        try:
            y, mo = map(int, e['month'].split('-'))
            day = int(re.findall(r'\d+', e.get('days', ''))[0])
        except (KeyError, ValueError, IndexError):
            continue
        title = html.unescape(e.get('title', ''))
        kind, _, who = title.partition(' - ')
        who = re.sub(r'\s+', ' ', who or title).strip()
        t = _parse_time(e.get('time'))
        when = dt.datetime.combine(dt.date(y, mo, day), t or dt.time(9))
        out.append({'id': f'fed-{y}{mo:02d}{day:02d}-{zlib.crc32(title.encode()) % 10**6}',
                    'speaker': who, 'kind': kind.strip() or e.get('type'),
                    'topic': html.unescape(e.get('description', '')),
                    'where': html.unescape(e.get('location', '')),
                    'when_et': when.isoformat(timespec='minutes'), 'time_known': t is not None, 'source': 'Fed Board calendar'})
    return out


def _manual_path():
    return os.path.join(cache_dir(), 'speakers_manual.json')


def manual_speakers():
    try:
        with open(_manual_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_manual_speakers(rows):
    tmp = _manual_path() + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=1)
    os.replace(tmp, _manual_path())


def speakers(now_utc, days_ahead=14):
    """Upcoming Board speeches/testimony from the Fed calendar plus manually added speakers."""
    try:
        rows, info = _cached('fed_calendar.json', 3 * 3600, lambda: parse_fed_calendar(_get(FED_CAL_URL)))
    except Exception as exc:
        rows, info = [], {'source': 'unavailable', 'error': str(exc)}
    rows = rows + manual_speakers()
    now_et = cal.to_et(now_utc).replace(tzinfo=None)
    horizon = now_et + dt.timedelta(days=days_ahead)
    upcoming = [r for r in rows
                if now_et - dt.timedelta(hours=2) <= dt.datetime.fromisoformat(r['when_et']) <= horizon]
    return sorted(upcoming, key=lambda r: r['when_et']), info
