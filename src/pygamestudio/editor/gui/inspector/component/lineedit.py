from PySide6.QtWidgets import *


class NameLineEdit(QLineEdit):
    def __init__(self, inspector_window, attr, text=''):
        super().__init__()
        self._inspector_window = inspector_window
        self.setText(text)

        self.textChanged.connect(self._inspector_window.rename)