# pseudo-decompiled boe_ois.pyc

def <module>():   # line 1
    """MPC-implied policy path from the Bank of England's own OIS curve.

Every input comes from the Bank, free and unauthenticated:
  * MPC dates       - bankofengland.co.uk upcoming-MPC-dates page
  * Bank Rate/SONIA - Interactive Statistical Database (IUDBEDR / IUDSOIA)
  * OIS forwards    - latest-yield-curve-data.zip, "OIS daily data current
                      month.xlsx", sheet "1. fwds, short end"

The instantaneous forward at horizon T is the market's expected overnight rate
at T, so reading the curve shortly after a meeting date gives the Bank Rate
expected to prevail once that decision has landed. SONIA sits a couple of bp
under Bank Rate, so the live spread is added back to state the answer in Bank
Rate terms.

Note the curve is T+1: the Bank publishes each day's fit by noon the next
business day, so `curve_date` normally trails today by one business day."""
    L1: <SETUP_ANNOTATIONS > ; __doc__ = 'MPC-implied policy path from the Bank of England\'s own OIS curve.\n\nEvery input comes from the Bank, free and unauthenticated:\n  * MPC dates       - bankofengland.co.uk upcoming-MPC-dates page\n  * Bank Rate/SONIA - Interactive Statistical Database (IUDBEDR / IUDSOIA)\n  * OIS forwards    - latest-yield-curve-data.zip, "OIS daily data current\n                      month.xlsx", sheet "1. fwds,...
    L18: annotations = import __future__.annotations ; import __future__
    L20: io = import io
    L21: re = import re
    L22: zipfile = import zipfile
    L23: date = import datetime.date ; datetime = import datetime.datetime ; timedelta = import datetime.timedelta ; import datetime
    L24: List = import typing.List ; Optional = import typing.Optional ; Tuple = import typing.Tuple ; import typing
    L26: app_logging = import app_logging
    L27: Path = import ratecore.Path ; session = import ratecore.session ; import ratecore
    L29: log = app_logging.get('rates')
    L31: MPC_DATES_URL = 'https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates'
    L32: YIELD_CURVE_ZIP = 'https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip'
    L34: OIS_MEMBER = 'OIS daily data current month.xlsx'
    L35: OIS_SHEET = '1. fwds, short end'
    L36: IADB = 'https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp?csv.x=yes&Datefrom={frm}&Dateto=now&SeriesCodes={code}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N'
    L40: MONTH_NAME = iter(enumerate([*('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')]))()
    L46: POST_MEETING_DAYS = 14
    L47: AVG_DAYS_PER_MONTH = 30.4375
    L49: _calendar_cache = {'fetched': None, 'dates': []} ; __annotations__['_calendar_cache'] = 'dict'
    L52: _mpc_dates = func<code _mpc_dates>
    L86: _iadb_latest = func<code _iadb_latest>
    L101: _forward_curve = func<code _forward_curve>
    L129: _interp = func<code _interp>
    L141: fetch = func<code fetch> ; return None

    def <dictcomp>(.0):   # line 40
        L40: for-next .0 (exhausted->30) ; i = <item>[0] ; m = <item>[1] ; map-add m: (i + 1) ; goto 6 ; @30: ; return .0

    def _mpc_dates(timeout):   # line 52
        """Scheduled MPC announcement dates. Cached for the day."""
        L54: today = date.today()
        L55: if not (_calendar_cache['fetched'] == today): goto 126 ; if not _calendar_cache['dates']: goto 126
        L56: return _calendar_cache['dates']
        L58: @126: ; r = session.get(MPC_DATES_URL, timeout=timeout)
        L59: r.raise_for_status()
        L60: html = r.text
        L62: out = []
        L63: for-next iter(re.findall('<table.*?</table>', html, re.S)) (exhausted->748) ; table = <item>
        L66: preceding = html[:html.find(table)]
        L67: years = re.findall('(20\\d{2})', preceding)
        L68: if years: goto 412
        L69: goto 302
        L70: @412: ; year = int(years[-1])
        L71: @522: ; text = re.sub('&nbsp;', ' ', re.sub('<[^>]+>', ' ', table))
        L72: for-next iter(re.findall('(\\d{1,2})\\s+(January|February|March|April|May|June|July|August|September|October|November|December)', text)) (exhausted->746) ; day_text = <item>[0] ; month_text = <item>[1]
        L76: out.append(date(year, MONTH_NAME[month_text], int(day_text))) ; goto 580 ; except-handler:
        L77: except ValueError? ; if not match(ValueError): goto 738 ; <exc>
        L78: pop_except ; goto 580
        L77: @738: ; reraise ; pop_except ; reraise
        L72: @746: ; goto 302
        L80: @748: ; out = sorted(set(out))
        L81: if not out: goto 864
        L82: @848: ; _calendar_cache.update(fetched=today, dates=out)
        L83: @864: ; return out

    def _iadb_latest(code, timeout):   # line 86
        L87: frm = (date.today() - timedelta(days=60)).strftime('%d/%b/%Y')
        L88: r = session.get(IADB.format(frm=frm, code=code), timeout=timeout)
        L89: r.raise_for_status()
        L90: value = None
        L91: for-next iter(r.text.strip().splitlines()) (exhausted->502) ; line = <item>
        L92: parts = line.split(',')
        L93: if not (len(parts) >= 2): goto 500
        L95: value = float(parts[1]) ; goto 338 ; except-handler:
        L96: except ValueError? ; if not match(ValueError): goto 492 ; <exc>
        L97: pop_except ; goto 338
        L96: @492: ; reraise ; pop_except ; reraise
        L93: @500: ; goto 338
        L98: @502: ; return value

    def _forward_curve(timeout):   # line 101
        """(curve_date, [(months, rate), ...]) from the Bank's daily OIS fit."""
        L103: openpyxl = import openpyxl
        L105: r = session.get(YIELD_CURVE_ZIP, timeout=timeout)
        L106: r.raise_for_status()
        L107: with zipfile.ZipFile(io.BytesIO(r.content)): ; z = <as zipfile.ZipFile(io.BytesIO(r.content))>
        L108: raw = z.read(OIS_MEMBER)
        L107: None(None, None) ; goto 290 ; except-handler: ; <WITH_EXCEPT_START > ; if <exc>: goto 282 ; reraise ; pop_except ; reraise ; @282: ; ? ; pop_except ; <with-exit> ; ?
        L110: @290: ; wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        L112: ws = wb[OIS_SHEET]
        L113: rows = list(ws.iter_rows(values_only=True))
        L115: wb.close() ; goto 564 ; except-handler: ; wb.close() ; reraise ; pop_except ; reraise
        L117: @564: ; horizons = iter(rows[2][1:])()
        L118: dated = iter(rows)()
        L119: if not horizons: goto 648 ; if dated: goto 656
        L120: @648: ; return (None, [])
        L122: @656: ; last = dated[-1]
        L123: values = list(last[1:(1 + len(horizons))])
        L124: points = iter(zip(horizons, values))()
        L126: return (last[0].date(), points)

        def _forward_curve.<locals>.<listcomp>(.0):   # line 117
            L117: for-next .0 (exhausted->72) ; c = <item> ; if not isinstance(c, (int, float)): goto 6 ; append c ; goto 6 ; @72: ; return .0

        def _forward_curve.<locals>.<listcomp>(.0):   # line 118
            L118: for-next .0 (exhausted->70) ; row = <item> ; if not isinstance(row[0], datetime): goto 6 ; append row ; goto 6 ; @70: ; return .0

        def _forward_curve.<locals>.<listcomp>(.0):   # line 124
            L124: for-next .0 (exhausted->82) ; h = <item>[0] ; v = <item>[1]
            L124: if not isinstance(v, (int, float)): goto 6 ; append (h, v) ; goto 6 ; @82: ; return .0

    def _interp(points, months):   # line 129
        L130: if points: goto 10
        L131: return None
        L132: @10: ; if not (months <= points[0][0]): goto 74
        L133: return points[0][1]
        L134: @74: ; for-next iter(zip(points, points[1:])) (exhausted->242) ; m1 = <item>[0][0] ; v1 = <item>[0][1] ; m2 = <item>[1][0] ; v2 = <item>[1][1]
        L135: if not (m1 <= months): goto 172 ; if not (months <= m2): goto 240 ; goto 176 ; @172: ; iter(zip(points, points[1:])) ; goto 122
        L136: @176: ; span = (m2 - m1)
        L137: if not (span == 0): goto 202 ; goto 234 ; @202: ; @230: ; @234: ; v1 ; return (v1 + (((v2 - v1) * (months - m1)) / span))
        L135: @240: ; goto 122
        L138: @242: ; return points[-1][1]

    def fetch():   # line 141
        L142: bank_rate = _iadb_latest('IUDBEDR')
        L143: sonia = _iadb_latest('IUDSOIA')
        L144: if bank_rate is None: goto 72 ; if sonia is not None: goto 132
        L145: @72: ; log.warning('BOE: missing Bank Rate (%s) or SONIA (%s)', bank_rate, sonia)
        L146: return None
        L147: @132: ; spread = (bank_rate - sonia)
        L149: curve_date = _forward_curve()[0] ; points = _forward_curve()[1]
        L150: if points: goto 236
        L151: log.warning('BOE: could not read OIS forward curve')
        L152: return None
        L154: @236: ; today = date.today()
        L155: meetings = iter(_mpc_dates())()
        L156: if meetings: goto 386
        L157: log.warning('BOE: no upcoming MPC dates parsed')
        L158: return None
        L160: @386: ; path = []
        L161: for-next iter(meetings) (exhausted->574) ; meeting = <item>
        L162: offset = ((meeting + timedelta(days=POST_MEETING_DAYS)) - curve_date)
        L163: months = (offset.days / AVG_DAYS_PER_MONTH)
        L164: fwd = _interp(points, months)
        L165: if fwd is not None: goto 520
        L166: goto 394
        L167: @520: ; path.append((meeting, (fwd + spread))) ; goto 394
        L169: @574: ; if path: goto 634
        L170: log.warning('BOE: no meetings mapped onto the curve')
        L171: return None
        L172: @634: ; @646: ; log.info('BOE: curve %s, Bank Rate %.2f, SONIA %.4f', curve_date, bank_rate, sonia)
        L173: return (bank_rate, path)

        def fetch.<locals>.<listcomp>(.0):   # line 155
            L155: for-next .0 (exhausted->30) ; d = <item> ; if not (d > today): goto 8 ; append d ; goto 8 ; @30: ; return .0