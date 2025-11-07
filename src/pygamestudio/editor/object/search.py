from PySide6.QtWidgets import QLineEdit


class SearchLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)