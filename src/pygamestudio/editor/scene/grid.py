from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPen, QColor, QPainter, QMouseEvent
from PySide6.QtCore import Qt, QLine, QEvent
import math


class GridGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.__zoom_limit = [0.2, 5]
        self.__zoom_factor = 1.05
        self.__current_scale = 1.0
        self.__previous_scale = 1.0
        self.__is_dragging = False

        self.setScene(scene)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing|QPainter.RenderHint.SmoothPixmapTransform)

    def is_dragging(self):
        return self.__is_dragging

    def __on_mouse_mid_button_pressed(self, event):
        self.__is_dragging = True
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        press_event = QMouseEvent(QEvent.Type.MouseButtonPress, event.position(), event.globalPosition(), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, event.modifiers())
        super().mousePressEvent(press_event)

    def __on_mouse_mid_button_released(self, event):
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.__is_dragging = False

    def __zoom(self, event):
        if event.angleDelta().y() > 0:
            zoom_factor = self.__zoom_factor            
        else:
            zoom_factor = 1 / self.__zoom_factor

        self.__current_scale *= zoom_factor

        if self.__current_scale < self.__zoom_limit[0] or self.__current_scale > self.__zoom_limit[1]:
            self.__current_scale = self.__previous_scale
            zoom_factor = 1.0

        self.__previous_scale = self.__current_scale
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.__on_mouse_mid_button_pressed(event)
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.__on_mouse_mid_button_released(event)
        return super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self.__is_dragging:
            return
        
        self.__zoom(event)


class GridGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__bg_color = QColor('#393939')
        self.__line_color_dark = QColor('#292929')
        self.__line_color_light = QColor('#2f2f2f')
        self.__pen_dark = QPen(self.__line_color_dark)
        self.__pen_light = QPen(self.__line_color_light)
        self.__pen_dark.setWidth(2)
        self.__pen_light.setWidth(1)

        self.__grid_square_size = 20
        self.__grid_square_num = 5

        self.__scene_width = 64000
        self.__scene_height = 64000

        self.setBackgroundBrush(self.__bg_color)
        self.setSceneRect(-self.__scene_width//2, -self.__scene_height//2, self.__scene_width, self.__scene_height)

    def __get_lines(self, rect):
        top = int(math.floor(rect.top()))
        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        bottom = int(math.ceil(rect.bottom()))

        first_top = top - (top % self.__grid_square_size)
        first_left = left - (left % self.__grid_square_size)
        
        lines_light, lines_dark = [], []
        for x in range(first_left, right, self.__grid_square_size):
            if x % (self.__grid_square_size * self.__grid_square_num) == 0:
                lines_dark.append(QLine(x, top, x, bottom))
            else:
                lines_light.append(QLine(x, top, x, bottom))

        for y in range(first_top, bottom, self.__grid_square_size):
            if y % (self.__grid_square_size * self.__grid_square_num) == 0:
                lines_dark.append(QLine(left, y, right, y))
            else:
                lines_light.append(QLine(left, y, right, y))

        return lines_light, lines_dark

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        lines_light, lines_dark = self.__get_lines(rect)
        painter.setPen(self.__pen_light)
        painter.drawLines(lines_light)
        painter.setPen(self.__pen_dark)
        painter.drawLines(lines_dark)