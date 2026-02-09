from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from pygamestudio.editor.gui.hierarchy.type import *
from pygamestudio.game.object.type import *


class ContextMenu(QMenu):
    add_signal = Signal(str)
    cut_signal = Signal()
    copy_signal = Signal()
    paste_signal = Signal()
    delete_signal = Signal()
    rename_signal = Signal()
    duplicate_signal = Signal()
    copy_uuid_signal = Signal()
    copy_path_signal = Signal()
    copy_name_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._parent = parent

    def _add_actions(self, item_type):
        add_text_action = QAction('文本', self)
        add_rect_action = QAction('矩形', self)
        add_circle_action = QAction('圆形', self)
        cut_action = QAction('剪切', self)
        copy_action = QAction('复制', self)
        paste_action = QAction('粘贴', self)
        delete_action = QAction('删除', self)
        rename_action = QAction('重命名', self)
        duplicate_action = QAction('生成副本', self)
        copy_uuid_action = QAction('复制UUID', self)
        copy_path_action = QAction('复制路径', self)
        copy_name_action = QAction('复制名称', self)

        add_text_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_TEXT))
        add_rect_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_RECT))
        add_circle_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_CIRCLE))
        cut_action.triggered.connect(self.cut_signal.emit)
        copy_action.triggered.connect(self.copy_signal.emit)
        paste_action.triggered.connect(self.paste_signal.emit)
        delete_action.triggered.connect(self.delete_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        duplicate_action.triggered.connect(self.duplicate_signal.emit)
        copy_uuid_action.triggered.connect(self.copy_uuid_signal.emit)
        copy_path_action.triggered.connect(self.copy_path_signal.emit)
        copy_name_action.triggered.connect(self.copy_name_signal.emit)

        # Create actions are for all object types.
        add_menu = QMenu(title='添加')
        self.addMenu(add_menu)
        add_menu.addAction(add_text_action)
        add_menu.addAction(add_rect_action)
        add_menu.addAction(add_circle_action)  

        # Right click on the blank area.
        if item_type is None:
            self.addAction(paste_action)

        # Right click on the root object.
        elif item_type == OBJECT_SCENE:
            self.addAction(paste_action)
            self.addSeparator()
            copy_menu = QMenu(title='复制路径 | 名称 | UUID')
            copy_menu.addAction(copy_path_action)
            copy_menu.addAction(copy_name_action)
            copy_menu.addAction(copy_uuid_action)
            self.addMenu(copy_menu)

        # Right click on the regular object.
        else:
            self.addSeparator()
            self.addAction(cut_action)
            self.addAction(copy_action)
            self.addAction(duplicate_action)
            self.addAction(paste_action)
            self.addSeparator()
            self.addAction(delete_action)
            self.addAction(rename_action)
            self.addSeparator()
            copy_menu = QMenu(title='复制路径 | 名称 | UUID')
            copy_menu.addAction(copy_path_action)
            copy_menu.addAction(copy_name_action)
            copy_menu.addAction(copy_uuid_action)
            self.addMenu(copy_menu)

        self._set_paste_action_status(paste_action)

    def _set_paste_action_status(self, paste_action):
        if self._parent.get_clipboard_content():
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        
    def show(self, pos, object_type):
        self.clear()
        self._add_actions(object_type)
        self.exec(pos)