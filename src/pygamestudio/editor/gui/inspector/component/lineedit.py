from PySide6.QtWidgets import *


class NameLineEdit(QLineEdit):
    def __init__(self, text=''):
        super().__init__()
        self.setText(text)
