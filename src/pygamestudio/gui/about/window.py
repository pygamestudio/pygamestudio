from datetime import datetime
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.config import *
from pygamestudio.common.utils.constant import *
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.i18n.translator import Translator as T


class AboutBody(QWidget):
    def __init__(self):
        super().__init__()
        self._logo_label = QLabel()
        self._version_label = QLabel()
        self._copyright_label = QLabel()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self._logo_label.setFixedSize(100, 100)
        pixmap = QPixmap(str(RES_PATH / 'images/logo.png'))
        scaled_pixmap = pixmap.scaled(self._logo_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._logo_label.setPixmap(scaled_pixmap)

        self._version_label.setText(T.tr('about.version', 'Version {}').format(VERSION))
        self._copyright_label.setText(f'Pygame Studio © Ren Lushun (Louis Ren) {datetime.now().year} All rights reserved')

    def _set_signal(self):
        T.add_observer(self)

    def _set_layout(self):
        v_layout = QVBoxLayout(self)
        v_layout.addStretch(1)
        v_layout.addWidget(self._logo_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v_layout.addWidget(self._version_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v_layout.addWidget(self._copyright_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v_layout.addStretch(1)

    def _set_object_name(self):
        self._copyright_label.setObjectName('aboutCopyrightLabel')

    def retranslate(self):
        self._version_label.setText(T.tr('about.version', 'Version {}').format(VERSION))


class AboutWindow(WindowBase):
    def __init__(self):
        super().__init__()
        self._about_body = AboutBody()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.resize(400, 200)
        self.set_window_body(self._about_body)
        self.window_title.set_title_name(T.tr('menu.about_pygamestudio', 'About Pygame Studio'))

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.window_title.set_title_name(T.tr('menu.about_pygamestudio', 'About Pygame Studio'))