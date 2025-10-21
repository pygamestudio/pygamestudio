from PySide6.QtWidgets import QWidget, QVBoxLayout
from grid import GridGraphicsView, GridGraphicsScene
from canvas import PygameWidget


class SceneWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__pygame_widget = PygameWidget()
        self.__grid_scene = GridGraphicsScene()
        self.__grid_view = GridGraphicsView(self.__grid_scene, self)

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        self.__grid_scene.addWidget(self.__pygame_widget)
        self.__pygame_widget.set_scene(self.__grid_scene)
        self.__pygame_widget.move(-self.__pygame_widget.width()//2, -self.__pygame_widget.height()//2)

    def __set_signal(self):
        pass

    def __set_layout(self):
        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self.__grid_view)
        window_layout.setContentsMargins(0, 0, 0, 0)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = SceneWindow()
    window.show()
    sys.exit(app.exec())