"""The interactive tile-map canvas: shows the map and paints tiles.

The canvas is the edit surface of the tile map editor. It draws the map's
cells (checkerboard behind empty cells + grid lines), handles the mouse to
paint strokes, and commits every finished stroke to the undo stack as ONE
command via ``GameManager.commit_tile_map_paint`` (the tile data is mutated
live during a stroke for instant preview).

All rendering uses QImage/``drawImage`` (never QPixmap) because scaled
QPixmap drawing is unstable on some (offscreen/test) platforms.
"""

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from pygamestudio.gui.tile_map_editor.utils import make_checker_image, surface_to_qimage

# Tools.
TOOL_PENCIL = 'pencil'
TOOL_ERASE = 'erase'
TOOL_FILL = 'fill'
TOOL_PICK = 'pick'

TOOL_ERASE_TILE = -1   # the eraser paints the "empty" tile id

_CHECKER_C1 = (58, 58, 58)
_CHECKER_C2 = (46, 46, 46)


class TileMapCanvas(QWidget):
    """Paints + edits one tile-map object (bound via ``set_object``)."""

    # Emitted when the "pick" tool reads a tile from the map (the host then
    # makes it the current tile and switches back to the pencil).
    tile_picked = Signal(int)
    # Emitted when the user zooms with the wheel (the host resizes us).
    zoom_changed = Signal(float)

    def __init__(self, game_manager, parent=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._object = None
        self._tool = TOOL_PENCIL
        self._current_tile = 0
        self._zoom = 1.0

        self._tile_images = []       # cached QImages of the current tileset
        self._pix_cache_key = None   # (id(obj), tileset_path, tile_w, tile_h)
        self._checker = make_checker_image(c1=_CHECKER_C1, c2=_CHECKER_C2)
        self._background = None      # full-size checker QImage (per widget size)
        self._background_size = None
        # When True, solid cells (per-tile collision) get a translucent red
        # overlay so the collision layout can be previewed while painting.
        self._show_collision = False

        # Stroke state (live painting happens outside the undo stack).
        self._stroke_old_tiles = None
        self._stroke_active = False
        self._right_erase = False
        self._last_cell = None
        self._hover_cell = None

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ------------------------------------------------------------- public
    def set_object(self, obj):
        """Bind to a tile-map object (None clears the canvas)."""
        self._object = obj
        self._stroke_active = False
        self._stroke_old_tiles = None
        self._right_erase = False
        self._last_cell = None
        self._hover_cell = None
        self._pix_cache_key = None
        self.update()

    def object(self):
        return self._object

    def has_object(self):
        return self._object is not None

    def set_tool(self, tool):
        if tool in (TOOL_PENCIL, TOOL_ERASE, TOOL_FILL, TOOL_PICK):
            self._tool = tool

    def tool(self):
        return self._tool

    def set_current_tile(self, tile_id):
        self._current_tile = int(tile_id)

    def current_tile(self):
        return self._current_tile

    def set_zoom(self, zoom):
        self._zoom = max(0.1, min(16.0, float(zoom)))
        self.update()

    def zoom(self):
        return self._zoom

    def map_pixel_size(self):
        """(width, height) of the whole map at the current zoom."""
        obj = self._object
        if obj is None:
            return (0, 0)
        return (max(1, int(obj.columns * obj.tile_width * self._zoom)),
                max(1, int(obj.rows * obj.tile_height * self._zoom)))

    def refresh(self):
        """Drop cached tile images (tileset may have changed) and repaint."""
        self._pix_cache_key = None
        self.update()

    def set_show_collision(self, show):
        """Show/hide the translucent solid-cell overlay."""
        self._show_collision = bool(show)
        self.update()

    def show_collision(self):
        return self._show_collision

    # -------------------------------------------------------------- paint
    def _ensure_tile_images(self):
        obj = self._object
        if obj is None:
            self._tile_images = []
            return
        key = (id(obj), obj.tileset_path, obj.tile_width, obj.tile_height)
        if key == self._pix_cache_key:
            return
        self._tile_images = [surface_to_qimage(s) for s in obj.get_tileset_tiles()]
        self._pix_cache_key = key

    def _ensure_background(self):
        size = (self.width(), self.height())
        if self._background is None or self._background_size != size:
            w, h = size
            if w <= 0 or h <= 0:
                return
            bg = QImage(max(1, w), max(1, h), QImage.Format.Format_ARGB32)
            bg.fill(QColor(*_CHECKER_C2))
            painter = QPainter(bg)
            cell = 8
            for yy in range(0, h, cell * 2):
                for xx in range(0, w, cell * 2):
                    painter.fillRect(xx, yy, cell, cell, QColor(*_CHECKER_C1))
                    painter.fillRect(xx + cell, yy + cell, cell, cell, QColor(*_CHECKER_C1))
            painter.end()
            self._background = bg
            self._background_size = size

    def paintEvent(self, event):
        self._ensure_background()
        painter = QPainter(self)
        if self._background is not None:
            painter.drawImage(0, 0, self._background)

        obj = self._object
        if obj is None:
            painter.end()
            return

        self._ensure_tile_images()
        tw = obj.tile_width * self._zoom
        th = obj.tile_height * self._zoom
        columns, rows = obj.columns, obj.rows

        # Visible cell range (the widget may be scrolled in a QScrollArea).
        left, top = self._scroll_offset()
        right = left + self.width()
        bottom = top + self.height()

        col0 = max(0, int(left / tw)) if tw > 0 else 0
        row0 = max(0, int(top / th)) if th > 0 else 0
        col1 = min(columns, int(right / tw) + 1) if tw > 0 else columns
        row1 = min(rows, int(bottom / th) + 1) if th > 0 else rows

        images = self._tile_images
        layer_count = obj.get_layer_count()
        for row in range(row0, row1):
            for col in range(col0, col1):
                # Composite the VISIBLE layers TOP-DOWN and stop at the first
                # tile found: the TOPMOST layer that has a tile at this cell
                # wins (mirrors the runtime content surface, where the last
                # (top) layer is blitted last).
                for layer in range(layer_count - 1, -1, -1):
                    if not obj.is_layer_visible(layer):
                        continue
                    tile_id = obj.get_tile(col, row, layer)
                    if 0 <= tile_id < len(images):
                        painter.drawImage(QRectF(col * tw, row * th, tw, th),
                                          images[tile_id])
                        break

        # Grid lines.
        painter.setPen(QColor(0, 0, 0, 90))
        for col in range(col0, col1 + 1):
            x = int(col * tw)
            painter.drawLine(x, int(top), x, int(bottom))
        for row in range(row0, row1 + 1):
            y = int(row * th)
            painter.drawLine(int(left), y, int(right), y)

        # 1px outline around the whole map.
        painter.setPen(QColor(0, 0, 0, 160))
        painter.drawRect(0, 0, int(columns * tw) - 1, int(rows * th) - 1)

        # Per-tile collision overlay (translucent red on solid cells).
        if self._show_collision and hasattr(obj, 'is_cell_solid'):
            for row in range(row0, row1):
                for col in range(col0, col1):
                    if obj.is_cell_solid(col, row):
                        painter.fillRect(QRectF(col * tw, row * th, tw, th),
                                         QColor(255, 30, 30, 80))

        # Hover cell highlight (only for tools that paint/read a cell).
        cell = self._hover_cell
        if cell and self._tool in (TOOL_PENCIL, TOOL_ERASE, TOOL_PICK):
            painter.fillRect(QRectF(cell[0] * tw, cell[1] * th, tw, th),
                             QColor(255, 255, 255, 60))
        painter.end()

    def resizeEvent(self, event):
        self._background = None
        return super().resizeEvent(event)

    def _scroll_offset(self):
        """Top-left of the visible area in widget coordinates (0,0 when the
        canvas fills the viewport and is not scrolled)."""
        scroll = self.parentWidget()
        while scroll is not None and not scroll.inherits('QScrollArea'):
            scroll = scroll.parentWidget()
        if scroll is None:
            return (0, 0)
        return (scroll.horizontalScrollBar().value(),
                scroll.verticalScrollBar().value())

    # -------------------------------------------------------------- mouse
    def wheelEvent(self, event):
        if self._object is None:
            return super().wheelEvent(event)
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = max(0.1, min(16.0, self._zoom * 1.25))
        else:
            self._zoom = max(0.1, min(16.0, self._zoom / 1.25))
        self.update()
        self.zoom_changed.emit(self._zoom)
        event.accept()

    def _widget_to_cell(self, pos):
        obj = self._object
        if obj is None:
            return None
        tw = obj.tile_width * self._zoom
        th = obj.tile_height * self._zoom
        if tw <= 0 or th <= 0:
            return None
        col = int(pos.x() // tw)
        row = int(pos.y() // th)
        if 0 <= col < obj.columns and 0 <= row < obj.rows:
            return (col, row)
        return None

    def _paint_cell(self, col, row, tile_id):
        obj = self._object
        if obj is None:
            return
        if obj.get_tile(col, row) == tile_id:
            return
        obj.set_tile(col, row, tile_id)
        self.update()

    def _start_stroke(self):
        obj = self._object
        if obj is not None:
            # Snapshot the ACTIVE layer's tiles; the stroke edits that layer
            # and is committed to the undo stack as one layer paint command.
            self._stroke_old_tiles = list(obj.get_active_layer_tiles())
            self._stroke_active = True

    def _end_stroke(self):
        if self._stroke_active and self._object is not None:
            old = self._stroke_old_tiles
            self._stroke_active = False
            self._stroke_old_tiles = None
            self._game_manager.commit_tile_map_paint(self._object.uuid, old)
        else:
            self._stroke_active = False
            self._stroke_old_tiles = None

    def _flood_fill(self, col, row):
        obj = self._object
        if obj is None:
            return
        target = obj.get_tile(col, row)
        replacement = self._current_tile
        if target == replacement:
            return
        columns, rows = obj.columns, obj.rows
        seen = set()
        stack = [(col, row)]
        while stack:
            c, r = stack.pop()
            if (c, r) in seen:
                continue
            if not (0 <= c < columns and 0 <= r < rows):
                continue
            if obj.get_tile(c, r) != target:
                continue
            seen.add((c, r))
            stack.extend(((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)))
        for (c, r) in seen:
            obj.set_tile(c, r, replacement)
        self.update()

    def mousePressEvent(self, event):
        obj = self._object
        if obj is None:
            return super().mousePressEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            cell = self._widget_to_cell(event.position())
            if cell is None:
                return
            if self._tool == TOOL_PICK:
                self.tile_picked.emit(obj.get_tile(cell[0], cell[1]))
                return
            if self._tool == TOOL_FILL:
                self._start_stroke()
                self._flood_fill(cell[0], cell[1])
                self._end_stroke()          # fill = one undo command
                return
            # pencil / erase: begin a live stroke.
            self._start_stroke()
            self._last_cell = cell
            tile_id = self._current_tile if self._tool == TOOL_PENCIL else TOOL_ERASE_TILE
            self._paint_cell(cell[0], cell[1], tile_id)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            # Right-drag always erases cells (quick way to remove tiles).
            cell = self._widget_to_cell(event.position())
            if cell is None:
                return
            self._right_erase = True
            self._start_stroke()
            self._last_cell = cell
            self._paint_cell(cell[0], cell[1], TOOL_ERASE_TILE)
            event.accept()
            return

        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        obj = self._object
        if obj is None:
            return super().mouseMoveEvent(event)

        cell = self._widget_to_cell(event.position())
        self._hover_cell = cell
        self.update()

        buttons = event.buttons()
        if self._stroke_active and cell is not None and self._last_cell is not None:
            left_paint = (buttons & Qt.MouseButton.LeftButton
                          and self._tool in (TOOL_PENCIL, TOOL_ERASE))
            right_paint = (buttons & Qt.MouseButton.RightButton and self._right_erase)
            if left_paint or right_paint:
                erase = (self._tool == TOOL_ERASE) or right_paint
                tile_id = TOOL_ERASE_TILE if erase else self._current_tile
                for c, r in self._line_cells(self._last_cell, cell):
                    self._paint_cell(c, r, tile_id)
                self._last_cell = cell
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._right_erase = False
            self._end_stroke()
            self._last_cell = None
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._stroke_active:
            self._end_stroke()
            self._last_cell = None
            event.accept()
            return
        return super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover_cell = None
        self.update()
        return super().leaveEvent(event)

    @staticmethod
    def _line_cells(a, b):
        """Bresenham cell walk between two grid cells (inclusive)."""
        x0, y0 = a
        x1, y1 = b
        cells = []
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            cells.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
        return cells
