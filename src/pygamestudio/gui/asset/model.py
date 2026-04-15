from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
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
        self._excluded_extensions = ['.pygs']

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

    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        file_info = source_model.fileInfo(index)

        if file_info.isDir():
            return True
        
        file_name = file_info.fileName()
        if self._excluded_extensions:
            for ext in self._excluded_extensions:
                if file_name.lower().endswith(ext.lower()):
                    return False
        
        return True