from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.gui.asset.type import *


class AssetFileSystemModel(QFileSystemModel):
    def __init__(self, parent):
        super().__init__()
        self._tree_view = parent

    def hasChildren(self, parent):
        file_info = self.fileInfo(parent)
        dir = QDir(file_info.absoluteFilePath())
        return bool(dir.entryList(self.filter()))
    

class AssetSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent):
        super().__init__()
        self._tree_view = parent
    
    def lessThan(self, source_left, source_right):
        source_model = self.sourceModel()

        if source_model.isDir(source_left) and not source_model.isDir(source_right):
            return True
        if not source_model.isDir(source_left) and source_model.isDir(source_right):
            return False

        sort_type = self._tree_view.get_sort_type()
        left_file_info = source_model.fileInfo(source_left)
        right_file_info = source_model.fileInfo(source_right)

        if sort_type == SORT_BY_NAME_ASC:
            left_value = left_file_info.fileName().lower()
            right_value = right_file_info.fileName().lower()
            return left_value < right_value
        elif sort_type == SORT_BY_NAME_DESC:
            left_value = left_file_info.fileName().lower()
            right_value = right_file_info.fileName().lower()
            return left_value > right_value
        elif sort_type == SORT_BY_TYPE_ASC:
            left_value = left_file_info.suffix().lower()
            right_value = right_file_info.suffix().lower()
            return left_value < right_value
        elif sort_type == SORT_BY_TYPE_DESC:
            left_value = left_file_info.suffix().lower()
            right_value = right_file_info.suffix().lower()
            return left_value > right_value
        elif sort_type == SORT_BY_SIZE_ASC:
            left_value = left_file_info.size()
            right_value = right_file_info.size()
            return left_value < right_value
        elif sort_type == SORT_BY_SIZE_DESC:
            left_value = left_file_info.size()
            right_value = right_file_info.size()
            return left_value > right_value
        elif sort_type == SORT_BY_TIME_ASC:
            left_value = left_file_info.lastModified().toSecsSinceEpoch()
            right_value = right_file_info.lastModified().toSecsSinceEpoch()
            return left_value < right_value
        elif sort_type == SORT_BY_TIME_DESC:
            left_value = left_file_info.lastModified().toSecsSinceEpoch()
            right_value = right_file_info.lastModified().toSecsSinceEpoch()
            return left_value > right_value

        

    # def setFilterRegularExpression(self, pattern):
    #     super().setFilterRegularExpression(pattern)

    # def filterAcceptsRow(self, source_row, source_parent):
    #     source_index = self.sourceModel().index(source_row, 0, source_parent)

        
    #     if super().filterAcceptsRow(source_row, source_parent):
    #         self.matching_items.add(source_index)
    #         return True
    #     else:

    #         child_count = self.sourceModel().rowCount(source_index)
    #         for child_row in range(child_count):
    #             if self.filterAcceptsRow(child_row, source_index):
    #                 self.matching_items.add(source_index)
    #                 return True
                
    #     return False
        # item_name = self.sourceModel().fileName(source_index)


        # child_count = self.sourceModel().rowCount(source_index)
        # for child_row in range(child_count):
        #     self.filterAcceptsRow(child_row, source_index)

        # if self._pattern.match(item_name).hasMatch():
        #     print(111)
        #     self._tree_view.setExpanded(source_index, True)
        #     print(self._tree_view.isExpanded(source_index))
        #     return True
        # else:
        #     return False

        # return self._pattern.match(item_name).hasMatch()