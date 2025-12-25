from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pygamestudio.common.utils.path import RES_PATH
from pathlib import Path


class AssetTreeWidgetDelegate(QStyledItemDelegate):
    def __init__(self, tree_view=None, proxy_model=None, file_model=None):
        super().__init__(tree_view)
        self.__tree_view = tree_view
        self.__proxy_model = proxy_model
        self.__file_model = file_model

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            text = index.data(Qt.ItemDataRole.DisplayRole)
            last_dot = text.rfind('.')
            if last_dot > 0:
                QTimer.singleShot(0, lambda: editor.setSelection(0, last_dot))
                        
        return editor

    def paint(self, painter, option, index):
        clipboard_content = self.__tree_view.get_clipboard_content()
        index_path = Path(self.__file_model.filePath(self.__proxy_model.mapToSource(index)))

        painter.setOpacity(1)
        if self.__tree_view.is_cut():
            if index_path in clipboard_content:
                painter.setOpacity(0.5)
        
        if index_path in self.__tree_view.get_highlight_indexes_paths():
            painter.setPen(QPen(QColor(0, 255, 255, 100)))
            painter.setBrush(QColor(0, 255, 255, 100))
            painter.drawRect(option.rect)

        return super().paint(painter, option, index)

