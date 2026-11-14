# pseudo-decompiled ratecore.pyc

def <module>():   # line 1
    """Shared plumbing for the policy-rate fetchers: HTTP, scheduling, rendering.

Each central bank module supplies a `fetch()` returning (base_rate, path),
where `path` is [(meeting_date, implied_rate_after_that_meeting), ...] and
both rates are in percent. This module turns that into the three ticker lines
and runs it on the daily schedule."""
    L1: __doc__ = 'Shared plumbing for the policy-rate fetchers: HTTP, scheduling, rendering.\n\nEach central bank module supplies a `fetch()` returning (base_rate, path),\nwhere `path` is [(meeting_date, implied_rate_after_that_meeting), ...] and\nboth rates are in percent. This module turns that into the three ticker lines\nand runs it on the daily schedule.\n'
    L8: annotations = import __future__.annotations ; import __future__
    L10: threading = import threading
    L11: date = import datetime.date ; datetime = import datetime.datetime ; timedelta = import datetime.timedelta ; timezone = import datetime.timezone ; import datetime
    L12: Callable = import typing.Callable ; List = import typing.List ; Optional = import typing.Optional ; Tuple = import typing.Tuple ; import typing
    L14: requests = import requests
    L15: HTTPAdapter = import requests.adapters.HTTPAdapter ; import requests.adapters
    L16: Retry = import urllib3.util.retry.Retry ; import urllib3.util.retry
    L18: app_logging = import app_logging
    L19: write_text = import atomic_write.write_text ; import atomic_write
    L20: data_file = import paths.data_file ; import paths
    L22: log = app_logging.get('rates')
    L24: MONTHS = ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC')
    L26: DEFAULT_MOVE_BPS = 25.0
    L31: SCHEDULE_TZ = 'Europe/London'
    L32: SCHEDULE_HHMM = ((6, 30), (11, 20), (16, 10), (21, 0))
    L35: WAKE_CAP_SECONDS = 900
    L37: Path = List[Tuple[(date, float)]]
    L40: _schedule_tz = func<code _schedule_tz>
    L52: _TZ = _schedule_tz()
    L55: build_session = func<code build_session>
    L73: session = build_session()
    L76: _mon = func<code _mon>
    L80: _mon_yy = func<code _mon_yy>
    L84: _fmt_bps = func<code _fmt_bps>
    L90: blank = func<code blank>
    L94: render = func<code render>
    L124: _slots_on = func<code _slots_on>
    L129: _next_slot = func<code _next_slot>
    L138: _sleep_until = func<code _sleep_until>
    L150: FetchFn = Callable[([], Optional[Tuple[(float, Path)]])]
    L153: fetch_text = func<code fetch_text>
    L168: run_loop = func<code run_loop>
    L196: run_forever = func<code run_forever> ; return None

    def _schedule_tz():   # line 40
        """Europe/London, or UTC if tzdata is missing (e.g. a stripped EXE build)."""
        L43: ZoneInfo = import zoneinfo.ZoneInfo ; import zoneinfo
        L45: return ZoneInfo(SCHEDULE_TZ) ; except-handler:
        L46: except Exception? ; if not match(Exception): goto 176 ; e = <exc>
        L47: log.warning('no %s tzdata (%s); scheduling against UTC instead', SCHEDULE_TZ, e)
        L49: pop_except ; e = None ; del e ; return timezone.utc ; e = None ; del e ; reraise
        L46: @176: ; reraise ; pop_except ; reraise

    def build_session():   # line 55
        L56: s = requests.Session()
        L59: s.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        L63: retry = Retry(total=3, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=('GET',))
        L69: s.mount('https://', HTTPAdapter(max_retries=retry, pool_maxsize=4))
        L70: return s

    def _mon(d):   # line 76
        L77: return MONTHS[(d.month - 1)]

    def _mon_yy(d):   # line 80
        L81: return f"{MONTHS[(d.month - 1)]}{(d.year % 100):02d}"

    def _fmt_bps(bps):   # line 84
        L86: rounded = round(bps, 1)
        L87: if not (rounded == 0): goto 50 ; goto 52 ; @50: ; @52: ; return f"{rounded:+.1f}bps"

    def blank(prefix):   # line 90
        L91: return '\n'.join(([f"{prefix} --"] * 3))

    def render(prefix, base, path, move_bps):   # line 94
        """Three ticker lines: next meeting, year end, first full move."""
        L97: if path: goto 40
        L98: return blank(prefix)
        L100: @40: ; path = sorted(path, key=func<code <lambda>>)
        L101: bps = iter(path)()
        L103: nxt_d = bps[0][0] ; nxt_b = bps[0][1]
        L104: line1 = f"{prefix} {_mon(nxt_d)} {_fmt_bps(nxt_b)}"
        L106: year = datetime.now().year
        L107: in_year = iter(bps)()
        L108: [in_year or ...] (else goto 280) ; @280: ; ye_d = bps[-1][0] ; ye_b = bps[-1][1]
        L109: line2 = f"{prefix} {_mon_yy(ye_d)} {_fmt_bps(ye_b)}"
        L111: line3 = None
        L112: for-next iter(bps) (exhausted->528) ; d = <item>[0] ; b = <item>[1]
        L113: if not (abs(b) >= move_bps): goto 526
        L114: if not (b > 0): goto 444 ; goto 448 ; @444: ; @448: ; step = (-move_bps)
        L115: line3 = f"{prefix} {_fmt_bps(step)} BY {_mon_yy(d)}"
        L116: move_bps ; goto 528
        L113: @526: ; goto 380
        L117: @528: ; if line3 is not None: goto 674
        L118: if not (bps[-1][1] >= 0): goto 572 ; goto 576 ; @572: ; @576: ; step = (-move_bps)
        L119: line3 = f"{prefix} {_fmt_bps(step)} NOT BY {_mon_yy(bps[-1][0])}"
        L121: @674: ; @676: ; return '\n'.join((line1, line2, line3))

        def render.<locals>.<lambda>(md):   # line 100
            L100: return md[0]

        def render.<locals>.<listcomp>(.0):   # line 101
            L101: for-next .0 (exhausted->40) ; d = <item>[0] ; r = <item>[1] ; append (d, ((r - base) * 100.0)) ; goto 8 ; @40: ; return .0

        def render.<locals>.<listcomp>(.0):   # line 107
            L107: for-next .0 (exhausted->52) ; db = <item> ; if not (db[0].year == year): goto 8 ; append db ; goto 8 ; @52: ; return .0

    def _slots_on(day):   # line 124
        L125: return func<code <genexpr>>(iter(SCHEDULE_HHMM)())

        def _slots_on.<locals>.<genexpr>(.0):   # line 125
            L125: ? ; for-next .0 (exhausted->108)
            L126: h = <item>[0] ; m = <item>[1]
            L125: (yield datetime(day.year, day.month, day.day, h, m, tzinfo=_TZ)) ; goto 10 ; @108: ; return None

    def _next_slot(now):   # line 129
        L130: today = now.astimezone(_TZ).date()
        L131: for-next iter((0, 1)) (exhausted->194) ; offset = <item>
        L132: for-next iter(_slots_on((today + timedelta(days=offset)))) (exhausted->192) ; slot = <item>
        L133: if not (slot > now): goto 190
        L134: iter(_slots_on((today + timedelta(days=offset)))) ; iter((0, 1)) ; return slot
        L133: @190: ; goto 162
        L132: @192: ; goto 94
        L135: @194: ; @222: ; return (now + timedelta(seconds=WAKE_CAP_SECONDS))

    def _sleep_until(target, stop):   # line 138
        """Wait for `target`. False if `stop` was set first (GUI quitting)."""
        L140: if stop.is_set(): goto 284
        L141: remaining = (target - datetime.now(timezone.utc)).total_seconds()
        L142: if not (remaining <= 0): goto 160
        L143: return True
        L145: @160: ; if not stop.wait(min(remaining, WAKE_CAP_SECONDS)): goto 244
        L146: return False
        L140: @244: ; if not stop.is_set(): goto 42
        L147: @284: ; return False

    def fetch_text(prefix, fetch):   # line 153
        L155: result = fetch() ; goto 142 ; except-handler:
        L156: except Exception? ; if not match(Exception): goto 134 ; <exc>
        L157: log.exception('%s: fetch failed', prefix)
        L158: pop_except ; return blank(prefix)
        L156: @134: ; reraise ; pop_except ; reraise
        L159: @142: ; if result: goto 230
        L160: log.warning('%s: fetch returned nothing', prefix)
        L161: return blank(prefix)
        L162: @230: ; base = result[0] ; path = result[1]
        L163: text = render(prefix, base, path)
        L164: log.info('%s: base=%.4f | %s', prefix, base, text.replace('\n', ' | '))
        L165: return text

    def run_loop(prefix, fetch, stop):   # line 168
        """Fetch on the daily schedule until `stop` is set. Runs in a daemon thread."""
        L170: out = data_file(prefix)
        L171: if out.exists(): goto 236
        L173: write_text(out, blank(prefix)) ; goto 236 ; except-handler:
        L174: except OSError? ; if not match(OSError): goto 228 ; e = <exc>
        L175: log.error('%s: cannot write placeholder: %s', prefix, e) ; pop_except ; e = None ; del e ; goto 236 ; e = None ; del e ; reraise
        L174: @228: ; reraise ; pop_except ; reraise
        L179: @236:
        L180: write_text(out, fetch_text(prefix, fetch)) ; goto 386 ; except-handler:
        L181: except Exception? ; if not match(Exception): goto 378 ; <exc>
        L182: log.exception('%s: startup write failed', prefix) ; pop_except ; goto 386
        L181: @378: ; reraise ; pop_except ; reraise
        L184: @386: ; if stop.is_set(): goto 884
        L185: target = _next_slot(datetime.now(timezone.utc))
        L186: log.info('%s: next refresh %s', prefix, target.astimezone(_TZ).strftime('%Y-%m-%d %H:%M %Z'))
        L188: if _sleep_until(target, stop): goto 690
        L189: return None
        L190: @690:
        L191: write_text(out, fetch_text(prefix, fetch)) ; goto 840 ; except-handler:
        L192: except Exception? ; if not match(Exception): goto 832 ; <exc>
        L193: log.exception('%s: scheduled write failed', prefix) ; pop_except ; goto 840
        L192: @832: ; reraise ; pop_except ; reraise
        L184: @840: ; if not stop.is_set(): goto 426 ; return None ; @884: ; return None

    def run_forever(prefix, fetch):   # line 196
        L197: stop = threading.Event()
        L199: run_loop(prefix, fetch, stop) ; return None ; except-handler:
        L200: except KeyboardInterrupt? ; if not match(KeyboardInterrupt): goto 146 ; <exc>
        L201: stop.set() ; pop_except ; return None
        L200: @146: ; reraise ; pop_except ; reraise