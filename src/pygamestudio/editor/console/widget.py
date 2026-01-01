from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.editor.console.type import *
from pygamestudio.common.utils.path import RES_PATH


class LogCheckBox(QWidget):
    check_box_clicked = Signal(bool)

    def __init__(self, parent=None, log_level=INFO):
        super().__init__(parent)
        self.__log_level = log_level
        self.__check_box = QCheckBox()
        self.__log_icon = QLabel()
        self.__log_text = QLabel()
        self.__setup()
    
    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        self.__check_box.setChecked(True)
        self.__log_text.setText('0')
        self.__set_icon()

    def __set_signal(self):
        self.__check_box.clicked.connect(lambda: self.check_box_clicked.emit(self.__check_box.isChecked()))

    def __set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addWidget(self.__check_box)
        h_layout.addWidget(self.__log_icon)
        h_layout.addWidget(self.__log_text)

    def __set_icon(self):
        pixmap = QPixmap()
        if self.__log_level == ERROR:
            pixmap = QPixmap(RES_PATH/'images/error.png')
        elif self.__log_level == WARNING:
            pixmap = QPixmap(RES_PATH/'images/warning.png')
        else:
            pixmap = QPixmap(RES_PATH/'images/info.png')
        pixmap = pixmap.scaled(QSize(18, 18))
        self.__log_icon.setPixmap(pixmap)

    def increase_one_log_num(self):
        num = int(self.__log_text.text())
        self.__log_text.setText(str(num+1))

    def reset_log_num(self):
        self.__log_text.setText('0')


class ClearButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QIcon(str(RES_PATH/'images/clear.png')))
        self.setText('清空')
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