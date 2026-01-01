from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import re

from pygamestudio.editor.console.type import *
from pygamestudio.editor.console.menu import *


class ConsoleLogBrowser(QTextBrowser):
    clear_log_signal = Signal()
    info_log_signal = Signal(str)
    error_log_signal = Signal(str)
    warning_log_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__context_menu = ContextMenu('', self)
        
        self.__logs = []
        self.__search_keyword = ''

        info_format = QTextCharFormat()
        error_format = QTextCharFormat()
        warning_format = QTextCharFormat()
        info_format.setForeground(QColor('#000000'))
        error_format.setForeground(QColor('#FF0000'))
        warning_format.setForeground(QColor('#FFFF00'))
        self.__log_formats = {
            INFO: info_format,
            ERROR: error_format,
            WARNING: warning_format
        }

        self.__log_check_states = {
            INFO: True,
            ERROR: True,
            WARNING: True
        }

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()

    def __set_widget(self):
        font = QFont('Consolas', 10)
        self.setFont(font)

        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def __set_signal(self):
        self.customContextMenuRequested.connect(self.__show_context_menu)
        self.__context_menu.select_all_signal.connect(self.selectAll)
        self.__context_menu.copy_signal.connect(self.__copy)

    def __add_log(self, msg, log_level):
        self.__logs.append((msg, log_level))
        log_format = self.__log_formats[log_level]
        self.textCursor().insertText(f'{msg}\n', log_format)
    
    def __show_context_menu(self, pos):
        global_pos = self.mapToGlobal(pos)
        self.__context_menu.show(global_pos)

    def __copy(self):
        selected_text = self.textCursor().selection().toPlainText()
        QApplication.clipboard().setText(selected_text)
        
    def clear_log(self):
        self.clear()
        self.__logs = []
        self.clear_log_signal.emit()

    def info(self, msg):
        log_level = INFO
        self.__add_log(msg, log_level)
        self.info_log_signal.emit(log_level)

    def error(self, msg):
        log_level = ERROR
        self.__add_log(msg, log_level)
        self.error_log_signal.emit(log_level)

    def warning(self, msg):
        log_level = WARNING
        self.__add_log(msg, log_level)
        self.warning_log_signal.emit(log_level)
    
    def __filter(self):
        self.clear()
        for msg, log_level in self.__logs:
            if not self.__log_check_states[log_level]:
                continue

            if self.__search_keyword and self.__search_keyword.lower() not in msg.lower():
                continue

            log_format = self.__log_formats[log_level]
            self.textCursor().insertText(f'{msg}\n', log_format)

    def search(self, keyword):
        self.__search_keyword = keyword.strip()
        self.__filter()

    def on_info_check_box_clicked(self, is_checked):
        self.__log_check_states[INFO] = is_checked
        self.__filter()

    def on_error_check_box_clicked(self, is_checked):
        self.__log_check_states[ERROR] = is_checked
        self.__filter()

    def on_warning_check_box_clicked(self, is_checked):
        self.__log_check_states[WARNING] = is_checked
        self.__filter()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_A:
                self.selectAll()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self.__copy()
                event.accept()
                return
        
        super().keyPressEvent(event)