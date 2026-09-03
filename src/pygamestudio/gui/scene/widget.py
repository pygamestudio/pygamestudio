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
        self.setToolTip(T.tr('scene.run', 'Run'))
        self.setIcon(QIcon(':/images/run.png'))

    def _set_signal(self):
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('sceneRunProjectBtn')
    
    def retranslate(self):
        self.setToolTip(T.tr('scene.run', 'Run'))


class RefreshButton(QPushButton):
    """Refresh button for the scene editor.

    A single click refreshes once; holding the button down refreshes
    repeatedly (a short timer keeps firing until the mouse is released).
    The actual refresh action is exposed through ``refresh_requested``.
    """

    refresh_requested = Signal()

    def __init__(self, repeat_interval_ms=10):
        super().__init__()
        self._repeat_interval_ms = repeat_interval_ms
        self._repeat_timer = QTimer(self)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()

    def _set_widget(self):
        self.setToolTip(T.tr('scene.refresh', 'Refresh'))
        self.setIcon(QIcon(':/images/refresh.png'))

    def _set_signal(self):
        T.add_observer(self)
        self._repeat_timer.setInterval(self._repeat_interval_ms)
        self._repeat_timer.timeout.connect(self.refresh_requested.emit)
        self.pressed.connect(self._on_pressed)
        self.released.connect(self._on_released)

    def _set_object_name(self):
        self.setObjectName('sceneRefreshBtn')

    def _on_pressed(self):
        # Refresh immediately on press, then keep going while held down.
        self.refresh_requested.emit()
        self._repeat_timer.start()

    def _on_released(self):
        self._repeat_timer.stop()

    def retranslate(self):
        self.setToolTip(T.tr('scene.refresh', 'Refresh'))
