from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import re
from datetime import datetime

from pygamestudio.gui.console.type import *
from pygamestudio.gui.console.menu import *
from pygamestudio.gui.console.logger import Logger


class ConsoleLogBrowser(QTextBrowser):
    clear_log_signal = Signal()
    info_log_signal = Signal(str)
    error_log_signal = Signal(str)
    warning_log_signal = Signal(str)

    def __init__(self, parent=None, object_manager=None):
        super().__init__(parent)
        self._object_manager = object_manager
        self._context_menu = ContextMenu('', self)
        
        self._logs = []
        self._search_keyword = ''

        info_format = QTextCharFormat()
        error_format = QTextCharFormat()
        warning_format = QTextCharFormat()
        info_format.setForeground(QColor('#000000'))
        error_format.setForeground(QColor('#FF0000'))
        warning_format.setForeground(QColor('#FFFF00'))
        self._log_formats = {
            INFO: info_format,
            ERROR: error_format,
            WARNING: warning_format
        }

        self._log_check_states = {
            INFO: True,
            ERROR: True,
            WARNING: True
        }

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_logger()

    def _set_widget(self):
        font = QFont('Consolas', 10)
        self.setFont(font)

        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _set_signal(self):
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu.select_all_signal.connect(self.selectAll)
        self._context_menu.copy_signal.connect(self._copy)

    def _set_logger(self):
        Logger.set_log_widget(self)

    def _add_log(self, msg, log_level):
        self._logs.append((msg, log_level))
        log_format = self._log_formats[log_level]
        self.textCursor().insertText(f'{msg}\n', log_format)
    
    def _show_context_menu(self, pos):
        global_pos = self.mapToGlobal(pos)
        self._context_menu.show(global_pos)

    def _copy(self):
        selected_text = self.textCursor().selection().toPlainText()
        QApplication.clipboard().setText(selected_text)
    
    def _reset(self):
        self._logs = []
        self._search_keyword = ''

    def get_ready_for_project(self):
        ...
        
    def clean_up(self):
        self._reset()

    def clear_log(self):
        self.clear()
        self._logs = []
        self.clear_log_signal.emit()

    def info(self, msg):
        # timestamp = datetime.now().strftime("%H:%M:%S")
        log_level = INFO
        self._add_log(msg, log_level)
        self.info_log_signal.emit(log_level)

    def error(self, msg):
        log_level = ERROR
        self._add_log(msg, log_level)
        self.error_log_signal.emit(log_level)

    def warning(self, msg):
        log_level = WARNING
        self._add_log(msg, log_level)
        self.warning_log_signal.emit(log_level)
    
    def _filter(self):
        self.clear()
        for msg, log_level in self._logs:
            if not self._log_check_states[log_level]:
                continue

            if self._search_keyword and self._search_keyword.lower() not in msg.lower():
                continue

            log_format = self._log_formats[log_level]
            self.textCursor().insertText(f'{msg}\n', log_format)

    def search(self, keyword):
        self._search_keyword = keyword.strip()
        self._filter()

    def on_info_check_box_clicked(self, is_checked):
        self._log_check_states[INFO] = is_checked
        self._filter()

    def on_error_check_box_clicked(self, is_checked):
        self._log_check_states[ERROR] = is_checked
        self._filter()

    def on_warning_check_box_clicked(self, is_checked):
        self._log_check_states[WARNING] = is_checked
        self._filter()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_A:
                self.selectAll()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self._copy()
                event.accept()
                return
        
        super().keyPressEvent(event)