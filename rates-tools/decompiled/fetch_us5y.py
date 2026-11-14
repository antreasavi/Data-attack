# pseudo-decompiled fetch_us5y.pyc

def <module>():   # line 1
    L1: os = import os
    L2: sys = import sys
    L3: threading = import threading
    L4: urllib = import urllib.request
    L5: datetime = import datetime.datetime ; import datetime
    L7: yf = import yfinance
    L9: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    L11: app_logging = import app_logging
    L12: write_text = import atomic_write.write_text ; import atomic_write
    L13: data_file = import paths.data_file ; import paths
    L15: log = app_logging.get('us5y')
    L16: REFRESH_SECONDS = 600
    L17: PREFIX = 'US5Y'
    L19: TREASURY_URL = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_real_yield_curve&field_tdr_date_value={year}&page&_format=csv'
    L26: _real_5y_series = func<code _real_5y_series>
    L42: _nominal_5y_series = func<code _nominal_5y_series>
    L47: fetch_once = func<code fetch_once>
    L57: start = func<code start>
    L75: if not (__name__ == '__main__'): goto 510
    L76: start(threading.Event()) ; return None
    L75: @510: ; return None

    def _real_5y_series():   # line 26
        L27: url = TREASURY_URL.format(year=datetime.now().year)
        L28: req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        L29: with urllib.request.urlopen(req, timeout=20): ; resp = <as urllib.request.urlopen(req, timeout=20)>
        L30: text = resp.read().decode('utf-8')
        L29: None(None, None) ; goto 362 ; except-handler: ; <WITH_EXCEPT_START > ; if <exc>: goto 354 ; reraise ; pop_except ; reraise ; @354: ; ? ; pop_except ; <with-exit> ; ?
        L31: @362: ; out = []
        L32: for-next iter(text.strip().split('\n')[1:]) (exhausted->714) ; line = <item>
        L33: parts = iter(line.split(','))()
        L34: if not (len(parts) >= 2): goto 712 ; if not parts[1]: goto 712
        L36: out.append((parts[0], float(parts[1]))) ; goto 460 ; except-handler:
        L37: except ValueError? ; if not match(ValueError): goto 704 ; <exc>
        L38: pop_except ; goto 460
        L37: @704: ; reraise ; pop_except ; reraise ; @712: ; goto 460
        L39: @714: ; return out

        def _real_5y_series.<locals>.<listcomp>(.0):   # line 33
            L33: for-next .0 (exhausted->90) ; p = <item> ; append p.strip().strip('"') ; goto 6 ; @90: ; return .0

    def _nominal_5y_series():   # line 42
        L43: hist = yf.Ticker('^FVX').history(period='10d')
        L44: return iter(hist.iterrows())()

        def _nominal_5y_series.<locals>.<listcomp>(.0):   # line 44
            L44: for-next .0 (exhausted->102) ; idx = <item>[0] ; row = <item>[1] ; append (idx.strftime('%m/%d/%Y'), float(row['Close'])) ; goto 6 ; @102: ; return .0

    def fetch_once():   # line 47
        L48: real = _real_5y_series()
        L49: nominal = _nominal_5y_series()
        L50: if not real: goto 66 ; if nominal: goto 96
        L51: @66: ; raise RuntimeError('insufficient data')
        L53: @96: ; latest_be = (nominal[-1][1] - real[0][1])
        L54: return f"{PREFIX} {latest_be:.2f}"

    def start(stop):   # line 57
        L58: out = data_file(PREFIX)
        L59: if out.exists(): goto 234
        L61: write_text(out, f"{PREFIX} --") ; goto 234 ; except-handler:
        L62: except OSError? ; if not match(OSError): goto 226 ; e = <exc>
        L63: log.error('placeholder write failed: %s', e) ; pop_except ; e = None ; del e ; goto 234 ; e = None ; del e ; reraise
        L62: @226: ; reraise ; pop_except ; reraise
        L65: @234: ; if stop.is_set(): goto 570
        L67: write_text(out, fetch_once())
        L68: log.info('updated') ; goto 470 ; except-handler:
        L69: except Exception? ; if not match(Exception): goto 462 ; <exc>
        L70: log.exception('fetch failed') ; pop_except ; goto 470
        L69: @462: ; reraise ; pop_except ; reraise
        L71: @470: ; if not stop.wait(REFRESH_SECONDS): goto 526
        L72: return None
        L65: @526: ; if not stop.is_set(): goto 274 ; return None ; @570: ; return None