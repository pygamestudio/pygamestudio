from pygamestudio.gui.window import Editor
from pygamestudio.gui.dashboard.window import DashboardWindow
from pygamestudio.game.object.manager import ObjectManager


class PygameStudio:
    def __init__(self):
        self._object_manager = ObjectManager()
        self._dashboard = DashboardWindow()
        self._editor = None
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        ...

    def _set_signal(self):
        self._dashboard.open_project_signal.connect(self._show_editor)

    def _show_editor(self, project_path):
        self._object_manager.set_project_path(project_path)
        self._editor = Editor(self._object_manager)
        self._dashboard.hide()
        self._editor.show()

    def start(self):
        self._dashboard.show()