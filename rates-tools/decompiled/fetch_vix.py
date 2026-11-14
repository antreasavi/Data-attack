# pseudo-decompiled fetch_vix.pyc

def <module>():   # line 1
    L1: os = import os
    L2: sys = import sys
    L3: threading = import threading
    L5: yf = import yfinance
    L7: sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    L9: app_logging = import app_logging
    L10: write_text = import atomic_write.write_text ; import atomic_write
    L11: data_file = import paths.data_file ; import paths
    L13: log = app_logging.get('vix')
    L14: REFRESH_SECONDS = 600
    L15: PREFIX = 'VIX'
    L18: fetch_once = func<code fetch_once>
    L23: start = func<code start>
    L41: if not (__name__ == '__main__'): goto 406
    L42: start(threading.Event()) ; return None
    L41: @406: ; return None

    def fetch_once():   # line 18
        L19: last = float(yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1])
        L20: return f"{PREFIX} {last:.2f}"

    def start(stop):   # line 23
        L24: out = data_file(PREFIX)
        L25: if out.exists(): goto 234
        L27: write_text(out, f"{PREFIX} --") ; goto 234 ; except-handler:
        L28: except OSError? ; if not match(OSError): goto 226 ; e = <exc>
        L29: log.error('placeholder write failed: %s', e) ; pop_except ; e = None ; del e ; goto 234 ; e = None ; del e ; reraise
        L28: @226: ; reraise ; pop_except ; reraise
        L31: @234: ; if stop.is_set(): goto 570
        L33: write_text(out, fetch_once())
        L34: log.info('updated') ; goto 470 ; except-handler:
        L35: except Exception? ; if not match(Exception): goto 462 ; <exc>
        L36: log.exception('fetch failed') ; pop_except ; goto 470
        L35: @462: ; reraise ; pop_except ; reraise
        L37: @470: ; if not stop.wait(REFRESH_SECONDS): goto 526
        L38: return None
        L31: @526: ; if not stop.is_set(): goto 274 ; return None ; @570: ; return None