from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.color import normalise_rgba


class ColorPicker(QPushButton):
    def __init__(self, inspector_container, color_rgba=(255, 255, 255, 255), attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        self._current_color_rgba = color_rgba
        self.set_color(color_rgba)

        self.clicked.connect(self._on_color_picker_clicked)

    def set_color(self, color_rgba):
        """Show ``color_rgba`` on the swatch.

        The stored value is kept as it is (the popup gets the object's exact
        colour), but the swatch itself is painted from a normalised RGBA - a
        colour without an alpha channel must not end up using its blue channel
        as the opacity.
        """
        self._current_color_rgba = color_rgba
        r, g, b, a = normalise_rgba(color_rgba)
        self.setStyleSheet(f"""
        QPushButton {{
            background-color: rgba{r, g, b, round(a/255, 1)};
            border: 2px solid #3c3c3c;
            border-radius: 5px;
        }}

        QPushButton:hover {{
            border: 2px solid #007acc;
        }}
        """)
    
    def _on_color_picker_clicked(self):
        self._inspector_container.show_color_picker(self._current_color_rgba, self._attr)