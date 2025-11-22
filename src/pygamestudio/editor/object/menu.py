from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from pygamestudio.editor.object.type import *


class ContextMenu(QMenu):
    create_signal = Signal(int)
    cut_signal = Signal()
    copy_signal = Signal()
    paste_signal = Signal()
    delete_signal = Signal()
    rename_signal = Signal()
    duplicate_signal = Signal()
    copy_uuid_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self.__parent = parent

    def __add_actions(self, item_type):
        create_text_action = QAction('文本', self)
        create_rect_action = QAction('矩形', self)
        create_circle_action = QAction('圆形', self)
        cut_action = QAction('剪切', self)
        copy_action = QAction('复制', self)
        paste_action = QAction('粘贴', self)
        delete_action = QAction('删除', self)
        rename_action = QAction('重命名', self)
        duplicate_action = QAction('生成副本', self)
        copy_uuid_action = QAction('复制UUID', self)

        create_text_action.triggered.connect(lambda: self.create_signal.emit(ITEM_TEXT))
        create_rect_action.triggered.connect(lambda: self.create_signal.emit(ITEM_RECT))
        create_circle_action.triggered.connect(lambda: self.create_signal.emit(ITEM_CIRCLE))
        cut_action.triggered.connect(self.cut_signal.emit)
        copy_action.triggered.connect(self.copy_signal.emit)
        paste_action.triggered.connect(self.paste_signal.emit)
        delete_action.triggered.connect(self.delete_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        duplicate_action.triggered.connect(self.duplicate_signal.emit)
        copy_uuid_action.triggered.connect(self.copy_uuid_signal.emit)
        
        # Create actions are for all item types.
        create_menu = QMenu(title='创建')
        self.addMenu(create_menu)
        create_menu.addAction(create_text_action)
        create_menu.addAction(create_rect_action)
        create_menu.addAction(create_circle_action)  

        # Right click on the blank area.
        if item_type is None:
            self.addAction(paste_action)

        # Right click on the root item.
        elif item_type == ITEM_ROOT:
            self.addAction(paste_action)
            self.addAction(copy_uuid_action)

        # Right click on the regular item.
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
            self.addAction(copy_uuid_action)

        self.__set_paste_action_status(paste_action)

    def __set_paste_action_status(self, paste_action):
        if self.__parent.get_clipboard_items():
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        
    def show(self, pos, item_type):
        self.clear()
        self.__add_actions(item_type)
        self.exec(pos)