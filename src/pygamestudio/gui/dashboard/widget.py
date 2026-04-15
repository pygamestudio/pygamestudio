from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.i18n.translator import Translator as T


class CreateProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
    
    def _set_widget(self):
        self.setText(T.tr('dashboard.create', 'Create'))
        self.setIcon(QIcon(str(RES_PATH / 'images/create.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }    

        QPushButton:pressed {
            background-color: cyan;
        }                            
        """)

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setText(T.tr('dashboard.create', 'Create'))


class ImportProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setText(T.tr('dashboard.import', 'Import'))
        self.setIcon(QIcon(str(RES_PATH / 'images/folder.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }    

        QPushButton:pressed {
            background-color: cyan;
        }                            
        """)

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setText(T.tr('dashboard.import', 'Import'))


class SortTypeComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.addItems([T.tr('dashboard.sort_by_time', 'Sort by Time'), T.tr('dashboard.sort_by_name', 'Sort by Name'), T.tr('dashboard.sort_by_path', 'Sort by Path')])

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.clear()
        self.addItems([T.tr('dashboard.sort_by_time', 'Sort by Time'), T.tr('dashboard.sort_by_name', 'Sort by Name'), T.tr('dashboard.sort_by_path', 'Sort by Path')])
