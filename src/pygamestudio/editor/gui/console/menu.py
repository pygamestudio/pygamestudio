from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from pygamestudio.editor.gui.asset.type import *


class ContextMenu(QMenu):
    copy_signal = Signal()
    select_all_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._console_log_browser = parent

    def _add_actions(self):
        copy_action = QAction('复制', self)
        select_all_action = QAction('全选', self)
        copy_action.triggered.connect(self.copy_signal.emit)
        select_all_action.triggered.connect(self.select_all_signal.emit)

        selected_text = self._console_log_browser.textCursor().selection().toPlainText()
        if selected_text:
            self.addAction(copy_action)
        self.addAction(select_all_action)
        
    def show(self, pos):
        self.clear()
        self._add_actions()
        self.exec(pos)