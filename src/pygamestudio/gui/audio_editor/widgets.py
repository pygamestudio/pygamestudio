"""Custom-drawn waveform / progress displays for the audio panel.

``AudioProgress`` is the player-style display: click/drag seeks, the real
peak envelope is highlighted up to the playhead. ``AudioWaveformView`` is
the editor's waveform: it works on the raw samples, supports a drag
selection, wheel zoom and middle-drag panning - and falls back to the
envelope display (click-to-seek only) for formats that cannot be edited.
"""

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget


class AudioProgress(QWidget):
    seek_requested = Signal(float)          # fraction 0..1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._envelope = []
        self._progress = 0.0
        self._placeholder = ''
        self.setMinimumWidth(200)
        self.setMinimumHeight(56)
        self._sync_cursor()

    # ------------------------------------------------------------------ api
    def _sync_cursor(self):
        """Hand pointer only once there is audio to seek - an empty panel
        must not promise a click that does nothing."""
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._envelope
                       else Qt.CursorShape.ArrowCursor)

    def set_envelope(self, envelope):
        self._envelope = list(envelope or [])
        self._sync_cursor()
        self.update()

    def set_placeholder(self, text):
        """Text shown when no audio is loaded (instead of the gray bar)."""
        text = text or ''
        if text != self._placeholder:
            self._placeholder = text
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
        if self._placeholder and not self._envelope:
            self._paint_placeholder(painter)
        else:
            rect = QRectF(self.rect()).adjusted(2, 6, -2, -8)
            if rect.width() > 0 and rect.height() > 0:
                if self._envelope:
                    self._paint_waveform(painter, rect)
                else:
                    self._paint_bar(painter, rect)
        painter.end()

    def _paint_placeholder(self, painter):
        palette = self.palette()
        color = palette.text().color()
        color.setAlpha(140)
        # Same visual weight as the image editor empty hint (16px).
        font = self.font()
        font.setPixelSize(16)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(self.rect(),
                         Qt.AlignmentFlag.AlignCenter, self._placeholder)

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


class AudioWaveformView(QWidget):
    """The audio editor's waveform: selection, zoom and pan.

    Modes:

    * samples mode - the editor's working buffer drives the display. Drag
      with the left button to select a range, a plain click seeks (and drops
      the selection), the wheel zooms around the cursor and a middle-button
      drag pans. Double click resets to the whole file.
    * envelope mode - used while a format the editor cannot edit is only
      previewed: the peak envelope is drawn and a click seeks, exactly like
      the player's old display.

    ``seek_requested`` always carries the fraction of the WHOLE file.
    """

    seek_requested = Signal(float)          # fraction 0..1
    selection_changed = Signal()

    #: Zoom-in stops here (less than this many frames makes no sense).
    MIN_ZOOM_FRAMES = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mono = None                   # float32 mono mix of the buffer
        self._envelope = []
        self._progress = 0.0
        self._placeholder = ''
        self._selection = None              # (start_frame, end_frame)
        self._view = (0.0, 1.0)             # visible frame range
        self._anchor = None                 # drag anchor (frame)
        self._dragging = False
        self._panning = False
        self._pan_origin = None
        self._pan_view = None
        self.setMinimumWidth(200)
        self.setMinimumHeight(56)
        self.setMouseTracking(True)
        self._sync_cursor()

    # ------------------------------------------------------------------ api
    def _sync_cursor(self):
        """Hand pointer only once there is audio to seek / select; the empty
        panel shows the normal arrow instead."""
        active = self._mono is not None or bool(self._envelope)
        self.setCursor(Qt.CursorShape.PointingHandCursor if active
                       else Qt.CursorShape.ArrowCursor)

    def has_samples(self):
        return self._mono is not None

    def set_samples(self, samples, samplerate):
        """Show the editor buffer (enables selection / zoom / pan)."""
        array = np.asarray(samples, dtype=np.float32)
        total = float(max(1, len(array)))
        self._envelope = []
        self._selection = None
        self._anchor = None
        self._dragging = False
        self._view = (0.0, total)
        self.refresh_samples(samples)

    def refresh_samples(self, samples):
        """The buffer changed: re-read it, keep selection/view (clamped).

        A view that showed the whole (old) file keeps showing the whole (new)
        file, so an undo restoring a longer buffer is not left half hidden;
        only a zoomed-in view is clamped to the new length.
        """
        was_whole = False
        if self._mono is not None:
            start, end = self._view
            was_whole = start <= 0.0 and end >= float(max(1, len(self._mono)))
        mono = np.asarray(samples, dtype=np.float32)
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        self._mono = mono
        total = float(max(1, len(mono)))
        if was_whole:
            self._view = (0.0, total)
        else:
            start, end = self._view
            span = min(max(1.0, end - start), total)
            end = min(max(start, end), total)
            start = max(0.0, end - span)
            self._view = (start, end)
        if self._selection is not None:
            lo, hi = self._selection
            hi = min(hi, total)
            lo = min(max(0.0, lo), max(0.0, hi - 1.0))
            self._selection = (lo, hi) if hi - lo >= 1.0 else None
        self.update()
        self._sync_cursor()

    def set_envelope(self, envelope):
        """Show the player-style envelope (no selection / zoom / pan)."""
        self._mono = None
        self._selection = None
        self._view = (0.0, 1.0)
        self._envelope = list(envelope or [])
        self.update()
        self._sync_cursor()

    def set_placeholder(self, text):
        """Text shown when no audio is loaded (instead of the gray bar)."""
        text = text or ''
        if text != self._placeholder:
            self._placeholder = text
            self.update()

    def set_progress(self, fraction):
        fraction = max(0.0, min(1.0, float(fraction)))
        if abs(fraction - self._progress) > 1e-4:
            self._progress = fraction
            self.update()

    # ------------------------------------------------------- selection / view
    def selection(self):
        """The selected frame range ``(start, end)`` or None."""
        return self._selection

    def clear_selection(self):
        if self._selection is None:
            return
        self._selection = None
        self.update()
        self.selection_changed.emit()

    def reset_view(self):
        """Show the whole file again."""
        if self._mono is None:
            return
        self._view = (0.0, float(max(1, len(self._mono))))
        self.update()

    def view(self):
        """The visible frame range ``(start, end)``."""
        return self._view

    # ------------------------------------------------------------- mapping
    def _total_frames(self):
        if self._mono is not None:
            return float(max(1, len(self._mono)))
        return float(max(1, len(self._envelope)))

    def _frame_at(self, x):
        start, end = self._view
        width = max(1, self.width())
        fraction = max(0.0, min(1.0, x / width))
        return start + (end - start) * fraction

    def _fraction_of_total(self, frame):
        return max(0.0, min(1.0, frame / self._total_frames()))

    def _fraction_from_pos(self, pos):
        width = self.width()
        if width <= 1:
            return 0.0
        return max(0.0, min(1.0, pos.x() / width))

    # --------------------------------------------------------------- mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._mono is not None:
            self._panning = True
            self._pan_origin = event.globalPosition()
            self._pan_view = self._view
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._mono is not None:
                self._anchor = self._frame_at(event.position().x())
                self._dragging = False
            else:
                self.seek_requested.emit(self._fraction_from_pos(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            if event.buttons() & Qt.MouseButton.MiddleButton:
                self._pan(event)
                return
            self._end_pan()                 # the middle button went up elsewhere
        if self._mono is not None and self._anchor is not None \
                and (event.buttons() & Qt.MouseButton.LeftButton):
            current = self._frame_at(event.position().x())
            if abs(current - self._anchor) >= 1.0:
                self._dragging = True
            if self._dragging:
                total = self._total_frames()
                lo, hi = sorted((self._anchor, current))
                lo = max(0.0, min(lo, total - 1.0))
                hi = max(lo + 1.0, min(hi, total))
                self._selection = (lo, hi)
                self.selection_changed.emit()
                self.update()
            event.accept()
            return
        if self._mono is None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.seek_requested.emit(self._fraction_from_pos(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._end_pan()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._anchor is not None:
            was_drag = self._dragging
            self._anchor = None
            self._dragging = False
            if not was_drag:
                # A plain click seeks and drops the selection (like Audacity).
                self._selection = None
                frame = self._frame_at(event.position().x())
                self.seek_requested.emit(self._fraction_of_total(frame))
                self.selection_changed.emit()
                self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._mono is not None:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        """Zoom the time axis around the cursor (samples mode only)."""
        if self._mono is None:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if not delta:
            return
        total = self._total_frames()
        start, end = self._view
        span = end - start
        factor = 1 / 1.25 if delta > 0 else 1.25
        new_span = min(total, max(min(self.MIN_ZOOM_FRAMES, total), span * factor))
        width = max(1, self.width())
        fraction = max(0.0, min(1.0, event.position().x() / width))
        anchor = start + span * fraction
        new_start = anchor - new_span * fraction
        new_start = max(0.0, min(total - new_span, new_start))
        self._view = (new_start, new_start + new_span)
        self.update()
        event.accept()

    # ------------------------------------------------------------ panning
    def _pan(self, event):
        """Scroll the view so the grabbed spot stays under the cursor."""
        if self._pan_origin is None or self._pan_view is None:
            return
        delta = event.globalPosition() - self._pan_origin
        start, end = self._pan_view
        span = end - start
        total = self._total_frames()
        shift = -delta.x() / max(1, self.width()) * span
        new_start = max(0.0, min(total - span, start + shift))
        self._view = (new_start, new_start + span)
        self.update()
        event.accept()

    def _end_pan(self):
        if not self._panning:
            return
        self._panning = False
        self._pan_origin = None
        self._pan_view = None
        self._sync_cursor()

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._placeholder and self._mono is None and not self._envelope:
            self._paint_placeholder(painter)
        else:
            rect = QRectF(self.rect()).adjusted(2, 6, -2, -8)
            if rect.width() > 0 and rect.height() > 0:
                if self._mono is not None:
                    self._paint_samples(painter, rect)
                elif self._envelope:
                    self._paint_envelope(painter, rect)
                else:
                    self._paint_bar(painter, rect)
        painter.end()

    def _paint_placeholder(self, painter):
        color = self.palette().text().color()
        color.setAlpha(140)
        font = self.font()
        font.setPixelSize(16)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)

    def _colors(self):
        palette = self.palette()
        return QColor('#007acc'), palette.mid().color()

    def _paint_samples(self, painter, rect):
        played, track = self._colors()
        start, end = self._view
        span = max(1e-6, end - start)
        total = self._total_frames()
        if self._selection is not None:
            lo, hi = self._selection
            x0 = rect.x() + (lo - start) / span * rect.width()
            x1 = rect.x() + (hi - start) / span * rect.width()
            left = max(rect.left(), x0)
            right = min(rect.right(), x1)
            if right > left:
                overlay = QColor(played)
                overlay.setAlpha(38)
                painter.fillRect(QRectF(left, rect.top(), right - left, rect.height()),
                                 overlay)
                edge = QColor(played)
                painter.setPen(edge)
                for x in (x0, x1):
                    if rect.left() <= x <= rect.right():
                        painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
        columns = max(1, int(rect.width()))
        center = rect.center().y()
        half = rect.height() / 2
        progress_frame = self._progress * total
        for column in range(columns):
            a = start + span * column / columns
            b = start + span * (column + 1) / columns
            ia = max(0, int(a))
            ib = min(int(total), max(ia + 1, int(round(b))))
            if ia >= int(total):
                break
            segment = self._mono[ia:ib]
            top = min(1.0, float(segment.max()))
            bottom = max(-1.0, float(segment.min()))
            y_top = center - top * half
            y_bottom = center - bottom * half
            if y_bottom - y_top < 1.0:
                y_top, y_bottom = center - 0.5, center + 0.5
            color = played if (ia + ib) / 2 <= progress_frame else track
            painter.setPen(color)
            x = int(rect.x()) + column
            painter.drawLine(x, int(y_top), x, int(y_bottom))
        self._paint_playhead(painter, rect)

    def _paint_envelope(self, painter, rect):
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
        self._paint_playhead(painter, rect)

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

    def _paint_playhead(self, painter, rect):
        if self._mono is not None:
            start, end = self._view
            span = max(1e-6, end - start)
            frame = self._progress * self._total_frames()
            x = rect.x() + (frame - start) / span * rect.width()
            if not (rect.left() <= x <= rect.right()):
                return
        else:
            x = rect.x() + self._progress * rect.width()
        # A mid grey stays visible on both the white and the dark theme (pure
        # white disappeared on the light waveform); painting without
        # antialiasing keeps the line a crisp single pixel instead of a
        # blurred pair of half-covered columns.
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QColor('#909399'))
        painter.drawLine(int(x), int(rect.y()), int(x), int(rect.bottom()))
        painter.restore()

