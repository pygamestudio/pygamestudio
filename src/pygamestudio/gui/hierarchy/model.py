from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


class HierarchySortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, tree_view, standard_model):
        super().__init__()
        self._tree_view = tree_view
        self._standard_model = standard_model

    # def filterAcceptsRow(self, source_row, source_parent):
    #     filter_text = self.filterRegularExpression().pattern().lower().replace('\\', '')
    #     if not filter_text:
    #         return True

    #     item = self._standard_model.itemFromIndex(self._standard_model.index(source_row, 0, source_parent))
    #     item_data = item.data(Qt.ItemDataRole.UserRole+1)
    #     return filter_text in item.text().lower() or filter_text in item_data['uuid'].lower()


