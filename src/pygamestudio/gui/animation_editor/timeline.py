"""Timeline widget of the animation editor.

One track of keyframe diamonds (snapshot-style keyframes: each diamond holds
the whole set of animated channels), a time ruler and a draggable playhead.
The widget only handles times and indexes - the window owns the object, the
undo commands and the preview.
"""
from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

PAD = 12                 # horizontal padding of the track
RULER_HEIGHT = 26        # the time ruler strip at the top
TRACK_TOP = 40           # top of the diamond band
TRACK_HEIGHT = 44        # height of the diamond band
DIAMOND_RADIUS = 6
HIT_RADIUS = 11
MIN_LENGTH = 0.001

_STEPS = (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0)


def _tick_step(length):
    """A tick spacing that yields ~10 ticks over the timeline."""
    for step in _STEPS:
        if length / step <= 10:
            return step
    return _STEPS[-1]


def _format_time(seconds, step):
    if step >= 1.0:
        return '{}s'.format(int(round(seconds)))
    return '{}s'.format(round(seconds, 2))


class AnimationTimeline(QWidget):
    """The keyframe track: ruler, diamonds and playhead."""

    time_scrubbed = Signal(float)           # live while dragging the playhead
    scrub_finished = Signal(float)          # playhead released
    keyframe_selected = Signal(int)         # index, -1 = none (click / seek)
    keyframe_dragged = Signal(int, float)   # live while dragging a diamond
    keyframe_moved = Signal(int, float)     # committed on release
    keyframe_context_selected = Signal(int)  # right-click pick (no seek)
    keyframe_menu_requested = Signal(int, QPoint)  # right-click (index -1 = empty)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._keyframes = []
        self._length = 1.0
        self._time = 0.0
        self._selected = -1
        self._drag_index = None
        self._drag_time = 0.0
        self._scrubbing = False
        self._colors = self._theme_colors(True)
        self.setMinimumHeight(TRACK_TOP + TRACK_HEIGHT + 14)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)

    # ------------------------------------------------------------- state
    def set_keyframes(self, keyframes):
        self._keyframes = list(keyframes)
        if self._selected >= len(self._keyframes):
            self._selected = -1
        self.update()

    def keyframes(self):
        return list(self._keyframes)

    def set_length(self, length):
        self._length = max(float(length), MIN_LENGTH)
        self.update()

    def length(self):
        return self._length

    def set_time(self, time):
        self._time = max(0.0, min(float(time), self._length))
        self.update()

    def time(self):
        return self._time

    def set_selected(self, index):
        self._selected = index if 0 <= index < len(self._keyframes) else -1
        self.update()

    def selected_index(self):
        return self._selected

    def apply_theme(self, is_dark):
        self._colors = self._theme_colors(is_dark)
        self.update()

    @staticmethod
    def _theme_colors(is_dark):
        if is_dark:
            return {
                'ruler': QColor('#262626'),
                'line': QColor('#3d3d3d'),
                'text': QColor('#9a9a9a'),
                'track': QColor('#333333'),
                'diamond': QColor('#f0b030'),
                'diamond_edge': QColor('#7a5700'),
                'selected': QColor('#ffffff'),
                'playhead': QColor('#4fc1ff'),
            }
        return {
            'ruler': QColor('#e8e8e8'),
            'line': QColor('#c8c8c8'),
            'text': QColor('#555555'),
            'track': QColor('#ededed'),
            'diamond': QColor('#d08000'),
            'diamond_edge': QColor('#8a5200'),
            'selected': QColor('#1a1a1a'),
            'playhead': QColor('#0078d4'),
        }

    # ------------------------------------------------------------- geometry
    def _track_width(self):
        return max(1, self.width() - 2 * PAD)

    def _time_to_x(self, time):
        return PAD + self._track_width() * (time / self._length)

    def _x_to_time(self, x):
        fraction = (x - PAD) / self._track_width()
        return max(0.0, min(fraction, 1.0)) * self._length

    def _diamond_time(self, index):
        if self._drag_index == index:
            return self._drag_time
        return self._keyframes[index]['time']

    def _diamond_center(self, index):
        return QPointF(self._time_to_x(self._diamond_time(index)),
                       TRACK_TOP + TRACK_HEIGHT / 2.0)

    def _hit_diamond(self, pos):
        if not (TRACK_TOP - DIAMOND_RADIUS <= pos.y() <= TRACK_TOP + TRACK_HEIGHT + DIAMOND_RADIUS):
            return None
        best = None
        best_distance = HIT_RADIUS
        for index in range(len(self._keyframes)):
            center = self._diamond_center(index)
            distance = abs(center.x() - pos.x())
            if distance <= best_distance:
                best = index
                best_distance = distance
        return best

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        colors = self._colors
        width, height = self.width(), self.height()

        painter.fillRect(0, 0, width, height, colors['track'])
        painter.fillRect(0, 0, width, RULER_HEIGHT, colors['ruler'])
        painter.setPen(colors['line'])
        painter.drawLine(0, RULER_HEIGHT, width, RULER_HEIGHT)

        # Ruler ticks + labels.
        step = _tick_step(self._length)
        painter.setPen(colors['text'])
        moment = 0.0
        while moment <= self._length + 1e-9:
            x = self._time_to_x(moment)
            painter.drawLine(QPointF(x, RULER_HEIGHT - 6), QPointF(x, RULER_HEIGHT))
            painter.drawText(QPointF(x + 3, RULER_HEIGHT - 10),
                             _format_time(moment, step))
            moment += step

        # Keyframe diamonds.
        for index in range(len(self._keyframes)):
            center = self._diamond_center(index)
            selected = index == self._selected
            points = QPolygonF([
                QPointF(center.x(), center.y() - DIAMOND_RADIUS),
                QPointF(center.x() + DIAMOND_RADIUS, center.y()),
                QPointF(center.x(), center.y() + DIAMOND_RADIUS),
                QPointF(center.x() - DIAMOND_RADIUS, center.y()),
            ])
            painter.setBrush(colors['diamond'] if not selected else colors['selected'])
            pen = QPen(colors['diamond_edge'], 1.4)
            painter.setPen(pen)
            painter.drawPolygon(points)

        # Playhead: a plain vertical line (no arrow head).
        x = self._time_to_x(min(self._time, self._length))
        painter.setPen(QPen(colors['playhead'], 1.6))
        painter.drawLine(QPointF(x, 0), QPointF(x, height))

    # ------------------------------------------------------------- mouse
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if pos.y() <= RULER_HEIGHT:
            self._scrubbing = True
            self._scrub_to(pos.x())
            return
        index = self._hit_diamond(pos)
        if index is not None:
            self._drag_index = index
            self._drag_time = self._keyframes[index]['time']
            self._selected = index
            self.update()
            self.keyframe_selected.emit(index)
            return
        # Empty track: drop the keyframe (the rows reset) and scrub.
        if self._selected != -1:
            self._selected = -1
            self.update()
            self.keyframe_selected.emit(-1)
        self._scrubbing = True
        self._scrub_to(pos.x())

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._scrubbing:
            self._scrub_to(pos.x())
        elif self._drag_index is not None:
            self._drag_time = round(self._x_to_time(pos.x()), 2)
            self.update()
            self.keyframe_dragged.emit(self._drag_index, self._drag_time)
        else:
            # Hovering a diamond must read as clickable.
            over_diamond = self._hit_diamond(pos) is not None
            self.setCursor(Qt.CursorShape.PointingHandCursor if over_diamond
                           else Qt.CursorShape.ArrowCursor)

    def contextMenuEvent(self, event):
        """Right-click opens the menu; on a diamond it also selects it.

        The pick is reported WITHOUT seeking: the menu's New Keyframe lands
        on the playhead, which must stay where the user left it.
        """
        index = self._hit_diamond(event.pos())
        if index is not None and index != self._selected:
            self._selected = index
            self.update()
            self.keyframe_context_selected.emit(index)
        self.keyframe_menu_requested.emit(index if index is not None else -1,
                                          QPoint(event.globalPos()))

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._scrubbing:
            self._scrubbing = False
            self.scrub_finished.emit(self._time)
            return
        if self._drag_index is not None:
            index = self._drag_index
            moment = self._drag_time
            self._drag_index = None
            self.update()
            self.keyframe_moved.emit(index, moment)

    def _scrub_to(self, x):
        self._time = round(self._x_to_time(x), 2)
        self.update()
        self.time_scrubbed.emit(self._time)
