from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.config import *
from pygamestudio.api.core.game import normalize_desktop_fit, normalize_mobile_fit
from pygamestudio.gui.base.window import CenteredListWidget, WindowBase
from pygamestudio.common.i18n.translator import Translator as T


class ProjectSettingsBody(QWidget):
    #: Mobile screen fit modes: (config value, translation key, fallback text).
    #: The value is what the runtime reads from project.pygs as
    #: ``screen_scale_mode``. ``none`` draws the canvas 1:1 (no adaptation at
    #: all); every other mode scales it to the screen.
    SCREEN_FIT_MODES = (
        ('fixed_width', 'settings.screen_fit_fixed_width', 'Fit width'),
        ('fixed_height', 'settings.screen_fit_fixed_height', 'Fit height'),
        ('exact_fit', 'settings.screen_fit_exact_fit', 'Stretch to screen'),
        ('none', 'settings.screen_fit_none', 'No scaling'),
    )
    #: Desktop fit: the window (the default, canvas at 1:1) or full screen with
    #: one of the scaling modes - the label says so, because the window the game
    #: opens in is a different thing there. Stored as ``desktop_display_mode``.
    DESKTOP_FIT_MODES = (
        ('window', 'settings.desktop_window', 'No scaling (windowed)'),
        ('fixed_width', 'settings.desktop_fit_fixed_width', 'Fit width (full screen)'),
        ('fixed_height', 'settings.desktop_fit_fixed_height', 'Fit height (full screen)'),
        ('exact_fit', 'settings.desktop_fit_exact_fit', 'Stretch to screen (full screen)'),
    )
    #: Browser canvas fit: how the page scales the canvas. Stored as
    #: ``web_scale_mode``. The default shows the canvas at its own size (only
    #: centred); the other modes scale it exactly like the phone modes.
    WEB_FIT_MODES = (('none', 'settings.screen_fit_none', 'No scaling'),) + tuple(
        mode for mode in SCREEN_FIT_MODES if mode[0] != 'none')

    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._list_widget = CenteredListWidget()
        self._main_stacked_widget = QStackedWidget()

        self._screen_stacked_widget = QWidget()
        self._screen_width_label = QLabel()
        self._screen_height_label = QLabel()
        self._screen_fit_label = QLabel()
        self._desktop_display_label = QLabel()
        self._web_fit_label = QLabel()
        self._screen_width_spinbox = QDoubleSpinBox()
        self._screen_height_spinbox = QDoubleSpinBox()
        self._screen_fit_combobox = QComboBox()
        self._desktop_display_combobox = QComboBox()
        self._web_fit_combobox = QComboBox()

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
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
        self._screen_fit_combobox.currentIndexChanged.connect(self._update_screen_fit)
        self._desktop_display_combobox.currentIndexChanged.connect(self._update_desktop_display)
        self._web_fit_combobox.currentIndexChanged.connect(self._update_web_fit)
        T.add_observer(self)

    def _set_layout(self):
        screen_stack_grid_layout = QGridLayout(self._screen_stacked_widget)
        screen_stack_grid_layout.addWidget(self._screen_width_label, 0, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_width_spinbox, 0, 1, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_height_label, 1, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_height_spinbox, 1, 1, 1, 1)
        screen_stack_grid_layout.addWidget(self._desktop_display_label, 2, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._desktop_display_combobox, 2, 1, 1, 1)
        screen_stack_grid_layout.addWidget(self._web_fit_label, 3, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._web_fit_combobox, 3, 1, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_fit_label, 4, 0, 1, 1)
        screen_stack_grid_layout.addWidget(self._screen_fit_combobox, 4, 1, 1, 1)
        screen_stack_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_h_layout = QHBoxLayout(self)
        main_h_layout.addWidget(self._list_widget)
        main_h_layout.addWidget(self._main_stacked_widget)

    def _set_screen_stacked_widget(self):
        self._screen_width_label.setText(T.tr('settings.screen_width', 'Screen Width'))
        self._screen_height_label.setText(T.tr('settings.screen_height', 'Screen Height'))
        self._screen_fit_label.setText(T.tr('settings.screen_fit', 'Mobile Screen Fit'))
        self._desktop_display_label.setText(T.tr('settings.desktop_fit', 'Desktop Fit'))
        self._web_fit_label.setText(T.tr('settings.web_fit', 'Web Canvas Fit'))

        self._screen_width_spinbox.blockSignals(True)
        self._screen_height_spinbox.blockSignals(True)
        self._screen_fit_combobox.blockSignals(True)
        self._desktop_display_combobox.blockSignals(True)
        self._web_fit_combobox.blockSignals(True)
        screen_width = get_project_config()['screen_width']
        screen_height = get_project_config()['screen_height']
        self._screen_width_spinbox.setRange(1, 99999)
        self._screen_height_spinbox.setRange(1, 99999)
        self._screen_width_spinbox.setValue(screen_width)
        self._screen_height_spinbox.setValue(screen_height)

        self._screen_fit_combobox.clear()
        for value, key, fallback in self.SCREEN_FIT_MODES:
            self._screen_fit_combobox.addItem(T.tr(key, fallback), value)
        # An old project may still store a retired mode: show the one the
        # engine maps it to (see normalize_mobile_fit), not an empty box.
        current = normalize_mobile_fit(get_project_config().get('screen_scale_mode'))
        self._screen_fit_combobox.setCurrentIndex(max(0, self._screen_fit_combobox.findData(current)))

        self._desktop_display_combobox.clear()
        for value, key, fallback in self.DESKTOP_FIT_MODES:
            self._desktop_display_combobox.addItem(T.tr(key, fallback), value)
        desktop = normalize_desktop_fit(get_project_config().get('desktop_display_mode'))
        self._desktop_display_combobox.setCurrentIndex(
            max(0, self._desktop_display_combobox.findData(desktop)))

        self._web_fit_combobox.clear()
        for value, key, fallback in self.WEB_FIT_MODES:
            self._web_fit_combobox.addItem(T.tr(key, fallback), value)
        web = str(get_project_config().get('web_scale_mode') or 'none')
        if web == 'show_all':    # retired pick: the page shows the canvas 1:1 now
            web = 'none'
        self._web_fit_combobox.setCurrentIndex(max(0, self._web_fit_combobox.findData(web)))

        self._screen_width_spinbox.blockSignals(False)
        self._screen_height_spinbox.blockSignals(False)
        self._screen_fit_combobox.blockSignals(False)
        self._desktop_display_combobox.blockSignals(False)
        self._web_fit_combobox.blockSignals(False)

    def _update_screen_fit(self):
        """Remember the fit mode the runtime uses for the mobile screen."""
        update_project_config('screen_scale_mode', self._screen_fit_combobox.currentData())

    def _update_desktop_display(self):
        """Remember whether a desktop run fills the screen, and how it scales."""
        update_project_config('desktop_display_mode', self._desktop_display_combobox.currentData())

    def _update_web_fit(self):
        """Remember how the browser page scales the canvas."""
        update_project_config('web_scale_mode', self._web_fit_combobox.currentData())

    def _update_screen_size(self):
        screen_width = self._screen_width_spinbox.value()
        screen_height = self._screen_height_spinbox.value()

        update_project_config('screen_width', screen_width)
        update_project_config('screen_height', screen_height)
        update_project_config('screen_size', [screen_width, screen_height])

        self._game_manager.resize(self._game_manager.canvas_object_uuid, (screen_width, screen_height))

    def _change_stacked_widget(self):
        self._main_stacked_widget.setCurrentIndex(self._list_widget.currentIndex().row())

    def get_ready_for_project(self):
        self._set_screen_stacked_widget()

    def retranslate(self):
        self._list_widget.clear()
        self._list_widget.addItems([T.tr('settings.game_screen', 'Game Screen')])
        self._screen_width_label.setText(T.tr('settings.screen_width', 'Screen Width'))
        self._screen_height_label.setText(T.tr('settings.screen_height', 'Screen Height'))
        self._screen_fit_label.setText(T.tr('settings.screen_fit', 'Mobile Screen Fit'))
        self._desktop_display_label.setText(T.tr('settings.desktop_fit', 'Desktop Fit'))
        self._web_fit_label.setText(T.tr('settings.web_fit', 'Web Canvas Fit'))
        for index, (_value, key, fallback) in enumerate(self.SCREEN_FIT_MODES):
            if index < self._screen_fit_combobox.count():
                self._screen_fit_combobox.setItemText(index, T.tr(key, fallback))
        for index, (_value, key, fallback) in enumerate(self.DESKTOP_FIT_MODES):
            if index < self._desktop_display_combobox.count():
                self._desktop_display_combobox.setItemText(index, T.tr(key, fallback))
        for index, (_value, key, fallback) in enumerate(self.WEB_FIT_MODES):
            if index < self._web_fit_combobox.count():
                self._web_fit_combobox.setItemText(index, T.tr(key, fallback))

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)
    
    
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
    
    def get_ready_for_project(self):
        return self._project_settings_body.get_ready_for_project()
    
    def retranslate(self):
        self.window_title.set_title_name(T.tr('menu.project_settings', 'Project Settings'))

