from PySide6.QtWidgets import *
from pygamestudio.editor.console.browser import ConsoleLogBrowser
from pygamestudio.editor.console.search import SearchLineEdit
from pygamestudio.editor.console.widget import *
from pygamestudio.editor.console.type import *


class ConsoleWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__console_log_browser = ConsoleLogBrowser(self)
        self.__search_line_edit = SearchLineEdit(self)

        self.__clear_btn = ClearButton(self)
        self.__info_check_box = LogCheckBox(self, INFO)
        self.__error_check_box = LogCheckBox(self, ERROR)
        self.__warning_check_box = LogCheckBox(self, WARNING)

        self.__set_up()

        self.__console_log_browser.info('这是一条INFO消息')
        self.__console_log_browser.error('这是一条ERROR消息\n你的还会第哦啊是')
        self.__console_log_browser.warning('这是一条WARNING消息')
        self.__console_log_browser.error("""
还有一个文件不存在的错误：
File "missing.py", line 10
    import unknown_module
ModuleNotFoundError: No module named 'unknown_module'
        """)
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        ...

    def __set_signal(self):
        self.__console_log_browser.clear_log_signal.connect(self.__info_check_box.reset_log_num)
        self.__console_log_browser.clear_log_signal.connect(self.__error_check_box.reset_log_num)
        self.__console_log_browser.clear_log_signal.connect(self.__warning_check_box.reset_log_num)
        self.__console_log_browser.info_log_signal.connect(self.__info_check_box.increase_one_log_num)
        self.__console_log_browser.error_log_signal.connect(self.__error_check_box.increase_one_log_num)
        self.__console_log_browser.warning_log_signal.connect(self.__warning_check_box.increase_one_log_num)

        self.__clear_btn.clicked.connect(self.__console_log_browser.clear_log)
        self.__search_line_edit.search_signal.connect(self.__console_log_browser.search)
        self.__info_check_box.check_box_clicked.connect(self.__console_log_browser.on_info_check_box_clicked)
        self.__error_check_box.check_box_clicked.connect(self.__console_log_browser.on_error_check_box_clicked)
        self.__warning_check_box.check_box_clicked.connect(self.__console_log_browser.on_warning_check_box_clicked)

    def __set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self.__clear_btn)
        h_layout.addWidget(self.__search_line_edit)
        h_layout.addStretch(1)
        h_layout.addWidget(self.__info_check_box)
        h_layout.addWidget(self.__warning_check_box)
        h_layout.addWidget(self.__error_check_box)
        h_layout.setContentsMargins(0, 0, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self.__console_log_browser)
