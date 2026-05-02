from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.config import *
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.i18n.translator import Translator as T


class EditorSettingsBody(QWidget):
    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._list_widget = QListWidget()
        self._main_stacked_widget = QStackedWidget()

        self._general_stacked_widget = QWidget()
        self._language_label = QLabel()
        self._language_combobox = QComboBox()

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self._set_general_stacked_widget()

        self._list_widget.setMaximumWidth(200)
        self._list_widget.addItems([T.tr('settings.general', 'General')])
        self._list_widget.setCurrentItem(self._list_widget.item(0))
        self._main_stacked_widget.addWidget(self._general_stacked_widget)

    def _set_signal(self):
        self._list_widget.clicked.connect(self._change_stacked_widget)
        self._language_combobox.currentTextChanged.connect(self._toggle_language)
        T.add_observer(self)

    def _set_layout(self):
        general_stack_grid_layout = QGridLayout(self._general_stacked_widget)
        general_stack_grid_layout.addWidget(self._language_label, 0, 0, 1, 1)
        general_stack_grid_layout.addWidget(self._language_combobox, 0, 1, 1, 1)
        general_stack_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_h_layout = QHBoxLayout(self)
        main_h_layout.addWidget(self._list_widget)
        main_h_layout.addWidget(self._main_stacked_widget)

    def _set_general_stacked_widget(self):
        self._language_label.setText(T.tr('settings.language', 'Language'))
        self._language_combobox.addItems(['en', 'zh_CN'])
        editor_config = get_editor_config()
        self._language_combobox.setCurrentText(editor_config['lang'])

    def _toggle_language(self):
        lang_code = self._language_combobox.currentText()
        T.toggle_language(lang_code)
        update_editor_config('lang', lang_code)

    def _change_stacked_widget(self):
        self._main_stacked_widget.setCurrentIndex(self._list_widget.currentIndex().row())

    def retranslate(self):
        self._list_widget.clear()
        self._list_widget.addItems([T.tr('settings.general', 'General')])
        self._language_label.setText(T.tr('settings.language', 'Language'))



class EditorSettingsWindow(WindowBase):
    def __init__(self, game_manager):
        super().__init__()
        self._editor_settings_body = EditorSettingsBody(game_manager)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()

    def _set_widget(self):
        self.resize(800, 600)
        self.set_window_body(self._editor_settings_body)
        self.window_title.set_title_name(T.tr('menu.editor_settings', 'Editor Settings'))

    def _set_signal(self):
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('editorSettings')

    def retranslate(self):
        self.window_title.set_title_name(T.tr('menu.editor_settings', 'Editor Settings'))
