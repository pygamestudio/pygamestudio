import pygame
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QPixmap, QTransform
from PySide6.QtCore import QTimer

from buttontest import Button


class PygameWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__scene = None
        self.__update_screen_timer = QTimer(self)
        self.__clock = pygame.time.Clock()
        self.__surface = pygame.Surface((self.width(), self.height()))

        self.button = Button(image_path='./button.png', x=20, y=0)
        self.circle_rect = None
        self.object_list = [self.button]

        self.__selected_object= None
        self.__mouse_x = None
        self.__mouse_y = None

        self.__setup()
        self.run()
    
    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_pygame()

    def __set_widget(self):
        self.setWindowTitle("Scene Window")
        self.setFixedSize(800, 600)
        self.installEventFilter(self)

    def __set_signal(self):
        self.__update_screen_timer.timeout.connect(self.__update_scene)

    def __set_pygame(self):
        pygame.init()
        self.__surface = pygame.Surface((self.width(), self.height()))
        self.__clock.tick(60)

    def __update_scene(self):
        self.__surface.fill((0, 0, 0))                                                          # Clear screen with black
        self.circle_rect = pygame.draw.circle(self.__surface, (255, 0, 0), (0, 500), 50)        # Draw a red circle
        self.button.draw(self.__surface)                                                        # Draw button on surface
        
        self.update()                                                       # Trigger repaint

    def __convert_pygame_surface_to_qimage(self, surface):
        # surarray.shape returns (width, height, depth). However, QImage expects (height, width, depth).
        # Thats why we need to swap width and height and transform the image here.
        surarray = pygame.surfarray.pixels3d(surface)
        img_width, img_height, img_depth = surarray.shape
        img = QImage(surarray.tobytes(), img_height, img_width, img_height * img_depth, QImage.Format.Format_RGB888)
        img = img.transformed(QTransform().rotate(90))
        img.mirrored_inplace(True, False)
        return img
    
    def run(self):
        self.__update_screen_timer.start(16)        # Approximately 60 FPS

    def set_scene(self, scene):
        self.__scene = scene

    def __check_object_selection(self, pos):
        for obj in self.object_list:
            if obj and hasattr(obj, 'rect') and obj.rect.collidepoint((pos.x(), pos.y())):
                self.__selected_object = obj
                return
        self.__selected_object = None

    def __move_selected_object(self, pos):
        if not self.__selected_object:
            return
        
        self.__selected_object.rect.x += pos.x()-self.__mouse_x
        self.__selected_object.rect.y += pos.y()-self.__mouse_y
        self.__mouse_x = pos.x()
        self.__mouse_y = pos.y()

    def __on_mouse_left_button_pressed(self, event):
        pos = event.position()
        self.__mouse_x = pos.x()
        self.__mouse_y = pos.y()
        self.__check_object_selection(pos)

    def __on_mouse_move(self, event):
        self.__move_selected_object(event.position())

    def __on_mouse_left_button_released(self, event):
        self.__mouse_x = None
        self.__mouse_y = None
        self.__selected_object = None
    
    def __emit_selected_object_info(self):
        pass

    def add_button(self):
        pass

    def add_sprite(self):
        pass

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
        if obj == self and self.__scene and not self.__scene.views()[0].is_dragging():
            if event.type() == event.Type.MouseButtonPress:
                self.__on_mouse_left_button_pressed(event)
                return True
            elif event.type() == event.Type.MouseMove:
                self.__on_mouse_move(event)
                return True
            elif event.type() == event.Type.MouseButtonRelease:
                self.__on_mouse_left_button_released(event)
                return True
        return super().eventFilter(obj, event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        img = self.__convert_pygame_surface_to_qimage(self.__surface)
        painter.drawPixmap(0, 0, QPixmap.fromImage(img))

    def resizeEvent(self, event):
        new_window_size = event.size()
        self.__surface = pygame.Surface((new_window_size.width(), new_window_size.height()))
        return super().resizeEvent(event)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PygameWidget()
    window.show()
    sys.exit(app.exec())