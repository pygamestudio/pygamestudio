"""Timeline widget of the animation editor.

One track of keyframe diamonds (snapshot-style keyframes: each diamond holds
the whole set of animated channels), a time ruler and a draggable playhead.
The widget only handles times and indexes - the window owns the object, the
undo commands and the preview.

The ruler divides every 0.1 s (the finest useful division for durations in
seconds); divisions too close to read are thinned out while painting, and
the EXACT length is labelled at the right end (a duration like 1.24 s has
no tick of its own). The wheel stretches / compacts the time axis around
the cursor (with limits) and a middle drag moves it; a double click fits
the whole timeline again.
"""
import math

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

#: The ruler's division: one grid line every 0.1 s.
TICK_INTERVAL = 0.1
#: The preview time resolution (what scrubbing / retiming snaps to).
TIME_DECIMALS = 3
#: Ruler divisions closer than this are thinned out while painting (the
#: wheel zooms in to reveal them); labels are at least this far apart.
TICK_MIN_PX = 4.0
LABEL_MIN_PX = 42.0
#: One wheel notch stretches / compacts the axis by this factor ...
WHEEL_ZOOM_STEP = 1.25
#: ... and the visible span stays between this much time and the whole
#: timeline (so the view can neither stretch nor compact without limits).
MIN_VIEW_SPAN = 0.002

_STEP_FACTORS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000,
                 10000, 20000, 50000, 100000)


def _scaled_step(base, minimum_pixels, pixels_per_second):
    """The smallest multiple of ``base`` drawn at least ``minimum_pixels``
    wide: keeps the ruler readable at any zoom, never finer than ``base``."""
    for factor in _STEP_FACTORS:
        step = base * factor
        if step * pixels_per_second >= minimum_pixels:
            return step
    return base * _STEP_FACTORS[-1]


def _format_time(seconds, step):
    if step >= 1.0:
        return '{}s'.format(int(round(seconds)))
    decimals = max(1, int(round(-math.log10(step))))
    return '{}s'.format(round(seconds, decimals))


def _format_length(seconds):
    """The exact timeline length: '2.0s', '1.2s', '1.24s' (hundredths only
    when the duration really has any)."""
    text = '{:.2f}'.format(round(float(seconds), 2)).rstrip('0')
    if text.endswith('.'):
        text += '0'
    return '{}s'.format(text)


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
        self._view = (0.0, self._length)   # visible (start, end) seconds
        self._panning = False
        self._pan_origin = None
        self._pan_view = None
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
        """Set the timeline length; a fitted view follows it, a zoomed one
        is only clamped into the new range."""
        fitted = (self._view[0] <= 1e-9
                  and abs((self._view[1] - self._view[0]) - self._length) <= 1e-9)
        self._length = max(float(length), MIN_LENGTH)
        if fitted:
            self._view = (0.0, self._length)
        else:
            self._clamp_view()
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

    def _clamp_view(self):
        """Keep the visible window inside the timeline and its limits."""
        start, end = self._view
        span = min(max(end - start, min(MIN_VIEW_SPAN, self._length)),
                   self._length)
        start = max(0.0, min(start, self._length - span))
        self._view = (start, start + span)

    def view(self):
        """The visible (start, end) times in seconds."""
        return self._view

    def reset_view(self):
        """Show the whole timeline again (double click, new object)."""
        self._view = (0.0, self._length)
        self.update()

    def _pixels_per_second(self):
        span = max(self._view[1] - self._view[0], 1e-9)
        return self._track_width() / span

    def _time_to_x(self, time):
        return PAD + (time - self._view[0]) * self._pixels_per_second()

    def _x_to_time(self, x):
        time = self._view[0] + (x - PAD) / self._pixels_per_second()
        return max(0.0, min(time, self._length))

    def _tick_interval(self):
        """The ruler's division: 0.1 s.

        Divisions too close to read are thinned out while painting (see
        TICK_MIN_PX) and the wheel zooms in to stretch them apart; the
        exact length is labelled at the right end (see paintEvent).
        """
        return TICK_INTERVAL

    def _tick_label_x(self, painter, x, text):
        """Where a tick label is drawn: right of its tick, flipped to the
        left when it would run out of the widget (the last label at the edge
        used to be clipped to '1.')."""
        metrics = painter.fontMetrics()
        label_x = x + 3
        if label_x + metrics.horizontalAdvance(text) > self.width() - 2:
            label_x = x - 3 - metrics.horizontalAdvance(text)
        return label_x

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

        # Ruler ticks + labels: the finest division is 0.1 s, thinned out to
        # whatever stays readable at this zoom.
        interval = self._tick_interval()
        pixels_per_second = self._pixels_per_second()
        tick_step = _scaled_step(interval, TICK_MIN_PX, pixels_per_second)
        label_step = _scaled_step(interval, LABEL_MIN_PX, pixels_per_second)
        view_start, view_end = self._view
        last_moment = min(view_end, self._length)
        first_index = max(0, int(math.ceil((view_start - 1e-9) / tick_step)))
        moment = first_index * tick_step
        metrics = painter.fontMetrics()
        # The EXACT length is labelled at the right end (a duration like
        # 1.24 s has no tick of its own): a tick label that would collide
        # with it is left out instead of being painted underneath.
        end_visible = view_end >= self._length - 1e-9
        end_text = _format_length(self._length) if end_visible else ''
        end_label_x = (self._tick_label_x(painter, self._time_to_x(self._length),
                                          end_text) if end_visible else 0.0)
        end_left = end_label_x - 2
        end_right = end_label_x + metrics.horizontalAdvance(end_text) + 2
        while moment <= last_moment + 1e-9:
            x = self._time_to_x(moment)
            ratio = moment / label_step
            labelled = abs(ratio - round(ratio)) < 1e-6
            painter.drawLine(QPointF(x, RULER_HEIGHT - 6 if labelled else RULER_HEIGHT - 3),
                             QPointF(x, RULER_HEIGHT))
            if labelled:
                text = _format_time(moment, label_step)
                label_x = self._tick_label_x(painter, x, text)
                collides = (end_visible
                            and label_x - 2 < end_right
                            and end_left < label_x + metrics.horizontalAdvance(text) + 2)
                if not collides:
                    painter.drawText(QPointF(label_x, RULER_HEIGHT - 10), text)
            moment = round(moment + tick_step, 9)
        if end_visible:
            painter.drawText(QPointF(end_label_x, RULER_HEIGHT - 10), end_text)

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
        if event.button() == Qt.MouseButton.MiddleButton:
            # Middle button: move the (zoomed) view, like the audio waveform.
            self._panning = True
            self._pan_origin = event.globalPosition()
            self._pan_view = self._view
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
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
        if self._panning:
            if event.buttons() & Qt.MouseButton.MiddleButton:
                self._pan(event)
            else:
                self._end_pan()               # the middle button went up elsewhere
            return
        if self._scrubbing:
            self._scrub_to(pos.x())
        elif self._drag_index is not None:
            self._drag_time = round(self._x_to_time(pos.x()), TIME_DECIMALS)
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
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._end_pan()
            return
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

    def mouseDoubleClickEvent(self, event):
        """Double click fits the whole timeline again."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        """Stretch / compact the time axis around the cursor (with limits)."""
        delta = event.angleDelta().y()
        if not delta:
            super().wheelEvent(event)
            return
        start, end = self._view
        span = end - start
        factor = 1 / WHEEL_ZOOM_STEP if delta > 0 else WHEEL_ZOOM_STEP
        new_span = max(min(MIN_VIEW_SPAN, self._length),
                       min(span * factor, self._length))
        fraction = max(0.0, min(1.0,
                               (event.position().x() - PAD) / self._track_width()))
        anchor = start + span * fraction
        new_start = max(0.0, min(anchor - new_span * fraction,
                                  self._length - new_span))
        self._view = (new_start, new_start + new_span)
        self._clamp_view()
        self.update()
        event.accept()

    def _pan(self, event):
        """Scroll the view so the grabbed spot stays under the cursor."""
        if self._pan_origin is None or self._pan_view is None:
            return
        delta = event.globalPosition() - self._pan_origin
        start, end = self._pan_view
        shift = -delta.x() / max(1, self.width()) * (end - start)
        self._view = (start + shift, end + shift)
        self._clamp_view()
        self.update()
        event.accept()

    def _end_pan(self):
        if not self._panning:
            return
        self._panning = False
        self._pan_origin = None
        self._pan_view = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _scrub_to(self, x):
        self._time = round(self._x_to_time(x), TIME_DECIMALS)
        self.update()
        self.time_scrubbed.emit(self._time)
