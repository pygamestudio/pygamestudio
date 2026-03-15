from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from pygamestudio.game.object.type import *


class ContextMenu(QMenu):
    open_signal = Signal()
    rename_signal = Signal()
    delete_signal = Signal()
    create_signal = Signal()
    import_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._parent = parent

    def _add_actions(self, is_valid_index):
        open_action = QAction('打开', self)
        rename_action = QAction('重命名', self)
        delete_action = QAction('删除', self)
        create_action = QAction('创建', self)
        import_action = QAction('导入', self)

        open_action.triggered.connect(self.open_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        delete_action.triggered.connect(self.delete_signal.emit)
        create_action.triggered.connect(self.create_signal.emit)
        import_action.triggered.connect(self.import_signal.emit)

        # Right click on the blank area.
        if not is_valid_index:
            self.addAction(create_action)
            self.addAction(import_action)

        # Right click on the item.
        else:
            self.addAction(open_action)
            self.addAction(rename_action)
            self.addAction(delete_action)
        
    def show(self, pos, is_valid_index):
        self.clear()
        self._add_actions(is_valid_index)
        self.exec(pos)