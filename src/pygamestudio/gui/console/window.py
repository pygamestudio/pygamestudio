from PySide6.QtWidgets import *
from pygamestudio.gui.console.type import *
from pygamestudio.gui.console.widget import *
from pygamestudio.gui.console.search import SearchLineEdit
from pygamestudio.gui.console.browser import ConsoleLogBrowser


class ConsoleWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._console_log_browser = ConsoleLogBrowser(self, game_manager)
        self._search_line_edit = SearchLineEdit(self)

        self._clear_btn = ClearButton(self)
        self._info_check_box = LogCheckBox(self, INFO)
        self._error_check_box = LogCheckBox(self, ERROR)
        self._warning_check_box = LogCheckBox(self, WARNING)

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        ...

    def _set_signal(self):
        self._console_log_browser.clear_log_signal.connect(self._info_check_box.reset_log_num)
        self._console_log_browser.clear_log_signal.connect(self._error_check_box.reset_log_num)
        self._console_log_browser.clear_log_signal.connect(self._warning_check_box.reset_log_num)
        self._console_log_browser.info_log_signal.connect(self._info_check_box.increase_one_log_num)
        self._console_log_browser.error_log_signal.connect(self._error_check_box.increase_one_log_num)
        self._console_log_browser.warning_log_signal.connect(self._warning_check_box.increase_one_log_num)

        self._clear_btn.clicked.connect(self._console_log_browser.clear_log)
        self._search_line_edit.search_signal.connect(self._console_log_browser.search)
        self._info_check_box.check_box_clicked.connect(self._console_log_browser.on_info_check_box_clicked)
        self._error_check_box.check_box_clicked.connect(self._console_log_browser.on_error_check_box_clicked)
        self._warning_check_box.check_box_clicked.connect(self._console_log_browser.on_warning_check_box_clicked)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._clear_btn)
        h_layout.addWidget(self._search_line_edit)
        h_layout.addStretch(1)
        h_layout.addWidget(self._info_check_box)
        h_layout.addWidget(self._warning_check_box)
        h_layout.addWidget(self._error_check_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self._console_log_browser)

    def get_ready_for_project(self):
        self._console_log_browser.get_ready_for_project()

    def clean_up(self):
        self._console_log_browser.clean_up()