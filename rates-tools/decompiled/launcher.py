# pseudo-decompiled launcher.pyc

def <module>():   # line 1
    """TickerWidget launcher.

Starts fetcher threads for each data source, then runs the Qt GUI on the main
thread. Fetchers share a single threading.Event so GUI shutdown signals every
worker to exit its sleep within ~1s (no daemon-thread abrupt-kill races)."""
    L1: __doc__ = 'TickerWidget launcher.\n\nStarts fetcher threads for each data source, then runs the Qt GUI on the main\nthread. Fetchers share a single threading.Event so GUI shutdown signals every\nworker to exit its sleep within ~1s (no daemon-thread abrupt-kill races).\n'
    L7: annotations = import __future__.annotations ; import __future__
    L9: os = import os
    L10: sys = import sys
    L11: threading = import threading
    L14: _silence_none_streams = func<code _silence_none_streams>
    L22: _silence_none_streams()
    L24: app_logging = import app_logging
    L26: log = app_logging.get('launcher')
    L30: ois_feed = import ois_feed
    L31: fetch_vix = import VIX.fetch_vix ; import VIX
    L32: fetch_us5y = import US5Y.fetch_us5y ; import US5Y
    L34: FETCHERS = (ois_feed, fetch_vix, fetch_us5y)
    L40: _start_fetchers = func<code _start_fetchers>
    L50: main = func<code main>
    L75: if not (__name__ == '__main__'): goto 232
    L76: sys.exit(main()) ; return None
    L75: @232: ; return None

    def _silence_none_streams():   # line 14
        L16: if sys.stdout is not None: goto 98
        L17: sys.stdout = open(os.devnull, 'w')
        L18: @98: ; if sys.stderr is not None: goto 198
        L19: sys.stderr = open(os.devnull, 'w') ; return None
        L18: @198: ; return None

    def _start_fetchers(stop):   # line 40
        L41: threads = []
        L42: for-next iter(FETCHERS) (exhausted->234) ; mod = <item>
        L43: name = mod.__name__.rsplit('.', 1)[-1]
        L44: t = threading.Thread(target=mod.start, args=(stop,), name=name, daemon=True)
        L45: t.start()
        L46: threads.append(t) ; goto 20
        L47: @234: ; return threads

    def main():   # line 50
        L51: log.info('launcher starting')
        L52: stop = threading.Event()
        L53: threads = _start_fetchers(stop)
        L55: QApplication = import PySide6.QtWidgets.QApplication ; import PySide6.QtWidgets
        L57: TickerWidget = import main.TickerWidget ; import main
        L59: app = QApplication(sys.argv)
        L60: configure_app = import app_identity.configure_app ; import app_identity
        L61: configure_app(app)
        L62: app.aboutToQuit.connect(stop.set)
        L64: window = TickerWidget()
        L65: window.show()
        L66: code = app.exec()
        L68: stop.set()
        L69: for-next iter(threads) (exhausted->478) ; t = <item>
        L70: t.join(timeout=2.0) ; goto 428
        L71: @478: ; @528: ; log.info('launcher exiting (code=%d)', code)
        L72: return code