from PySide6.QtWidgets import *
from pygamestudio.gui.asset.widget import *
from pygamestudio.gui.asset.tree import AssetTreeView
from pygamestudio.gui.asset.search import SearchLineEdit


class AssetWindow(QWidget):
    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._asset_tree_view = AssetTreeView(self, game_manager)
        self._search_line_edit = SearchLineEdit(self)

        self._add_asset_button = AddAssetButton(self)
        self._sort_asset_button = SortAssetButton(self)
        self._refresh_asset_button = RefreshAssetButton(self)

        self._set_up()
    
    def _set_up(self):
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_signal(self):
        self._search_line_edit.search_signal.connect(self._asset_tree_view.search)

        self._add_asset_button.add_signal.connect(self._asset_tree_view.add)
        self._sort_asset_button.sort_signal.connect(self._asset_tree_view.set_sort_type)
        self._refresh_asset_button.clicked.connect(self._asset_tree_view.refresh)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._add_asset_button)
        h_layout.addWidget(self._sort_asset_button)
        h_layout.addWidget(self._refresh_asset_button)
        h_layout.addWidget(self._search_line_edit)
        h_layout.setContentsMargins(0, 4, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self._asset_tree_view)
        v_layout.setSpacing(5)
        v_layout.setContentsMargins(0, 0, 0, 0)

    def _set_object_name(self):
        self.setObjectName('asset')

    def get_ready_for_project(self):
        self._asset_tree_view.get_ready_for_project()

    def clean_up(self):
        self._search_line_edit.clear()
        self._asset_tree_view.clean_up()