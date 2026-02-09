from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from pygamestudio.common.utils.path import RES_PATH


class SearchLineEdit(QLineEdit):
    search_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._btn = QPushButton(self)
        self._set_up()
    
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setTextMargins(20, 0, 0, 0)
        self.setPlaceholderText('search by name or uuid')

        self._btn.setIcon(QIcon(str(RES_PATH / 'images/search.png')))
        self._btn.resize(self.height(), self.height())
        self._btn.setStyleSheet("""
            border: none;
            margin-left: 4px;
        """)

    def _set_signal(self):
        self.textChanged.connect(lambda: self.search_signal.emit(self.text().strip().lower()))

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addWidget(self._btn)
        h_layout.addStretch(1)
        h_layout.setContentsMargins(0, 0, 0, 0)