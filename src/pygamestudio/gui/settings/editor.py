import secrets

from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.config import *
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.utils.theme import set_editor_theme
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.console.logger import Logger
from pygamestudio.gui.inspector.component.spinbox import SuffixSpinBox

#: Default port of the editor's MCP server (see pygamestudio.mcp.server).
DEFAULT_MCP_PORT = 8765


class EditorSettingsBody(QWidget):
    theme_toggled = Signal(str)
    
    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._list_widget = QListWidget()
        self._main_stacked_widget = QStackedWidget()

        self._general_stacked_widget = QWidget()
        self._language_label = QLabel()
        self._language_combobox = QComboBox()
        self._theme_label = QLabel()
        self._theme_combobox = QComboBox()

        # MCP server page (Model Context Protocol: let an AI client drive the editor).
        self._mcp_stacked_widget = QWidget()
        self._mcp_enabled_checkbox = QCheckBox()
        self._mcp_port_label = QLabel()
        # The inspector's spin box look (no buttons until the mouse is over it).
        self._mcp_port_spinbox = SuffixSpinBox()
        self._mcp_token_label = QLabel()
        self._mcp_token_lineedit = QLineEdit()
        self._mcp_token_button = QPushButton()
        self._mcp_status_label = QLabel()

        self._lang_dict = {
            'en': 'English',
            'zh_CN': '中文简体'
        }
        self._theme_dict = {
            'dark': T.tr('theme.dark', 'Dark'),
            'light': T.tr('theme.light', 'Light'),
        }

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self._set_general_stacked_widget()
        self._set_mcp_stacked_widget()

        self._list_widget.setMaximumWidth(200)
        self._list_widget.addItems([T.tr('settings.general', 'General'),
                                    T.tr('settings.mcp_server', 'MCP Server')])
        self._list_widget.setCurrentItem(self._list_widget.item(0))
        self._main_stacked_widget.addWidget(self._general_stacked_widget)
        self._main_stacked_widget.addWidget(self._mcp_stacked_widget)

    def _set_signal(self):
        self._list_widget.clicked.connect(self._change_stacked_widget)
        self._language_combobox.currentTextChanged.connect(self._toggle_language)
        self._theme_combobox.currentTextChanged.connect(self._toggle_theme)
        self._mcp_enabled_checkbox.toggled.connect(self._toggle_mcp_server)
        self._mcp_port_spinbox.valueChanged.connect(self._on_mcp_port_changed)
        self._mcp_token_button.clicked.connect(self._copy_mcp_token)
        T.add_observer(self)

    def _set_layout(self):
        general_stack_grid_layout = QGridLayout(self._general_stacked_widget)
        general_stack_grid_layout.addWidget(self._language_label, 0, 0, 1, 1)
        general_stack_grid_layout.addWidget(self._language_combobox, 0, 1, 1, 1)
        general_stack_grid_layout.addWidget(self._theme_label, 1, 0, 1, 1)
        general_stack_grid_layout.addWidget(self._theme_combobox, 1, 1, 1, 1)
        general_stack_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        mcp_layout = QGridLayout(self._mcp_stacked_widget)
        mcp_layout.addWidget(self._mcp_enabled_checkbox, 0, 0, 1, 3)
        mcp_layout.addWidget(self._mcp_port_label, 1, 0, 1, 1)
        mcp_layout.addWidget(self._mcp_port_spinbox, 1, 1, 1, 1)
        mcp_layout.addWidget(self._mcp_token_label, 2, 0, 1, 1)
        mcp_layout.addWidget(self._mcp_token_lineedit, 2, 1, 1, 1)
        mcp_layout.addWidget(self._mcp_token_button, 2, 2, 1, 1)
        mcp_layout.addWidget(self._mcp_status_label, 3, 0, 1, 3)
        mcp_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        mcp_layout.setColumnStretch(1, 1)

        main_h_layout = QHBoxLayout(self)
        main_h_layout.addWidget(self._list_widget)
        main_h_layout.addWidget(self._main_stacked_widget)

    def _set_general_stacked_widget(self):
        self._language_label.setText(T.tr('settings.language', 'Language'))
        self._language_combobox.addItems(list(self._lang_dict.values()))
        self._theme_label.setText(T.tr('settings.theme', 'Theme'))
        self._theme_combobox.addItems(list(self._theme_dict.values()))

        editor_config = get_editor_config()
        lang_code = editor_config.get('lang') if editor_config.get('lang') else 'en'
        theme_code = editor_config.get('theme') if editor_config.get('theme') else 'dark'
        self._language_combobox.setCurrentText(self._lang_dict.get(lang_code))
        self._theme_combobox.setCurrentText(self._theme_dict.get(theme_code))

    def _toggle_language(self):
        lang_code = self._get_lang_code_by_value(self._language_combobox.currentText())
        T.toggle_language(lang_code)
        update_editor_config('lang', lang_code)

    # ------------------------------------------------------------------- MCP
    def _set_mcp_stacked_widget(self):
        editor_config = get_editor_config()
        self._mcp_enabled_checkbox.setText(T.tr('settings.mcp_enabled', 'Enable MCP server'))
        self._mcp_enabled_checkbox.setToolTip(T.tr(
            'settings.mcp_enabled_tooltip',
            'Let an AI client (VS Code Copilot, Claude Desktop, ...) read and edit this project '
            'through the Model Context Protocol. Every change stays undoable with Ctrl+Z.'))
        self._mcp_port_label.setText(T.tr('settings.mcp_port', 'Port'))
        self._mcp_port_spinbox.setDecimals(0)
        self._mcp_port_spinbox.setRange(1024, 65535)
        self._mcp_port_spinbox.setSingleStep(1)
        self._mcp_port_spinbox.setSuffix('')
        self._mcp_port_spinbox.setFixedWidth(110)
        self._mcp_port_spinbox.setValue(int(editor_config.get('mcp_port') or DEFAULT_MCP_PORT))
        self._mcp_token_label.setText(T.tr('settings.mcp_token', 'Token'))
        self._mcp_token_lineedit.setReadOnly(True)
        self._mcp_token_lineedit.setToolTip(T.tr(
            'settings.mcp_token_tooltip',
            'Send this token with every request (Authorization: Bearer <token>).'))
        self._mcp_token_lineedit.setText(self._ensure_mcp_token(editor_config))
        self._mcp_token_button.setText(T.tr('settings.mcp_copy', 'Copy'))
        self._mcp_enabled_checkbox.setChecked(bool(editor_config.get('mcp_enabled')))
        self._update_mcp_status()

    def _ensure_mcp_token(self, editor_config=None) -> str:
        """The token clients must send - created once and stored in the config.

        It is generated as soon as the settings page is built (not only when
        the server is enabled), so it can be copied into a client config before
        switching the server on.
        """
        editor_config = editor_config if editor_config is not None else get_editor_config()
        token = str(editor_config.get('mcp_token') or '')
        if not token:
            token = secrets.token_urlsafe(24)
            update_editor_config('mcp_token', token)
        return token

    def _toggle_mcp_server(self, is_enabled):
        update_editor_config('mcp_enabled', bool(is_enabled))
        self._restart_mcp_server()

    def _on_mcp_port_changed(self, port):
        update_editor_config('mcp_port', int(port))
        if self._mcp_enabled_checkbox.isChecked():
            self._restart_mcp_server()

    def _copy_mcp_token(self):
        QApplication.clipboard().setText(self._mcp_token_lineedit.text())
        self._mcp_token_button.setText(T.tr('settings.mcp_copied', 'Copied'))
        QTimer.singleShot(1500, lambda: self._mcp_token_button.setText(T.tr('settings.mcp_copy', 'Copy')))

    def _restart_mcp_server(self):
        try:
            import pygamestudio.mcp as mcp
            if not self._mcp_enabled_checkbox.isChecked():
                mcp.stop_server()
            else:
                mcp.start_server(port=int(self._mcp_port_spinbox.value()),
                                 token=self._mcp_token_lineedit.text(), force=True)
        except Exception as e:  # noqa: BLE001 - MCP is optional
            Logger.error('MCP server error: {}'.format(e))
        self._update_mcp_status()

    def _update_mcp_status(self):
        try:
            import pygamestudio.mcp as mcp
            info = mcp.server_info()
        except Exception as e:  # noqa: BLE001
            self._mcp_status_label.setText(str(e))
            return
        if info['running']:
            self._mcp_status_label.setText(T.tr(
                'settings.mcp_status_running', 'Running: {} - add this URL to your MCP client.').format(info['url']))
            self._mcp_status_label.setStyleSheet('QLabel { color: #3fa34d; }')
        else:
            self._mcp_status_label.setText(T.tr(
                'settings.mcp_status_stopped', 'Stopped. Enable it, then connect your MCP client.'))
            self._mcp_status_label.setStyleSheet('')

    def _toggle_theme(self):
        theme_code = self._get_theme_code_by_value(self._theme_combobox.currentText())
        set_editor_theme(theme_code)
        update_editor_config('theme', theme_code)
        self.theme_toggled.emit(theme_code)

    def _change_stacked_widget(self):
        self._main_stacked_widget.setCurrentIndex(self._list_widget.currentIndex().row())

    def _get_lang_code_by_value(self, value):
        for k, v in self._lang_dict.items():
            if v == value:
                return k
        return None
    
    def _get_theme_code_by_value(self, value):
        for k, v in self._theme_dict.items():
            if v == value:
                return k
        return None

    def retranslate(self):
        self._list_widget.clear()
        self._list_widget.addItems([T.tr('settings.general', 'General'),
                                    T.tr('settings.mcp_server', 'MCP Server')])
        self._language_label.setText(T.tr('settings.language', 'Language'))
        self._theme_label.setText(T.tr('settings.theme', 'Theme'))
        self._mcp_enabled_checkbox.setText(T.tr('settings.mcp_enabled', 'Enable MCP server'))
        self._mcp_port_label.setText(T.tr('settings.mcp_port', 'Port'))
        self._mcp_token_label.setText(T.tr('settings.mcp_token', 'Token'))
        self._mcp_token_button.setText(T.tr('settings.mcp_copy', 'Copy'))
        self._update_mcp_status()

        self._theme_dict = {
            'dark': T.tr('theme.dark', 'Dark'),
            'light': T.tr('theme.light', 'Light'),
        }
        editor_config = get_editor_config()
        self._theme_combobox.clear()
        self._theme_combobox.addItems(list(self._theme_dict.values()))
        theme_code = editor_config.get('theme') if editor_config.get('theme') else 'dark'
        self._theme_combobox.setCurrentText(self._theme_dict.get(theme_code))

    def enterEvent(self, event):
        self._update_mcp_status()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)
    

class EditorSettingsWindow(WindowBase):
    theme_toggled = Signal(str)

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
        self._editor_settings_body.theme_toggled.connect(self.theme_toggled.emit)
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('editorSettings')
        
    def retranslate(self):
        self.window_title.set_title_name(T.tr('menu.editor_settings', 'Editor Settings'))
