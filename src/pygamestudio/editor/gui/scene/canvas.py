import pygame
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from pygamestudio.editor.gui.scene.buttontest import Button
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.game.object.type import *
from pygamestudio.game.object.rect import ObjectRect


class PygameWidget(QWidget):
    def __init__(self, scene_window=None, object_manager=None):
        super().__init__()
        self._scene = None
        self._scene_window = scene_window
        self._object_manager = object_manager
        
        self._clock = pygame.time.Clock()
        self._update_screen_timer = QTimer(self)
        self._surface = pygame.Surface((self.width(), self.height()))

        self.button = Button(image_path=str(RES_PATH / 'images/button.png'), x=20, y=0)
        self.circle_rect = None
        self._all_objects = []
        self._final_selected_object = None
        self._mouse_x = None
        self._mouse_y = None
        self._is_ctrl_pressed = False

        self._setup()
        self.run()
    
    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_pygame()

    def _set_widget(self):
        self.setWindowTitle("Scene Window")
        self.setFixedSize(800, 600)
        self.installEventFilter(self)

    def _set_signal(self):
        self._object_manager.object_added.connect(self._on_object_added)
        self._object_manager.object_deleted.connect(self._on_object_deleted)
        self._object_manager.object_selected.connect(self._on_object_selected)
        self._object_manager.object_deselected.connect(self._on_object_deselected)
        self._object_manager.object_moved.connect(self._on_object_moved)
        self._object_manager.object_resized.connect(self._on_object_resized)
        self._object_manager.object_showed.connect(self._on_object_showed)
        self._object_manager.object_hidden.connect(self._on_object_hidden)
        self._object_manager.object_color_changed.connect(self._on_object_color_changed)
        # self._update_screen_timer.timeout.connect(self._update_scene)
        ...

    def _set_pygame(self):
        pygame.init()
        self._surface = pygame.Surface((self.width(), self.height()))
        self._clock.tick(60)

    def _on_object_added(self, parent_uuid, object_uuid, inserted_pos):
        self._update_scene()

    def _delete(self):
        # 找出所有选中的is_selected为True的对s象，然后调用object_manager.delete()
        selected_uuids = self._object_manager.get_selected_objects_uuids()
        self._object_manager.delete(selected_uuids)

    def _on_object_deleted(self, object_uuid):
        self._update_scene()

    def _on_object_selected(self, object_uuid):
        self._update_scene()

    def _on_object_deselected(self, object_uuid):
        self._update_scene()

    def _on_object_moved(self, object_uuid):
        self._update_scene()

    def _on_object_resized(self, object_uuid):
        self._update_scene()

    def _on_object_showed(self, object_uuid):
        self._update_scene()

    def _on_object_hidden(self, object_uuid):
        self._update_scene()

    def _on_object_color_changed(self, object_uuid):
        self._update_scene()

    def _update_scene(self):
        # 更新过
        self._surface.fill((0, 0, 0)) 

        def _update(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            
            if obj.is_visible:
                if obj.type == OBJECT_SCENE:
                    if obj.is_selected:
                        pygame.draw.rect(self._surface, (255, 255, 50), (0, 0, self._surface.width, self._surface.height), 2)
                else:
                    obj.draw(self._surface)
                    if obj.is_selected:
                        pygame.draw.rect(self._surface, (255, 255, 50), obj.get_rect(), 2)

                for child_object_tree_struct in value['children']:
                    _update(child_object_tree_struct)
                
            # if obj.type == OBJECT_SCENE:
            #     if obj.is_visible:
            #         if obj.is_selected:
            #             pygame.draw.rect(self._surface, (255, 255, 50), (0, 0, self._surface.width, self._surface.height), 2)
                    
            #         for child_object_tree_struct in value['children']:
            #             _update(child_object_tree_struct)
            # else:
            #     # 这里要判断祖先对象是否可以见
            #     if obj.is_visible:
            #         obj.draw(self._surface)

            #         if obj.is_selected:
            #             pygame.draw.rect(self._surface, (255, 255, 50), obj.get_rect(), 2)

            #         for child_object_tree_struct in value['children']:
            #             _update(child_object_tree_struct)

        _update(self._object_manager.all_object_tree_struct)
        self.update()

    def _convert_pygame_surface_to_qimage(self, surface):
        # surarray.shape returns (width, height, depth). However, QImage expects (height, width, depth).
        # Thats why we need to swap width and height and transform the image here.
        surarray = pygame.surfarray.pixels3d(surface)
        img_width, img_height, img_depth = surarray.shape
        img = QImage(surarray.tobytes(), img_height, img_width, img_height * img_depth, QImage.Format.Format_RGB888)
        img = img.transformed(QTransform().rotate(90))
        img.mirrored_inplace(True, False)
        return img
    
    def run(self):
        self._update_screen_timer.start(16)        # Approximately 60 FPS

    def set_scene(self, scene):
        self._scene = scene

    def _on_mouse_left_button_pressed(self, event):
        self._object_manager.undo_stack.beginMacro('Move')
        pos = event.position()
        self._mouse_x = pos.x()
        self._mouse_y = pos.y()
        self._update_object_selection(pos)

    def _on_mouse_move(self, event):
        self._move_selected_objects(event.position())

    def _on_mouse_left_button_released(self, event):
        self._mouse_x = None
        self._mouse_y = None
        self._object_manager.undo_stack.endMacro()

    def _update_object_selection(self, pos):
        if not self._is_ctrl_pressed:
            self._object_manager.deselect_all()

        self._set_selected_object(pos)
        self._update_scene()

    def _set_selected_object(self, pos):
        # 要在这里加上gizmo！！！！！！！！！！！！！！
        self._final_selected_object = None

        def _set(object_tree_struct, pos):
            value = list(object_tree_struct.values())[0]

            if value['object'].type != OBJECT_SCENE and value['object'].get_rect().collidepoint((pos.x(), pos.y())):
                # value['object'].is_selected = True
                self._final_selected_object = value['object']
                # self._object_manager.select(value['object'].uuid)

                # if not value['children']:
                #     # self._object_manager.select(self._final_selected_object.uuid)
                #     return True
                
            for child_object_tree_struct in reversed(value['children']):
                _set(child_object_tree_struct, pos)
                if self._final_selected_object:
                    return
                # result = _set(child_object_tree_struct, pos)
                # if result:
                #     return True

            # if self._final_selected_object:
            #     self._object_manager.select(self._final_selected_object.uuid)
            #     return True
            # else:
            #     # Clear selection if no object is selected.
            #     self._object_manager.deselect_all()
            #     # self._final_selected_object = None
            #     self._object_manager.select(self._object_manager.scene_object_uuid)
            #     return False

        _set(self._object_manager.all_object_tree_struct, pos)
        if self._final_selected_object:
            self._object_manager.select(self._final_selected_object.uuid)
        else:
            # Clear selection if no object is selected.
            self._object_manager.deselect_all()
            # self._final_selected_object = None
            self._object_manager.select(self._object_manager.scene_object_uuid)

    def _move_selected_objects(self, pos):
        if not self._final_selected_object:
            return
        
        selected_objects = self._object_manager.get_objects_to_move()
        for obj in selected_objects:
            new_x = obj.x+pos.x()-self._mouse_x
            new_y = obj.y+pos.y()-self._mouse_y
            self._object_manager.move(obj.uuid, (new_x, new_y))
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
            # uuid_list = []
            # for obj in self._all_objects:
            #     if obj.is_selected:
            #         uuid_list.append(obj.uuid)

            # for uuid in uuid_list:
            #     self.delete_by_uuid(uuid)
            #     self._scene_window.scene_to_hierarchy_delete_signal.emit(uuid)

        return super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._is_ctrl_pressed = False

        return super().keyReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        img = self._convert_pygame_surface_to_qimage(self._surface)
        painter.drawPixmap(0, 0, QPixmap.fromImage(img))

    def resizeEvent(self, event):
        new_window_size = event.size()
        self._surface = pygame.Surface((new_window_size.width(), new_window_size.height()))
        return super().resizeEvent(event)