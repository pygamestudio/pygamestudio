from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T


class ColorPicker(QPushButton):
    def __init__(self, inspector_container, color_rgba=(255, 255, 255, 255), attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._current_color_rgba = color_rgba
        self.set_color(color_rgba)

        self.clicked.connect(self._on_color_picker_clicked)

    def set_color(self, color_rgba):
        self._current_color_rgba = color_rgba
        self.setStyleSheet(f"""
        QPushButton {{
            background-color: rgba{color_rgba[0], color_rgba[1], color_rgba[2], round(color_rgba[-1]/255, 1)};
            border: 2px solid #3c3c3c;
            border-radius: 5px;
        }}

        QPushButton:hover {{
            border: 2px solid #007acc;
        }}
        """)
    
    def _on_color_picker_clicked(self):
        self._inspector_container.show_color_picker(self._current_color_rgba)