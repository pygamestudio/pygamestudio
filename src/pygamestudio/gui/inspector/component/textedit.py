from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class TextEdit(QTextEdit):
    def __init__(self, inspector_container, text='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._text = text
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setText(self._text)
        self.setMaximumHeight(150)

    def _set_signal(self):
        self.textChanged.connect(self._inspector_container.set_object_text)

    def contextMenuEvent(self, e):
        pass