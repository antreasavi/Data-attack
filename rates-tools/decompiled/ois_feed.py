# pseudo-decompiled ois_feed.pyc

def <module>():   # line 1
    """Free Eurex OIS curves, augmented with eligible ICE dated futures quotes.

The public CSV contains daily discount factors, not par swap quotes. Forward
rates are calculated from DF(start)/DF(end) using the index day-count basis.
Meeting estimates cover aligned intermeeting periods; they remain fitted-curve
estimates, not directly observed meeting-dated swap quotes or odds.
BOE/ECB matching period rates use an audited quote-age weighted mean when ICE
has a valid dated observation. Changes remain relative to the curve's overnight
rate at its valuation date. Refreshes every five minutes; quotes can be delayed."""
    L1: __doc__ = "Free Eurex OIS curves, augmented with eligible ICE dated futures quotes.\n\nThe public CSV contains daily discount factors, not par swap quotes. Forward\nrates are calculated from DF(start)/DF(end) using the index day-count basis.\nMeeting estimates cover aligned intermeeting periods; they remain fitted-curve\nestimates, not directly observed meeting-dated swap quotes or odds.\nBOE/ECB matching p...
    L11: annotations = import __future__.annotations ; import __future__
    L13: csv = import csv
    L14: json = import json
    L15: math = import math
    L16: re = import re
    L17: threading = import threading
    L18: monthrange = import calendar.monthrange ; import calendar
    L19: date = import datetime.date ; datetime = import datetime.datetime ; timedelta = import datetime.timedelta ; timezone = import datetime.timezone ; import datetime
    L20: unescape = import html.unescape ; import html
    L21: urljoin = import urllib.parse.urljoin ; urlparse = import urllib.parse.urlparse ; import urllib.parse
    L23: app_logging = import app_logging
    L24: write_text = import atomic_write.write_text ; import atomic_write
    L25: data_dir = import paths.data_dir ; data_file = import paths.data_file ; import paths
    L26: build_session = import ratecore.build_session ; render = import ratecore.render ; import ratecore
    L27: load_calendar = import ois_periods.load_calendar ; meeting_periods = import ois_periods.meeting_periods ; ecb_settlement_check = import ois_periods.ecb_settlement_check ; import ois_periods
    L28: apply_composite = import market_composite.apply_composite ; reference_check = import market_composite.reference_check ; import market_composite
    L30: log = app_logging.get('ois')
    L31: SOURCE = 'https://www.eurex.com/ec-en/clear/eurex-otc-clear/settlement-prices'
    L32: ECB_CALENDAR = 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'
    L33: BOJ_CALENDAR = 'https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm'
    L34: BANKS = {'FED': ('USD.FEDFUNDS.1D', 360, 'Fed Funds'), 'BOE': ('GBP.SONIA.1D', 365, 'SONIA'), 'ECB': ('EUR.ESTR.1D', 360, 'ESTR'), 'BOJ': ('JPY.TONAR.1D', 365, 'TONA')}
    L40: MONTH_COUNT = 24
    L41: MAX_AGE_DAYS = 7
    L42: MAX_OFFSET = 1100
    L45: plain = func<code plain>
    L49: parse_ecb = func<code parse_ecb>
    L58: parse_boj = func<code parse_boj>
    L82: meeting_dates = func<code meeting_dates>
    L95: parse_curves = func<code parse_curves>
    L131: load_curves = func<code load_curves>
    L166: forward = func<code forward>
    L175: add_months = func<code add_months>
    L180: bank_snapshot = func<code bank_snapshot>
    L220: refresh = func<code refresh>
    L295: start = func<code start>
    L306: if not (__name__ == '__main__'): goto 410
    L307: if not refresh(): goto 392 ; goto 394 ; @392: ; @394: ; raise 0(1)
    L306: @410: ; return None

    def plain(html):   # line 45
        L46: return ' '.join(unescape(re.sub('<[^>]+>', ' ', html)).split())

    def parse_ecb(html):   # line 49
        L50: dates = []
        L51: for-next iter(re.findall('<dt\\b[^>]*>(.*?)</dt>\\s*<dd\\b[^>]*>(.*?)</dd>', html, (re.S | re.I))) (exhausted->340) ; day = <item>[0] ; description = <item>[1]
        L52: text = plain(description).lower()
        L53: if not ('monetary policy meeting' in text): goto 338 ; if not ('non-monetary' not in text): goto 338 ; if not ('day 2' in text): goto 338
        L54: dates.append(datetime.strptime(plain(day), '%d/%m/%Y').date()) ; @338: ; goto 96
        L55: @340: ; return sorted(set(dates))

    def parse_boj(html):   # line 58
        L59: dates = []
        L60: months = iter(enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'), 1))()
        L62: for-next iter(re.findall('<table\\b[^>]*>.*?</table>', html, (re.S | re.I))) (exhausted->824) ; table = <item>
        L63: caption = re.search('<caption\\b[^>]*>.*?(20\\d{2}).*?</caption>', table, (re.S | re.I))
        L64: if not caption: goto 256 ; if not ('Date of MPM' not in table): goto 258
        L65: @256: ; goto 148
        L66: @258: ; for-next iter(re.findall('<tr\\b[^>]*>(.*?)</tr>', table, (re.S | re.I))) (exhausted->820) ; row = <item>
        L67: @368: ; cell = re.search('<td\\b[^>]*>(.*?)</td>', row, (re.S | re.I))
        L68: if cell: goto 448
        L69: goto 348
        L70: @448: ; text = re.sub('\\[.*?\\]|\\(.*?\\)', '', plain(cell[1]))
        L71: @548: ; parts = re.findall('([A-Za-z]+)\\.?\\s+(\\d{1,2})|,\\s*(\\d{1,2})', text)
        L72: month = None
        L73: for-next iter(parts) (exhausted->700) ; name = <item>[0] ; day = <item>[1] ; second_day = <item>[2]
        L74: if not name: goto 664
        L75: month = months[name[:3].lower()]
        L76: @664: ; [day or ...] (else goto 682) ; @682: ; final_day = int(second_day) ; goto 580
        L77: @700: ; if not parts: goto 818 ; if not month: goto 818
        L78: dates.append(date(int(caption[1]), month, final_day)) ; @818: ; goto 348
        L66: @820: ; goto 148
        L79: @824: ; return sorted(set(dates))

        def parse_boj.<locals>.<dictcomp>(.0):   # line 60
            L60: for-next .0 (exhausted->24) ; i = <item>[0] ; name = <item>[1] ; map-add name: i ; goto 6 ; @24: ; return .0

    def meeting_dates(bank, http):   # line 82
        L83: if not (bank == 'FED'): goto 46
        L84: _fomc_dates = import fed_ois._fomc_dates ; import fed_ois
        L85: return _fomc_dates()
        L86: @46: ; if not (bank == 'BOE'): goto 90
        L87: _mpc_dates = import boe_ois._mpc_dates ; import boe_ois
        L88: return _mpc_dates()
        L89: @90: ; if not (bank == 'ECB'): goto 130 ; goto 156 ; @130: ; @156: ; url = (BOJ_CALENDAR, parse_boj)[0] ; parser = (BOJ_CALENDAR, parse_boj)[1]
        L90: response = http.get(url, timeout=(10, 25))
        L91: response.raise_for_status()
        L92: return parser(response.text)

    def parse_curves(lines):   # line 95
        """Keep the daily short end; reject mixed dates and conflicting values."""
        L97: curves = iter(BANKS.values())()
        L98: asof = None
        L99: reader = csv.DictReader(lines)
        L100: required = {}+frozenset({'Curve ID', 'Value', 'Value DateTime', 'Value Type', 'Maturity Date', 'Maturity Offset'})
        L101: [reader.fieldnames or ...] (else goto 166) ; @166: ; if required.issubset([]): goto 212
        L102: raise ValueError('Eurex CSV schema changed')
        L103: @212: ; for-next iter(reader) (exhausted->872) ; row = <item>
        L104: key = row['Curve ID']
        L105: if (key not in curves): goto 270 ; if not (row['Value Type'] != 'S'): goto 272
        L106: @270: ; goto 216
        L107: @272: ; offset = int(row['Maturity Offset'])
        L108: @328: ; if not (0 <= offset): goto 352 ; if (offset <= MAX_OFFSET): goto 356 ; goto 354 ; @352: ; iter(reader)
        L109: @354: ; goto 216
        L110: @356: ; stamp = date.fromisoformat(row['Value DateTime'][:10])
        L111: if asof is None: goto 470 ; if not (stamp != asof): goto 470
        L112: raise ValueError('Mixed curve valuation dates')
        L113: @470: ; asof = stamp
        L114: @496: ; maturity = date.fromisoformat(row['Maturity Date'][:10])
        L115: value = float(row['Value'])
        L116: if ((maturity - stamp).days != offset): goto 664 ; if not math.isfinite(value): goto 664 ; if not (value <= 0): goto 694
        L117: @664: ; raise ValueError('Invalid discount factor/date')
        L118: @694: ; old = curves[key].get(str(offset))
        L119: if old is None: goto 820 ; if not (old != value): goto 820
        L120: raise ValueError('Conflicting discount factors')
        L121: @820: ; curves[key][str(offset)] = value ; goto 216
        L122: @872: ; if asof is not None: goto 906
        L123: raise ValueError('No OIS curves found')
        L124: @906: ; for-next iter(curves.items()) (exhausted->1100) ; key = <item>[0] ; points = <item>[1]
        L125: points['0'] = 1.0
        L126: if not func<code <genexpr>>(iter(range((MAX_OFFSET + 1)))()): goto 1098
        L127: raise ValueError(f"Incomplete daily curve: {key}")
        L126: @1098: ; goto 946
        L128: @1100: ; return {'asof': asof.isoformat(), 'curves': curves}

        def parse_curves.<locals>.<dictcomp>(.0):   # line 97
            L97: for-next .0 (exhausted->26) ; key = <item>[0] ; _ = <item>[1] ; _ = <item>[2] ; map-add key: {} ; goto 6 ; @26: ; return .0

        def parse_curves.<locals>.<genexpr>(.0):   # line 126
            L126: ? ; for-next .0 (exhausted->54) ; day = <item> ; (yield (str(day) not in points)) ; goto 10 ; @54: ; return None

    def load_curves(http):   # line 131
        L132: cache_path = (data_dir() / 'ois_curves.json')
        L133: cached = None
        L135: cached = json.loads(cache_path.read_text(encoding='utf-8')) ; goto 170 ; except-handler:
        L136: except (OSError, ValueError)? ; if not match((OSError, ValueError)): goto 162 ; <exc>
        L137: pop_except ; goto 170
        L136: @162: ; reraise ; pop_except ; reraise
        L138: @170:
        L139: page = http.get(SOURCE, timeout=(10, 25))
        L140: page.raise_for_status()
        L141: links = re.findall('href=["\\\']([^"\\\']*settlement-prices_(\\d{8})\\.csv)["\\\']', page.text, re.I)
        L142: if links: goto 376
        L143: raise ValueError('Eurex settlement CSV link missing')
        L144: @376: ; link = max(links, key=func<code <lambda>>)[0] ; _ = max(links, key=func<code <lambda>>)[1]
        L145: url = urljoin(SOURCE, unescape(link))
        L146: if not (urlparse(url).hostname != 'www.eurex.com'): goto 564
        L147: raise ValueError('Unexpected settlement file host')
        L148: @564: ; if not cached: goto 626 ; if not (cached.get('url') == url): goto 626
        L149: return (cached, None)
        L150: @626: ; with http.get(url, timeout=(10, 60), stream=True): ; response = <as http.get(url, timeout=(10, 60), stream=True)>
        L151: response.raise_for_status()
        L153: response.encoding = 'utf-8-sig'
        L154: payload = parse_curves(response.iter_lines(decode_unicode=True))
        L150: None(None, None) ; goto 846 ; except-handler: ; <WITH_EXCEPT_START > ; if <exc>: goto 838 ; reraise ; pop_except ; reraise ; @838: ; ? ; pop_except ; <with-exit> ; ?
        L155: @846: ; payload['url'] = url
        L156: payload['fetched_at'] = datetime.now(timezone.utc).isoformat()
        L157: write_text(cache_path, json.dumps(payload))
        L158: return (payload, None) ; except-handler:
        L159: except Exception? ; if not match(Exception): goto 1140 ; exc = <exc>
        L160: if not cached: goto 1130
        L161: log.warning('Eurex refresh failed; using dated cache: %s', exc)
        L162: pop_except ; exc = None ; del exc ; return (cached, 'Source refresh failed; showing cached curve')
        L163: @1130: ; raise  ; exc = None ; del exc ; reraise
        L159: @1140: ; reraise ; pop_except ; reraise

        def load_curves.<locals>.<lambda>(item):   # line 144
            L144: return item[1]

    def forward(points, asof, start, end, basis):   # line 166
        L167: if (end <= start): goto 26 ; if not (start < asof): goto 56
        L168: @26: ; raise ValueError('Invalid forward interval')
        L169: @56: ; last = (end - asof).days ; first = (start - asof).days
        L171: b = points[str(last)] ; a = points[str(first)]
        L172: return (((math.expm1((math.log(a) - math.log(b))) * basis) / (last - first)) * 100)

    def add_months(day, count):   # line 175
        L176: year = divmod(((((day.year * 12) + day.month) - 1) + count), 12)[0] ; month = divmod(((((day.year * 12) + day.month) - 1) + count), 12)[1]
        L177: return date(year, (month + 1), min(day.day, monthrange(year, (month + 1))[1]))

    def bank_snapshot(bank, payload, meetings, today, period_calendar):   # line 180
        L181: key = BANKS[bank][0] ; basis = BANKS[bank][1] ; benchmark = BANKS[bank][2]
        L182: asof = date.fromisoformat(payload['asof'])
        L183: age = (today - asof).days
        L184: if (age < 0): goto 142 ; if not (age > MAX_AGE_DAYS): goto 180
        L185: @142: ; raise ValueError(f"Curve date {asof} is outside the freshness limit")
        L186: @180: ; points = payload['curves'][key]
        L187: base = forward(points, asof, asof, (asof + timedelta(days=1)), basis)
        L188: monthly = []
        L190: first = add_months(today.replace(day=1), 1)
        L191: front_rate = forward(points, asof, today, first, basis)
        L192: front_month = {'start': today.isoformat(), 'end': first.isoformat(), 'rate_percent': front_rate, 'change_bps': ((front_rate - base) * 100), 'partial': (today.day != 1)}
        L195: for-next iter(range(MONTH_COUNT)) (exhausted->802) ; i = <item>
        L196: end = add_months(first, (i + 1)) ; start = add_months(first, i)
        L197: rate = forward(points, asof, start, end, basis)
        L198: monthly.append({'start': start.isoformat(), 'end': end.isoformat(), 'rate_percent': rate, 'change_bps': ((rate - base) * 100)}) ; goto 552
        L200: @802: ; path = []
        L201: for-next iter(meeting_periods(bank, meetings, period_calendar)) (exhausted->1106) ; meeting = <item>[0] ; start = <item>[1] ; end = <item>[2]
        L202: if not (today < meeting): goto 1104 ; if not ((meeting - today).days <= 730): goto 1104
        L203: rate = forward(points, asof, start, end, basis)
        L205: @1052:
        L204: path.append({'date': meeting.isoformat(), 'start': start.isoformat(), 'end': end.isoformat(), 'rate_percent': rate, 'change_bps': ((rate - base) * 100)}) ; @1104: ; goto 840
        L207: @1106:
        L210: [period_calendar or ...] (else goto 1188) ; @1188:
        L207: return {'bank': bank, 'benchmark': benchmark, 'asof': asof.isoformat(), 'source': SOURCE, 'source_file': payload['url'], 'base_percent': base, 'front_month': front_month, 'monthly': monthly, 'meetings': path, 'period_calendar_sources': {}.get('sources', []), 'method': 'Annualized compounded intermeeting OIS forwards; changes versus curve-date overnight rate', 'meeting_convention': {'ECB': 'Published ECB reserve maintenance periods', 'BOE': 'MPC announcement to next announcement (ICE MPC SONIA convention)', 'FED': 'Assumed next-day implementation to next implementation', 'BOJ': 'Assumed next BOJ business day to next implementation; official bank holidays'}[bank]}

    def refresh(http):   # line 220
        L221: [http or ...] (else goto 36) ; @36: ; http = build_session()
        L222: today = date.today()
        L224: payload = load_curves(http)[0] ; warning = load_curves(http)[1] ; goto 286 ; except-handler:
        L225: except Exception? ; if not match(Exception): goto 278 ; <exc>
        L226: log.exception('OIS download failed')
        L227: for-next iter(BANKS) (exhausted->272) ; bank = <item>
        L228: write_text(data_file(bank), f"{bank} OIS --\nSOURCE UNAVAILABLE\nSEE LAST DATED DATA") ; goto 202
        L229: @272: ; pop_except ; return False
        L225: @278: ; reraise ; pop_except ; reraise
        L230: @286: ; success = True
        L231: for-next iter(BANKS) (exhausted->2434) ; bank = <item>
        L233: calendar_warning = None
        L234: period_calendar = None
        L235: period_warning = None
        L237: @342: ; meetings = meeting_dates(bank, http)
        L238: if func<code <genexpr>>(iter(meetings)()): goto 442
        L239: raise ValueError('No future meetings parsed')
        L238: @442: ; goto 538 ; except-handler:
        L240: except Exception? ; if not match(Exception): goto 530 ; <exc>
        L241: log.exception('%s calendar unavailable', bank)
        L242: meetings = []
        L243: calendar_warning = 'Meeting calendar unavailable; monthly curve remains available' ; pop_except ; goto 538
        L240: @530: ; reraise ; pop_except ; reraise
        L244: @538: ; if not (bank in ('ECB', 'BOJ')): goto 682 ; if not meetings: goto 682
        L246: period_calendar = load_calendar(bank, http)[0] ; period_warning = load_calendar(bank, http)[1] ; goto 682 ; except-handler:
        L247: except Exception? ; if not match(Exception): goto 674 ; <exc>
        L248: log.exception('%s period calendar unavailable', bank)
        L249: period_warning = 'Meeting periods unavailable; monthly curve remains available' ; pop_except ; goto 682
        L247: @674: ; reraise ; pop_except ; reraise
        L250: @682: ; snapshot = bank_snapshot(bank, payload, meetings, today, period_calendar)
        L251: future = iter(meetings)()
        L252: covered = iter(snapshot['meetings'])()
        L253: snapshot['unavailable_meetings'] = iter(future)()
        L254: if not snapshot['unavailable_meetings']: goto 900
        L255: period_warning = func<code <genexpr>>(iter((period_warning, 'Meeting coverage ends where published period endpoints end'))())
        L256: @900: ; if not (bank == 'ECB'): goto 1058
        L258: snapshot['exchange_check'] = ecb_settlement_check(http, snapshot) ; goto 1058 ; except-handler:
        L259: except Exception? ; if not match(Exception): goto 1050 ; <exc>
        L260: log.warning('ECB same-date exchange check unavailable', exc_info=True)
        L261: snapshot['exchange_check'] = {'matches': [], 'note': 'Same-date exchange check unavailable'} ; pop_except ; goto 1058
        L259: @1050: ; reraise ; pop_except ; reraise
        L262: @1058: ; [func<code <genexpr>>(iter((warning, calendar_warning, period_warning))()) or ...] (else goto 1128) ; @1128: ; snapshot['warning'] = None
        L264: snapshot = apply_composite(http, snapshot) ; goto 1262 ; except-handler:
        L265: except Exception? ; if not match(Exception): goto 1254 ; <exc>
        L266: log.warning('%s composite unavailable; retaining Eurex estimate', bank, exc_info=True) ; pop_except ; goto 1262
        L265: @1254: ; reraise ; pop_except ; reraise
        L267: @1262: ; write_text((data_dir() / f"ois_{bank.lower()}.json"), json.dumps(snapshot, indent=2))
        L268: path = iter(snapshot['meetings'])()
        L269: if not path: goto 1494 ; goto 1502 ; @1494: ; @1502: ; text = f"{bank} OIS\nCALENDAR UNAVAILABLE\nMONTHLY DATA ON HOVER"
        L272: if not future: goto 2036 ; if not path: goto 2036
        L273: lines = text.splitlines()
        L274: if not (min(future).isoformat() not in covered): goto 1716
        L275: lines[0] = (f"{bank} {min(future):%b}".upper() + ' --')
        L276: @1716: ; this_year = iter(future)()
        L277: if not this_year: goto 1908 ; if not (max(this_year).isoformat() not in covered): goto 1908
        L278: lines[1] = (f"{bank} {max(this_year):%b%y}".upper() + ' --')
        L279: @1908: ; if not (min(future).isoformat() not in covered): goto 1994
        L280: lines[2] = f"{bank} PATH INCOMPLETE"
        L281: @1994: ; text = '\n'.join(lines)
        L282: @2036: ; write_text(data_file(bank), text)
        L283: log.info('%s OIS %s: %d months, %d meetings', bank, snapshot['asof'], len(snapshot['monthly']), len(path)) ; goto 304 ; except-handler:
        L284: except Exception? ; if not match(Exception): goto 2426 ; <exc>
        L285: success = False
        L286: log.exception('%s OIS failed', bank)
        L287: write_text(data_file(bank), f"{bank} OIS --\nCURVE UNAVAILABLE\nASOF {payload.get('asof', '--')}") ; pop_except ; goto 304
        L284: @2426: ; reraise ; pop_except ; reraise
        L288: @2434:
        L289: reference_check(http) ; goto 2556 ; except-handler:
        L290: except Exception? ; if not match(Exception): goto 2548 ; <exc>
        L291: log.warning('Reference curve check failed', exc_info=True) ; pop_except ; goto 2556
        L290: @2548: ; reraise ; pop_except ; reraise
        L292: @2556: ; return success

        def refresh.<locals>.<genexpr>(.0):   # line 238
            L238: ? ; for-next .0 (exhausted->32) ; d = <item> ; (yield (d > today)) ; goto 10 ; @32: ; return None

        def refresh.<locals>.<listcomp>(.0):   # line 251
            L251: for-next .0 (exhausted->58) ; d = <item> ; if not (today < d): goto 8 ; @40: ; if not ((d - today).days <= 730): goto 8 ; append d ; goto 8 ; @58: ; return .0

        def refresh.<locals>.<setcomp>(.0):   # line 252
            L252: for-next .0 (exhausted->28) ; r = <item> ; set-add r['date'] ; goto 6 ; @28: ; return .0

        def refresh.<locals>.<listcomp>(.0):   # line 253
            L253: for-next .0 (exhausted->98) ; d = <item> ; if not (d.isoformat() not in covered): goto 8 ; append d.isoformat() ; goto 8 ; @98: ; return .0

        def refresh.<locals>.<genexpr>(.0):   # line 255
            L255: ? ; for-next .0 (exhausted->26) ; w = <item> ; if not w: goto 8 ; (yield w) ; @24: ; goto 8 ; @26: ; return None

        def refresh.<locals>.<genexpr>(.0):   # line 262
            L262: ? ; for-next .0 (exhausted->26) ; w = <item> ; if not w: goto 8 ; (yield w) ; @24: ; goto 8 ; @26: ; return None

        def refresh.<locals>.<listcomp>(.0):   # line 268
            L268: for-next .0 (exhausted->80) ; p = <item> ; append (date.fromisoformat(p['date']), p['rate_percent']) ; goto 6 ; @80: ; return .0

        def refresh.<locals>.<listcomp>(.0):   # line 276
            L276: for-next .0 (exhausted->50) ; d = <item> ; if not (d.year == today.year): goto 8 ; append d ; goto 8 ; @50: ; return .0

    def start(stop):   # line 295
        L296: http = build_session()
        L297: if stop.is_set(): goto 278
        L299: refresh(http) ; goto 188 ; except-handler:
        L300: except Exception? ; if not match(Exception): goto 180 ; <exc>
        L301: log.exception('OIS refresh failed') ; pop_except ; goto 188
        L300: @180: ; reraise ; pop_except ; reraise
        L302: @188: ; if not stop.wait(300): goto 234
        L303: return None
        L297: @234: ; if not stop.is_set(): goto 70 ; return None ; @278: ; return None