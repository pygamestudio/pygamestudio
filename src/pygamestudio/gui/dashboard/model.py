from datetime import datetime
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.dashboard.type import *


class DashboardSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent):
        super().__init__()
        self._list_view = parent
    
    def lessThan(self, source_left, source_right):
        sort_type = self._list_view.get_sort_type()

        left_time = source_left.data(self._list_view.ProjectDateRole)
        left_name = source_left.data(self._list_view.ProjectNameRole)
        left_path = source_left.data(self._list_view.ProjectPathRole)
        right_time = source_right.data(self._list_view.ProjectDateRole)
        right_name = source_right.data(self._list_view.ProjectNameRole)
        right_path = source_right.data(self._list_view.ProjectPathRole)

        if sort_type == SORT_BY_TIME:
            return datetime.strptime(left_time, '%Y-%m-%d %H:%M:%S') > datetime.strptime(right_time, '%Y-%m-%d %H:%M:%S')
        elif sort_type == SORT_BY_NAME:
            return left_name < right_name
        elif sort_type == SORT_BY_PATH:
            return left_path < right_path
        
    def filterAcceptsRow(self, source_row, source_parent):
        source_index = self.sourceModel().index(source_row, 0, source_parent)
        project_name = source_index.data(self._list_view.ProjectNameRole)
        filter_text = self.filterRegularExpression().pattern().lower().replace('\\', '')

        if filter_text in project_name:
            return True
        return False
       