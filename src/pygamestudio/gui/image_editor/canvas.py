"""The image canvas: paints the working QImage, handles mouse drawing and
exposes the editing API (tools, brush, color, undo/redo, transform, zoom).
"""

import math
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QPainter, QPen, QPolygonF, QTransform)
from PySide6.QtWidgets import QWidget


# Tool identifiers.
TOOL_PENCIL = 'pencil'
TOOL_ERASER = 'eraser'
TOOL_LINE = 'line'
TOOL_RECT = 'rect'
TOOL_ELLIPSE = 'ellipse'
TOOL_FILL = 'fill'
TOOL_PICKER = 'picker'

# The checkerboard tile used behind transparent areas (two grays).
_CHECKER_1 = QColor(205, 205, 205)
_CHECKER_2 = QColor(235, 235, 235)

MAX_UNDO = 30


def _alpha_blend(src_rgba, dst_rgba):
    """Blend a source color over an opaque-ish destination (both (r,g,b,a)
    tuples) - only used for a color overlay preview, never saved."""
    a = src_rgba[3] / 255.0
    if a >= 1.0:
        return src_rgba
    r = int(src_rgba[0] * a + dst_rgba[0] * (1 - a))
    g = int(src_rgba[1] * a + dst_rgba[1] * (1 - a))
    b = int(src_rgba[2] * a + dst_rgba[2] * (1 - a))
    return (r, g, b, dst_rgba[3])


class ImageCanvas(QWidget):
    """Editable raster canvas.

    Holds one QImage and draws it scaled by ``_zoom``; transparent pixels are
    shown on a checkerboard. Editing operations (strokes, shapes, fill,
    transforms) go through undoable snapshots.
    """

    modified_changed = Signal(bool)     # True while there are unsaved edits
    zoom_changed = Signal(float)        # current zoom factor
    color_picked = Signal(QColor)       # eyedropper picked a color
    image_size_changed = Signal()       # underlying image dimensions changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self._zoom = 1.0
        self._tool = TOOL_PENCIL
        self._brush_size = 4
        self._color = QColor(20, 20, 20, 255)
        self._modified = False
        self._img_w = -1
        self._img_h = -1

        self._undo_stack = []
        self._redo_stack = []

        # Stroke state.
        self._drawing = False
        self._last_point = None
        self._shape_start = None
        self._shape_current = None
        self._stroke_points = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAutoFillBackground(False)

    # ------------------------------------------------------------ image io
    def load(self, path):
        """Load an image file. Returns True on success."""
        image = QImage(path)
        if image.isNull():
            return False
        self.set_image(image.convertToFormat(QImage.Format.Format_ARGB32))
        return True

    def set_image(self, image):
        """Replace the working image (used by tests / scripting)."""
        self._image = image.convertToFormat(QImage.Format.Format_ARGB32)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._drawing = False
        self._shape_start = self._shape_current = None
        self._stroke_points = None
        self._modified = False
        self._sync_size()
        self.update()
        self.modified_changed.emit(False)

    def image(self):
        """The current working image (may be shared - copy before mutating)."""
        return self._image

    def image_size(self):
        if self._image is None:
            return (0, 0)
        return (self._image.width(), self._image.height())

    def has_image(self):
        return self._image is not None

    def is_modified(self):
        return self._modified

    def current_color(self):
        return QColor(self._color)

    def save(self, path):
        """Write the image to ``path`` (format derived from the suffix).
        Returns True on success."""
        if self._image is None:
            return False
        ok = self._image.save(path)
        if ok:
            self._modified = False
            self.modified_changed.emit(False)
        return ok

    # ------------------------------------------------------------ edit state
    def _mark_modified(self):
        if not self._modified:
            self._modified = True
            self.modified_changed.emit(True)

    def _push_undo(self):
        if self._image is None:
            return
        self._undo_stack.append(self._image.copy())
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._mark_modified()

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def undo(self):
        if not self._undo_stack or self._image is None:
            return
        self._redo_stack.append(self._image.copy())
        self._image = self._undo_stack.pop()
        self.update()
        self.modified_changed.emit(True)

    def redo(self):
        if not self._redo_stack or self._image is None:
            return
        self._undo_stack.append(self._image.copy())
        self._image = self._redo_stack.pop()
        self.update()
        self.modified_changed.emit(True)

    # ------------------------------------------------------------ tools
    def set_tool(self, tool):
        self._tool = tool
        self.setCursor(Qt.CursorShape.CrossCursor if tool in (TOOL_FILL, TOOL_PICKER, TOOL_LINE, TOOL_RECT, TOOL_ELLIPSE)
                       else Qt.CursorShape.CrossCursor)

    def tool(self):
        return self._tool

    def set_brush_size(self, size):
        self._brush_size = max(1, int(size))

    def brush_size(self):
        return self._brush_size

    def set_color(self, color):
        self._color = QColor(color)

    # ------------------------------------------------------------ transforms
    def flip_h(self):
        if self._image is None:
            return
        self._push_undo()
        self._image = self._image.mirrored(True, False)
        self.update()

    def flip_v(self):
        if self._image is None:
            return
        self._push_undo()
        self._image = self._image.mirrored(False, True)
        self.update()

    def rotate_cw(self):
        """Rotate the image 90 degrees clockwise."""
        if self._image is None:
            return
        self._push_undo()
        self._image = self._image.transformed(QTransform().rotate(90),
                                              Qt.TransformationMode.SmoothTransformation)
        self._sync_size()
        self.update()

    def rotate_ccw(self):
        """Rotate the image 90 degrees counter-clockwise."""
        if self._image is None:
            return
        self._push_undo()
        self._image = self._image.transformed(QTransform().rotate(-90),
                                              Qt.TransformationMode.SmoothTransformation)
        self._sync_size()
        self.update()

    def clear(self):
        if self._image is None:
            return
        self._push_undo()
        self._image.fill(0)
        self.update()

    # ------------------------------------------------------------ zoom / size
    def zoom(self):
        return self._zoom

    def set_zoom(self, zoom):
        zoom = max(0.02, min(32.0, float(zoom)))
        if abs(zoom - self._zoom) < 1e-9:
            return
        self._zoom = zoom
        self._sync_size()
        self.update()
        self.zoom_changed.emit(self._zoom)

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.25)

    def actual_size(self):
        self.set_zoom(1.0)

    def fit_in_view(self, viewport_width, viewport_height):
        """Zoom so the whole image fits inside the given viewport area."""
        if self._image is None or viewport_width <= 0 or viewport_height <= 0:
            return
        scale = min(viewport_width / self._image.width(),
                    viewport_height / self._image.height())
        self.set_zoom(max(0.02, scale))

    def _sync_size(self):
        w = self._image.width() if self._image is not None else 0
        h = self._image.height() if self._image is not None else 0
        if w != self._img_w or h != self._img_h:
            self._img_w = w
            self._img_h = h
            self.image_size_changed.emit()
        self.setFixedSize(int(w * self._zoom), int(h * self._zoom))

    # ------------------------------------------------------------ coordinates
    def _to_image(self, pos):
        """Map a widget position to integer image coordinates (clamped)."""
        if self._image is None:
            return None
        x = int(pos.x() / self._zoom)
        y = int(pos.y() / self._zoom)
        x = max(0, min(self._image.width() - 1, x))
        y = max(0, min(self._image.height() - 1, y))
        return (x, y)

    # ------------------------------------------------------------ painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), _CHECKER_1)
        if self._image is None:
            return
        # Checkerboard for transparency.
        tile = 8
        for ty in range(0, int(self.height()), tile):
            for tx in range(0, int(self.width()), tile):
                if ((tx // tile) + (ty // tile)) % 2 == 0:
                    painter.fillRect(tx, ty, tile, tile, _CHECKER_2)

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._zoom < 1.0)
        target = QRectF(0, 0, self._image.width() * self._zoom,
                        self._image.height() * self._zoom)
        painter.drawImage(target, self._image)

        if self._shape_start is not None and self._shape_current is not None:
            self._draw_shape_preview(painter)

        if self._drawing and self._stroke_points:
            self._draw_stroke_preview(painter)

    def _draw_shape_preview(self, painter):
        painter.save()
        pen = QPen(self._color, max(1, self._brush_size), Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        z = self._zoom
        p1 = QPointF(self._shape_start[0] * z, self._shape_start[1] * z)
        p2 = QPointF(self._shape_current[0] * z, self._shape_current[1] * z)
        if self._tool == TOOL_LINE:
            painter.drawLine(p1, p2)
        elif self._tool in (TOOL_RECT, TOOL_ELLIPSE):
            rect = QRectF(p1, p2).normalized()
            if self._tool == TOOL_RECT:
                painter.drawRect(rect)
            else:
                painter.drawEllipse(rect)
        painter.restore()

    def _draw_stroke_preview(self, painter):
        """Live overlay of the freehand pencil stroke while dragging."""
        pts = self._stroke_points
        if not pts:
            return
        z = self._zoom
        pen = QPen(self._color, max(1.0, self._brush_size * z))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.save()
        painter.setPen(pen)
        if len(pts) == 1:
            x, y = pts[0]
            painter.drawPoint(QPointF(x * z, y * z))
        else:
            poly = QPolygonF([QPointF(x * z, y * z) for (x, y) in pts])
            painter.drawPolyline(poly)
        painter.restore()

    def _commit_stroke(self):
        """Paint the collected freehand stroke into the image in a single
        pass, so the alpha value is applied once (matching the translucent
        look of line/rect/ellipse strokes)."""
        if self._image is None or not self._stroke_points:
            return
        pts = self._stroke_points
        painter = self._painter()
        try:
            if len(pts) == 1:
                x, y = pts[0]
                painter.drawPoint(QPointF(x, y))
            else:
                poly = QPolygonF([QPointF(x, y) for (x, y) in pts])
                painter.drawPolyline(poly)
        finally:
            painter.end()

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, event):
        if self._image is None or event.button() != Qt.MouseButton.LeftButton:
            return
        point = self._to_image(event.position())
        if point is None:
            return

        if self._tool == TOOL_FILL:
            self._push_undo()
            self._flood_fill(point[0], point[1], self._color)
            self._shape_start = self._shape_current = None
            self.update()
            return

        if self._tool == TOOL_PICKER:
            picked = self._image.pixelColor(point[0], point[1])
            self._color = picked
            self.color_picked.emit(picked)
            return

        if self._tool == TOOL_PENCIL:
            self._push_undo()
            self._drawing = True
            self._stroke_points = [point]
            self.update()
            return

        if self._tool == TOOL_ERASER:
            self._push_undo()
            self._drawing = True
            self._last_point = point
            self._stamp_point(point, point)
            self.update()
            return

        # Shape tools: remember the start point, draw the preview on move.
        self._push_undo()
        self._shape_start = point
        self._shape_current = point

    def mouseMoveEvent(self, event):
        if self._image is None:
            return
        point = self._to_image(event.position())
        if point is None:
            return

        if self._drawing and (event.buttons() & Qt.MouseButton.LeftButton):
            if self._stroke_points is not None:
                # Freehand pencil only accumulates the path here; it is painted
                # once on release so a translucent color does not stack up to
                # an opaque one (matches the line/rect/ellipse behaviour).
                if self._stroke_points[-1] != point:
                    self._stroke_points.append(point)
                self.update()
            elif self._last_point is not None:
                self._stamp_point(self._last_point, point)
                self._last_point = point
                self.update()
            return

        if self._shape_start is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self._shape_current = point
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drawing:
            if self._stroke_points is not None:
                self._commit_stroke()
            self._drawing = False
            self._stroke_points = None
            self._last_point = None
            return
        if self._shape_start is not None and self._shape_current is not None:
            self._commit_shape()
            self._shape_start = None
            self._shape_current = None
            self.update()

    def wheelEvent(self, event):
        if self._image is None:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self._zoom * factor)
            event.accept()

    # ------------------------------------------------------------ drawing
    def _painter(self):
        painter = QPainter(self._image)
        if self._tool == TOOL_ERASER:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._color if self._tool != TOOL_ERASER else QColor(0, 0, 0, 0),
                   max(1, self._brush_size))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        return painter

    def _stamp_point(self, from_point, to_point):
        """Stamp a pencil/eraser stroke segment between two image points."""
        if self._image is None:
            return
        painter = self._painter()
        try:
            if from_point == to_point:
                painter.drawPoint(from_point[0], from_point[1])
            else:
                painter.drawLine(from_point[0], from_point[1],
                                 to_point[0], to_point[1])
        finally:
            painter.end()

    def _commit_shape(self):
        """Paint the finished line/rect/ellipse into the image."""
        if self._image is None:
            return
        p1 = QPointF(self._shape_start[0], self._shape_start[1])
        p2 = QPointF(self._shape_current[0], self._shape_current[1])
        painter = self._painter()
        try:
            if self._tool == TOOL_LINE:
                painter.drawLine(p1, p2)
            elif self._tool == TOOL_RECT:
                painter.drawRect(QRectF(p1, p2).normalized())
            elif self._tool == TOOL_ELLIPSE:
                painter.drawEllipse(QRectF(p1, p2).normalized())
        finally:
            painter.end()

    # ------------------------------------------------------------ flood fill
    def _flood_fill(self, x, y, color):
        """Flood-fill from (x, y) with ``color`` (4-way, on a RGBA copy)."""
        image = self._image.convertToFormat(QImage.Format.Format_RGBA8888)
        width, height = image.width(), image.height()
        stride = image.bytesPerLine()
        bits = image.bits()
        if hasattr(bits, 'setsize'):        # sip.voidptr in older PySide6
            bits.setsize(image.sizeInBytes())
        data = bytearray(bits)

        start = y * stride + x * 4
        target = bytes(data[start:start + 4])
        rgba = color.getRgb()
        replacement = bytes((rgba[0], rgba[1], rgba[2], rgba[3]))
        if target == replacement:
            return

        queue = deque([(x, y)])
        data[start:start + 4] = replacement
        while queue:
            px, py = queue.popleft()
            for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                index = ny * stride + nx * 4
                if data[index:index + 4] == target:
                    data[index:index + 4] = replacement
                    queue.append((nx, ny))

        new_image = QImage(bytes(data), width, height, stride,
                           QImage.Format.Format_RGBA8888)
        self._image = new_image.convertToFormat(QImage.Format.Format_ARGB32)

    # ------------------------------------------------------------ keys
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.redo()
                else:
                    self.undo()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Y:
                self.redo()
                event.accept()
                return
        super().keyPressEvent(event)
