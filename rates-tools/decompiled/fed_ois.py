# pseudo-decompiled fed_ois.pyc

def <module>():   # line 1
    """FOMC-implied policy path from 30-day Fed Funds futures.

All three inputs are public and free:
  * FOMC meeting dates  - federalreserve.gov FOMC calendar
  * current EFFR        - New York Fed markets API (official, no key)
  * the futures strip   - 30-day Fed Funds (ZQ) monthly contracts via Yahoo

ZQ settles on the *average* EFFR over the contract month, which is what makes
the meeting arithmetic work: for a month containing a decision, splitting the
average either side of the effective date backs out the post-meeting rate.
This is the same construction CME FedWatch uses.

A month with no meeting is a free re-anchor — its average simply *is* the
prevailing rate — which stops solve errors compounding along the strip."""
    L1: <SETUP_ANNOTATIONS > ; __doc__ = 'FOMC-implied policy path from 30-day Fed Funds futures.\n\nAll three inputs are public and free:\n  * FOMC meeting dates  - federalreserve.gov FOMC calendar\n  * current EFFR        - New York Fed markets API (official, no key)\n  * the futures strip   - 30-day Fed Funds (ZQ) monthly contracts via Yahoo\n\nZQ settles on the *average* EFFR over the contract month, which is what makes\nthe meeting ...
    L16: annotations = import __future__.annotations ; import __future__
    L18: re = import re
    L19: monthrange = import calendar.monthrange ; import calendar
    L20: date = import datetime.date ; datetime = import datetime.datetime ; timedelta = import datetime.timedelta ; import datetime
    L21: List = import typing.List ; Optional = import typing.Optional ; Tuple = import typing.Tuple ; import typing
    L23: app_logging = import app_logging
    L24: Path = import ratecore.Path ; session = import ratecore.session ; import ratecore
    L26: log = app_logging.get('rates')
    L28: FOMC_CALENDAR = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
    L29: EFFR_API = 'https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json'
    L30: YAHOO_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/{sym}'
    L32: MONTH_CODE = {1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M', 7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'}
    L34: MONTH_NAME = iter(enumerate([*('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')]))()
    L40: MONTHS_AHEAD = 16
    L42: _calendar_cache = {'fetched': None, 'dates': []} ; __annotations__['_calendar_cache'] = 'dict'
    L45: _fomc_dates = func<code _fomc_dates>
    L95: _effr = func<code _effr>
    L105: _zq_rate = func<code _zq_rate>
    L122: _next_month = func<code _next_month>
    L126: fetch = func<code fetch> ; return None

    def <dictcomp>(.0):   # line 34
        L34: for-next .0 (exhausted->30) ; i = <item>[0] ; m = <item>[1] ; map-add m: (i + 1) ; goto 6 ; @30: ; return .0

    def _fomc_dates(timeout):   # line 45
        """Scheduled FOMC decision dates, from the Fed's own calendar page.

    Cached for the day: the schedule is published years ahead and never moves
    outside an emergency meeting."""
        L51: today = date.today()
        L52: if not (_calendar_cache['fetched'] == today): goto 126 ; if not _calendar_cache['dates']: goto 126
        L53: return _calendar_cache['dates']
        L55: @126: ; r = session.get(FOMC_CALENDAR, timeout=timeout)
        L56: r.raise_for_status()
        L57: html = r.text
        L59: out = []
        L60: for-next iter((today.year, (today.year + 1), (today.year + 2))) (exhausted->1018) ; year = <item>
        L61: start = html.find(f"{year} FOMC Meetings")
        L62: if not (start < 0): goto 358
        L63: goto 290
        L64: @358: ; end = html.find('FOMC Meetings', (start + 10))
        L65: if not (end > 0): goto 428 ; @426: ; goto 456 ; @428: ; @456: ; segment = start[end:len(html)]
        L68: rows = re.findall('fomc-meeting__month[^>]*>\\s*<strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', segment, re.S)
        L72: for-next iter(rows) (exhausted->1014) ; month_text = <item>[0] ; day_text = <item>[1]
        L73: nums = re.findall('\\d+', day_text)
        L74: if nums: goto 596
        L75: goto 538
        L76: @596: ; day = int(nums[-1])
        L77: @654: ; names = iter(month_text.strip().split('/'))()
        L78: if names: goto 742
        L79: goto 538
        L82: @742: ; if not (len(names) > 1): goto 868 ; if not (int(nums[0]) > day): goto 868
        L81: goto 904
        L83: @868:
        L81: @904: ; month = MONTH_NAME[names[0]]
        L85: @946: ; out.append(date(year, month, day)) ; goto 538 ; except-handler:
        L86: except ValueError? ; if not match(ValueError): goto 1006 ; <exc>
        L87: pop_except ; goto 538
        L86: @1006: ; reraise ; pop_except ; reraise
        L72: @1014: ; goto 290
        L89: @1018: ; out = sorted(set(out))
        L90: if not out: goto 1134
        L91: _calendar_cache.update(fetched=today, dates=out)
        L92: @1134: ; return out

        def _fomc_dates.<locals>.<listcomp>(.0):   # line 77
            L77: for-next .0 (exhausted->34) ; n = <item> ; if not (n in MONTH_NAME): goto 6 ; append n ; goto 6 ; @34: ; return .0

    def _effr(timeout):   # line 95
        L96: r = session.get(EFFR_API, timeout=timeout)
        L97: r.raise_for_status()
        L98: [r.json() or ...] (else goto 138) ; @138: ; [{}.get('refRates') or ...] (else goto 180) ; @180: ; rows = []
        L99: for-next iter(rows) (exhausted->330) ; row = <item>
        L100: if not (row.get('type') == 'EFFR'): goto 328 ; if row.get('percentRate') is None: goto 328
        L101: iter(rows) ; return float(row['percentRate']) ; @328: ; goto 186
        L102: @330: ; return None

    def _zq_rate(year, month, timeout):   # line 105
        """Implied average EFFR for a contract month: 100 - price."""
        L107: sym = f"ZQ{MONTH_CODE[month]}{(year % 100):02d}.CBT"
        L109: r = session.get(YAHOO_CHART.format(sym=sym), params={'range': '1d', 'interval': '1d'}, timeout=timeout)
        L111: if not (r.status_code != 200): goto 178
        L112: return None
        L113: @178: ; [r.json().get('chart') or ...] (else goto 258) ; @258: ; result = {}.get('result')
        L114: if result: goto 306
        L115: return None
        L116: @306: ; price = result[0].get('meta', {}).get('regularMarketPrice')
        L117: if price is None: goto 440 ; goto 442 ; @440: ; @442: ; return None ; except-handler:
        L118: except Exception? ; if not match(Exception): goto 470 ; <exc>
        L119: pop_except ; return None
        L118: @470: ; reraise ; pop_except ; reraise

    def _next_month(d):   # line 122
        L123: return (d.replace(day=28) + timedelta(days=8)).replace(day=1)

    def fetch():   # line 126
        L127: base = _effr()
        L128: if base is not None: goto 94
        L129: log.warning('FED: no EFFR from NY Fed')
        L130: return None
        L132: @94: ; today = date.today()
        L133: meetings = iter(_fomc_dates())()
        L134: if meetings: goto 244
        L135: log.warning('FED: no upcoming FOMC dates parsed')
        L136: return None
        L138: @244: ; rate = base
        L139: path = []
        L140: cursor = today.replace(day=1)
        L141: for-next iter(range(MONTHS_AHEAD)) (exhausted->692) ; _ = <item>
        L142: avg = _zq_rate(cursor.year, cursor.month)
        L143: in_month = iter(meetings)()
        L145: if avg is None: goto 660
        L146: if in_month: goto 434
        L148: rate = avg ; goto 660
        L150: @434: ; n = monthrange(cursor.year, cursor.month)[1]
        L153: before = min(in_month[-1].day, n)
        L154: after = (n - before)
        L155: if not (after > 0): goto 602
        L156: rate = (((avg * n) - (before * rate)) / after)
        L157: @602: ; path.append((in_month[-1], rate))
        L158: @660: ; cursor = _next_month(cursor) ; goto 336
        L160: @692: ; if path: goto 752
        L161: log.warning('FED: no ZQ contracts resolved')
        L162: return None
        L163: @752: ; return (base, path)

        def fetch.<locals>.<listcomp>(.0):   # line 133
            L133: for-next .0 (exhausted->30) ; d = <item> ; if not (d > today): goto 8 ; append d ; goto 8 ; @30: ; return .0

        def fetch.<locals>.<listcomp>(.0):   # line 143
            L143: for-next .0 (exhausted->82) ; d = <item>
            L144: if not (d.year == cursor.year): goto 8 ; if not (d.month == cursor.month): goto 8
            L144: append d ; @80: ; goto 8 ; @82: ; return .0