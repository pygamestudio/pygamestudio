from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.inspector.widget import *
from pygamestudio.gui.inspector.container import Container


class InspectorWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._select_previous_object_btn = SelectPreviousObjectButton()
        self._select_next_object_btn = SelectNextObjectButton()
        self._container = Container(self, game_manager)
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setMinimumWidth(270)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._select_previous_object_btn)
        h_layout.addWidget(self._select_next_object_btn)
        h_layout.addStretch(1)
        h_layout.setContentsMargins(0, 4, 0, 0)
        v_layout.addLayout(h_layout)
        v_layout.addWidget(self._container)
        v_layout.setSpacing(5)
        v_layout.setContentsMargins(0, 0, 0, 0)

    def _set_object_name(self):
        self.setObjectName('inspector')

    def get_ready_for_project(self):
        self._container.get_ready_for_project()
        
    def clean_up(self):
        self._container.clean_up()