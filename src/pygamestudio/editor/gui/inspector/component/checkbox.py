from PySide6.QtWidgets import *


class VisibilityCheckBox(QCheckBox):
    def __init__(self, is_checked=True):
        super().__init__()
        self.setChecked(is_checked)