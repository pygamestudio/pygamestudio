from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal


class ContextMenu(QMenu):
    create_signal = Signal(str)
    cut_signal = Signal()
    copy_signal = Signal()
    paste_signal = Signal()
    delete_signal = Signal()
    rename_signal = Signal()
    copy_uuid_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self.__parent = parent
        self.__setup()

    def __setup(self):
       self.__set_widget()
       self.__set_signal()

    def __set_widget(self):
        ...

    def __set_signal(self):
        ...

    def __add_basic_actions(self):
        create_text_action = QAction('文本', self)
        create_rect_action = QAction('矩形', self)
        create_circle_action = QAction('圆形', self)
        cut_action = QAction('剪切', self)
        copy_action = QAction('复制', self)
        paste_action = QAction('粘贴', self)

        create_text_action.triggered.connect(lambda: self.create_signal.emit('TEXT'))
        create_rect_action.triggered.connect(lambda: self.create_signal.emit('RECT'))
        create_circle_action.triggered.connect(lambda: self.create_signal.emit('CIRCLE'))
        cut_action.triggered.connect(self.cut_signal.emit)
        copy_action.triggered.connect(self.copy_signal.emit)
        paste_action.triggered.connect(self.paste_signal.emit)
        
        create_menu = QMenu(title='创建')
        self.addMenu(create_menu)
        
        create_menu.addAction(create_text_action)
        create_menu.addAction(create_rect_action)
        create_menu.addAction(create_circle_action)        
        self.addSeparator()
        self.addAction(cut_action)
        self.addAction(copy_action)
        self.addAction(paste_action)
        self.__set_paste_action_status(paste_action)

    def __add_actions_for_item(self):
        delete_action = QAction('删除', self)
        rename_action = QAction('重命名', self)
        copy_uuid_action = QAction('复制UUID', self)

        delete_action.triggered.connect(self.delete_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        copy_uuid_action.triggered.connect(self.copy_uuid_signal.emit)

        self.addSeparator()
        self.addAction(delete_action)
        self.addAction(rename_action)
        self.addSeparator()
        self.addAction(copy_uuid_action)

    def __set_paste_action_status(self, paste_action):
        if self.__parent.get_clipboard_items():
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        
    def show(self, pos, is_right_click_on_item):
        self.clear()
        self.__add_basic_actions()
        if is_right_click_on_item:
            self.__add_actions_for_item()
        self.exec(pos)