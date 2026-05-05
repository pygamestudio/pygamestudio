from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T


class RunProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()
    
    def _set_widget(self):
        self.setToolTip(T.tr('scene.run_project', 'Run Project'))
        self.setIcon(QIcon(':/images/run.png'))

    def _set_signal(self):
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('sceneRunProjectBtn')
    
    def retranslate(self):
        self.setToolTip(T.tr('scene.run_project', 'Run Project'))
