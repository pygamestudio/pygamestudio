from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class MoveGizmo(QWidget):
    """On-canvas move gizmo (the two-axis arrow shown on the selected object).

    The widget floats above the scene view at the selected object's position.
    Dragging its X axis, Y axis or the center plane moves the selected objects
    along that direction. The whole drag is wrapped in ONE undo macro so that
    Ctrl+Z undoes the entire drag instead of every tiny mouse step.
    """

    # Hit-test result: which part of the gizmo is under the cursor.
    HIT_NONE = 0
    HIT_AXIS_X = 1
    HIT_AXIS_Y = 2
    HIT_PLANE = 3

    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self._screen = parent          # PygameScreen: snapping + guide overlay
        self._game_manager = game_manager
        self._current_object = None
        self._axis_length = 100
        self._plane_size = 25
        self._arrow_size = 10

        self._is_hover = False
        self._is_dragging = False
        self._hit_type = self.HIT_NONE
        self._mouse_start_x = 0
        self._mouse_start_y = 0
        self._is_macro_open = False  # True while an undo macro is open for the current drag.

        self._offset_x = 20
        self._offset_y = 20

        self._set_up()

    @property
    def is_dragging(self):
        return self._is_dragging

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

    def remove_object(self):
        self._current_object = None

    def get_object(self):
        return self._current_object

    def _update_pos(self):
        """Keep the gizmo glued to the selected object's top-left corner
        (skipped while dragging so it doesn't fight the user's cursor)."""
        if self._is_dragging or not self._current_object:
            return
        
        object_hightlight_line_width = 2
        self.move(round(self._current_object._get_world_rect().x)-self._offset_x-object_hightlight_line_width, round(self._current_object._get_world_rect().y)-self._offset_y-object_hightlight_line_width)
        self.update()

    def update_pos(self):
        return self._update_pos()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)

        # axis X
        if self._hit_type == self.HIT_AXIS_X:
            color = QColor(255, 255, 255)
        else:
            color = QColor(255, 60, 60)
        pen_x = QPen(color, 4)
        pen_x.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen_x)
        painter.setBrush(color)
        painter.drawLine(self._offset_x, self._offset_y, self._offset_x + self._axis_length - self._offset_x//2, self._offset_y)
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
        pen_y = QPen(color, 4)
        pen_y.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen_y)
        painter.setBrush(color)
        painter.drawLine(self._offset_x, self._offset_y+1, self._offset_x, self._offset_y + self._axis_length - self._offset_x//2)
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
        """Decide which part of the gizmo (plane / X axis / Y axis / none) is
        under the cursor, using a small hit radius around each handle."""
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
        """Move every selected object (respecting parent-selection pruning) by
        the given pixel delta through the manager's undoable move()."""
        selected_objects = self._game_manager.get_objects_to_move()
        for obj in selected_objects:
            new_x = obj.x + dx
            new_y = obj.y + dy
            self._game_manager.move(obj.uuid, (new_x, new_y))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._hit_type = self._get_hit_type(event.position())
            if self._hit_type != self.HIT_NONE:
                # Safety: close any macro left open by an interrupted previous
                # drag, so a new drag always starts from a clean undo state.
                if self._is_macro_open:
                    self._game_manager.undo_stack.endMacro()

                # Record the press position; the drag delta is measured from it.
                self._is_dragging = True
                self._is_macro_open = False
                self._mouse_start_x = event.position().x()
                self._mouse_start_y = event.position().y()
                if self._screen is not None:
                    self._screen.clear_alignment_guides()
                return

        return super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if not self._is_dragging:
            # Hover: only update the highlighted handle and repaint.
            self._hit_type = self._get_hit_type(event.position())
            self.update()
            return super().mouseMoveEvent(event)
        
        # Drag: delta is measured from the press position (cumulative), which
        # keeps the movement stable regardless of mouse-event jitter.
        dx = int(event.position().x() - self._mouse_start_x)
        dy = int(event.position().y() - self._mouse_start_y)

        # A single-axis handle only ever moves along its own axis.
        if self._hit_type == self.HIT_AXIS_X:
            dy = 0
        elif self._hit_type == self.HIT_AXIS_Y:
            dx = 0

        if dx == 0 and dy == 0:
            return

        # The screen snaps the step (only along the active axis) and records
        # any Photoshop-style alignment guides that match the target position.
        if self._hit_type == self.HIT_AXIS_X:
            allow_x, allow_y = True, False
        elif self._hit_type == self.HIT_AXIS_Y:
            allow_x, allow_y = False, True
        else:
            allow_x, allow_y = True, True
        if self._screen is not None:
            dx, dy = self._screen.resolve_move_delta(dx, dy, allow_x, allow_y)

        if dx == 0 and dy == 0:
            return

        # Open the undo macro lazily on the first real move, so a simple click
        # without movement doesn't pollute the undo history with an empty macro.
        if not self._is_macro_open:
            self._is_macro_open = True
            self._game_manager.undo_stack.beginMacro('Move')

        # Keep the gizmo glued to the object: move it by the same (possibly
        # snapped) amount as the objects, along the dragged axis only.
        if allow_x:
            self.move(self.x()+dx, self.y())
        if allow_y:
            self.move(self.x(), self.y()+dy)

        if dx != 0 or dy != 0:
            self._move_selected_objects(dx, dy)

        self.update()

    def mouseReleaseEvent(self, event):
        # End of the drag: reset the drag state and close the undo macro so
        # the whole drag becomes a single undoable step.
        self._is_dragging = False
        self._mouse_start_x = 0
        self._mouse_start_y = 0
        self._hit_type = self.HIT_NONE
        if self._is_macro_open:
            self._is_macro_open = False
            self._game_manager.undo_stack.endMacro()
        if self._screen is not None:
            self._screen.clear_alignment_guides()


