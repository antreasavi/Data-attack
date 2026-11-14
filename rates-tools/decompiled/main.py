# pseudo-decompiled main.pyc

def <module>():   # line 1
    """Ticker GUI — reads data files written by fetcher threads.

Performance notes:
- reload_data() only re-reads a file if its mtime changed since last poll.
  Cuts the steady-state reload from 8 file opens/min to ~0.
- Data directory lives under %LOCALAPPDATA% (via paths.data_file) so the
  GUI and the fetchers share state even from a PyInstaller EXE."""
    L1: __doc__ = 'Ticker GUI — reads data files written by fetcher threads.\n\nPerformance notes:\n- reload_data() only re-reads a file if its mtime changed since last poll.\n  Cuts the steady-state reload from 8 file opens/min to ~0.\n- Data directory lives under %LOCALAPPDATA% (via paths.data_file) so the\n  GUI and the fetchers share state even from a PyInstaller EXE.\n'
    L9: annotations = import __future__.annotations ; import __future__
    L11: signal = import signal
    L12: sys = import sys
    L13: json = import json
    L14: time = import time
    L15: dataclass = import dataclasses.dataclass ; import dataclasses
    L16: datetime = import datetime.datetime ; import datetime
    L17: Optional = import typing.Optional ; import typing
    L19: QEvent = import PySide6.QtCore.QEvent ; Qt = import PySide6.QtCore.Qt ; QTimer = import PySide6.QtCore.QTimer ; import PySide6.QtCore
    L20: QCursor = import PySide6.QtGui.QCursor ; QFont = import PySide6.QtGui.QFont ; QFontMetrics = import PySide6.QtGui.QFontMetrics ; import PySide6.QtGui
    L21: QApplication = import PySide6.QtWidgets.QApplication ; QFrame = import PySide6.QtWidgets.QFrame ; QHBoxLayout = import PySide6.QtWidgets.QHBoxLayout ; QLabel = import PySide6.QtWidgets.QLabel ; QMainWindow = import PySide6.QtWidgets.QMainWindow ; QScrollArea = import PySide6.QtWidgets.QScrollArea ; QVBoxLayout = import PySide6.QtWidgets.QVBoxLayout ; QWidget = import PySide6.QtWidgets.QWidget ; import PySide6.QtWidgets
    L26: app_logging = import app_logging
    L27: data_file = import paths.data_file ; data_dir = import paths.data_dir ; import paths
    L28: CurvePopup = import curve_popup.CurvePopup ; import curve_popup
    L30: log = app_logging.get('gui')
    L32: signal.signal(signal.SIGINT, signal.SIG_DFL)
    L35: SECTIONS = (('#00ff66', 'FED'), ('#ff4444', 'BOE'), ('#55bbff', 'ECB'), ('#dd88ff', 'BOJ'))
    L42: MAX_LINES = 3
    L47: STACK_COLUMN = (('#ffffff', None), ('#ffa500', 'VIX'), ('#1e90ff', 'US5Y'))
    L52: STACK_PREFIXES = func<code <genexpr>>(iter(STACK_COLUMN)())
    L54: RESIZE_MARGIN = 8
    L55: DATA_POLL_MS = 2000
    L56: CLOCK_INTERVAL_MS = 1000
    L58: FONT_PX = 16
    L59: SECTION_SPACING = 16
    L60: SECTION_MARGIN = 0
    L61: LABEL_STYLE = 'color: {color}; background: transparent;'
    L64: _section_font = func<code _section_font>
    L73: _Cache = __build_class__(func<code _Cache>, '_Cache')()
    L78: Section = __build_class__(func<code Section>, 'Section', QWidget)
    L129: TickerWidget = __build_class__(func<code TickerWidget>, 'TickerWidget', QMainWindow)
    L406: if not (__name__ == '__main__'): goto 686
    L407: app = QApplication(sys.argv)
    L408: configure_app = import app_identity.configure_app ; import app_identity
    L409: configure_app(app)
    L410: ticker = TickerWidget()
    L411: ticker.show()
    L412: sys.exit(app.exec()) ; return None
    L406: @686: ; return None

    def <genexpr>(.0):   # line 52
        L52: ? ; for-next .0 (exhausted->32) ; _ = <item>[0] ; p = <item>[1] ; if not p: goto 8 ; (yield p) ; goto 8 ; @32: ; return None

    def _section_font():   # line 64
        L65: f = QFont('Consolas')
        L66: f.setStyleHint(QFont.Monospace)
        L67: f.setPixelSize(FONT_PX)
        L68: f.setBold(True)
        L69: return f

    def _Cache():   # line 72
        L72: __module__ = __name__ ; __qualname__ = '_Cache' ; <SETUP_ANNOTATIONS >
        L74: mtime = 0.0 ; __annotations__['mtime'] = 'float'
        L75: text = '' ; __annotations__['text'] = 'str' ; return None

    def Section():   # line 78
        L78: __module__ = __name__ ; __qualname__ = 'Section'
        L79: __doc__ = 'One column of the ticker: MAX_LINES labels stacked with no gap.\n\n    `colors` carries one colour per line, so a column can mix them — the market\n    stack is white/orange/blue while a central bank column repeats one colour.\n    '
        L85: __init__ = func<code __init__>
        L110: set_line = func<code set_line>
        L115: set_text = func<code set_text>
        L122: _resize_to_content = func<code _resize_to_content> ; __classcell__ = __class__ ; return __class__

        def Section.__init__(self, colors, font, line_h, parent):   # line 85
            L87: super().__init__(parent)
            L88: self.setStyleSheet('background: transparent;')
            L89: self.setMouseTracking(True)
            L90: self._fm = QFontMetrics(font)
            L94: self.setFixedHeight((MAX_LINES * line_h))
            L95: layout = QVBoxLayout(self)
            L96: layout.setContentsMargins(0, 0, 0, 0)
            L97: layout.setSpacing(0)
            L99: self.lines = []
            L100: for-next iter(range(MAX_LINES)) (exhausted->872) ; i = <item>
            L101: lbl = QLabel()
            L102: lbl.setFont(font)
            L103: lbl.setStyleSheet(LABEL_STYLE.format(color=colors[i]))
            L104: lbl.setAlignment((Qt.AlignLeft | Qt.AlignVCenter))
            L105: lbl.setFixedHeight(line_h)
            L106: lbl.setMouseTracking(True)
            L107: layout.addWidget(lbl)
            L108: self.lines.append(lbl) ; goto 426
            L100: @872: ; return None

        def Section.set_line(self, index, text):   # line 110
            """Replace a single line, leaving the others alone."""
            L112: self.lines[index].setText(text)
            L113: self._resize_to_content() ; return None

        def Section.set_text(self, text):   # line 115
            """Fill the column from a multi-line blob, top down."""
            L117: parts = text.split('\n')
            L118: for-next iter(enumerate(self.lines)) (exhausted->192) ; i = <item>[0] ; lbl = <item>[1]
            L119: if not (i < len(parts)): goto 172 ; goto 174 ; @172: ; @174: ; parts[i]('') ; goto 84
            L120: @192: ; self._resize_to_content() ; return None

        def Section._resize_to_content(self):   # line 122
            L125: widths = iter(self.lines)()
            L126: self.setFixedWidth(max(widths, default=0)) ; return None

            def Section._resize_to_content.<locals>.<listcomp>(.0):   # line 125
                L125: for-next .0 (exhausted->102) ; lbl = <item> ; append self._fm.horizontalAdvance(lbl.text()) ; goto 8 ; @102: ; return .0

    def TickerWidget():   # line 129
        L129: __module__ = __name__ ; __qualname__ = 'TickerWidget'
        L130: __init__ = func<code __init__>
        L171: _build_ui = func<code _build_ui>
        L218: _apply_preferred_size = func<code _apply_preferred_size>
        L232: _start_timers = func<code _start_timers>
        L250: eventFilter = func<code eventFilter>
        L273: _bank_under_cursor = func<code _bank_under_cursor>
        L285: _poll_curve_hover = func<code _poll_curve_hover>
        L301: _hide_curve_if_outside = func<code _hide_curve_if_outside>
        L305: closeEvent = func<code closeEvent>
        L310: update_clock = func<code update_clock>
        L313: reload_data = func<code reload_data>
        L350: _reload_ois_details = func<code _reload_ois_details>
        L366: mousePressEvent = func<code mousePressEvent>
        L383: mouseMoveEvent = func<code mouseMoveEvent>
        L400: mouseReleaseEvent = func<code mouseReleaseEvent> ; __classcell__ = __class__ ; return __class__

        def TickerWidget.__init__(self):   # line 130
            L131: super().__init__()
            L132: self.setWindowTitle('TickerWidget')
            L134: self.setWindowFlags(((Qt.Window | Qt.FramelessWindowHint) | Qt.WindowStaysOnTopHint))
            L135: self.setAttribute(Qt.WA_TranslucentBackground)
            L137: self._font = _section_font()
            L139: _fm = QFontMetrics(self._font)
            L140: self._line_h = _fm.height()
            L142: self.old_pos = None
            L143: self.resizing = False
            L144: self.resize_edge = None
            L145: self.last_mouse_x = 0.0
            L147: self._cache = iter((iter(SECTIONS)() + list(STACK_PREFIXES)))()
            L151: self._ois_mtimes = {}
            L152: self._ois_payloads = {}
            L153: self.curve_popup = CurvePopup(self)
            L154: self._hover_bank = None
            L155: self._hover_since = 0.0
            L157: self._build_ui()
            L161: self._start_timers()
            L162: self._apply_preferred_size()
            L164: self.setMouseTracking(True)
            L165: self.central_widget.setMouseTracking(True)
            L166: self.scroll_area.setMouseTracking(True)
            L167: self.scroll_area.viewport().setMouseTracking(True)
            L168: self.ticker_container.setMouseTracking(True)
            L169: QApplication.instance().installEventFilter(self) ; return None

            def TickerWidget.__init__.<locals>.<dictcomp>(.0):   # line 147
                L147: for-next .0 (exhausted->42)
                L149: prefix = <item>
                L147: map-add prefix: _Cache() ; goto 6 ; @42: ; return .0

            def TickerWidget.__init__.<locals>.<listcomp>(.0):   # line 149
                L149: for-next .0 (exhausted->22) ; _ = <item>[0] ; p = <item>[1] ; append p ; goto 6 ; @22: ; return .0

        def TickerWidget._build_ui(self):   # line 171
            L172: self.central_widget = QFrame()
            L173: self.central_widget.setObjectName('MainFrame')
            L174: self.central_widget.setStyleSheet('QFrame#MainFrame { background-color: rgba(0, 0, 0, 245); border: 1px solid #333; border-radius: 6px; }')
            L179: self.root_layout = QHBoxLayout(self.central_widget)
            L180: self.root_layout.setContentsMargins(10, 0, 10, 0)
            L181: self.root_layout.setSpacing(0)
            L183: self.scroll_area = QScrollArea()
            L184: self.scroll_area.setWidgetResizable(True)
            L185: self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            L186: self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            L187: self.scroll_area.setStyleSheet('background: transparent; border: none;')
            L189: self.ticker_container = QWidget()
            L190: self.ticker_container.setStyleSheet('background: transparent;')
            L191: self.ticker_layout = QHBoxLayout(self.ticker_container)
            L192: self.ticker_layout.setSpacing(SECTION_SPACING)
            L193: self.ticker_layout.setContentsMargins(SECTION_MARGIN, 0, SECTION_MARGIN, 0)
            L197: self.sections = {}
            L198: for-next iter(SECTIONS) (exhausted->1168) ; color = <item>[0] ; prefix = <item>[1]
            L199: sec = Section(([color] * MAX_LINES), self._font, self._line_h)
            L200: sec.set_text(f"{prefix} ...")
            L201: sec.setToolTip('Six-month forward curve')
            L202: self.ticker_layout.addWidget(sec, 0, Qt.AlignVCenter)
            L203: self.sections[prefix] = sec ; goto 898
            L206: @1168:
            L206: self.stack = func<code <listcomp>>(iter(STACK_COLUMN)(), self._font, self._line_h)
            L208: for-next iter(enumerate(STACK_COLUMN)) (exhausted->1388) ; i = <item>[0] ; _ = <item>[1][0] ; prefix = <item>[1][1]
            L209: if not prefix: goto 1368 ; goto 1370 ; @1368: ; @1370: ; i(f"{prefix} ...", '') ; goto 1302
            L210: @1388: ; @1438: ; self.ticker_layout.addWidget(self.stack, 0, Qt.AlignVCenter)
            L211: @1474: ; self.ticker_layout.addStretch(1)
            L213: self.scroll_area.setWidget(self.ticker_container)
            L214: self.root_layout.addWidget(self.scroll_area)
            L216: self.setCentralWidget(self.central_widget) ; return None

            def TickerWidget._build_ui.<locals>.<listcomp>(.0):   # line 206
                L206: for-next .0 (exhausted->22) ; c = <item>[0] ; _ = <item>[1] ; append c ; goto 6 ; @22: ; return .0

        def TickerWidget._apply_preferred_size(self):   # line 218
            """Size the window to show every section at once.

        The ticker no longer scrolls, so anything that does not fit is simply
        unreadable. Width is capped to the screen; drag inside the row to pan
        if the sections still overflow."""
            L225: height = ((MAX_LINES * self._line_h) + 12)
            L226: width = (self.ticker_container.sizeHint().width() + 20)
            L227: screen = QApplication.instance().primaryScreen()
            L228: if screen is None: goto 312
            L229: width = min(width, screen.availableGeometry().width())
            L230: @312: ; self.resize(max(width, 300), height) ; return None

        def TickerWidget._start_timers(self):   # line 232
            L234: self.data_timer = QTimer(self)
            L235: self.data_timer.timeout.connect(self.reload_data)
            L236: self.data_timer.start(DATA_POLL_MS)
            L238: self.clock_timer = QTimer(self)
            L239: self.clock_timer.timeout.connect(self.update_clock)
            L240: self.clock_timer.start(CLOCK_INTERVAL_MS)
            L244: self.hover_timer = QTimer(self)
            L245: self.hover_timer.timeout.connect(self._poll_curve_hover)
            L246: self.hover_timer.start(100)
            L248: self.reload_data() ; return None

        def TickerWidget.eventFilter(self, obj, event):   # line 250
            L251: if not (event.type() == QEvent.ToolTip): goto 302
            L252: widget = obj
            L253: if not isinstance(widget, QWidget): goto 302
            L254: for-next iter(SECTIONS) (exhausted->220) ; color = <item>[0] ; prefix = <item>[1]
            L255: if not (widget is self.sections[prefix]): goto 218
            L256: self._poll_curve_hover()
            L257: iter(SECTIONS) ; return True
            L255: @218: ; goto 132
            L258: @220: ; widget = widget.parentWidget()
            L253: if isinstance(widget, QWidget): goto 118
            L259: @302: ; @308: ; if not (event.type() == QEvent.Leave): goto 464 ; if not isinstance(obj, QWidget): goto 464
            L260: QTimer.singleShot(0, self._hide_curve_if_outside)
            L261: @464: ; @486: ; if not (event.type() == QEvent.MouseButtonPress): goto 596
            L262: self.curve_popup.hide()
            L263: self._hover_bank = None
            L264: @596: ; if not (event.type() == QEvent.MouseMove): goto 1158 ; if self.old_pos: goto 1158
            L265: pos = self.mapFromGlobal(event.globalPosition().toPoint())
            L266: if not (0 <= pos.y()): goto 892 ; if not (pos.y() <= self.height()): goto 1158 ; goto 896 ; @892: ; ? ; goto 1158
            L267: @896: ; if (pos.x() <= RESIZE_MARGIN): goto 1054 ; if not (pos.x() >= (self.width() - RESIZE_MARGIN)): goto 1118
            L268: @1054: ; self.setCursor(Qt.SizeHorCursor) ; goto 1158
            L270: @1118: ; self.unsetCursor()
            L271: @1158: ; return super().eventFilter(obj, event)

        def TickerWidget._bank_under_cursor(self):   # line 273
            L274: if not self.isVisible(): goto 82 ; if not self.isMinimized(): goto 86
            L275: @82: ; return None
            L277: @86: ; widget = QApplication.widgetAt(QCursor.pos())
            L278: if widget is None: goto 272
            L279: for-next iter(SECTIONS) (exhausted->228) ; _ = <item>[0] ; bank = <item>[1]
            L280: if not (widget is self.sections[bank]): goto 226
            L281: iter(SECTIONS) ; return bank
            L280: @226: ; goto 178
            L282: @228: ; widget = widget.parentWidget()
            L278: if widget is not None: goto 164
            L283: @272: ; return None

        def TickerWidget._poll_curve_hover(self):   # line 285
            L286: bank = self._bank_under_cursor()
            L287: if self.old_pos is not None: goto 124 ; if not (QApplication.mouseButtons() != Qt.NoButton): goto 128
            L288: @124: ; bank = None
            L289: @128: ; if not (bank != self._hover_bank): goto 262
            L290: self.curve_popup.hide()
            L291: self._hover_bank = bank
            L292: self._hover_since = time.monotonic()
            L293: @262: ; if bank is not None: goto 320
            L294: self.curve_popup.hide()
            L295: return None
            L296: @320: ; if not ((time.monotonic() - self._hover_since) >= 0.3): goto 692 ; if self.curve_popup.isVisible(): goto 696
            L297: color = func<code <genexpr>>(iter(SECTIONS)())
            L298: self.curve_popup.set_curve(bank, color, self._ois_payloads.get(bank, {}))
            L299: self.curve_popup.show_at(QCursor.pos()) ; return None
            L296: @692: ; return None ; @696: ; return None

            def TickerWidget._poll_curve_hover.<locals>.<genexpr>(.0):   # line 297
                L297: ? ; for-next .0 (exhausted->42) ; color = <item>[0] ; prefix = <item>[1] ; if not (prefix == bank): goto 10 ; (yield color) ; goto 10 ; @42: ; return None

        def TickerWidget._hide_curve_if_outside(self):   # line 301
            L302: if not (self._bank_under_cursor() != self._hover_bank): goto 104
            L303: self._poll_curve_hover() ; return None
            L302: @104: ; return None

        def TickerWidget.closeEvent(self, event):   # line 305
            L306: self.hover_timer.stop()
            L307: self.curve_popup.hide()
            L308: super().closeEvent(event) ; return None

        def TickerWidget.update_clock(self):   # line 310
            L311: self.stack.set_line(0, datetime.now().strftime('%H:%M:%S')) ; return None

        def TickerWidget.reload_data(self):   # line 313
            L314: self._reload_ois_details()
            L315: for-next iter((list(self.sections) + list(STACK_PREFIXES))) (exhausted->994) ; prefix = <item>
            L316: path = data_file(prefix)
            L317: cache = self._cache[prefix]
            L319: mtime = path.stat().st_mtime ; goto 364 ; except-handler:
            L320: except FileNotFoundError? ; if not match(FileNotFoundError): goto 264 ; <exc>
            L321: pop_except ; goto 124
            L322: @264: ; except OSError? ; if not match(OSError): goto 356 ; e = iter((list(self.sections) + list(STACK_PREFIXES)))
            L323: log.warning('%s: stat failed: %s', prefix, e)
            L324: pop_except ; e = None ; del e ; goto 124 ; e = None ; del e ; reraise
            L322: @356: ; reraise ; pop_except ; reraise
            L325: @364: ; if not (mtime == cache.mtime): goto 388
            L326: goto 124
            L328: @388:
            L329: @404: ; raw = path.read_text(encoding='utf-8') ; goto 538 ; except-handler:
            L330: except OSError? ; if not match(OSError): goto 530 ; e = <exc>
            L331: log.warning('%s: read failed: %s', prefix, e)
            L332: pop_except ; e = None ; del e ; goto 124 ; e = None ; del e ; reraise
            L330: @530: ; reraise ; pop_except ; reraise
            L334: @538: ; @572: ; lines = iter(raw.split('\n'))()
            L336: if not (prefix in STACK_PREFIXES): goto 794
            L339: if not lines: goto 638 ; goto 646 ; @638: ; @646: ; text = f"{prefix} --"
            L340: @652: ; if not (text != cache.text): goto 792
            L341: cache.text = text
            L342: self.stack.set_line((STACK_PREFIXES.index(prefix) + 1), text) ; @792: ; goto 976
            L344: @794: ; if not lines: goto 866 ; goto 874 ; @866: ; @874: ; text = f"{prefix} --"
            L345: if not (text != cache.text): goto 976
            L346: cache.text = text
            L347: @920: ; self.sections[prefix].set_text(text)
            L348: @976: ; cache.mtime = mtime ; goto 124
            L315: @994: ; return None

            def TickerWidget.reload_data.<locals>.<listcomp>(.0):   # line 334
                L334: for-next .0 (exhausted->92) ; l = <item> ; if not l.strip(): goto 6 ; append l.strip() ; goto 6 ; @92: ; return .0

        def TickerWidget._reload_ois_details(self):   # line 350
            L351: for-next iter(SECTIONS) (exhausted->620) ; _ = <item>[0] ; prefix = <item>[1]
            L352: path = (data_dir() / f"ois_{prefix.lower()}.json")
            L354: stamp = path.stat().st_mtime_ns
            L355: if not (self._ois_mtimes.get(prefix) == stamp): goto 222
            L356: goto 18
            L357: @222: ; payload = json.loads(path.read_text(encoding='utf-8'))
            L358: self._ois_payloads[prefix] = payload
            L359: if not self.curve_popup.isVisible(): goto 524 ; if not (self.curve_popup.bank == prefix): goto 524
            L360: @426: ; color = func<code <genexpr>>(iter(SECTIONS)())
            L361: self.curve_popup.set_curve(prefix, color, payload)
            L362: @524: ; self._ois_mtimes[prefix] = stamp ; goto 18 ; except-handler:
            L363: except (OSError, ValueError, KeyError, TypeError)? ; if not match((OSError, ValueError, KeyError, TypeError)): goto 612 ; <exc>
            L364: pop_except ; goto 18
            L363: @612: ; reraise ; pop_except ; reraise
            L351: @620: ; return None

            def TickerWidget._reload_ois_details.<locals>.<genexpr>(.0):   # line 360
                L360: ? ; for-next .0 (exhausted->42) ; color = <item>[0] ; bank = <item>[1] ; if not (bank == prefix): goto 10 ; (yield color) ; goto 10 ; @42: ; return None

        def TickerWidget.mousePressEvent(self, event):   # line 366
            L367: if not (event.button() != Qt.LeftButton): goto 74
            L368: return None
            L369: @74: ; self.old_pos = event.globalPosition().toPoint()
            L370: self.last_mouse_x = event.position().x()
            L371: x = self.last_mouse_x
            L374: if not (x >= (self.width() - RESIZE_MARGIN)): goto 356
            L375: self.resizing = True
            L376: self.resize_edge = 'right' ; return None
            L377: @356: ; if not (x <= RESIZE_MARGIN): goto 410
            L378: self.resizing = True
            L379: self.resize_edge = 'left' ; return None
            L381: @410: ; self.resizing = False ; return None

        def TickerWidget.mouseMoveEvent(self, event):   # line 383
            L384: if self.old_pos is not None: goto 20
            L385: return None
            L386: @20: ; curr_pos = event.globalPosition().toPoint()
            L387: delta = (curr_pos - self.old_pos)
            L388: if not self.resizing: goto 702
            L389: if not (self.resize_edge == 'right'): goto 342
            L390: self.resize(max(300, (self.width() + delta.x())), self.height()) ; goto 786
            L392: @342: ; new_w = max(300, (self.width() - delta.x()))
            L393: actual_delta = (self.width() - new_w)
            L394: self.move((self.x() + actual_delta), self.y())
            L395: self.resize(new_w, self.height()) ; goto 786
            L397: @702: ; self.move((self.pos() + delta))
            L398: @786: ; self.old_pos = curr_pos ; return None

        def TickerWidget.mouseReleaseEvent(self, event):   # line 400
            L401: self.old_pos = None
            L402: self.resizing = False
            L403: self.resize_edge = None ; return None