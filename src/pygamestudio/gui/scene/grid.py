import math
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.scene.widget import *
from pygamestudio.common.utils.config import get_editor_config


class GridGraphicsView(QGraphicsView):
    rubber_band_changed = Signal(QRectF)

    def __init__(self, game_manager, scene, pygame_screen):
        super().__init__()
        self._game_manager = game_manager
        self._scene = scene
        self._pygame_screen = pygame_screen
        self._zoom_limit = [0.2, 5]
        self._zoom_factor = 1.05
        self._current_scale = 1.0
        self._previous_scale = 1.0
        self._is_dragging = False
        self._is_first_show = True
        self._run_project_btn = RunProjectButton()
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._rb_origin = QPoint()
        self._setup()
    
    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.scale(0.6, 0.6)
        self.setScene(self._scene)
        self._center()

        self.setDragMode(QGraphicsView.NoDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing|QPainter.RenderHint.SmoothPixmapTransform)

    def _set_signal(self):
        self._run_project_btn.clicked.connect(self._game_manager.run_project)

    def _set_layout(self):
        v_layout = QVBoxLayout(self)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self._run_project_btn)
        h_layout.addStretch(1)
        v_layout.addLayout(h_layout)
        v_layout.addStretch(1)

    def _center(self):
        screen_width = self._pygame_screen.width()
        screen_height = self._pygame_screen.height()
        self.centerOn(QPointF(screen_width/2, screen_height/2))

    def resizeEvent(self, event):
        # Make sure the scene is at center when the editor shows up.
        if self._is_first_show:
            self._center()
        return super().resizeEvent(event)

    def get_ready_for_project(self):
        self._center()

    def clean_up(self):
        self._zoom_limit = [0.2, 5]
        self._zoom_factor = 1.05
        self._current_scale = 1.0
        self._previous_scale = 1.0
        self._is_dragging = False
        self._is_first_show = True

    def is_dragging(self):
        return self._is_dragging
    
    def _on_mouse_left_button_pressed(self, event):
        # Deselect all objects if users click outside the Canvas.
        proxy_screen_widget = self.scene().items()[0]
        if not proxy_screen_widget.boundingRect().contains(self.mapToScene(event.pos())):
            self._game_manager.deselect_all()

        self._rb_origin = event.pos()
        self._rubber_band.setGeometry(QRect(self._rb_origin, QSize()))
        self._rubber_band.show()

    def _on_mouse_left_button_moved(self, event):
        # Do not show the rubber band when the gizmo is working.
        proxy_screen_widget = self.scene().items()[0]
        scene_widget = proxy_screen_widget.widget()
        if scene_widget.is_dragging_by_move_gizmo():
            return
        
        rb_view_rect = QRect(self._rb_origin, event.pos()).normalized()
        self._rubber_band.setGeometry(rb_view_rect)
        rb_scene_rect = self.mapToScene(rb_view_rect).boundingRect()
        self.rubber_band_changed.emit(rb_scene_rect)
        self.viewport().update()

    def _on_mouse_left_button_released(self, event):
        self._rubber_band.hide()
        self._rb_origin = QPoint()
        self.viewport().update()

    def _on_mouse_mid_button_pressed(self, event):
        self._is_dragging = True
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        press_event = QMouseEvent(QEvent.Type.MouseButtonPress, event.position(), event.globalPosition(), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, event.modifiers())
        super().mousePressEvent(press_event)

    def _on_mouse_mid_button_released(self, event):
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._is_dragging = False

    def _zoom(self, event):
        if event.angleDelta().y() > 0:
            zoom_factor = self._zoom_factor            
        else:
            zoom_factor = 1 / self._zoom_factor

        self._current_scale *= zoom_factor

        if self._current_scale < self._zoom_limit[0] or self._current_scale > self._zoom_limit[1]:
            self._current_scale = self._previous_scale
            zoom_factor = 1.0

        self._previous_scale = self._current_scale
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_mouse_left_button_pressed(event)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._on_mouse_mid_button_pressed(event)
        return super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and not self._rb_origin.isNull():
            self._on_mouse_left_button_moved(event)
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_mouse_left_button_released(event)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._on_mouse_mid_button_released(event)
        return super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self._is_dragging:
            return
        
        self._zoom(event)

    def paintEvent(self, event):
        self._is_first_show = False
        return super().paintEvent(event)


class GridGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_color = QColor()
        self._line_color_bold = QColor()
        self._line_color_thin = QColor()
        self._pen_bold = QPen()
        self._pen_thin = QPen()
        self._grid_square_size = 20
        self._grid_square_num = 5
        self._scene_width = 64000
        self._scene_height = 64000

        self.setSceneRect(-self._scene_width//2, -self._scene_height//2, self._scene_width, self._scene_height)
        self._update_grid_style()

    def _get_lines(self, rect):
        top = int(math.floor(rect.top()))
        left = int(math.floor(rect.left()))
        right = int(math.ceil(rect.right()))
        bottom = int(math.ceil(rect.bottom()))

        first_top = top - (top % self._grid_square_size)
        first_left = left - (left % self._grid_square_size)
        
        lines_thin, lines_bold = [], []
        for x in range(first_left, right, self._grid_square_size):
            if x % (self._grid_square_size * self._grid_square_num) == 0:
                lines_bold.append(QLine(x, top, x, bottom))
            else:
                lines_thin.append(QLine(x, top, x, bottom))

        for y in range(first_top, bottom, self._grid_square_size):
            if y % (self._grid_square_size * self._grid_square_num) == 0:
                lines_bold.append(QLine(left, y, right, y))
            else:
                lines_thin.append(QLine(left, y, right, y))

        return lines_thin, lines_bold
    
    def _update_grid_style(self, theme_code=''):
        if not theme_code:
            theme_code = get_editor_config().get('theme')

        if theme_code == 'light':
            self._bg_color = QColor('#f2f2f2')
            self._line_color_bold = QColor('#d0d0d0')
            self._line_color_thin = QColor('#e0e0e0')
        else:
            self._bg_color = QColor('#393939')
            self._line_color_bold = QColor('#292929')
            self._line_color_thin = QColor('#2f2f2f')
        
        self._pen_bold = QPen(self._line_color_bold)
        self._pen_thin = QPen(self._line_color_thin)
        self._pen_bold.setWidth(2)
        self._pen_thin.setWidth(1)

        self.setBackgroundBrush(self._bg_color)
        self.update()

    def update_grid_style(self, theme_code):
        return self._update_grid_style(theme_code)
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        lines_thin, lines_bold = self._get_lines(rect)
        painter.setPen(self._pen_thin)
        painter.drawLines(lines_thin)
        painter.setPen(self._pen_bold)
        painter.drawLines(lines_bold)