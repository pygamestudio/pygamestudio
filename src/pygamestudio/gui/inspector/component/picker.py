from PySide6.QtWidgets import *


class ColorPicker(QPushButton):
    def __init__(self, inspector_window, color_hex='#ffffff', attr=''):
        super().__init__()
        self._inspector_window = inspector_window
        self.set_color(color_hex)

        self.clicked.connect(self._on_color_picker_clicked)

    def set_color(self, color_hex):
        self.setStyleSheet(f"""
        QPushButton {{
            background-color: {color_hex};
            border: 2px solid #34495e;
            border-radius: 4px;
        }}
        """)
    
    def _on_color_picker_clicked(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self._inspector_window.set_object_color(color.name())