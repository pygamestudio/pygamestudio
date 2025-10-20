from PySide6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QVBoxLayout
from PySide6.QtGui import QPen, QColor, QPainter, QMouseEvent
from PySide6.QtCore import Qt, QLine, QEvent
import math

class SceneWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__grid_scene = GridGraphicsScene()
        self.__grid_view = GridGraphicsView(self.__grid_scene, self)

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        self.setWindowTitle("Scene Window")
        self.setGeometry(200, 200, 800, 600)

    def __set_signal(self):
        pass

    def __set_layout(self):
        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self.__grid_view)
        window_layout.setContentsMargins(0, 0, 0, 0)


class GridGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.setScene(scene)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing|QPainter.RenderHint.SmoothPixmapTransform)

        self.__zoom_limit = [0.5, 5]
        self.__zoom_factor = 1.05
        self.__current_scale = 1.0
        self.__previous_scale = 1.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.__is_dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            # release_event = QMouseEvent(QEvent.Type.MouseButtonRelease, event.position(), event.globalPosition(), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, event.modifiers())
            # super().mouseReleaseEvent(release_event)

            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.__is_dragging = True

            press_event = QMouseEvent(QEvent.Type.MouseButtonPress, event.position(), event.globalPosition(), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, event.modifiers())
            super().mousePressEvent(press_event)
        
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            # release_event = QMouseEvent(QEvent.Type.MouseButtonRelease, event.position(), event.globalPosition(), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, event.modifiers())
            # super().mouseReleaseEvent(release_event)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.__is_dragging = False

        return super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self.__is_dragging:
            return super().wheelEvent(event)
        
        if event.angleDelta().y() > 0:
            zoom_factor = self.__zoom_factor            
        else:
            zoom_factor = 1 / self.__zoom_factor

        self.__current_scale *= zoom_factor

        if self.__current_scale < self.__zoom_limit[0] or self.__current_scale > self.__zoom_limit[1]:
            zoom_factor = 1.0
            self.__current_scale = self.__previous_scale

        self.__previous_scale = self.__current_scale
        self.scale(zoom_factor, zoom_factor)


class GridGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__grid_size = 20
        self.__grid_square = 5

        self.__bg_color = QColor('#393939')
        self.__line_color_light = QColor('#2f2f2f')
        self.__line_color_dark = QColor('#292929')
        self.__pen_light = QPen(self.__line_color_light)
        self.__pen_dark = QPen(self.__line_color_dark)
        self.__pen_light.setWidth(1)
        self.__pen_dark.setWidth(2)
        
        self.__scene_width = 64000
        self.__scene_height = 64000
        self.setSceneRect(-self.__scene_width//2, -self.__scene_height//2, self.__scene_width, self.__scene_height)
        self.setBackgroundBrush(self.__bg_color)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)

        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        top = int(math.floor(rect.top()))
        bottom = int(math.ceil(rect.bottom()))

        first_left = left - (left % self.__grid_size)
        first_top = top - (top % self.__grid_size)
        
        lines_light, lines_dark = [], []
        for x in range(first_left, right, self.__grid_size):
            if x % (self.__grid_size * self.__grid_square) == 0:
                lines_dark.append(QLine(x, top, x, bottom))
            else:
                lines_light.append(QLine(x, top, x, bottom))

        for y in range(first_top, bottom, self.__grid_size):
            if y % (self.__grid_size * self.__grid_square) == 0:
                lines_dark.append(QLine(left, y, right, y))
            else:
                lines_light.append(QLine(left, y, right, y))

        painter.setPen(self.__pen_light)
        painter.drawLines(lines_light)
        
        painter.setPen(self.__pen_dark)
        painter.drawLines(lines_dark)



if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = SceneWindow()
    window.show()
    sys.exit(app.exec())