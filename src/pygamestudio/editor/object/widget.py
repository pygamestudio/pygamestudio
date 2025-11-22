from PySide6.QtWidgets import QPushButton, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal

from pygamestudio.editor.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ExpandCollapseAllButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__set_up()

    def __set_up(self):
        self.__set_widget()
    
    def __set_widget(self):
        self.setIcon(QIcon(str(RES_PATH / 'images/expand.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }    

        QPushButton:pressed {
            background-color: cyan;
        }                            
        """)


class CreateItemButton(QPushButton):
    create_signal = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__set_up()

    def __set_up(self):
        self.__set_widget()
    
    def __set_widget(self):
        self.setIcon(QIcon(str(RES_PATH / 'images/create.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }                       
        """)

    def mousePressEvent(self, event):
        self.__show_context_menu(event.pos())
        super().mousePressEvent(event)

    def __show_context_menu(self, pos):
        menu = QMenu()
        create_text_action = QAction('文本', self)
        create_rect_action = QAction('矩形', self)
        create_circle_action = QAction('圆形', self)

        create_text_action.triggered.connect(lambda: self.create_signal.emit(ITEM_TEXT))
        create_rect_action.triggered.connect(lambda: self.create_signal.emit(ITEM_RECT))
        create_circle_action.triggered.connect(lambda: self.create_signal.emit(ITEM_CIRCLE))

        menu.addAction(create_text_action)
        menu.addAction(create_rect_action)
        menu.addAction(create_circle_action)

        menu.exec(self.mapToGlobal(pos))

