from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.scene.screen import PygameScreen
from pygamestudio.gui.scene.grid import GridGraphicsView, GridGraphicsScene


class SceneWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._grid_scene = GridGraphicsScene()
        self._pygame_screen = PygameScreen(game_manager, self._grid_scene)
        self._grid_view = GridGraphicsView(game_manager, self._grid_scene, self._pygame_screen)

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self._pygame_proxy = self._grid_scene.addWidget(self._pygame_screen)
        # The (transparent) editor overlay wraps the canvas in a margin ring;
        # parking it at scene (-offset, -offset) keeps the canvas at scene
        # (0, 0, W, H) so all world/scene coordinates stay valid.
        ox, oy = self._pygame_screen.scene_offset()
        self._pygame_proxy.setPos(-ox, -oy)

    def _set_signal(self):
        self._grid_view.rubber_band_changed.connect(self._pygame_screen.update_selection_by_rubber_band)

    def _set_layout(self):
        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self._grid_view)
        window_layout.setContentsMargins(0, 0, 0, 0)
    
    def get_ready_for_project(self):
        self._pygame_screen.get_ready_for_project()
        self._grid_view.get_ready_for_project()

    def clean_up(self):
        self._grid_view.clean_up()
        self._pygame_screen.clean_up()

    def update_grid_style(self, theme_code):
        self._grid_scene.update_grid_style(theme_code)
