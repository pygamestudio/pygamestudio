import pygame
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QPixmap
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt


class PygameWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__surface = pygame.Surface((self.width(), self.height()))
        self.__clock = pygame.time.Clock()
        self.__update_screen_timer = QTimer(self)

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
        self.__surface = pygame.Surface((self.height(), self.width()))
        self.__clock.tick(60)

    def __update_scene(self):
        self.__surface.fill((0, 0, 0))                                       # Clear screen with black
        pygame.draw.circle(self.__surface, (255, 0, 0), (50, 50), 50)        # Draw a red circle
        self.update()                                                       # Trigger repaint

    def __convert_pygame_surface_to_qimage(self, surface):
        img = pygame.surfarray.pixels3d(surface)
        img_height, img_width, img_depth = img.shape
        img = QImage(img.tobytes(), img_width, img_height, img_width * img_depth, QImage.Format.Format_RGB888)
        return img
    
    def run(self):
        self.__update_screen_timer.start(16)        # Approximately 60 FPS
    
    def paintEvent(self, event):
        painter = QPainter(self)
        img = self.__convert_pygame_surface_to_qimage(self.__surface)
        painter.drawPixmap(0, 0, QPixmap.fromImage(img))

    def resizeEvent(self, event):
        new_window_size = event.size()
        self.__surface = pygame.Surface((new_window_size.height(), new_window_size.width()))
        super().resizeEvent(event)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PygameWidget()
    window.show()
    window.run()
    sys.exit(app.exec())