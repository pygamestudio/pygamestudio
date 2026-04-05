from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


class TextEdit(QTextEdit):
    def __init__(self, inspector_window, attr, text=''):
        super().__init__()
        self._inspector_window = inspector_window
        self.setText(text)
        self.setMaximumHeight(150)
        self.textChanged.connect(self._inspector_window.set_object_text)

        