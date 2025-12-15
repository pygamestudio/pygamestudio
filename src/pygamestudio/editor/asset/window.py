from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from pygamestudio.editor.asset.tree import AssetTreeView
from pygamestudio.editor.asset.search import SearchLineEdit
from pygamestudio.editor.asset.widget import *


class AssetWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__asset_tree_view = AssetTreeView(self)
        self.__search_line_edit = SearchLineEdit(self)

        self.__create_asset_button = CreateAssetButton(self)
        self.__sort_asset_button = SortAssetButton(self)
        self.__refresh_asset_button = RefreshAssetButton(self)

        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        ...

    def __set_signal(self):
        ...
        self.__search_line_edit.search_signal.connect(self.__asset_tree_view.search)

        self.__create_asset_button.create_signal.connect(self.__asset_tree_view.create)
        self.__sort_asset_button.sort_signal.connect(self.__asset_tree_view.set_sort_type)
        self.__refresh_asset_button.clicked.connect(self.__asset_tree_view.refresh)

    def __set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self.__create_asset_button)
        h_layout.addWidget(self.__sort_asset_button)
        h_layout.addWidget(self.__search_line_edit)
        h_layout.addWidget(self.__refresh_asset_button)
        h_layout.setSpacing(0)
        h_layout.setContentsMargins(0, 0, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self.__asset_tree_view)
