from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.common.i18n.translator import Translator as T


class SelectPreviousObjectButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setToolTip(T.tr('inspector.select_previous', 'Select Previous Object'))
        self.setIcon(QIcon(':/images/left_arrow.png'))

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setToolTip(T.tr('inspector.select_previous_object', 'Select Previous Object'))


class SelectNextObjectButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setToolTip(T.tr('inspector.select_next', 'Select Next Object'))
        self.setIcon(QIcon(':/images/right_arrow.png'))

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setToolTip(T.tr('inspector.select_next_object', 'Select Next Object'))
