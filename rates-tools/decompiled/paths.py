# pseudo-decompiled paths.pyc

def <module>():   # line 1
    """Runtime paths for TickerWidget.

Data and logs live under %LOCALAPPDATA%\TickerWidget so they persist across
EXE runs (PyInstaller's _MEIPASS extraction directory is wiped each launch)."""
    L1: __doc__ = "Runtime paths for TickerWidget.\n\nData and logs live under %LOCALAPPDATA%\\TickerWidget so they persist across\nEXE runs (PyInstaller's _MEIPASS extraction directory is wiped each launch).\n"
    L6: os = import os
    L7: sys = import sys
    L8: Path = import pathlib.Path ; import pathlib
    L10: APP_NAME = 'TickerWidget'
    L13: _app_root = func<code _app_root>
    L20: data_dir = func<code data_dir>
    L26: log_dir = func<code log_dir>
    L32: data_file = func<code data_file>
    L36: bundle_root = func<code bundle_root> ; return None

    def _app_root():   # line 13
        L14: base = os.environ.get('LOCALAPPDATA')
        L15: if not base: goto 114
        L16: return (Path(base) / APP_NAME)
        L17: @114: ; return (Path.home() / f".{APP_NAME.lower()}")

    def data_dir():   # line 20
        L21: p = (_app_root() / 'data')
        L22: p.mkdir(parents=True, exist_ok=True)
        L23: return p

    def log_dir():   # line 26
        L27: p = (_app_root() / 'logs')
        L28: p.mkdir(parents=True, exist_ok=True)
        L29: return p

    def data_file(prefix):   # line 32
        L33: return (data_dir() / f"data_{prefix.lower()}.txt")

    def bundle_root():   # line 36
        """Location where bundled resources live at runtime (frozen or dev)."""
        L38: if not getattr(sys, 'frozen', False): goto 194
        L39: return Path(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)))
        L40: @194: ; return Path(__file__).resolve().parent