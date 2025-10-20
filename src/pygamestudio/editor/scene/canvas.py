import pygame
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QPixmap, QTransform
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt

from buttontest import Button


class PygameWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
    
    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_pygame()

    def __set_widget(self):
        self.setWindowTitle("Scene Window")
        self.resize(800, 600)

    def __set_signal(self):
        self.__update_screen_timer.timeout.connect(self.__update_scene)

    def __set_pygame(self):
        pygame.init()
        self.__surface = pygame.Surface((self.width(), self.height()))
        self.__clock.tick(60)

    def __update_scene(self):
        self.__surface.fill((0, 0, 0))                                       # Clear screen with black
        self.circle_rect = pygame.draw.circle(self.__surface, (255, 0, 0), (0, 500), 50)        # Draw a red circle
        self.button.draw(self.__surface)                                         # Draw button on surface
        
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
    
    def __emit_selected_object_info(self):
        pass

    def add_button(self):
        pass

    def add_sprite(self):
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        img = self.__convert_pygame_surface_to_qimage(self.__surface)
        painter.drawPixmap(0, 0, QPixmap.fromImage(img))

    def resizeEvent(self, event):
        new_window_size = event.size()
        self.__surface = pygame.Surface((new_window_size.width(), new_window_size.height()))
        return super().resizeEvent(event)

    def mousePressEvent(self, event):
        pos = event.position()
        self.__mouse_x = pos.x()
        self.__mouse_y = pos.y()
        self.__check_object_selection(pos)
        return super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        self.__move_selected_object(event.position())
        return super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.__mouse_x = None
        self.__mouse_y = None
        self.__selected_object = None
        return super().mouseReleaseEvent(event)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PygameWidget()
    window.show()
    window.run()
    sys.exit(app.exec())