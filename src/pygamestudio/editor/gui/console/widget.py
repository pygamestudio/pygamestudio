from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.editor.gui.console.type import *
from pygamestudio.common.utils.path import RES_PATH


class LogCheckBox(QWidget):
    check_box_clicked = Signal(bool)

    def __init__(self, parent=None, log_level=INFO):
        super().__init__(parent)
        self._log_level = log_level
        self._check_box = QCheckBox()
        self._log_icon = QLabel()
        self._log_text = QLabel()
        self._setup()
    
    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self._check_box.setChecked(True)
        self._log_text.setText('0')
        self._set_icon()

    def _set_signal(self):
        self._check_box.clicked.connect(lambda: self.check_box_clicked.emit(self._check_box.isChecked()))

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addWidget(self._check_box)
        h_layout.addWidget(self._log_icon)
        h_layout.addWidget(self._log_text)

    def _set_icon(self):
        pixmap = QPixmap()
        if self._log_level == ERROR:
            pixmap = QPixmap(RES_PATH/'images/error.png')
        elif self._log_level == WARNING:
            pixmap = QPixmap(RES_PATH/'images/warning.png')
        else:
            pixmap = QPixmap(RES_PATH/'images/info.png')
        pixmap = pixmap.scaled(QSize(18, 18))
        self._log_icon.setPixmap(pixmap)

    def increase_one_log_num(self):
        num = int(self._log_text.text())
        self._log_text.setText(str(num+1))

    def reset_log_num(self):
        self._log_text.setText('0')


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