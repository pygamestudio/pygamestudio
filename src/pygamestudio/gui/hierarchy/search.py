from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.i18n.translator import Translator as T


class SearchLineEdit(QLineEdit):
    search_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_icon = QLabel(self)
        self._set_up()
    
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setPlaceholderText(T.tr('hierarchy.search_placeholder', 'Search by name or uuid'))

        self._search_icon.setFixedSize(14, 14)
        pixmap = QPixmap(str(RES_PATH / 'images/search.png'))
        pixmap = pixmap.scaled(self._search_icon.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._search_icon.setPixmap(pixmap)

    def _set_signal(self):
        self.textChanged.connect(lambda: self.search_signal.emit(self.text().strip().lower()))
        T.add_observer(self)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addWidget(self._search_icon)
        h_layout.addStretch(1)
        h_layout.setContentsMargins(5, 0, 0, 0)

    def _set_object_name(self):
        self.setObjectName('hierarchySearchLineEdit')

    def retranslate(self):
        self.setPlaceholderText(T.tr('hierarchy.search_placeholder', 'Search by name or uuid'))