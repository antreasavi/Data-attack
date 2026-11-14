# pseudo-decompiled app_identity.pyc

def <module>():   # line 1
    """Shared application identity for source and packaged Windows launches."""
    L1: __doc__ = 'Shared application identity for source and packaged Windows launches.'
    L2: sys = import sys
    L4: QIcon = import PySide6.QtGui.QIcon ; import PySide6.QtGui
    L6: bundle_root = import paths.bundle_root ; import paths
    L9: configure_app = func<code configure_app> ; return None

    def configure_app(app):   # line 9
        L10: if not (sys.platform == 'win32'): goto 206
        L11: ctypes = import ctypes
        L12: logging = import logging
        L13: result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('TickerWidget.Rates')
        L14: if not (result < 0): goto 206
        L15: logging.getLogger('identity').warning('Windows application identity failed: %s', result)
        L16: @206: ; app.setApplicationName('TickerWidget')
        L17: app.setApplicationDisplayName('TickerWidget')
        L18: icon = QIcon(str(((bundle_root() / 'assets') / 'app_icon.ico')))
        L19: if not icon.isNull(): goto 452
        L20: raise RuntimeError('Bundled application icon is missing or invalid')
        L21: @452: ; app.setWindowIcon(icon) ; return None