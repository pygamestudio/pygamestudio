import os
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.i18n.translator import Translator as T


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
        self._delete_button = QPushButton(self)
        self._image_path = Path(image_path)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setTextMargins(0, 0, 24, 0)
        self.setReadOnly(True)
        
        if not str(self._image_path) == '.':
            project_path = Path(get_project_path())
            image_absolute_path = project_path / self._image_path
            self.setToolTip(self._image_path.as_posix())
            self.setText(self._image_path.name)

            if not image_absolute_path.exists():
                self.setStyleSheet('color: rgb(255, 0, 0);')

        self._browse_button.setFixedSize(18, 18)
        self._browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/browse.png')
        scaled_pixmap = pixmap.scaled(self._browse_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._browse_button.setIcon(QIcon(scaled_pixmap))
        
        self._delete_button.setFixedSize(18, 18)
        self._delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/close.png')
        scaled_pixmap = pixmap.scaled(self._delete_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._delete_button.setIcon(QIcon(scaled_pixmap))
        self._delete_button.hide()

    def _set_signal(self):
        self._browse_button.clicked.connect(self._choose_image)
        self._delete_button.clicked.connect(self._delete_image)
        self.textChanged.connect(self._inspector_container.set_object_image_path)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addStretch(1)
        h_layout.addWidget(self._delete_button)
        h_layout.addWidget(self._browse_button)
        h_layout.setContentsMargins(0, 2, 5, 0)

    def _choose_image(self):
        image_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_image', 'Select Image'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), T.tr('inspector.format', 'Format') + ' (*.png *.jpg *.jpeg *.gif *.bmp *.lbm *.pcx *.qoi *.svg *.tga *.tiff *.webp *.xpm *.xcf)')
        if not image_path:
            return

        self._image_path = Path(image_path)
        self.setToolTip(self._image_path.as_posix())
        self._inspector_container.set_object_image_path()

        self.setStyleSheet('')

    def _delete_image(self):
        self._image_path = Path('')
        self.setToolTip('')
        self._inspector_container.set_object_image_path()

        self.setStyleSheet('')

    def enterEvent(self, event):
        if not str(self._image_path) == '.':
            self._delete_button.show()
        return super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._delete_button.hide()
        return super().leaveEvent(event)


class FontPathLineEdit(QLineEdit):
    def __init__(self, inspector_container, font_path='',  attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._browse_button = QPushButton(self)
        self._delete_button = QPushButton(self)
        self._font_path = Path(font_path)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setTextMargins(0, 0, 24, 0)
        self.setReadOnly(True)
        
        if not str(self._font_path) == '.':
            project_path = Path(get_project_path())
            font_absolute_path = project_path / self._font_path
            self.setToolTip(self._font_path.as_posix())
            self.setText(self._font_path.name)

            if not font_absolute_path.exists():
                self.setStyleSheet('color: rgb(255, 0, 0);')

        self._browse_button.setFixedSize(18, 18)
        self._browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/browse.png')
        scaled_pixmap = pixmap.scaled(self._browse_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._browse_button.setIcon(QIcon(scaled_pixmap))

        self._delete_button.setFixedSize(18, 18)
        self._delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/close.png')
        scaled_pixmap = pixmap.scaled(self._delete_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._delete_button.setIcon(QIcon(scaled_pixmap))
        self._delete_button.hide()

    def _set_signal(self):
        self._browse_button.clicked.connect(self._choose_font)
        self._delete_button.clicked.connect(self._delete_font)
        self.textChanged.connect(self._inspector_container.set_object_font_path)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addStretch(1)
        h_layout.addWidget(self._delete_button)
        h_layout.addWidget(self._browse_button)
        h_layout.setContentsMargins(0, 0, 5, 0)

    def _choose_font(self):
        font_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_font', 'Select Font'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), T.tr('inspector.format', 'Format') + ' (*.ttf)')
        if not font_path:
            return

        self._font_path = Path(font_path)
        self.setToolTip(self._font_path.as_posix())
        self._inspector_container.set_object_font_path()

        self.setStyleSheet('')

    def _delete_font(self):
        self._font_path = Path('')
        self.setToolTip('')
        self._inspector_container.set_object_font_path()

        self.setStyleSheet('')

    def enterEvent(self, event):
        if not str(self._font_path) == '.':
            self._delete_button.show()
        return super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._delete_button.hide()
        return super().leaveEvent(event)


class ScriptPathLineEdit(QLineEdit):
    def __init__(self, inspector_container, script_path='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._browse_button = QPushButton(self)
        self._delete_button = QPushButton(self)
        self._script_path = Path(script_path)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setTextMargins(0, 0, 24, 0)
        self.setReadOnly(True)

        if not str(self._script_path) == '.':
            project_path = Path(get_project_path())
            script_absolute_path = project_path / self._script_path
            self.setToolTip(self._script_path.as_posix())
            self.setText(self._script_path.name)

            if not script_absolute_path.exists():
                self.setStyleSheet('color: rgb(255, 0, 0);')

        self._browse_button.setFixedSize(18, 18)
        self._browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/browse.png')
        scaled_pixmap = pixmap.scaled(self._browse_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._browse_button.setIcon(QIcon(scaled_pixmap))

        self._delete_button.setFixedSize(18, 18)
        self._delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/close.png')
        scaled_pixmap = pixmap.scaled(self._delete_button.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._delete_button.setIcon(QIcon(scaled_pixmap))
        self._delete_button.hide()

    def _set_signal(self):
        self._browse_button.clicked.connect(self._choose_script)
        self._delete_button.clicked.connect(self._delete_script)
        self.textChanged.connect(self._inspector_container.set_object_script_path)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addStretch(1)
        h_layout.addWidget(self._delete_button)
        h_layout.addWidget(self._browse_button)
        h_layout.setContentsMargins(0, 2, 5, 0)

    def _choose_script(self):
        script_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_script', 'Select Script'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), T.tr('inspector.format', 'Format') + ' (*.py)')
        if not script_path:
            return

        self._script_path = Path(script_path)
        self.setToolTip(self._script_path.as_posix())
        self._inspector_container.set_object_script_path()

        self.setStyleSheet('')

    def _delete_script(self):
        self._script_path = Path('')
        self.setToolTip('')
        self._inspector_container.set_object_script_path()

        self.setStyleSheet('')

    def enterEvent(self, event):
        if not str(self._script_path) == '.':
            self._delete_button.show()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self._delete_button.hide()
        return super().leaveEvent(event)