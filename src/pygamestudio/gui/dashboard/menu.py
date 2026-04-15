from PySide6.QtCore import *
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from pygamestudio.game.object.type import *
from pygamestudio.common.i18n.translator import Translator as T

class ContextMenu(QMenu):
    open_project_signal = Signal(QModelIndex)
    rename_project_signal = Signal(QModelIndex)
    delete_project_signal = Signal(QModelIndex)
    create_project_signal = Signal()
    import_project_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._parent = parent

    def _add_actions(self, index):
        is_valid_index = index.isValid()

        open_action = QAction(T.tr('menu.open', 'Open'), self)
        rename_action = QAction(T.tr('menu.rename', 'Rename'), self)
        delete_action = QAction(T.tr('menu.delete', 'Delete'), self)
        create_action = QAction(T.tr('menu.create', 'Create'), self)
        import_action = QAction(T.tr('menu.import', 'Import'), self)

        open_action.triggered.connect(lambda: self.open_project_signal.emit(index))
        rename_action.triggered.connect(lambda: self.rename_project_signal.emit(index))
        delete_action.triggered.connect(lambda: self.delete_project_signal.emit(index))
        create_action.triggered.connect(self.create_project_signal.emit)
        import_action.triggered.connect(self.import_project_signal.emit)

        # Right click on the blank area.
        if not is_valid_index:
            self.addAction(create_action)
            self.addAction(import_action)

        # Right click on the item.
        else:
            self.addAction(open_action)
            self.addAction(rename_action)
            self.addAction(delete_action)
        
    def show(self, pos, index):
        self.clear()
        self._add_actions(index)
        self.exec(pos)