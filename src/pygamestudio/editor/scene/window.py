from PySide6.QtWidgets import QWidget, QVBoxLayout
from grid import GridGraphicsView, GridGraphicsScene


class SceneWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__grid_scene = GridGraphicsScene()
        self.__grid_view = GridGraphicsView(self.__grid_scene, self)

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        self.setWindowTitle("Scene Window")
        self.setGeometry(200, 200, 800, 600)

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