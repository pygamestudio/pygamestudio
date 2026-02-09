from PySide6.QtWidgets import *


class PropertyLabel(QLabel):
    def __init__(self, text=''):
        super().__init__()
        self.setText(text)
        