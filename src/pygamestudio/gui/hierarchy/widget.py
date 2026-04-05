from PySide6.QtWidgets import QPushButton, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal

from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.game.object.type import *


class ExpandCollapseAllButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
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


class AddItemButton(QPushButton):
    add_signal = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
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
        self._show_context_menu(event.pos())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu()
        # add_line_action = QAction('直线', self)
        add_rect_action = QAction('矩形', self)
        add_ellipse_action = QAction('椭圆', self)
        add_text_action = QAction('文本', self)

        # add_line_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_LINE))
        add_rect_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_RECT))
        add_ellipse_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_ELLIPSE))
        add_text_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_TEXT))

        add_shape_sub_menu = QMenu(title='形状')
        add_ui_sub_menu = QMenu(title='UI')
        menu.addMenu(add_shape_sub_menu)
        menu.addMenu(add_ui_sub_menu)

        # add_shape_sub_menu.addAction(add_line_action)
        add_shape_sub_menu.addAction(add_rect_action)
        add_shape_sub_menu.addAction(add_ellipse_action)
        add_ui_sub_menu.addAction(add_text_action)

        menu.exec(self.mapToGlobal(pos))

