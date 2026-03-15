from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.common.utils.path import RES_PATH


class CreateProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
        self.setText('创建')
        self.setIcon(QIcon(str(RES_PATH / 'images/create.png')))
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


class ImportProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
        self.setText('导入')
        self.setIcon(QIcon(str(RES_PATH / 'images/folder.png')))
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


class DeleteProjectButton(QPushButton):
    def __init__(self):
        super().__init__()


class RenameProjectButton(QPushButton):
    def __init__(self):
        super().__init__()


class OpenProjectButton(QPushButton):
    def __init__(self):
        super().__init__()


class SortTypeComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.addItems(['最近编辑', '名称', '路径'])