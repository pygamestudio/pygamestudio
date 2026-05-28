import os
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.path import RES_PATH


class NameLineEdit(QLineEdit):
    def __init__(self, inspector_container, text='',  attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._text = text
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setText(self._text)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def _set_signal(self):
        self.textChanged.connect(self._inspector_container.rename_object)


class ImagePathLineEdit(QLineEdit):
    def __init__(self, inspector_container, image_path='',  attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._browse_button = QPushButton(self)
        self._image_path = Path(image_path)
        self._set_up()
        print(self._image_path)

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setTextMargins(0, 0, 24, 0)
        self.setCursorPosition(0)
        self.setReadOnly(True)
        
        # Use the default image if there is no image set current object
        path = self._image_path
        if str(path) == '.':
            path = RES_PATH / 'images/image_placeholder.png'
            self.setToolTip(path.as_posix())
            self.setText(path.name)
        else:
            self.setToolTip(path.as_posix())
            self.setText(path.name)

        # Make the text red if the image does not exist.
        if not path.exists():
            self.setStyleSheet('color: rgb(255, 0, 0);')

        self._browse_button.setFixedSize(18, 18)
        self._browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/browse.png')
        scaled_pixmap = pixmap.scaled(self._browse_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._browse_button.setIcon(QIcon(scaled_pixmap))

    def _set_signal(self):
        self._browse_button.clicked.connect(self._choose_image)
        self.textChanged.connect(self._inspector_container.set_object_image_path)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addStretch(1)
        h_layout.addWidget(self._browse_button)
        h_layout.setContentsMargins(0, 0, 5, 0)

    def _choose_image(self):
        image_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_image', 'Select Image'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), 'Format (*png *.jpg *jpeg *.gif *.bmp *.lbm *.pcx *.qoi *.svg *.tga *.tiff *.webp *.xpm *.xcf)')
        if not image_path:
            return

        self._image_path = Path(image_path)
        self.setToolTip(self._image_path.as_posix())
        self._inspector_container.set_object_image_path()

        self.setStyleSheet('')
