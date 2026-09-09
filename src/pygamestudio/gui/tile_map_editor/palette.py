"""Tileset palette: the whole tileset cut into tiles, shown scaled.

The palette mirrors the SOURCE sheet: one row of the palette = one row of the
tileset image. The tile cells AUTO-SCALE so the whole tileset width always
fits the panel (drag the splitter narrower and the preview shrinks instead of
being clipped). When zoomed in with the mouse wheel the preview can grow
beyond the panel and the scroll area shows horizontal + vertical scrollbars.

Mouse wheel zooms the whole preview (Ctrl is not needed); Shift + wheel
scrolls vertically; scrollbars appear when the preview overflows. A left
click picks the current paint tile (emits ``tile_selected``).

Rendering uses QImage/``drawImage`` (never QPixmap) - scaled QPixmap drawing
is unstable on some (offscreen/test) platforms.
"""

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.tile_map_editor.utils import make_checker_image, surface_to_qimage

SPACING = 3            # gap between cells + outer margins
DEFAULT_CELL = 36      # cell size when the sheet layout is unknown
MIN_CELL = 6           # never shrink a tile below this (rare huge sheets)
MAX_CELL = 96          # cap for a single row when the sheet is very wide


class TilesetPalette(QWidget):
    tile_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tile_images = []
        self._current_tile = 0
        self._hint = ''
        self._object = None
        self._scroll = None            # the QScrollArea hosting us
        self._source_cols = None       # tiles per row of the SOURCE sheet
        self._aspect = 1.0             # tile_height / tile_width
        self._cell_w = DEFAULT_CELL
        self._cell_h = DEFAULT_CELL
        self._scale = 1.0              # manual zoom multiplier (wheel)
        self._checker = make_checker_image()
        self.setMouseTracking(True)
        self.setToolTip(T.tr('tile_map.palette_hint',
                             'Left: pick tile · Wheel: zoom · Shift+wheel: scroll'))

    # ------------------------------------------------------------- public
    def bind_scroll_area(self, scroll):
        """Remember the hosting scroll area and re-fit whenever it resizes."""
        self._scroll = scroll
        if scroll is not None:
            scroll.installEventFilter(self)
            scroll.viewport().installEventFilter(self)

    def set_object(self, obj):
        """Rebuild from a tile-map object (None clears the palette)."""
        self._object = obj
        self._source_cols = None
        self._aspect = 1.0
        self._tile_images = ([surface_to_qimage(s) for s in obj.get_tileset_tiles()]
                             if obj is not None else [])
        if obj is not None and getattr(obj, 'tileset_path', ''):
            sw, _sh = obj.get_tileset_dimensions()
            tw = int(getattr(obj, 'tile_width', 1) or 1)
            th = int(getattr(obj, 'tile_height', 1) or 1)
            if sw and tw:
                cols = sw // tw
                if cols > 0:
                    self._source_cols = cols
                    self._aspect = (th / tw) if tw else 1.0
        self._scale = 1.0             # reset to "fit width" per new sheet
        self.relayout()
        self.update()

    def relayout(self):
        """Recompute the cell size so the whole tileset width fits the panel
        (or honour the manual zoom), then size ourselves to the content."""
        count = len(self._tile_images)
        vw = self._viewport_width()

        if not count:
            self._cell_w = DEFAULT_CELL
            self._cell_h = DEFAULT_CELL
            self.setFixedSize(max(212, vw - 8), 120)
            self.updateGeometry()
            self.update()
            return

        if self._source_cols:
            cols = self._source_cols
            self._cols = cols
            # Fill one whole source row into the panel width EXACTLY: the
            # whole tileset always stays fully visible (drag the splitter
            # narrower and the preview shrinks, drag it wider and it grows),
            # scaled further by the manual wheel zoom. A vertical
            # scrollbar appears when the sheet is taller than the panel;
            # once zoomed in, a horizontal scrollbar appears too.
            usable = vw - (cols + 1) * SPACING
            fit = (usable / cols) if usable > 0 else 1.0
            cell_w = max(0.5, fit * self._scale)
        else:
            # Sheet layout unknown: pack at a fixed cell size that fits.
            cell_w = DEFAULT_CELL
            cols = max(1, (vw - SPACING) // (cell_w + SPACING))
            self._cols = cols

        cell_h = cell_w * self._aspect
        rows = (count + cols - 1) // cols
        content_w = cols * (cell_w + SPACING) + SPACING
        content_h = SPACING + rows * (cell_h + SPACING)

        self._cell_w = cell_w
        self._cell_h = cell_h
        self.setFixedSize(max(1, int(content_w)), max(1, int(content_h)))
        self.updateGeometry()
        self.update()

    def set_hint(self, text):
        self._hint = text or ''
        self.update()

    def set_current_tile(self, tile_id):
        self._current_tile = int(tile_id)
        self.update()

    def has_tiles(self):
        return bool(self._tile_images)

    def current_tile(self):
        return self._current_tile

    def columns(self):
        return self._cols if hasattr(self, '_cols') else 5

    def zoom_by(self, factor):
        """Multiply the preview zoom (mouse wheel). 1.0 = fit the pane width."""
        self._scale = max(0.3, min(6.0, self._scale * factor))
        self.relayout()
        self.update()

    # -------------------------------------------------------------- layout
    def _viewport_width(self):
        if self._scroll is not None and self._scroll.viewport() is not None:
            return max(1, self._scroll.viewport().width())
        return max(1, self.width())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and self._scroll is not None:
            self.relayout()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        if self._scroll is None:
            self.relayout()
        return super().resizeEvent(event)

    def wheelEvent(self, event):
        # A PLAIN wheel zooms the whole tileset preview (that is what the
        # left pane is for); Ctrl+wheel does the same. Shift+wheel is kept
        # for vertical scrolling, otherwise the wheel would be unusable once
        # the zoomed-in preview grows taller than the pane.
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self._scroll is not None:
                bar = self._scroll.verticalScrollBar()
                if bar is not None and bar.maximum() > 0:
                    delta = event.angleDelta().y()
                    step = bar.singleStep() * (3 if delta else 0)
                    bar.setValue(bar.value() - step)
                    event.accept()
                    return
        else:
            delta = event.angleDelta().y()
            if delta:
                self.zoom_by(1.2 if delta > 0 else (1 / 1.2))
                event.accept()
                return
        return super().wheelEvent(event)

    def _cell_size(self):
        return (self._cell_w + SPACING, self._cell_h + SPACING)

    # -------------------------------------------------------------- paint
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        if not self._tile_images:
            if self._hint:
                painter.setPen(QColor(150, 150, 150))
                font = QFont(painter.font())
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(QRect(8, 8, max(1, self.width() - 16),
                                       max(1, self.height() - 16)),
                                 Qt.AlignmentFlag.AlignLeft
                                 | Qt.AlignmentFlag.AlignTop
                                 | Qt.TextFlag.TextWordWrap, self._hint)
            painter.end()
            return

        step_w, step_h = self._cell_size()
        cols = self._cols
        for i, img in enumerate(self._tile_images):
            col = i % cols
            row = i // cols
            x = SPACING + col * step_w
            y = SPACING + row * step_h

            painter.drawImage(QRectF(x, y, self._cell_w, self._cell_h),
                              self._checker)
            painter.drawImage(QRectF(x, y, self._cell_w, self._cell_h), img)

            painter.setPen(QColor(0, 0, 0, 60))
            painter.drawRect(x, y, self._cell_w - 1, self._cell_h - 1)

            if i == self._current_tile:
                painter.setPen(QColor(0, 122, 204))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x - 1, y - 1,
                                 self._cell_w + 1, self._cell_h + 1)
                painter.drawRect(x + 1, y + 1,
                                 self._cell_w - 3, self._cell_h - 3)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self._tile_images:
            return super().mousePressEvent(event)
        step_w, step_h = self._cell_size()
        col = int((event.position().x() - SPACING) // step_w)
        row = int((event.position().y() - SPACING) // step_h)
        if col < 0 or row < 0:
            return
        index = row * self._cols + col
        if 0 <= index < len(self._tile_images):
            self.set_current_tile(index)
            self.tile_selected.emit(index)
        event.accept()
