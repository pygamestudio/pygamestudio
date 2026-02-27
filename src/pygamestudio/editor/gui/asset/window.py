from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from pygamestudio.editor.gui.asset.tree import AssetTreeView
from pygamestudio.editor.gui.asset.search import SearchLineEdit
from pygamestudio.editor.gui.asset.widget import *


class AssetWindow(QWidget):
    def __init__(self, parent=None, object_manager=None):
        super().__init__(parent)
        self._asset_tree_view = AssetTreeView(self, object_manager)
        self._search_line_edit = SearchLineEdit(self)

        self._create_asset_button = CreateAssetButton(self)
        self._sort_asset_button = SortAssetButton(self)
        self._refresh_asset_button = RefreshAssetButton(self)

        self._set_up()
    
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        ...

    def _set_signal(self):
        ...
        self._search_line_edit.search_signal.connect(self._asset_tree_view.search)

        self._create_asset_button.create_signal.connect(self._asset_tree_view.create)
        self._sort_asset_button.sort_signal.connect(self._asset_tree_view.set_sort_type)
        self._refresh_asset_button.clicked.connect(self._asset_tree_view.refresh)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._create_asset_button)
        h_layout.addWidget(self._sort_asset_button)
        h_layout.addWidget(self._search_line_edit)
        h_layout.addWidget(self._refresh_asset_button)
        h_layout.setSpacing(0)
        h_layout.setContentsMargins(0, 0, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self._asset_tree_view)
