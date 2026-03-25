from PySide6.QtWidgets import *
from PySide6.QtCore import *


class VisibilityCheckBox(QCheckBox):
    def __init__(self, inspector_window, attr, is_checked=True):
        super().__init__()
        self._inspector_window = inspector_window
        self.setChecked(is_checked)

        self.checkStateChanged.connect(self._on_check_state_changed)
    
    def _on_check_state_changed(self, check_state):
        if check_state == Qt.CheckState.Checked:
            self._inspector_window.show_object()
        else:
            self._inspector_window.hide_object()