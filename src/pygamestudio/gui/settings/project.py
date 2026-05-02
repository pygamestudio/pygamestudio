from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.config import *
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.i18n.translator import Translator as T


class ProjectSettingsBody(QWidget):
    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._list_widget = QListWidget()
        self._main_stacked_widget = QStackedWidget()

        self._screen_stacked_widget = QWidget()
        self._screen_width_label = QLabel()
        self._screen_height_label = QLabel()
        self._screen_width_spinbox = QDoubleSpinBox()
        self._screen_height_spinbox = QDoubleSpinBox()

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self._set_screen_stacked_widget()

        self._list_widget.setMaximumWidth(200)
        self._list_widget.addItems([T.tr('settings.game_screen', 'Game Screen')])
        self._list_widget.setCurrentItem(self._list_widget.item(0))
        self._screen_width_spinbox.setDecimals(0)
        self._screen_height_spinbox.setDecimals(0)
        self._main_stacked_widget.addWidget(self._screen_stacked_widget)

    def _set_signal(self):
        self._list_widget.clicked.connect(self._change_stacked_widget)
        self._screen_width_spinbox.valueChanged.connect(self._update_screen_size)
        self._screen_height_spinbox.valueChanged.connect(self._update_screen_size)
        T.add_observer(self)

    def _set_layout(self):
        screen_stack_grid_layout = QGridLayout(self._screen_stacked_widget)
        screen_stack_grid_layout.addWidget(self._screen_width_label, 0, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_width_spinbox, 0, 1, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_height_label, 1, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_height_spinbox, 1, 1, 1, 1)
        screen_stack_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_h_layout = QHBoxLayout(self)
        main_h_layout.addWidget(self._list_widget)
        main_h_layout.addWidget(self._main_stacked_widget)

    def _set_screen_stacked_widget(self):
        self._screen_width_label.setText(T.tr('settings.screen_width', 'Screen Width'))
        self._screen_height_label.setText(T.tr('settings.screen_height', 'Screen Height'))

        screen_width = get_project_config()['screen_width']
        screen_height = get_project_config()['screen_height']
        self._screen_width_spinbox.setRange(1, 99999)
        self._screen_height_spinbox.setRange(1, 99999)
        self._screen_width_spinbox.setValue(screen_width)
        self._screen_height_spinbox.setValue(screen_height)

    def _update_screen_size(self):
        screen_width = self._screen_width_spinbox.value()
        screen_height = self._screen_height_spinbox.value()

        update_project_config('screen_width', screen_width)
        update_project_config('screen_height', screen_height)
        update_project_config('screen_size', [screen_width, screen_height])

        self._game_manager.resize(self._game_manager.canvas_object_uuid, (screen_width, screen_height))

    def _change_stacked_widget(self):
        self._main_stacked_widget.setCurrentIndex(self._list_widget.currentIndex().row())

    def retranslate(self):
        self._list_widget.clear()
        self._list_widget.addItems([T.tr('settings.game_screen', 'Game Screen')])
        self._screen_width_label.setText(T.tr('settings.screen_width', 'Screen Width'))
        self._screen_height_label.setText(T.tr('settings.screen_height', 'Screen Height'))


class ProjectSettingsWindow(WindowBase):
    def __init__(self, game_manager):
        super().__init__()
        self._project_settings_body = ProjectSettingsBody(game_manager)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()

    def _set_widget(self):
        self.resize(800, 600)
        self.set_window_body(self._project_settings_body)
        self.window_title.set_title_name(T.tr('menu.project_settings', 'Project Settings'))

    def _set_signal(self):
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('projectSettings')

    def retranslate(self):
        self.window_title.set_title_name(T.tr('menu.project_settings', 'Project Settings'))

