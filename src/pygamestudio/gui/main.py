from pygamestudio.gui.window import Editor
from pygamestudio.gui.dashboard.window import DashboardWindow
from PySide6.QtCore import *

class PygameStudio:
    def __init__(self):
        self._dashboard = DashboardWindow()
        self._editor = Editor(self)
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        ...

    def _set_signal(self):
        self._dashboard.open_project_signal.connect(self._enter_editor)
        
    def _enter_editor(self, project_path):
        self._editor.get_ready_for_project(project_path)
        self._dashboard.hide()
        self._editor.show()

    def show_dashboard(self):
        self._dashboard.show()

    def show_dashboard_and_create_project_window(self):
        self._dashboard.show()
        self._dashboard.dashboard_list_view.show_create_project_window()

    def start(self):
        self._dashboard.show()