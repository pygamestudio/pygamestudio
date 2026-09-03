"""Custom-drawn progress display for the audio player.

The widget fills whatever space it is given. When waveform data is available
it draws the real peak envelope (played part highlighted), otherwise it falls
back to a clean rounded progress bar. Clicking (or dragging) anywhere on it
requests a seek via the ``seek_requested`` signal.
"""

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget


class AudioProgress(QWidget):
    seek_requested = Signal(float)          # fraction 0..1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._envelope = []
        self._progress = 0.0
        self.setMinimumWidth(200)
        self.setMinimumHeight(56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------ api
    def set_envelope(self, envelope):
        self._envelope = list(envelope or [])
        self.update()

    def set_progress(self, fraction):
        fraction = max(0.0, min(1.0, float(fraction)))
        if abs(fraction - self._progress) > 1e-4:
            self._progress = fraction
            self.update()

    # ------------------------------------------------------------- seeking
    def _fraction_from_pos(self, pos):
        width = self.width()
        if width <= 1:
            return 0.0
        return max(0.0, min(1.0, pos.x() / width))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.seek_requested.emit(self._fraction_from_pos(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.seek_requested.emit(self._fraction_from_pos(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 6, -2, -8)
        if rect.width() > 0 and rect.height() > 0:
            if self._envelope:
                self._paint_waveform(painter, rect)
            else:
                self._paint_bar(painter, rect)
        painter.end()

    def _colors(self):
        palette = self.palette()
        track = palette.mid().color()
        return QColor('#007acc'), track

    def _paint_waveform(self, painter, rect):
        played, track = self._colors()
        count = len(self._envelope)
        bar_slot = rect.width() / count
        bar_width = max(1.5, bar_slot * 0.6)
        available = rect.height()
        painter.setPen(Qt.PenStyle.NoPen)
        for index, value in enumerate(self._envelope):
            center_x = rect.x() + (index + 0.5) * bar_slot
            height = max(2.0, value * available)
            bar = QRectF(center_x - bar_width / 2,
                         rect.center().y() - height / 2,
                         bar_width, height)
            color = played if (index + 0.5) / count <= self._progress else track
            painter.setBrush(color)
            painter.drawRoundedRect(bar, bar_width / 2, bar_width / 2)
        # Play head line.
        x = rect.x() + self._progress * rect.width()
        painter.setPen(QColor('#ffffff'))
        painter.drawLine(int(x), int(rect.y()), int(x), int(rect.bottom()))

    def _paint_bar(self, painter, rect):
        played, track = self._colors()
        radius = min(rect.height() / 2, 6)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, track)
        if self._progress > 0:
            fill = QPainterPath()
            fill_rect = QRectF(rect)
            fill_rect.setWidth(max(rect.height(), rect.width() * self._progress))
            fill.addRoundedRect(fill_rect, radius, radius)
            painter.fillPath(fill, played)

