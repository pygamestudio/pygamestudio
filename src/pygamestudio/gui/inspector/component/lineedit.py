import os
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.i18n.translator import Translator as T


def _is_valid_dropped_file(mime_data, extensions):
    """Return True when the dragged data carries a local file whose suffix is
    in `extensions`. Used to accept/reject drag-and-drop in the path line edits."""
    if not mime_data.hasUrls():
        return False
    urls = mime_data.urls()
    if not urls:
        return False
    file_path = urls[0].toLocalFile()
    if not file_path:
        return False
    return Path(file_path).suffix.lower() in extensions


class _PathLineEditDropMixin:
    """Drag-and-drop handling shared by the path line edits (image/font/script).

    While a file is dragged over the widget the border gives instant feedback:
    blue (drop_state="valid") when the file type is accepted, red
    (drop_state="invalid") otherwise (see the QSS rules in dark.qss/light.qss).
    The feedback clears on drag leave or after a drop.
    """

    # Set of accepted file suffixes; each subclass defines its own.
    _drop_extensions = ()

    def _set_drop_feedback(self, state):
        """Apply the drop feedback property (True=valid, False=invalid,
        None=default) and repolish so the QSS rules take effect."""
        self.setProperty('drop_state', {True: 'valid', False: 'invalid'}.get(state, ''))
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        if _is_valid_dropped_file(event.mimeData(), self._drop_extensions):
            self._set_drop_feedback(True)
            event.acceptProposedAction()
        else:
            self._set_drop_feedback(False)
            # Accept the enter (not ignore) so dragLeaveEvent still fires and
            # clears the red feedback; the drop itself is rejected in dropEvent.
            event.accept()

    def dragLeaveEvent(self, event):
        self._set_drop_feedback(None)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        if _is_valid_dropped_file(event.mimeData(), self._drop_extensions):
            self._set_path_from_file(event.mimeData().urls()[0].toLocalFile())
        self._set_drop_feedback(None)
        event.acceptProposedAction()


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


class ImagePathLineEdit(_PathLineEditDropMixin, QLineEdit):
    # Accepted file suffixes for drag-and-drop.
    _drop_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.lbm', '.pcx', '.qoi', '.svg', '.tga', '.tiff', '.webp', '.xpm', '.xcf'}

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
        self.setAcceptDrops(True)
        
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
        self.textChanged.connect(self._notify_container)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addStretch(1)
        h_layout.addWidget(self._delete_button)
        h_layout.addWidget(self._browse_button)
        h_layout.setContentsMargins(0, 2, 5, 0)

    def _notify_container(self):
        """Tell the inspector which path attribute changed and its value, so
        it can be routed to the right object property (image_path or
        particle_image) even when called directly (not via a signal)."""
        attr = self.property('component_attribute') or 'image_path'
        self._inspector_container.set_object_path(attr, self.toolTip())

    def _set_path_from_file(self, file_path):
        """Apply a chosen/dropped image file: update the display and notify the
        inspector so the object's path attribute is set (same as picking it)."""
        self._image_path = Path(file_path)
        self.setToolTip(self._image_path.as_posix())
        self._notify_container()
        self.setStyleSheet('')

    def _choose_image(self):
        image_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_image', 'Select Image'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), T.tr('inspector.format', 'Format') + ' (*.png *.jpg *.jpeg *.gif *.bmp *.lbm *.pcx *.qoi *.svg *.tga *.tiff *.webp *.xpm *.xcf)')
        if not image_path:
            return

        self._set_path_from_file(image_path)

    def _delete_image(self):
        self._image_path = Path('')
        self.setToolTip('')
        self._notify_container()

        self.setStyleSheet('')

    def enterEvent(self, event):
        if not str(self._image_path) == '.':
            self._delete_button.show()
        return super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._delete_button.hide()
        return super().leaveEvent(event)


class FontPathLineEdit(_PathLineEditDropMixin, QLineEdit):
    # Accepted file suffixes for drag-and-drop.
    _drop_extensions = {'.ttf'}

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
        self.setAcceptDrops(True)
        
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

    def _set_path_from_file(self, file_path):
        """Apply a chosen/dropped font file: update the display and notify the
        inspector so the object's font_path is set (same as picking it)."""
        self._font_path = Path(file_path)
        self.setToolTip(self._font_path.as_posix())
        self._inspector_container.set_object_font_path()
        self.setStyleSheet('')

    def _choose_font(self):
        font_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_font', 'Select Font'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), T.tr('inspector.format', 'Format') + ' (*.ttf)')
        if not font_path:
            return

        self._set_path_from_file(font_path)

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


class ScriptPathLineEdit(_PathLineEditDropMixin, QLineEdit):
    # Accepted file suffixes for drag-and-drop.
    _drop_extensions = {'.py'}

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
        self.setAcceptDrops(True)

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

    def _set_path_from_file(self, file_path):
        """Apply a chosen/dropped script file: update the display and notify
        the inspector so the object's script_path is set (same as picking it)."""
        self._script_path = Path(file_path)
        self.setToolTip(self._script_path.as_posix())
        self._inspector_container.set_object_script_path()
        self.setStyleSheet('')

    def _choose_script(self):
        script_path, _ = QFileDialog.getOpenFileName(self, T.tr('inspector.select_script', 'Select Script'), os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'), T.tr('inspector.format', 'Format') + ' (*.py)')
        if not script_path:
            return

        self._set_path_from_file(script_path)

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


class FrameFolderLineEdit(_PathLineEditDropMixin, QLineEdit):
    """Folder picker for the frame-sequence object: points at a project
    folder whose images are the animation frames. Dragging a folder (or a
    single image file, whose parent folder is used) is accepted."""

    # Image files are accepted too; a dropped file picks its parent folder.
    _drop_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.lbm',
                        '.pcx', '.qoi', '.svg', '.tga', '.tiff', '.webp',
                        '.xpm', '.xcf'}

    def __init__(self, inspector_container, frame_folder='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._browse_button = QPushButton(self)
        self._delete_button = QPushButton(self)
        self._frame_folder = Path(frame_folder) if frame_folder else Path('')
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setTextMargins(0, 0, 24, 0)
        self.setReadOnly(True)
        self.setAcceptDrops(True)

        if str(self._frame_folder) not in ('', '.'):
            project_path = Path(get_project_path())
            folder_absolute_path = project_path / self._frame_folder
            self.setToolTip(self._frame_folder.as_posix())
            self.setText(self._frame_folder.name)

            if not folder_absolute_path.is_dir():
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
        self._browse_button.clicked.connect(self._choose_folder)
        self._delete_button.clicked.connect(self._delete_folder)
        self.textChanged.connect(self._notify_container)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.addStretch(1)
        h_layout.addWidget(self._delete_button)
        h_layout.addWidget(self._browse_button)
        h_layout.setContentsMargins(0, 2, 5, 0)

    def _notify_container(self):
        """Tell the inspector the frame folder changed (the value is carried
        by the tooltip, mirroring the image path widgets)."""
        attr = self.property('component_attribute') or 'frame_folder'
        self._inspector_container.set_object_path(attr, self.toolTip())

    def _is_valid_drop(self, mime_data):
        """Accept a dropped folder, or a single dropped image file (whose
        parent folder is used as the frame folder)."""
        if not mime_data.hasUrls():
            return False
        urls = mime_data.urls()
        if not urls:
            return False
        path = Path(urls[0].toLocalFile())
        if path.is_dir():
            return True
        return path.suffix.lower() in self._drop_extensions

    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        if self._is_valid_drop(event.mimeData()):
            self._set_drop_feedback(True)
            event.acceptProposedAction()
        else:
            self._set_drop_feedback(False)
            event.accept()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        if self._is_valid_drop(event.mimeData()):
            self._set_path_from_file(event.mimeData().urls()[0].toLocalFile())
        self._set_drop_feedback(None)
        event.acceptProposedAction()

    def _set_path_from_file(self, folder_path):
        """Apply a chosen/dropped folder (or image file -> its parent): update
        the display and notify the inspector so the frame_folder is set."""
        path = Path(folder_path)
        if path.is_file():
            path = path.parent
        self._frame_folder = path
        self.setToolTip(self._frame_folder.as_posix())
        self._notify_container()
        self.setStyleSheet('')

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, T.tr('inspector.select_folder', 'Select Frame Folder'),
            os.environ.get('__PYGAMESTUDIO_PROJECT_PATH', ''))
        if not folder:
            return

        self._set_path_from_file(folder)

    def _delete_folder(self):
        self._frame_folder = Path('')
        self.setToolTip('')
        self._notify_container()

        self.setStyleSheet('')

    def enterEvent(self, event):
        if str(self._frame_folder) not in ('', '.'):
            self._delete_button.show()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self._delete_button.hide()
        return super().leaveEvent(event)