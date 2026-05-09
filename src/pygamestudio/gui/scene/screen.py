import pygame
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.gui.scene.gizmo import MoveGizmo
from pygamestudio.common.utils.config import get_project_config


class PygameScreen(QWidget):
    def __init__(self, game_manager=None, scene=None):
        super().__init__()
        self._game_manager = game_manager
        self._scene = scene
        self._screen_width = 800
        self._screen_height = 600
        self._move_gizmo = MoveGizmo(self, game_manager)
        self._screen_surface = pygame.Surface((self._screen_width, self._screen_height))

        self._mouse_x = None
        self._mouse_y = None
        self._is_ctrl_pressed = False
        self._final_selected_object = None

        self._setup()
    
    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._screen_width, self._screen_height)
        self.installEventFilter(self)

    def _set_signal(self):
        self._game_manager.object_added.connect(self._update_scene)
        self._game_manager.object_deleted.connect(self._on_object_deleted)
        self._game_manager.object_selected.connect(self._on_object_selected)
        self._game_manager.object_deselected.connect(self._on_object_deselected)
        self._game_manager.object_moved.connect(self._update_scene)
        self._game_manager.object_scaled.connect(self._update_scene)
        self._game_manager.object_rotated.connect(self._update_scene)
        self._game_manager.object_resized.connect(self._on_object_resized)
        self._game_manager.object_showed.connect(self._update_scene)
        self._game_manager.object_hidden.connect(self._update_scene)
        self._game_manager.object_color_changed.connect(self._update_scene)
        self._game_manager.object_rect_border_radius_changed.connect(self._update_scene)
        self._game_manager.object_line_start_point_changed.connect(self._update_scene)
        self._game_manager.object_line_end_point_changed.connect(self._update_scene)
        self._game_manager.object_line_thickness_changed.connect(self._update_scene)
        self._game_manager.object_text_changed.connect(self._update_scene)
        self._game_manager.object_font_size_changed.connect(self._update_scene)
        self._game_manager.object_font_family_changed.connect(self._update_scene)
        self._game_manager.object_bold_state_changed.connect(self._update_scene)
        self._game_manager.object_italic_state_changed.connect(self._update_scene)
        self._game_manager.object_underline_state_changed.connect(self._update_scene)
        self._game_manager.object_strikethrough_state_changed.connect(self._update_scene)

    def _set_pygame_screen(self):
        self._screen_surface = pygame.Surface((self._screen_width, self._screen_height))

    def get_ready_for_project(self):
        self._screen_width = get_project_config()['screen_width']
        self._screen_height = get_project_config()['screen_height']
        self.setFixedSize(self._screen_width, self._screen_height)
        self._set_pygame_screen()
        self._update_scene()

    def clean_up(self):
        self._final_selected_object = None
        self._mouse_x = None
        self._mouse_y = None
        self._is_ctrl_pressed = False
        self._screen_width = 800
        self._screen_height = 600

    def _delete(self):
        # Delete all selected objects.
        selected_uuids = self._game_manager.get_selected_objects_uuids()
        self._game_manager.delete(selected_uuids)
    
    def _on_object_deleted(self, object_uuid):
        if object_uuid == self._move_gizmo.get_object().uuid:
            self._move_gizmo.hide()
        
        self._update_scene()

    def _on_object_selected(self, object_uuid):
        if object_uuid == self._game_manager.canvas_object_uuid:
            self._move_gizmo.hide()
        else:
            obj = self._game_manager.get_object(object_uuid)
            self._final_selected_object = obj
            self._move_gizmo.set_object(obj)

        self._update_scene()

    def _on_object_deselected(self, object_uuid):
        if object_uuid == self._move_gizmo.get_object().uuid:
            self._move_gizmo.hide()
        self._update_scene()

    def _on_object_resized(self, object_uuid):
        if object_uuid == self._game_manager.canvas_object_uuid:
            obj = self._game_manager.get_object(object_uuid)
            self.setFixedSize(obj.width, obj.height)
            self._screen_surface = pygame.Surface((obj.width, obj.height))

        self._update_scene()
    
    def _update_scene(self):
        if self._game_manager.is_empty():
            self._screen_surface.fill((0, 0, 0))
            self.update()
            return
        
        def _update(object_tree_struct, parent_surface):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            obj.update_surface()
            
            if obj.is_visible:
                for child_object_tree_struct in value['children']:
                    _update(child_object_tree_struct, obj.get_surface())

                obj.draw(parent_surface)

        _update(self._game_manager.all_object_tree_struct, self._screen_surface)
        self.update()

    def _convert_screen_surface_to_qimage(self, surface):
        # surarray.shape returns (width, height, depth). However, QImage expects (height, width, depth).
        # Thats why we need to swap width and height and transform the image here.
        surarray = pygame.surfarray.pixels3d(surface)
        img_width, img_height, img_depth = surarray.shape
        img = QImage(surarray.tobytes(), img_height, img_width, img_height * img_depth, QImage.Format.Format_RGB888)
        img = img.transformed(QTransform().rotate(90))
        img.mirrored_inplace(True, False)
        return img

    def _on_mouse_left_button_pressed(self, event):
        self._game_manager.undo_stack.beginMacro('Move')
        pos = event.position()
        self._mouse_x = pos.x()
        self._mouse_y = pos.y()
        self._update_object_selection(pos)

    def _on_mouse_move(self, event):
        self._move_selected_objects(event.position())

    def _on_mouse_left_button_released(self, event):
        self._mouse_x = None
        self._mouse_y = None
        self._game_manager.undo_stack.endMacro()

    def _update_object_selection(self, pos):
        if self._game_manager.is_empty():
            return
        
        if not self._is_ctrl_pressed:
            self._game_manager.deselect_all()

        self._set_selected_object(pos)
        self._update_scene()

    def _set_selected_object(self, pos):
        self._final_selected_object = None

        def _set(object_tree_struct, pos):
            value = list(object_tree_struct.values())[0]

            for child_object_tree_struct in reversed(value['children']):
                _set(child_object_tree_struct, pos)
                if self._final_selected_object:
                    return
                
            if value['object'].type != OBJECT_CANVAS and value['object'].check_click_collision((pos.x(), pos.y())):
                self._final_selected_object = value['object']

        _set(self._game_manager.all_object_tree_struct, pos)
        if self._final_selected_object:
            self._game_manager.select(self._final_selected_object.uuid)
        else:
            # Clear selection if no object is selected.
            self._move_gizmo.hide()
            self._game_manager.select(self._game_manager.canvas_object_uuid)

    def _move_selected_objects(self, pos):
        if not self._final_selected_object:
            return
        
        self._game_manager.undo_stack.beginMacro('Move')
        selected_objects = self._game_manager.get_objects_to_move()
        for obj in selected_objects:
            new_x = obj.x+pos.x()-self._mouse_x
            new_y = obj.y+pos.y()-self._mouse_y
            self._game_manager.move(obj.uuid, (new_x, new_y))
        
        self._game_manager.undo_stack.endMacro()
        self._mouse_x = pos.x()
        self._mouse_y = pos.y()

    def eventFilter(self, obj, event):
        """Move game objects when QGraphicsView is not being dragged"""

        """
        The approach of using event.button() to detect a middle mouse button press should work in theory. 
        However, I'm observing an unexpected behavior in my eventFilter: when the middle button is pressed, 
        the event filter first receives a value of MouseButton.LeftButton, and then subsequently receives MouseButton.MiddleButton. 
        This sequence is puzzling. It should only receive MouseButton.MiddleButton. By the way, my QGraphicsView can be dragged when a middle button is pressed.
        
        PySide6 version is 6.10.0.
        """

        # if QGraphicsView is being dragged, PygameWidget won't receive mouse event.
        if obj == self and self._scene and not self._scene.views()[0].is_dragging():
            if event.type() == event.Type.MouseButtonPress:
                self._on_mouse_left_button_pressed(event)
                return True
            elif event.type() == event.Type.MouseMove:
                self._on_mouse_move(event)
                return True
            elif event.type() == event.Type.MouseButtonRelease:
                self._on_mouse_left_button_released(event)
                return True
        return super().eventFilter(obj, event)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._is_ctrl_pressed = True

        elif event.key() == Qt.Key.Key_Delete:
            self._delete()

        return super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._is_ctrl_pressed = False

        return super().keyReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)

        if self._game_manager.is_current_canvas_visible():
            img = self._convert_screen_surface_to_qimage(self._screen_surface)
            painter.drawPixmap(0, 0, QPixmap.fromImage(img))
        else:
            painter.save()
            pen = QPen(Qt.GlobalColor.white)
            pen.setWidth(5)
            painter.setPen(pen)
            painter.drawRect(0, 0, self._screen_surface.get_width(), self._screen_surface.get_height())
            painter.restore()

    def resizeEvent(self, event):
        new_window_size = event.size()
        self._screen_surface = pygame.Surface((new_window_size.width(), new_window_size.height()))
        return super().resizeEvent(event)