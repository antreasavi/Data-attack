# pseudo-decompiled app_logging.pyc

def <module>():   # line 1
    """Single rotating log file for the entire app, written under %LOCALAPPDATA%."""
    L1: __doc__ = 'Single rotating log file for the entire app, written under %LOCALAPPDATA%.'
    L2: logging = import logging
    L3: RotatingFileHandler = import logging.handlers.RotatingFileHandler ; import logging.handlers
    L5: log_dir = import paths.log_dir ; import paths
    L7: _configured = False
    L10: setup = func<code setup>
    L30: get = func<code get> ; return None

    def setup(level):   # line 10
        L12: if not _configured: goto 20
        L13: return None
        L14: @20:
        L14: handler = RotatingFileHandler((log_dir() / 'app.log'), maxBytes=512000, backupCount=2, encoding='utf-8')
        L20: handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        L24: root = logging.getLogger()
        L25: root.setLevel(level)
        L26: root.addHandler(handler)
        L27: _configured = True ; return None

    def get(name):   # line 30
        L31: setup()
        L32: return logging.getLogger(name)