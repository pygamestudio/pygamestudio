from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal


class ObjectManagerMenu(QMenu):
    create_signal = Signal()
    cut_signal = Signal()
    copy_signal = Signal()
    paste_signal = Signal()
    delete_signal = Signal()
    rename_signal = Signal()
    move_to_group_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
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
        create_group_action = QAction('分组', self)
        cut_action = QAction('剪切', self)
        copy_action = QAction('复制', self)
        paste_action = QAction('粘贴', self)

        create_text_action.triggered.connect(self.create_signal.emit)
        create_rect_action.triggered.connect(self.create_signal.emit)
        create_circle_action.triggered.connect(self.create_signal.emit)
        create_group_action.triggered.connect(self.create_signal.emit)
        cut_action.triggered.connect(self.cut_signal.emit)
        copy_action.triggered.connect(self.copy_signal.emit)
        paste_action.triggered.connect(self.copy_signal.emit)

        create_menu = QMenu(title='创建')
        self.addMenu(create_menu)
        
        create_menu.addAction(create_text_action)
        create_menu.addAction(create_rect_action)
        create_menu.addAction(create_circle_action)
        create_menu.addSeparator()
        create_menu.addAction(create_group_action)
        
        self.addSeparator()
        self.addAction(cut_action)
        self.addAction(copy_action)
        self.addAction(paste_action)
        self.__set_paste_action_status(paste_action)

    def __add_actions_for_item(self):
        delete_action = QAction('删除', self)
        rename_action = QAction('重命名', self)
        move_to_group_action = QAction('移动到分组', self)

        delete_action.triggered.connect(self.delete_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        move_to_group_action.triggered.connect(self.move_to_group_signal.emit)

        self.addSeparator()
        self.addAction(delete_action)
        self.addAction(rename_action)
        self.addAction(move_to_group_action)

    def __set_paste_action_status(self, paste_action):
        mime_data = QApplication.clipboard().mimeData()
        paste_action.setEnabled(False)
        
    def show(self, pos, is_right_click_on_item):
        self.clear()
        self.__add_basic_actions()
        if is_right_click_on_item:
            self.__add_actions_for_item()
        self.exec(pos)
    