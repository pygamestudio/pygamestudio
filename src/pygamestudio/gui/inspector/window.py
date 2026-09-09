from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.inspector.widget import *
from pygamestudio.gui.inspector.container import Container


class InspectorWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._select_previous_object_button = SelectPreviousObjectButton()
        self._select_next_object_button = SelectNextObjectButton()
        self._container = Container(self, game_manager)
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setMinimumWidth(270)
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName('inspectorScrollArea')
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setMinimumWidth(270)
        # A long property list must scroll instead of being clipped.
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setWidget(self._container)
    
    def _set_signal(self):
        self._select_previous_object_button.clicked.connect(self._container.select_previous_object)
        self._select_next_object_button.clicked.connect(self._container.select_next_object)
        self._container.selection_history_changed.connect(self._update_select_buttons)
        self._container.selection_index_changed.connect(self._update_select_buttons)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._select_previous_object_button)
        h_layout.addWidget(self._select_next_object_button)
        h_layout.addStretch(1)
        h_layout.setContentsMargins(0, 4, 0, 0)
        v_layout.addLayout(h_layout)
        v_layout.addWidget(self._scroll_area, 1)
        v_layout.setSpacing(5)
        v_layout.setContentsMargins(0, 0, 0, 0)

    def _set_object_name(self):
        self.setObjectName('inspector')

    def _update_select_buttons(self, selection_history_length, current_index):
        if not selection_history_length:
            self._select_previous_object_button.set_disabled()
            self._select_next_object_button.set_disabled()
            return
        
        if current_index <= 0:
            self._select_previous_object_button.set_disabled()
        else:
            self._select_previous_object_button.set_enabled()

        if current_index >= selection_history_length - 1:
            self._select_next_object_button.set_disabled()
        else:
            self._select_next_object_button.set_enabled()

    def get_ready_for_project(self):
        self._container.get_ready_for_project()
        
    def clean_up(self):
        self._container.clean_up()