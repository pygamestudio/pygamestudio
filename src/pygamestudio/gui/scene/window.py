import platform
import subprocess
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from pygamestudio.gui.scene.grid import GridGraphicsView, GridGraphicsScene
from pygamestudio.gui.scene.screen import PygameScreen

class SceneWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._grid_scene = GridGraphicsScene()
        self._grid_view = GridGraphicsView(game_manager, self._grid_scene)
        self._pygame_screen = PygameScreen(game_manager, self._grid_scene)

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_layout()

    def _set_widget(self):
        self._grid_scene.addWidget(self._pygame_screen)

    def _set_layout(self):
        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self._grid_view)
        window_layout.setContentsMargins(0, 0, 0, 0)

    @property
    def pygame_widget(self):
        return self._pygame_screen
    
    def get_ready_for_project(self):
        self._grid_view.get_ready_for_project()
        self._pygame_screen.get_ready_for_project()

    def clean_up(self):
        self._grid_view.clean_up()
        self._pygame_screen.clean_up()