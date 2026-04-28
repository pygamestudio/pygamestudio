import pygame
from PySide6.QtCore import *
from pygamestudio.gui.window import Editor
from pygamestudio.gui.dashboard.window import DashboardWindow
from pygamestudio.common.utils.config import get_editor_config
from pygamestudio.common.i18n.translator import Translator as T


class PygameStudio:
    def __init__(self):
        pygame.init()
        self._set_translator()
        self._dashboard = DashboardWindow()
        self._editor = Editor(self)
        self._setup()
        self._enter_editor("C:/Users/louis/Desktop/111")

    def _setup(self):
        self._set_signal()

    def _set_translator(self):
        editor_config = get_editor_config()
        T.load_language(editor_config['lang'])

    def _set_signal(self):
        self._dashboard.open_project_signal.connect(self._enter_editor)
    
    def _enter_editor(self, project_path):
        # Clean up first if another project is opened while the edior is still visible.
        if self._editor.isVisible():
            self._editor.clean_up()

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