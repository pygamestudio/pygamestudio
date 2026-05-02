from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T


class ColorPicker(QPushButton):
    def __init__(self, inspector_container, color_hex='#ffffff', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.set_color(color_hex)

        self.clicked.connect(self._on_color_picker_clicked)

    def set_color(self, color_hex):
        self.setStyleSheet(f"""
        QPushButton {{
            background-color: {color_hex};
            border: 2px solid #3c3c3c;
            border-radius: 5px;
        }}

        QPushButton:hover {{
            border: 2px solid #007acc;
        }}
        """)
    
    def _on_color_picker_clicked(self):
        color = QColorDialog.getColor(title=T.tr('inspector.select_color'), parent=QApplication.activeWindow())
        if color.isValid():
            self._inspector_container.set_object_color(color.name())