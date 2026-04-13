from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pygamestudio.common.utils.path import RES_PATH


class RunProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
        self.setIcon(QIcon(str(RES_PATH / 'images/run.png')))
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