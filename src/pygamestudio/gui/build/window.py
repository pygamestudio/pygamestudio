from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.gui.build.desktop import DesktopAppBuildWindow
from pygamestudio.common.i18n.translator import Translator as T


class BuildWindowBody(QTabWidget):
    def __init__(self, game_manager):
        super().__init__()
        self._desktop_app_build_window = DesktopAppBuildWindow(game_manager)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.addTab(self._desktop_app_build_window, T.tr('build.desktop_app', 'Desktop App'))
    
    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setTabText(0, T.tr('build.desktop_app', 'Desktop App'))

    def get_ready_for_project(self):
        self._desktop_app_build_window.get_ready_for_project()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)


class BuildWindow(WindowBase):
    def __init__(self, game_manager):
        super().__init__()
        self._build_window_body = BuildWindowBody(game_manager)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()

    def _set_widget(self):
        self.resize(500, 260)
        self.set_window_body(self._build_window_body)
        self.window_title.set_title_name(T.tr('build.build', 'Build'))
    
    def _set_signal(self):
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('build')

    def retranslate(self):
        self.window_title.set_title_name(T.tr('build.build', 'Build'))

    def get_ready_for_project(self):
        self._build_window_body.get_ready_for_project()
