from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu
from pygamestudio.gui.asset.type import *
from pygamestudio.common.i18n.translator import Translator as T


class ContextMenu(QMenu):
    copy_signal = Signal()
    select_all_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._console_log_browser = parent

    def _add_actions(self):
        copy_action = QAction(T.tr('menu.copy', 'Copy'), self)
        select_all_action = QAction(T.tr('menu.select_all', 'Select All'), self)
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