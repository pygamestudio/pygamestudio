from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.hierarchy.tree import HierarchyTreeView
from pygamestudio.gui.hierarchy.search import SearchLineEdit
from pygamestudio.gui.hierarchy.widget import ExpandCollapseAllButton, AddItemButton


class HierarchyWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._hierarchy_tree_view = HierarchyTreeView(self, game_manager)
        self._search_line_edit = SearchLineEdit(self)
        self._add_item_button = AddItemButton(self)
        self._expand_collapse_all_button = ExpandCollapseAllButton(self)

        self._set_up()
    
    def _set_up(self):
        self._set_signal()
        self._set_layout()

    def _set_signal(self):
        self._add_item_button.add_signal.connect(self._hierarchy_tree_view.add)
        self._search_line_edit.search_signal.connect(self._hierarchy_tree_view.search)
        self._expand_collapse_all_button.clicked.connect(self._hierarchy_tree_view.expand_or_collapse_all)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._add_item_button)
        h_layout.addWidget(self._search_line_edit)
        h_layout.addWidget(self._expand_collapse_all_button)
        h_layout.setSpacing(0)
        h_layout.setContentsMargins(0, 0, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self._hierarchy_tree_view)

    @property
    def hierarchy_tree_view(self):
        return self._hierarchy_tree_view
    
    def get_ready_for_project(self):
        self._hierarchy_tree_view.get_ready_for_project()

    def clean_up(self):
        self._hierarchy_tree_view.clean_up()