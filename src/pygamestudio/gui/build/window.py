from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.gui.build.desktop import DesktopAppBuildWindow
from pygamestudio.gui.build.web import WebAppBuildWindow
from pygamestudio.gui.build.android import AndroidAppBuildWindow
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.config import update_project_config


class BuildWindowBody(QTabWidget):
    def __init__(self, game_manager):
        super().__init__()
        self._desktop_app_build_window = DesktopAppBuildWindow(game_manager)
        self._web_app_build_window = WebAppBuildWindow(game_manager)
        self._android_app_build_window = AndroidAppBuildWindow(game_manager)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.addTab(self._desktop_app_build_window, T.tr('build.desktop_app', 'Desktop App'))
        self.addTab(self._web_app_build_window, T.tr('build.web_app', 'Web App'))
        self.addTab(self._android_app_build_window, T.tr('build.android_app', 'Android APK'))
    
    def _set_signal(self):
        T.add_observer(self)
        # The app name and icon are one setting for both targets
        # (build.app_name / build.app_icon): an edit in either tab is saved at
        # once and mirrored to the other tab, so it survives closing the editor
        # and a build started from the other tab.
        self._desktop_app_build_window.app_icon_changed_signal.connect(self._on_app_icon_changed)
        self._web_app_build_window.app_icon_changed_signal.connect(self._on_app_icon_changed)
        self._android_app_build_window.app_icon_changed_signal.connect(self._on_app_icon_changed)
        self._desktop_app_build_window.app_name_changed_signal.connect(self._on_app_name_changed)
        self._web_app_build_window.app_name_changed_signal.connect(self._on_app_name_changed)
        self._android_app_build_window.app_name_changed_signal.connect(self._on_app_name_changed)

    def _on_app_icon_changed(self, icon_path):
        """Store the pick in project.pygs and show it in both tabs."""
        update_project_config('build.app_icon', icon_path)
        for build_window in (self._desktop_app_build_window, self._web_app_build_window,
                             self._android_app_build_window):
            build_window.set_app_icon(icon_path)

    def _on_app_name_changed(self, app_name):
        """Store the name in project.pygs and show it in both tabs."""
        update_project_config('build.app_name', app_name)
        for build_window in (self._desktop_app_build_window, self._web_app_build_window,
                             self._android_app_build_window):
            build_window.set_app_name(app_name)

    def retranslate(self):
        self.setTabText(0, T.tr('build.desktop_app', 'Desktop App'))
        self.setTabText(1, T.tr('build.web_app', 'Web App'))
        self.setTabText(2, T.tr('build.android_app', 'Android APK'))

    def get_ready_for_project(self):
        self._desktop_app_build_window.get_ready_for_project()
        self._web_app_build_window.get_ready_for_project()
        self._android_app_build_window.get_ready_for_project()

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
        self.resize(700, 330)
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
