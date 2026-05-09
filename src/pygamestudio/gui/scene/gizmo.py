from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class MoveGizmo(QWidget):
    HIT_NONE = 0
    HIT_AXIS_X = 1
    HIT_AXIS_Y = 2
    HIT_PLANE = 3

    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self._game_manager = game_manager
        self._current_object = None
        self._axis_length = 100
        self._plane_size = 20
        self._arrow_size = 10

        self._is_dragging = False
        self._is_hover = False
        self._hit_type = self.HIT_NONE
        self._mouse_start_x = 0
        self._mouse_start_y = 0

        self._offset_x = 20
        self._offset_y = 20

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.resize(self._axis_length+self._arrow_size+self._offset_x, self._axis_length+self._arrow_size+self._offset_y)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.hide()

    def _set_signal(self):
        self._game_manager.object_moved.connect(self._update_pos)

    def set_object(self, obj):
        self._current_object = obj
        self._update_pos()
        self.show()

    def get_object(self):
        return self._current_object

    def _update_pos(self):
        if self._is_dragging:
            return
        
        self.move(round(self._current_object.get_world_rect().x)-self._offset_x, round(self._current_object.get_world_rect().y)-self._offset_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        # axis X
        if self._hit_type == self.HIT_AXIS_X:
            color = QColor(255, 255, 255)
        else:
            color = QColor(255, 60, 60)
        pen_x = QPen(color, 2)
        painter.setPen(pen_x)
        painter.setBrush(color)
        painter.drawLine(self._offset_x, self._offset_y, self._offset_x + self._axis_length, self._offset_y)
        painter.drawPolygon([
            QPoint(self._offset_x + self._axis_length, self._offset_y),
            QPoint(self._offset_x + self._axis_length - self._arrow_size, self._offset_y - self._arrow_size//2),
            QPoint(self._offset_x + self._axis_length - self._arrow_size, self._offset_y + self._arrow_size//2),
        ])
        
        # axis Y
        if self._hit_type == self.HIT_AXIS_Y:
            color = QColor(255, 255, 255)
        else:
            color = QColor(60, 255, 60)
        pen_y = QPen(color, 2)
        painter.setPen(pen_y)
        painter.setBrush(color)
        painter.drawLine(self._offset_x, self._offset_y+1, self._offset_x, self._offset_y + self._axis_length)
        painter.drawPolygon([
            QPoint(self._offset_x, self._offset_y + self._axis_length),
            QPoint(self._offset_x - self._arrow_size//2, self._offset_y + self._axis_length - self._arrow_size),
            QPoint(self._offset_x + self._arrow_size//2, self._offset_y + self._axis_length - self._arrow_size)
        ])

        # plane
        if self._hit_type == self.HIT_PLANE:
            color = QColor(255, 255, 255, 150)
        else:
            color = QColor(200, 200, 200, 150)
        pen_plane = QPen(color, 1)
        painter.setPen(pen_plane)
        painter.setBrush(color)
        half = self._plane_size // 2
        painter.drawRect(QRect(self._offset_x-half, self._offset_y-half, self._plane_size, self._plane_size))

    def _get_hit_type(self, pos):
        px, py = pos.x(), pos.y()
        hit_radius = 5

        # Check the plane
        half = self._plane_size // 2
        if abs(px - self._offset_x) < half + hit_radius and abs(py - self._offset_y) < half + hit_radius:
            return self.HIT_PLANE

        # Check the axis X
        if (abs(py - self._offset_y) < hit_radius) and (self._offset_x < px < self._offset_x + self._axis_length):
            return self.HIT_AXIS_X

        # Check the axis Y
        if (abs(px - self._offset_x) < hit_radius) and (self._offset_y < py < self._offset_y + self._axis_length):
            return self.HIT_AXIS_Y

        return self.HIT_NONE
    
    def _move_selected_objects(self, dx, dy):
        self._game_manager.undo_stack.beginMacro('Move')
        selected_objects = self._game_manager.get_objects_to_move()
        for obj in selected_objects:
            new_x = obj.x + dx
            new_y = obj.y + dy
            self._game_manager.move(obj.uuid, (new_x, new_y))
        self._game_manager.undo_stack.endMacro()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._hit_type = self._get_hit_type(event.position())
            if self._hit_type != self.HIT_NONE:
                self._is_dragging = True
                self._mouse_start_x = event.position().x()
                self._mouse_start_y = event.position().y()
                return

        return super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if not self._is_dragging:
            self._hit_type = self._get_hit_type(event.position())
            self.update()
            return super().mouseMoveEvent(event)
        
        dx = int(event.position().x() - self._mouse_start_x)
        dy = int(event.position().y() - self._mouse_start_y)

        if self._hit_type == self.HIT_AXIS_X:
            self.move(self.x()+dx, self.y())
            self._move_selected_objects(dx, 0)
    
        elif self._hit_type == self.HIT_AXIS_Y:
            self.move(self.x(), self.y()+dy)
            self._move_selected_objects(0, dy)

        elif self._hit_type == self.HIT_PLANE:
            self.move(self.x()+dx, self.y()+dy)
            self._move_selected_objects(dx, dy)
            
        self.update()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self._mouse_start_x = 0
        self._mouse_start_y = 0
        self._hit_type = self.HIT_NONE

