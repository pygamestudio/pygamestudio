"""The image canvas: paints the working QImage, handles mouse drawing and
exposes the editing API (tools, brush, color, undo/redo, transform, zoom).
"""

import math
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QPainter, QPen, QTransform)
from PySide6.QtWidgets import QAbstractScrollArea, QWidget


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

#: Zoom factor from which the pixel grid appears: every image pixel becomes
#: a visible square (Aseprite style), so single pixels can be drawn by hand.
PIXEL_GRID_MIN_ZOOM = 8.0
#: Pixel-grid line colors: one thin line per pixel plus a stronger line every
#: _GRID_ACCENT_STEP-th line (pixel-art rulers, like the scene grid).
_GRID_COLOR = QColor(0, 0, 0, 48)
_GRID_ACCENT_COLOR = QColor(0, 0, 0, 96)
_GRID_ACCENT_STEP = 8


def _line_pixels(points):
    """The pixel path through ``points`` (Bresenham), every pixel once.

    Stamping is per pixel and deduplicated, so a revisited pixel (a crossing
    stroke, a back-and-forth scribble) is painted once - a translucent color
    never stacks up to a darker one.
    """
    if not points:
        return []
    path = []
    seen = set()

    def visit(x, y):
        if (x, y) not in seen:
            seen.add((x, y))
            path.append((x, y))

    if len(points) == 1:
        visit(points[0][0], points[0][1])
        return path
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            visit(x0, y0)
            if x0 == x1 and y0 == y1:
                break
            err2 = 2 * err
            if err2 > -dy:
                err -= dy
                x0 += sx
            if err2 < dx:
                err += dx
                y0 += sy
    return path


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
    transforms) go through undoable snapshots. Drawing is pixel exact (like a
    pixel-art tool): strokes are stamped pixel by pixel with hard edges -
    brush size 1 paints exactly one pixel - and from ``PIXEL_GRID_MIN_ZOOM``
    on every pixel is outlined by a grid. A middle-button drag pans the view
    (it scrolls the parent QScrollArea) and never paints.
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
        self._hover_point = None
        self._grid_visible = True
        self._panning = False
        self._pan_origin = None
        self._pan_scroll = (0, 0)

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
        self._hover_point = None
        self._panning = False
        self._pan_origin = None
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
        # A plain arrow everywhere: the hover marker below shows where the
        # tool would act, so the old crosshair (every tool had it) is gone.
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def tool(self):
        return self._tool

    def set_brush_size(self, size):
        self._brush_size = max(1, int(size))

    def brush_size(self):
        return self._brush_size

    def set_color(self, color):
        """Set the drawing color: a QColor, '#rrggbb' or [r, g, b(, a)].

        The list form is what MCP/agent callers pass; QColor does not accept a
        sequence itself, so it is unpacked here (same as the window helper).
        """
        if isinstance(color, (list, tuple)):
            color = QColor(*[int(channel) for channel in color])
        self._color = QColor(color)

    def grid_visible(self):
        """Whether the pixel-grid toggle is on (see PIXEL_GRID_MIN_ZOOM)."""
        return self._grid_visible

    def set_grid_visible(self, visible):
        """Show/hide the pixel grid (the toolbar toggle)."""
        visible = bool(visible)
        if visible == self._grid_visible:
            return
        self._grid_visible = visible
        self.update()

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

        self._draw_pixel_grid(painter, event.rect())

        if self._shape_start is not None and self._shape_current is not None:
            self._draw_shape_preview(painter)

        if self._drawing and self._stroke_points:
            self._draw_stroke_preview(painter)

        self._draw_hover_preview(painter)

    def _draw_shape_preview(self, painter):
        """Show the shape exactly as the pixels releasing the button will paint.

        The shape is rasterized at image resolution (the same code the commit
        runs) and then drawn block by block, so a line/rectangle/ellipse is
        already in pixel form while dragging - not a smooth vector outline
        that only turns into pixels on release.
        """
        if self._image is None:
            return
        margin = max(1, self._brush_size)
        x0 = max(0, min(self._shape_start[0], self._shape_current[0]) - margin)
        y0 = max(0, min(self._shape_start[1], self._shape_current[1]) - margin)
        x1 = min(self._image.width() - 1,
                 max(self._shape_start[0], self._shape_current[0]) + margin)
        y1 = min(self._image.height() - 1,
                 max(self._shape_start[1], self._shape_current[1]) + margin)
        width, height = x1 - x0 + 1, y1 - y0 + 1
        if width <= 0 or height <= 0:
            return
        overlay = QImage(width, height, QImage.Format.Format_ARGB32)
        overlay.fill(0)
        raster = QPainter(overlay)
        try:
            raster.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            pen = QPen(self._color, max(1, self._brush_size))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            raster.setPen(pen)
            raster.translate(-x0, -y0)
            self._paint_shape(raster)
        finally:
            raster.end()
        zoom = self._zoom
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(QRectF(x0 * zoom, y0 * zoom, width * zoom, height * zoom),
                          overlay)
        painter.restore()

    def _paint_shape(self, painter):
        """Stroke the current line / rectangle / ellipse (start -> current).

        Shared by the live preview and the commit, so the drag preview and
        the finished pixels are rasterized by the very same code.
        """
        p1 = QPointF(self._shape_start[0], self._shape_start[1])
        p2 = QPointF(self._shape_current[0], self._shape_current[1])
        if self._tool == TOOL_LINE:
            painter.drawLine(p1, p2)
        elif self._tool == TOOL_RECT:
            painter.drawRect(QRectF(p1, p2).normalized())
        elif self._tool == TOOL_ELLIPSE:
            painter.drawEllipse(QRectF(p1, p2).normalized())

    def _draw_stroke_preview(self, painter):
        """Live overlay of the freehand stroke: the exact pixel blocks that
        releasing the button will paint (brush size 1 = one square)."""
        pts = self._stroke_points
        if not pts:
            return
        z = self._zoom
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for (x, y) in _line_pixels(pts):
            rx, ry, rw, rh = self._brush_rect(x, y)
            painter.fillRect(QRectF(rx * z, ry * z, rw * z, rh * z), self._color)
        painter.restore()

    def _draw_hover_preview(self, painter):
        """Translucent marker showing where the current tool would act.

        Shown for the pencil, eraser, fill and the shape tools (line,
        rectangle, ellipse - the marker is the pen width there). The marker
        is the brush block itself (brush size 1 = exactly one pixel), filled
        with a translucent version of the current color (a neutral white for
        the eraser) and outlined in dark gray so it stays visible on both
        light and dark pixels. The color picker has no marker.
        """
        if (self._hover_point is None or self._drawing
                or self._shape_start is not None
                or self._tool == TOOL_PICKER):
            return
        zoom = self._zoom
        x, y = self._hover_point
        rx, ry, rw, rh = self._brush_rect(x, y)
        rect = QRectF(rx * zoom, ry * zoom, rw * zoom, rh * zoom).toAlignedRect()
        fill = QColor(255, 255, 255, 110) if self._tool == TOOL_ERASER else QColor(self._color)
        if self._tool != TOOL_ERASER:
            fill.setAlpha(96)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(rect, fill)
        painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.restore()

    def _draw_pixel_grid(self, painter, clip):
        """The Aseprite-style pixel grid: one square per image pixel.

        Only drawn from ``PIXEL_GRID_MIN_ZOOM`` on, and only for the visible
        part of the canvas (a zoomed-in image can be thousands of pixels
        wide, so invisible lines are skipped).
        """
        if self._image is None or not self._grid_visible or self._zoom < PIXEL_GRID_MIN_ZOOM:
            return
        zoom = self._zoom
        canvas_w = int(self._image.width() * zoom)
        canvas_h = int(self._image.height() * zoom)
        left = max(0, int(math.floor(clip.left() / zoom)))
        right = min(self._image.width(), int(math.ceil(clip.right() / zoom)))
        top = max(0, int(math.floor(clip.top() / zoom)))
        bottom = min(self._image.height(), int(math.ceil(clip.bottom() / zoom)))
        x0, x1 = max(0, clip.left()), min(canvas_w, clip.right())
        y0, y1 = max(0, clip.top()), min(canvas_h, clip.bottom())
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for x in range(left, right + 1):
            px = int(round(x * zoom))
            if px < x0 - 1 or px > x1 + 1:
                continue
            painter.setPen(_GRID_ACCENT_COLOR if x % _GRID_ACCENT_STEP == 0
                           else _GRID_COLOR)
            painter.drawLine(px, y0, px, y1)
        for y in range(top, bottom + 1):
            py = int(round(y * zoom))
            if py < y0 - 1 or py > y1 + 1:
                continue
            painter.setPen(_GRID_ACCENT_COLOR if y % _GRID_ACCENT_STEP == 0
                           else _GRID_COLOR)
            painter.drawLine(x0, py, x1, py)
        painter.restore()

    def _commit_stroke(self):
        """Paint the collected freehand stroke pixel by pixel (one stamp per
        pixel, so a translucent color is applied once - no stacked alpha)."""
        if self._image is None or not self._stroke_points:
            return
        self.draw_polyline(self._stroke_points)

    # ------------------------------------------------------------ panning
    def is_panning(self):
        """True while a middle-drag moves the view."""
        return self._panning

    def _start_pan(self, event):
        """Middle press: grab the view - dragging scrolls, nothing is drawn."""
        scroll = self._parent_scroll_area()
        if scroll is None:
            return
        self._panning = True
        self._pan_origin = event.globalPosition()
        self._pan_scroll = (scroll.horizontalScrollBar().value(),
                            scroll.verticalScrollBar().value())
        self._hover_point = None
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()
        event.accept()

    def _pan(self, event):
        """Scroll the view so the grabbed spot stays under the cursor.

        Global positions are used on purpose: scrolling moves the widget
        under the cursor, so widget-local coordinates would drift.
        """
        scroll = self._parent_scroll_area()
        if scroll is None or self._pan_origin is None:
            return
        delta = event.globalPosition() - self._pan_origin
        scroll.horizontalScrollBar().setValue(
            int(round(self._pan_scroll[0] - delta.x())))
        scroll.verticalScrollBar().setValue(
            int(round(self._pan_scroll[1] - delta.y())))
        event.accept()

    def _end_pan(self):
        if not self._panning:
            return
        self._panning = False
        self._pan_origin = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, event):
        if self._image is None:
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_pan(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
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
        if self._panning:
            if event.buttons() & Qt.MouseButton.MiddleButton:
                self._pan(event)
                return
            self._end_pan()          # the middle button went up elsewhere
        point = self._to_image(event.position())
        if point is None:
            return

        if point != self._hover_point:
            self._hover_point = point
            if not self._drawing and self._shape_start is None:
                self.update()

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
        if event.button() == Qt.MouseButton.MiddleButton:
            self._end_pan()
            return
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

    def leaveEvent(self, event):
        """The hover marker only exists while the pointer is on the canvas."""
        if self._hover_point is not None:
            self._hover_point = None
            self.update()
        super().leaveEvent(event)

    def handle_wheel(self, event):
        """Apply one wheel notch: zoom the image. True when consumed.

        The WHEEL zooms (Ctrl+wheel zooms too - it used to be the other way
        round); Shift+wheel scrolls the view instead, so a zoomed-in image
        can still be panned. The tileset palette of the tile map editor and
        the block canvas follow the same rule. The window forwards wheel
        events that land on the panel AROUND the image to this method, so
        the whole panel behaves the same wherever the cursor is.
        """
        if self._image is None:
            return False
        delta = event.angleDelta().y()
        if not delta:
            return False
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            scroll = self._parent_scroll_area()
            if scroll is None:
                return False
            bar = scroll.verticalScrollBar()
            if bar is None or bar.maximum() <= 0:
                return False
            step = bar.singleStep() * 3
            bar.setValue(bar.value() - step if delta > 0 else bar.value() + step)
            return True
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.set_zoom(self._zoom * factor)
        return True

    def wheelEvent(self, event):
        if self.handle_wheel(event):
            event.accept()
            return
        super().wheelEvent(event)

    def _parent_scroll_area(self):
        """The QScrollArea this canvas lives in (for Shift+wheel scrolling)."""
        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, QAbstractScrollArea):
                return widget
            widget = widget.parentWidget()
        return None

    # ------------------------------------------------------------ drawing
    def _painter(self):
        painter = QPainter(self._image)
        if self._tool == TOOL_ERASER:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        # No antialiasing anywhere: every tool paints hard pixels (pixel-art
        # editing), so brush size 1 covers exactly one pixel.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(self._color if self._tool != TOOL_ERASER else QColor(0, 0, 0, 0),
                   max(1, self._brush_size))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        return painter

    def _brush_rect(self, x, y):
        """The pixel block one brush stamp covers: size N = N x N pixels
        around (x, y); brush size 1 is exactly the pixel (x, y)."""
        offset = (self._brush_size - 1) // 2
        return (x - offset, y - offset, self._brush_size, self._brush_size)

    def draw_polyline(self, points):
        """Paint a pixel-exact stroke through ``points`` (image pixels).

        Every pixel of the (Bresenham) path is stamped exactly once with the
        brush block, so strokes have hard edges, a translucent color is
        applied once and brush size 1 paints single pixels - the way a
        pixel-art editor draws (Aseprite style). The eraser clears the same
        blocks instead. The caller pushes the undo snapshot.
        """
        if self._image is None or not points:
            return
        painter = self._painter()
        try:
            for (x, y) in _line_pixels(points):
                rx, ry, rw, rh = self._brush_rect(x, y)
                painter.fillRect(rx, ry, rw, rh, self._color)
        finally:
            painter.end()

    def _stamp_point(self, from_point, to_point):
        """Stamp the brush block along one drag segment (eraser live path)."""
        if self._image is None:
            return
        painter = self._painter()
        try:
            for (x, y) in _line_pixels([tuple(from_point), tuple(to_point)]):
                rx, ry, rw, rh = self._brush_rect(x, y)
                painter.fillRect(rx, ry, rw, rh, self._color)
        finally:
            painter.end()

    def _commit_shape(self):
        """Paint the finished line/rect/ellipse into the image."""
        if self._image is None:
            return
        painter = self._painter()
        try:
            self._paint_shape(painter)
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
