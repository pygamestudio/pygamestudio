from PySide6.QtWidgets import *


class ColorPicker(QPushButton):
    def __init__(self, color_hex='#ffffff'):
        super().__init__()
        self.setStyleSheet(f"""
        QPushButton {{
            background-color: {color_hex};
            border: 2px solid #34495e;
            border-radius: 4px;
        }}
        """)