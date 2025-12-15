from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from pygamestudio.common.utils.path import RES_PATH


class SearchLineEdit(QLineEdit):
    search_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__btn = QPushButton(self)
        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        self.setTextMargins(20, 0, 0, 0)
        self.setPlaceholderText('search by name or uuid')

        self.__btn.setIcon(QIcon(str(RES_PATH / 'images/search.png')))
        self.__btn.resize(self.height(), self.height())
        self.__btn.setStyleSheet("""
            border: none;
            margin-left: 4px;
        """)

    def __set_signal(self):
        self.textChanged.connect(lambda: self.search_signal.emit(self.text().strip().lower()))

    def __set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addWidget(self.__btn)
        h_layout.addStretch(1)
        h_layout.setContentsMargins(0, 0, 0, 0)