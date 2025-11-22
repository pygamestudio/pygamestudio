from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QAbstractItemView, QHeaderView
from PySide6.QtCore import Qt, QTimeLine, QSize, Signal
from PySide6.QtGui import QIcon, QColor, QUndoStack

from pygamestudio.editor.asset.menu import ContextMenu
from pygamestudio.editor.asset.command import *

from pygamestudio.editor.asset.search import SEARCH_BY_NAME, SEARCH_BY_UUID
import uuid
import copy
import shutil
from pathlib import Path


class AssetTreeWidget(QTreeWidget):
    trigger_search_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        ...

    def __set_signal(self):
        ...

    def __set_layout(self):
        ...    

    def __create_file(self, file_type):
        ...