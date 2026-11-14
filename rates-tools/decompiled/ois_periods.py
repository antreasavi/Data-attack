# pseudo-decompiled ois_periods.pyc

def <module>():   # line 1
    """Published accrual calendars for meeting-period OIS estimates.

ECB uses explicit maintenance periods; BOE uses announcement-to-announcement
as in ICE MPC SONIA. FED assumes next-day implementation and BOJ next bank
business day, consistent with their implementation notices. Future effective
dates remain assumptions until the decisions themselves are published."""
    L1: __doc__ = 'Published accrual calendars for meeting-period OIS estimates.\n\nECB uses explicit maintenance periods; BOE uses announcement-to-announcement\nas in ICE MPC SONIA. FED assumes next-day implementation and BOJ next bank\nbusiness day, consistent with their implementation notices. Future effective\ndates remain assumptions until the decisions themselves are published.\n'
    L8: json = import json
    L9: re = import re
    L10: date = import datetime.date ; datetime = import datetime.datetime ; timedelta = import datetime.timedelta ; import datetime
    L11: unescape = import html.unescape ; import html
    L12: urljoin = import urllib.parse.urljoin ; urlparse = import urllib.parse.urlparse ; import urllib.parse
    L14: write_text = import atomic_write.write_text ; import atomic_write
    L15: data_dir = import paths.data_dir ; import paths
    L17: ECB_INDEX = 'https://www.ecb.europa.eu/press/calendars/reserve/html/index.en.html'
    L18: ECB_PAGES = ('https://www.ecb.europa.eu/press/pr/date/2025/html/ecb.pr250424~2643533670.en.html', 'https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.pr260630~9f54a0a4fb.en.html')
    L22: BOJ_HOLIDAYS = 'https://www.boj.or.jp/en/about/outline/holi.htm'
    L25: plain = func<code plain>
    L29: calendar_date = func<code calendar_date>
    L39: parse_ecb_periods = func<code parse_ecb_periods>
    L60: parse_boj_holidays = func<code parse_boj_holidays>
    L82: load_calendar = func<code load_calendar>
    L120: next_boj_day = func<code next_boj_day>
    L131: meeting_periods = func<code meeting_periods>
    L158: ecb_settlement_check = func<code ecb_settlement_check> ; return None

    def plain(value):   # line 25
        L26: return ' '.join(unescape(re.sub('<[^>]+>', ' ', value)).split())

    def calendar_date(value):   # line 29
        L30: value = re.sub('^[A-Za-z]{3},\\s*', '', plain(value))
        L31: for-next iter(('%d %B %Y', '%d-%b-%y', '%d-%b-%Y')) (exhausted->196) ; fmt = <item>
        L33: iter(('%d %B %Y', '%d-%b-%y', '%d-%b-%Y')) ; return datetime.strptime(value, fmt).date() ; except-handler:
        L34: except ValueError? ; if not match(ValueError): goto 188 ; <exc>
        L35: pop_except ; goto 76
        L34: @188: ; reraise ; pop_except ; reraise
        L36: @196: ; raise ValueError(('Unrecognised calendar date: ' + value))

    def parse_ecb_periods(html):   # line 39
        L40: periods = {}
        L41: for-next iter(re.findall('<tr\\b[^>]*>(.*?)</tr>', html, (re.S | re.I))) (exhausted->788) ; row = <item>
        L42: cells = re.findall('<td\\b[^>]*>(.*?)</td>', row, (re.S | re.I))
        L43: if not (len(cells) != 7): goto 232
        L44: goto 96
        L45: @232:
        L46: meeting = iter(cells[1:4])()[0] ; start = iter(cells[1:4])()[1] ; last = iter(cells[1:4])()[2] ; goto 316 ; except-handler:
        L47: except ValueError? ; if not match(ValueError): goto 308 ; <exc>
        L48: pop_except ; goto 96
        L47: @308: ; reraise ; pop_except ; reraise
        L49: @316: ; end = (last + timedelta(days=1))
        L50: @368: ; if not (meeting <= start): goto 382 ; if not (start < end): goto 432 ; goto 386 ; @382: ; ? ; goto 432 ; @386: ; if not (1 <= (end - start).days): goto 430 ; if ((end - start).days <= 100): goto 462 ; goto 432 ; @430: ; func<code <listcomp>>
        L51: @432: ; raise ValueError('Invalid ECB maintenance period')
        L52: @462: ; @520: ; if not plain(cells[6]).isdigit(): goto 662 ; if not (int(plain(cells[6])) != (end - start).days): goto 662
        L53: raise ValueError('ECB maintenance day count mismatch')
        L54: @662: ; periods[meeting.isoformat()] = [start.isoformat(), end.isoformat()] ; goto 96
        L55: @788: ; if periods: goto 822
        L56: raise ValueError('No complete ECB maintenance periods')
        L57: @822: ; return periods

        def parse_ecb_periods.<locals>.<listcomp>(.0):   # line 46
            L46: for-next .0 (exhausted->42) ; c = <item> ; append calendar_date(c) ; goto 6 ; @42: ; return .0

    def parse_boj_holidays(html):   # line 60
        L61: years = {}
        L64: for-next iter(re.findall('<h3\\b[^>]*>\\s*(20\\d{2})\\s*</h3>\\s*(<table\\b.*?</table>)', html, (re.S | re.I))) (exhausted->808) ; year = <item>[0] ; table = <item>[1]
        L65: months = set() ; days = []
        L66: for-next iter(re.findall('<tr\\b[^>]*>(.*?)</tr>', table, (re.S | re.I))) (exhausted->646) ; row = <item>
        L67: cells = re.findall('<td\\b[^>]*>(.*?)</td>', row, (re.S | re.I))
        L68: if not (len(cells) != 2): goto 368
        L69: goto 234
        L70: @368: ; month = datetime.strptime(plain(cells[0]), '%B').month
        L71: months.add(month)
        L72: @502:
        L72: func<code <genexpr>>(iter(re.findall('\\d+', plain(cells[1])))()) ; goto 234
        L74: @646: ; if not (months != set(range(1, 13))): goto 742
        L75: raise ValueError('Incomplete BOJ holiday year')
        L76: @742: ; years[year] = sorted(set(days)) ; goto 100
        L77: @808: ; if years: goto 842
        L78: raise ValueError('No BOJ holiday calendar')
        L79: @842: ; return years

        def parse_boj_holidays.<locals>.<genexpr>(.0):   # line 72
            L72: ? ; for-next .0 (exhausted->142)
            L73: d = <item>
            L72: (yield date(int(year), month, int(d)).isoformat()) ; goto 10 ; @142: ; return None

    def load_calendar(bank, http):   # line 82
        """Refresh published calendars; retain provenance when using dated cache."""
        L84: path = (data_dir() / (('ois_period_calendar_' + bank.lower()) + '.json'))
        L86: if not (bank == 'ECB'): goto 982
        L87: urls = set(ECB_PAGES)
        L88: index = http.get(ECB_INDEX, timeout=(10, 25))
        L89: index.raise_for_status()
        L90: for-next iter(re.findall('<a\\b[^>]*href=["\\\']([^"\\\']+)["\\\'][^>]*>(.*?)</a>', index.text, (re.S | re.I))) (exhausted->694) ; href = <item>[0] ; label = <item>[1]
        L91: if not ('operational calendars' in plain(label).lower()): goto 692
        L92: years = re.findall('20\\d{2}', plain(label))
        L93: if not func<code <genexpr>>(iter(years)()): goto 692
        L94: url = urljoin(ECB_INDEX, unescape(href))
        L95: if not (urlparse(url).hostname == 'www.ecb.europa.eu'): goto 692
        L96: urls.add(url) ; @692: ; goto 336
        L97: @694: ; values = {}
        L98: for-next iter(sorted(urls)) (exhausted->980) ; url = <item>
        L99: response = http.get(url, timeout=(10, 25))
        L100: response.raise_for_status()
        L101: for-next iter(parse_ecb_periods(response.text).items()) (exhausted->978) ; meeting = <item>[0] ; interval = <item>[1]
        L102: if not (meeting in values): goto 966 ; if not (values[meeting] != interval): goto 966
        L103: raise ValueError('Conflicting ECB published periods')
        L104: @966: ; values[meeting] = interval ; goto 894
        L101: @978: ; goto 728
        L98: @980: ; goto 1134
        L106: @982: ; urls = {BOJ_HOLIDAYS}
        L107: @1052: ; response = http.get(BOJ_HOLIDAYS, timeout=(10, 25))
        L108: @1062: ; response.raise_for_status()
        L109: values = parse_boj_holidays(response.text)
        L110: @1134: ; @1232: ; result = {'values': values, 'sources': sorted(urls), 'fetched_on': date.today().isoformat()}
        L111: write_text(path, json.dumps(result))
        L112: return (result, None) ; except-handler:
        L113: except Exception? ; if not match(Exception): goto 1588 ; <exc>
        L114: cached = json.loads(path.read_text(encoding='utf-8'))
        L115: if not (0 <= (date.today() - date.fromisoformat(cached['fetched_on'])).days): goto 1544 ; if ((date.today() - date.fromisoformat(cached['fetched_on'])).days <= 7): goto 1576 ; goto 1546 ; @1544: ; iter(parse_ecb_periods(response.text).items())
        L116: @1546: ; raise ValueError('Published period calendar cache expired')
        L117: @1576: ; pop_except ; return iter(sorted(urls))
        L113: @1588: ; reraise ; pop_except ; reraise

        def load_calendar.<locals>.<genexpr>(.0):   # line 93
            L93: ? ; for-next .0 (exhausted->170) ; y = <item> ; [(date.today().year <= int(y)) and ...] (else goto 158) ; goto 162 ; @158: ; .0 ; @162: ; (yield (int(y) <= (date.today().year + 2))) ; goto 8 ; @170: ; return None

    def next_boj_day(day, years):   # line 120
        L121: day = (day += timedelta(days=1))
        L122: for-next iter(range(15)) (exhausted->336) ; _ = <item>
        L123: if not (str(day.year) not in years): goto 148
        L124: raise ValueError('BOJ holiday year unavailable')
        L125: @148: ; if not (day.weekday() < 5): goto 296 ; if not (day.isoformat() not in years[str(day.year)]): goto 296
        L126: iter(range(15)) ; return day
        L127: @296: ; day = (day += timedelta(days=1)) ; goto 70
        L128: @336: ; raise ValueError('Invalid BOJ holiday calendar')

    def meeting_periods(bank, meetings, calendar):   # line 131
        """Return only periods with known endpoints; final unbounded meeting omitted."""
        L133: meetings = sorted(set(meetings))
        L134: if not (bank == 'ECB'): goto 148
        L135: [calendar or ...] (else goto 78) ; @78: ; values = {}.get('values', {})
        L136: return iter(meetings)()
        L138: @148: ; periods = []
        L139: for-next iter(zip(meetings, meetings[1:])) (exhausted->666) ; meeting = <item>[0] ; following = <item>[1]
        L140: if not (1 <= (following - meeting).days): goto 254 ; if ((following - meeting).days <= 100): goto 258 ; goto 256 ; @254: ; iter(zip(meetings, meetings[1:]))
        L141: @256: ; goto 200
        L142: @258: ; if not (bank == 'BOE'): goto 280
        L143: end = following ; start = meeting ; goto 616
        L144: @280: ; if not (bank == 'FED'): goto 468
        L145: @316: ; end = (following + timedelta(days=1)) ; start = (meeting + timedelta(days=1))
        L146: if (start.weekday() >= 5): goto 464 ; if not (end.weekday() >= 5): goto 466
        L147: @464: ; goto 200
        L146: @466: ; goto 616
        L149: @468:
        L150: [calendar or ...] (else goto 476) ; @476: ; years = {}.get('values', {})
        L151: end = next_boj_day(following, years) ; start = next_boj_day(meeting, years) ; goto 616 ; except-handler:
        L152: except ValueError? ; if not match(ValueError): goto 608 ; <exc>
        L153: pop_except ; goto 200
        L152: @608: ; reraise ; pop_except ; reraise
        L154: @616: ; periods.append((meeting, start, end)) ; goto 200
        L155: @666: ; return periods

        def meeting_periods.<locals>.<listcomp>(.0):   # line 136
            L136: for-next .0 (exhausted->138)
            L137: m = <item> ; if not (m.isoformat() in values): goto 8
            L136: @104:
            L137: append tuple(func<code <genexpr>>+iter(values[m.isoformat()])()) ; goto 8 ; @138: ; return [m]

            def meeting_periods.<locals>.<listcomp>.<genexpr>(.0):   # line 136
                L136: ? ; for-next .0 (exhausted->58) ; d = <item> ; (yield date.fromisoformat(d)) ; goto 8 ; @58: ; return None

    def ecb_settlement_check(http, snapshot):   # line 158
        """Independent, same-date FEMP marks; diagnostic only, never a live quote."""
        L160: stamp = date.fromisoformat(snapshot['asof'])
        L161: url = f"https://www.eurex.com/api/v1/overallstatistics/4853044?busdate={stamp:%Y%m%d}&filtertype=overview"
        L162: response = http.get(url, timeout=(10, 25))
        L163: response.raise_for_status()
        L164: data = response.json()
        L165: if not (data.get('meta', {}).get('productCode') != 'FEMP'): goto 314
        L166: raise ValueError('Unexpected exchange product')
        L167: @314: ; dates = data.get('header', {}).get('tradingDates', [])
        L168: if not dates: goto 500 ; if not (datetime.strptime(dates[0], '%d-%m-%Y %H:%M').date() != stamp): goto 530
        L169: @500: ; raise ValueError('Exchange settlement date differs from curve date')
        L170: @530: ; contracts = iter(data.get('dataRows', []))()
        L171: matches = []
        L172: for-next iter(snapshot['meetings']) (exhausted->1026) ; row = <item>
        L173: contract = contracts.get(row['start'].replace('-', ''))
        L174: if contract: goto 718
        L175: goto 614
        L176: @718: ; price = float(contract['dSettle'])
        L177: if not (50 < price): goto 788 ; if (price < 150): goto 792 ; goto 790 ; @788: ; iter(snapshot['meetings'])
        L178: @790: ; goto 614
        L179: @792: ; rate = (100 - price)
        L180: @822:
        L184: @970:
        L180: matches.append({'date': row['date'], 'start': row['start'], 'end': row['end'], 'settlement': price, 'rate_percent': rate, 'change_bps': ((rate - snapshot['base_percent']) * 100), 'curve_minus_futures_bps': ((row['rate_percent'] - rate) * 100), 'volume': contract.get('volume'), 'open_interest': contract.get('openInt')}) ; goto 614
        L185: @1026:
        L185: return {'asof': snapshot['asof'], 'source': url, 'matches': matches, 'note': 'Official daily futures settlement marks; may have zero volume; not live OIS quotes'}

        def ecb_settlement_check.<locals>.<dictcomp>(.0):   # line 170
            L170: for-next .0 (exhausted->56) ; row = <item> ; map-add str(row['date']): row ; goto 6 ; @56: ; return .0