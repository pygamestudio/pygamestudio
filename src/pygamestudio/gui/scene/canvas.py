import pygame
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from pygamestudio.game.object.type import *


class PygameWidget(QWidget):
    def __init__(self, game_manager=None, scene=None):
        super().__init__()
        self._game_manager = game_manager
        self._scene = scene
        
        self._clock = pygame.time.Clock()
        self._canvas_surface = pygame.Surface((self.width(), self.height()))

        self._final_selected_object = None
        self._mouse_x = None
        self._mouse_y = None
        self._is_ctrl_pressed = False

        self._setup()
    
    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_pygame()

    def _set_widget(self):
        self.setWindowTitle("Scene Window")
        self.setFixedSize(800, 600)   # 这个大小要在项目打开时根据项目配置来，在项目开发时也需要可以被修改
        self.installEventFilter(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _set_signal(self):
        self._game_manager.object_added.connect(self._on_object_added)
        self._game_manager.object_deleted.connect(self._update_scene)
        self._game_manager.object_selected.connect(self._update_scene)
        self._game_manager.object_deselected.connect(self._update_scene)
        self._game_manager.object_moved.connect(self._update_scene)
        self._game_manager.object_scaled.connect(self._update_scene)
        self._game_manager.object_rotated.connect(self._update_scene)
        self._game_manager.object_resized.connect(self._update_scene)
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

    def _set_pygame(self):
        pygame.init()
        self._canvas_surface = pygame.Surface((self.width(), self.height()))
        self._clock.tick(60)
    
    def _reset(self):
        self._final_selected_object = None
        self._mouse_x = None
        self._mouse_y = None
        self._is_ctrl_pressed = False
        self._update_scene()

    def get_ready_for_project(self):
        ...
        
    def clean_up(self):
        self._reset()
        
    def _on_object_added(self, parent_uuid, object_uuid, inserted_pos):
        if object_uuid == self._game_manager.scene_object_uuid:
            obj = self._game_manager.get_object(object_uuid)
            setattr(obj, 'size', self._canvas_surface.get_size())
            obj.set_surface(self._canvas_surface)
            obj.update_surface()

        self._update_scene()

    def _delete(self):
        # 找出所有选中的is_selected为True的对s象，然后调用game_manager.delete()
        selected_uuids = self._game_manager.get_selected_objects_uuids()
        self._game_manager.delete(selected_uuids)
        
    def _update_scene(self):
        if self._game_manager.is_empty():
            self._canvas_surface.fill((0, 0, 0))
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

        _update(self._game_manager.all_object_tree_struct, self._canvas_surface)
        self.update()

    def _convert_canvas_surface_to_qimage(self, surface):
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
        # 要在这里加上gizmo！！！！！！！！！！！！！！
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
            self._game_manager.deselect_all()
            # self._final_selected_object = None
            self._game_manager.select(self._game_manager.scene_object_uuid)

    def _move_selected_objects(self, pos):
        if not self._final_selected_object:
            return
        
        selected_objects = self._game_manager.get_objects_to_move()
        for obj in selected_objects:
            new_x = obj.x+pos.x()-self._mouse_x
            new_y = obj.y+pos.y()-self._mouse_y
            self._game_manager.move(obj.uuid, (new_x, new_y))
            # obj.x += pos.x() - self._mouse_x
            # obj.y += pos.y() - self._mouse_y
        
        # self._final_selected_object.x += pos.x()-self._mouse_x
        # self._final_selected_object.y += pos.y()-self._mouse_y
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

        if self._game_manager.is_current_scene_visible():
            img = self._convert_canvas_surface_to_qimage(self._canvas_surface)
            painter.drawPixmap(0, 0, QPixmap.fromImage(img))
        else:
            painter.save()
            pen = QPen(Qt.GlobalColor.white)
            pen.setWidth(5)
            painter.setPen(pen)
            painter.drawRect(0, 0, self._canvas_surface.get_width(), self._canvas_surface.get_height())
            painter.restore()

    def resizeEvent(self, event):
        new_window_size = event.size()
        self._canvas_surface = pygame.Surface((new_window_size.width(), new_window_size.height()))
        return super().resizeEvent(event)