from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class FontFamilyComboBox(QComboBox):
    def __init__(self, inspector_container, current_text='',  attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._add_system_fonts()
        self.setCurrentText(current_text)
        self.currentTextChanged.connect(self._inspector_container.set_object_font_family)

    def _add_system_fonts(self):
        font_db = QFontDatabase()
        families = font_db.families()
        for family in families:
            self.addItem(family)        