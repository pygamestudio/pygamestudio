from PySide6.QtWidgets import *


class PosSpinBox(QSpinBox):
    def __init__(self, value):
        super().__init__()
        self.setValue(value)


class SizeSpinBox(QSpinBox):
    def __init__(self, value):
        super().__init__()
        self.setValue(value)