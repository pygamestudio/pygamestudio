from PySide6.QtWidgets import *


class PropertyLabel(QLabel):
    def __init__(self, inspector_window, text=''):
        super().__init__()
        self._inspector_window = inspector_window
        self.setText(text)
        