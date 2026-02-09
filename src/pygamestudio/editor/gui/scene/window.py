from PySide6.QtWidgets import *
from PySide6.QtCore import *
from pygamestudio.editor.gui.scene.grid import GridGraphicsView, GridGraphicsScene
from pygamestudio.editor.gui.scene.canvas import PygameWidget


class SceneWindow(QWidget):
    def __init__(self, parent=None, object_manager=None):
        super().__init__(parent)
        self._pygame_widget = PygameWidget(self, object_manager)
        self._grid_scene = GridGraphicsScene()
        self._grid_view = GridGraphicsView(self._grid_scene, self)

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self._grid_scene.addWidget(self._pygame_widget)
        self._pygame_widget.set_scene(self._grid_scene)
        self._pygame_widget.move(-self._pygame_widget.width()//2, -self._pygame_widget.height()//2)

    def _set_signal(self):
        ...

    def _set_layout(self):
        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self._grid_view)
        window_layout.setContentsMargins(0, 0, 0, 0)

    @property
    def pygame_widget(self):
        return self._pygame_widget