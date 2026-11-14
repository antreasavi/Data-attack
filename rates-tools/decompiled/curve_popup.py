# pseudo-decompiled curve_popup.pyc

def <module>():   # line 1
    """Opaque, explicitly painted meeting-date hover chart (independent of Qt theme)."""
    L1: __doc__ = 'Opaque, explicitly painted meeting-date hover chart (independent of Qt theme).'
    L2: math = import math
    L3: date = import datetime.date ; import datetime
    L5: QPointF = import PySide6.QtCore.QPointF ; QRectF = import PySide6.QtCore.QRectF ; Qt = import PySide6.QtCore.Qt ; import PySide6.QtCore
    L6: QColor = import PySide6.QtGui.QColor ; QFont = import PySide6.QtGui.QFont ; QFontMetrics = import PySide6.QtGui.QFontMetrics ; QPainter = import PySide6.QtGui.QPainter ; QPainterPath = import PySide6.QtGui.QPainterPath ; QPen = import PySide6.QtGui.QPen ; import PySide6.QtGui
    L7: QApplication = import PySide6.QtWidgets.QApplication ; QWidget = import PySide6.QtWidgets.QWidget ; import PySide6.QtWidgets
    L10: CurvePopup = __build_class__(func<code CurvePopup>, 'CurvePopup', QWidget) ; return None

    def CurvePopup():   # line 10
        L10: __module__ = __name__ ; __qualname__ = 'CurvePopup'
        L11: __init__ = func<code __init__>
        L24: set_curve = func<code set_curve>
        L43: show_at = func<code show_at>
        L55: paintEvent = func<code paintEvent> ; __classcell__ = __class__ ; return __class__

        def CurvePopup.__init__(self, parent):   # line 11
            L12: super().__init__(parent, ((((Qt.Tool | Qt.FramelessWindowHint) | Qt.WindowStaysOnTopHint) | Qt.WindowDoesNotAcceptFocus) | Qt.WindowTransparentForInput))
            L15: self.setAttribute(Qt.WA_ShowWithoutActivating)
            L16: self.setAttribute(Qt.WA_TransparentForMouseEvents)
            L17: self.setFocusPolicy(Qt.NoFocus)
            L18: self.setFixedSize(480, 272)
            L19: self.bank = ''
            L20: self.color = QColor('#55bbff')
            L21: self.payload = {}
            L22: self.points = [] ; return None

        def CurvePopup.set_curve(self, bank, color, payload):   # line 24
            L25: self.bank = bank ; self.color = QColor(color) ; self.payload = payload
            L26: self.points = []
            L28: rows = sorted(payload.get('meetings', []), key=func<code <lambda>>)
            L29: for-next iter(rows) (exhausted->578) ; row = <item>
            L30: day = date.fromisoformat(row['date'])
            L31: if not (day < date.today()): goto 272
            L32: goto 168
            L33: @272: ; change = float(row['change_bps']) ; rate = float(row['rate_percent'])
            L34: @376: ; if not math.isfinite(rate): goto 436 ; if math.isfinite(change): goto 466
            L35: @436: ; raise ValueError('Invalid curve value')
            L36: @466: ; self.points.append((day, rate, change))
            L37: if not (len(self.points) == 6): goto 576
            L38: iter(rows) ; goto 578
            L37: @576: ; goto 168 ; @578: ; goto 652 ; except-handler:
            L39: except (KeyError, TypeError, ValueError)? ; if not match((KeyError, TypeError, ValueError)): goto 644 ; <exc>
            L40: self.points = [] ; pop_except ; goto 652
            L39: @644: ; reraise ; pop_except ; reraise
            L41: @652: ; self.update() ; return None

            def CurvePopup.set_curve.<locals>.<lambda>(row):   # line 28
                L28: return row['date']

        def CurvePopup.show_at(self, position):   # line 43
            L44: [QApplication.screenAt(position) or ...] (else goto 78) ; @78: ; screen = QApplication.primaryScreen()
            L45: area = screen.availableGeometry()
            L46: y = (position.y() + 20) ; x = (position.x() + 12)
            L47: if not ((y + self.height()) > area.bottom()): goto 390
            L48: y = ((position.y() - self.height()) - 12)
            L49: @390: ; x = max(area.left(), min(x, ((area.right() - self.width()) + 1)))
            L50: y = max(area.top(), min(y, ((area.bottom() - self.height()) + 1)))
            L51: self.move(x, y)
            L52: self.show()
            L53: self.raise_() ; return None

        def CurvePopup.paintEvent(self, event):   # line 55
            L56: p = QPainter(self)
            L57: p.setRenderHint(QPainter.Antialiasing)
            L58: p.fillRect(self.rect(), QColor('#111820'))
            L59: p.setPen(QColor('#526170'))
            L60: p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            L62: text = func<code text>
            L71: text(QRectF(16, 9, 450, 25), f"{self.bank}  /  NEXT 6 MEETINGS", self.color, 16, True)
            L72: source = self.payload.get('display_source', f"Eurex {self.payload.get('asof', '--')}")
            L73: text(QRectF(16, 36, 450, 20), f"Post-meeting {self.payload.get('benchmark', 'OIS')} (%)  |  {source}")
            L74: if not (len(self.points) < 2): goto 934
            L75: text(QRectF(16, 100, 450, 60), 'Meeting curve data unavailable', size=15)
            L76: p.end()
            L77: return None
            L79: @934: ; plot = QRectF(58, 87, 382, 124)
            L80: rates = iter(self.points)()
            L81: spread = max((max(rates) - min(rates)), 0.1)
            L82: low = (min(rates) - (spread * 0.35)) ; high = (max(rates) + (spread * 0.35))
            L83: for-next iter((0.0, 0.5, 1.0)) (exhausted->1684) ; fraction = <item>
            L84: y = (plot.bottom() - (fraction * plot.height()))
            L85: p.setPen(QPen(QColor('#2b3947'), 1))
            L86: p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            L87: text(QRectF(4, (y - 9), 48, 18), {(low + (fraction * (high - low))):.2f}, '#99aabb', 11, align=(Qt.AlignRight | Qt.AlignVCenter)) ; goto 1184
            L89: @1684:
            L89: coords = iter(enumerate(rates))()
            L91: path = QPainterPath(coords[0])
            L92: for-next iter(coords[1:]) (exhausted->1854) ; point = <item>
            L93: path.lineTo(point) ; goto 1806
            L94: @1854: ; @1902: ; p.setPen(QPen(self.color, 2.5))
            L95: p.drawPath(path)
            L96: for-next iter(zip(coords, self.points)) (exhausted->2698) ; point = <item>[0] ; day = <item>[1][0] ; rate = <item>[1][1] ; change = <item>[1][2]
            L97: p.setPen(QPen(self.color, 1))
            L98: p.setBrush(self.color)
            L99: @2184: ; p.drawEllipse(point, 3.5, 3.5)
            L100: text(QRectF((point.x() - 35), (point.y() - 25), 70, 20), {rate:.3f}, '#ffffff', 12, True, Qt.AlignCenter)
            L101: text(QRectF((point.x() - 37), 218, 74, 20), day.strftime('%d %b %y'), size=11, align=Qt.AlignCenter)
            L102: text(QRectF((point.x() - 37), 240, 74, 20), f"{change:+.1f}bps", self.color, 11, align=Qt.AlignCenter) ; goto 2018
            L103: @2698: ; p.end() ; return None

            def CurvePopup.paintEvent.<locals>.text(rect, value, color, size, bold, align):   # line 62
                L63: font = QFont('Segoe UI')
                L64: font.setPixelSize(size)
                L65: font.setBold(bold)
                L66: p.setFont(font)
                L67: p.setPen(QColor(color))
                L68: value = QFontMetrics(font).elidedText(str(value), Qt.ElideRight, int(rect.width()))
                L69: p.drawText(rect, align, value) ; return None

            def CurvePopup.paintEvent.<locals>.<listcomp>(.0):   # line 80
                L80: for-next .0 (exhausted->28) ; row = <item> ; append row[1] ; goto 6 ; @28: ; return .0

            def CurvePopup.paintEvent.<locals>.<listcomp>(.0):   # line 89
                L89: for-next .0 (exhausted->276)
                L90: i = <item>[0] ; rate = <item>[1]
                L89: append QPointF((plot.left() + ((i * plot.width()) / (len(rates) - 1))), (plot.bottom() - (((rate - low) / (high - low)) * plot.height()))) ; goto 8 ; @276: ; return .0