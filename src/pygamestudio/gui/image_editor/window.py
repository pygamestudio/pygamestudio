from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPen,
                           QPixmap, QCursor)
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QToolButton,
                               QVBoxLayout, QWidget)

from pygamestudio.gui.image_editor.canvas import (ImageCanvas, TOOL_PENCIL,
                                                  TOOL_ERASER, TOOL_LINE,
                                                  TOOL_RECT, TOOL_ELLIPSE,
                                                  TOOL_FILL, TOOL_PICKER)
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.gui.inspector.color import ColorPicker
from pygamestudio.gui.inspector.component.spinbox import SuffixSpinBox
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.console.logger import Logger

# (tool id, icon file, i18n tooltip key, tooltip default)
TOOLS = (
    (TOOL_PENCIL, 'pen', 'image.pencil', 'Pencil'),
    (TOOL_ERASER, 'eraser', 'image.eraser', 'Eraser'),
    (TOOL_LINE, 'line', 'image.line', 'Line'),
    (TOOL_RECT, 'rect', 'image.rectangle', 'Rectangle'),
    (TOOL_ELLIPSE, 'ellipse', 'image.ellipse', 'Ellipse'),
    (TOOL_FILL, 'bucket', 'image.fill', 'Fill'),
    (TOOL_PICKER, 'color_picker', 'image.color_picker', 'Color Picker'),
)

# (button attr name -> icon file) for the icon-only action buttons.
ACTION_ICONS = {
    '_save_btn': 'save',
    '_save_as_btn': 'save_as',
    '_undo_btn': 'undo',
    '_redo_btn': 'redo',
    '_flip_h_btn': 'flip_horizontal',
    '_flip_v_btn': 'flip_vertical',
    '_rotate_cw_btn': 'rotate_cw',
    '_rotate_ccw_btn': 'rotate_ccw',
    '_clear_btn': 'clear',
    '_fit_btn': 'fit_window_size',
}

SAVE_FILTER = ('PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;'
               'WebP (*.webp);;GIF (*.gif);;TIFF (*.tif *.tiff)')


class ImageEditorWindow(QWidget):
    """The image editor panel.

    Lives as a tab in the editor's center top tab widget (right after the code
    editor). It can be detached into its own top-level window and later
    re-docked back to the tab, mirroring the code editor behaviour.
    """

    def __init__(self, game_manager=None):
        super().__init__()
        self._game_manager = game_manager
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None
        self._file_path = None

        self._canvas = ImageCanvas()
        self._scroll_area = QScrollArea()
        self._detach_btn = QPushButton()
        self._save_btn = QPushButton()
        self._save_as_btn = QPushButton()
        self._undo_btn = QPushButton()
        self._redo_btn = QPushButton()
        self._flip_h_btn = QPushButton()
        self._flip_v_btn = QPushButton()
        self._rotate_cw_btn = QPushButton()
        self._rotate_ccw_btn = QPushButton()
        self._zoom_in_btn = QPushButton()
        self._zoom_out_btn = QPushButton()
        self._fit_btn = QPushButton()
        self._actual_btn = QPushButton()
        self._clear_btn = QPushButton()
        self._brush_spinbox = SuffixSpinBox()
        self._color_btn = QPushButton()
        self._color_picker = ColorPicker()
        self._tool_buttons = {}
        self._file_label = QLabel()
        self._size_label = QLabel()
        self._zoom_label = QLabel()

        self._set_up()

    # ------------------------------------------------------------------ setup
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.setObjectName('imageEditorWindow')
        self._update_zoom_label()

    def _set_widget(self):
        self._detach_btn.setObjectName('codeEditorDetachBtn')   # reuse the QSS look
        self._detach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_detach_button_text()

        # Canvas inside a scroll area so large / zoomed images can pan.
        self._scroll_area.setObjectName('imageEditorScrollArea')
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setWidget(self._canvas)
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_area.viewport().setAutoFillBackground(True)
        self._scroll_area.viewport().installEventFilter(self)
        self._scroll_area.installEventFilter(self)

        # Zoom controls reuse the existing icons.
        self._zoom_in_btn.setObjectName('codeEditorZoomInBtn')
        self._zoom_out_btn.setObjectName('codeEditorZoomOutBtn')
        self._zoom_in_btn.setIcon(QIcon(':/images/zoom_in.png'))
        self._zoom_out_btn.setIcon(QIcon(':/images/zoom_out.png'))
        self._zoom_in_btn.setIconSize(QSize(16, 16))
        self._zoom_out_btn.setIconSize(QSize(16, 16))
        self._zoom_in_btn.setFixedSize(26, 26)
        self._zoom_out_btn.setFixedSize(26, 26)
        self._zoom_in_btn.setToolTip(T.tr('image.zoom_in', 'Zoom In'))
        self._zoom_out_btn.setToolTip(T.tr('image.zoom_out', 'Zoom Out'))
        self._fit_btn.setObjectName('imageEditorViewBtn')
        self._actual_btn.setObjectName('imageEditorViewBtn')
        self._actual_btn.setText('1:1')
        self._fit_btn.setFixedSize(30, 26)
        self._actual_btn.setFixedSize(42, 26)
        self._fit_btn.setToolTip(T.tr('image.fit', 'Fit to Window'))
        self._actual_btn.setToolTip(T.tr('image.actual_size', 'Actual Size'))

        # File / history / transform buttons (real icons from resources).
        for btn_name, key, default, width in (
            ('_save_btn', 'image.save', 'Save (Ctrl+S)', 30),
            ('_save_as_btn', 'image.save_as', 'Save As', 30),
            ('_undo_btn', 'image.undo', 'Undo (Ctrl+Z)', 26),
            ('_redo_btn', 'image.redo', 'Redo (Ctrl+Y)', 26),
            ('_flip_h_btn', 'image.flip_h', 'Flip Horizontal', 28),
            ('_flip_v_btn', 'image.flip_v', 'Flip Vertical', 28),
            ('_rotate_cw_btn', 'image.rotate_cw', 'Rotate 90° CW', 28),
            ('_rotate_ccw_btn', 'image.rotate_ccw', 'Rotate 90° CCW', 28),
            ('_clear_btn', 'image.clear', 'Clear', 28),
        ):
            btn = getattr(self, btn_name)
            btn.setObjectName('imageEditorToolBtn')
            btn.setIcon(QIcon(f':/images/{ACTION_ICONS[btn_name]}.png'))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(T.tr(key, default))
            btn.setFixedSize(width, 26)
        self._fit_btn.setIcon(QIcon(':/images/fit_window_size.png'))
        self._fit_btn.setIconSize(QSize(16, 16))

        # Tool buttons (exclusive, icon-only). They are intentionally NOT
        # checkable: the active tool is highlighted through the QSS "active"
        # property, which keeps the icon perfectly centered (no checked/
        # pressed style offset is applied).
        for tool_id, icon_name, key, default in TOOLS:
            btn = QToolButton(self)
            btn.setIcon(QIcon(f':/images/{icon_name}.png'))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(T.tr(key, default))
            btn.setFixedSize(30, 30)
            btn.setAutoRaise(False)
            self._tool_buttons[tool_id] = btn
        self._set_active_highlight(TOOL_PENCIL)

        # Brush size (same SuffixSpinBox style as the inspector: the up/down
        # arrows only appear while the mouse hovers over the control).
        self._brush_spinbox.setRange(1, 512)
        self._brush_spinbox.setDecimals(0)
        self._brush_spinbox.setSingleStep(1)
        self._brush_spinbox.setValue(self._canvas.brush_size())
        self._brush_spinbox.set_suffix('px')
        self._brush_spinbox.setFixedWidth(78)
        self._brush_spinbox.setToolTip(T.tr('image.brush_size', 'Brush Size'))

        # Color swatch: a flat color block with a thin border; the checkerboard
        # shows through any transparency.
        self._color_btn.setFixedSize(24, 24)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.setStyleSheet(
            'QPushButton { border: none; background: transparent; padding: 0px; }')
        self._update_color_button()

        self._file_label.setText(T.tr('image.untitled', 'Untitled'))
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._update_size_label()
        self._update_enabled_state()

    def _set_signal(self):
        self._canvas.modified_changed.connect(lambda modified: self._update_titles())
        self._canvas.zoom_changed.connect(lambda _: self._update_zoom_label())
        self._canvas.image_size_changed.connect(self._update_size_label)
        self._canvas.color_picked.connect(self.set_color)
        self._color_picker.color_changed.connect(self.set_color)

        self._detach_btn.clicked.connect(self.toggle_detached)
        self._save_btn.clicked.connect(self.save)
        self._save_as_btn.clicked.connect(self.save_as)
        self._undo_btn.clicked.connect(self._canvas.undo)
        self._redo_btn.clicked.connect(self._canvas.redo)
        self._flip_h_btn.clicked.connect(self._canvas.flip_h)
        self._flip_v_btn.clicked.connect(self._canvas.flip_v)
        self._rotate_cw_btn.clicked.connect(self._canvas.rotate_cw)
        self._rotate_ccw_btn.clicked.connect(self._canvas.rotate_ccw)
        self._clear_btn.clicked.connect(self._canvas.clear)
        self._zoom_in_btn.clicked.connect(self._canvas.zoom_in)
        self._zoom_out_btn.clicked.connect(self._canvas.zoom_out)
        self._fit_btn.clicked.connect(self._fit_to_window)
        self._actual_btn.clicked.connect(self._canvas.actual_size)
        self._brush_spinbox.valueChanged.connect(self._canvas.set_brush_size)
        self._color_btn.clicked.connect(self._choose_color)

        for tool_id, btn in self._tool_buttons.items():
            btn.clicked.connect(lambda checked=False, t=tool_id: self._activate_tool(t))

    def _set_layout(self):
        # Row 1: file / history / view / transform.
        row1 = QHBoxLayout()
        for w in (self._save_btn, self._save_as_btn, self._undo_btn, self._redo_btn,
                  self._flip_h_btn, self._flip_v_btn, self._rotate_ccw_btn,
                  self._rotate_cw_btn, self._clear_btn):
            row1.addWidget(w)
        row1.addStretch(1)
        row1.addWidget(self._zoom_out_btn)
        row1.addWidget(self._zoom_in_btn)
        row1.addWidget(self._actual_btn)
        row1.addWidget(self._fit_btn)

        # Row 2: drawing tools + brush + color + detach.
        row2 = QHBoxLayout()
        for tool_id, btn in self._tool_buttons.items():
            row2.addWidget(btn)
        row2.addSpacing(8)
        row2.addWidget(self._brush_spinbox)
        row2.addWidget(self._color_btn)
        row2.addStretch(1)
        row2.addWidget(self._detach_btn)

        # Status strip: file name  |  size  |  zoom.
        status = QHBoxLayout()
        status.addWidget(self._file_label)
        status.addStretch(1)
        status.addWidget(self._size_label)
        status.addSpacing(12)
        status.addWidget(self._zoom_label)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        main_layout.addLayout(row1)
        main_layout.addLayout(row2)
        main_layout.addWidget(self._scroll_area, 1)
        main_layout.addLayout(status)

        for row in (row1, row2):
            for i in range(row.count()):
                item = row.itemAt(i)
                if item.widget() is not None:
                    item.widget().setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------ tools
    def _activate_tool(self, tool_id):
        self._canvas.set_tool(tool_id)
        self._set_active_highlight(tool_id)

    def _set_active_highlight(self, tool_id):
        """Highlight the selected drawing tool without moving its icon."""
        for tid, btn in self._tool_buttons.items():
            active = (tid == tool_id)
            if btn.property('active') != active:
                btn.setProperty('active', active)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

    def _choose_color(self):
        """Open the built-in ColorPicker popup next to the cursor."""
        self._show_color_picker(self._canvas.current_color().getRgb())

    def _show_color_picker(self, rgba):
        screen = QApplication.primaryScreen()
        screen_width = screen.geometry().width()
        screen_height = screen.geometry().height()

        pos = QCursor.pos()
        x = pos.x()
        y = pos.y()
        if x + self._color_picker.width() > screen_width:
            x = screen_width - self._color_picker.width()
        else:
            x = int(x - self._color_picker.width() / 4)
        if y + self._color_picker.height() > screen_height:
            y = screen_height - self._color_picker.height()
        else:
            y = y + 20

        self._color_picker.set_rgba(tuple(int(v) for v in rgba))
        self._color_picker.move(x, y)
        self._color_picker.show()
        self._color_picker.raise_()
        self._color_picker.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def set_color(self, color):
        if isinstance(color, (tuple, list)):
            color = QColor(*[int(v) for v in color])
        self._canvas.set_color(color)
        self._update_color_button()

    def _update_color_button(self):
        """Swatch icon: a flat color block with a thin rounded border and a
        checkerboard that shows through any transparency."""
        color = self._canvas.current_color()
        side = 24
        pixmap = QPixmap(side, side)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, side - 1, side - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 3, 3)
        painter.setClipPath(path)
        tile = 5
        for row in range(0, side, tile):
            for col in range(0, side, tile):
                even = ((row // tile) + (col // tile)) % 2 == 0
                painter.fillRect(col, row, tile, tile,
                                 QColor('#ffffff' if even else '#b0b0b0'))
        painter.fillRect(0, 0, side, side, color)
        painter.setClipping(False)
        painter.setPen(QPen(QColor('#555555'), 1))
        painter.drawPath(path)
        painter.end()
        self._color_btn.setIcon(QIcon(pixmap))
        self._color_btn.setIconSize(QSize(side, side))
        self._color_btn.setText('')
        self._color_btn.setToolTip(
            T.tr('image.color', 'Color')
            + f'  rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})')

    # ------------------------------------------------------------------ file
    def open_image(self, file_path):
        """Open an image in the editor and bring the panel into view."""
        file_path = str(file_path)
        if not self._canvas.load(file_path):
            return False
        self._file_path = Path(file_path)
        self._update_enabled_state()
        self._update_titles()
        # Show the image at 1:1 by default (zoom controls let the user fit it).
        self._canvas.actual_size()
        self._raise_window()
        return True

    def save(self):
        """Save to the current file. Returns True on success (also reports
        the result to the console)."""
        if self._canvas.image() is None:
            return False
        if self._file_path is None:
            return self.save_as()
        if self._canvas.save(str(self._file_path)):
            self._update_titles()
            Logger.info(T.tr('image.saved', 'Image saved: {}').format(self._file_path.name))
            return True
        Logger.error(T.tr('image.save_failed', 'Failed to save image: {}').format(self._file_path.name))
        return False

    def save_as(self):
        """Pick a destination and save. Returns True on success."""
        if self._canvas.image() is None:
            return False
        start_dir = str(self._file_path.parent) if self._file_path else ''
        path, _ = QFileDialog.getSaveFileName(
            self, T.tr('image.save_as', 'Save As'), start_dir, SAVE_FILTER)
        if not path:
            return False
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix('.png')
        if self._canvas.save(str(path)):
            self._file_path = path
            self._update_titles()
            Logger.info(T.tr('image.saved', 'Image saved: {}').format(path.name))
            return True
        Logger.error(T.tr('image.save_failed', 'Failed to save image: {}').format(path.name))
        return False

    def _fit_to_window(self):
        viewport = self._scroll_area.viewport()
        self._canvas.fit_in_view(viewport.width(), viewport.height())

    def _update_size_label(self):
        """Show the current image's pixel dimensions in the status bar."""
        width, height = self._canvas.image_size()
        if width > 0 and height > 0:
            self._size_label.setText(T.tr('image.size_format', '{} × {} px').format(width, height))
        else:
            self._size_label.setText('')

    def _raise_window(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.show()
                self._standalone_window.raise_()
                self._standalone_window.activateWindow()
        elif self._tab_widget is not None:
            self._tab_widget.setCurrentWidget(self)

    # -------------------------------------------------- focus / shortcuts / zoom
    def focus_canvas(self):
        """Give the keyboard focus to the canvas (e.g. when its tab becomes
        the current one), so Ctrl+Z/Y act on the image editor right away."""
        self._canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event):
        # Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z act on the image undo stack even when
        # the focus is on a toolbar control instead of the canvas itself.
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self._canvas.undo()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Y:
                self._canvas.redo()
                event.accept()
                return
        elif (event.modifiers() == (Qt.KeyboardModifier.ControlModifier
                                    | Qt.KeyboardModifier.ShiftModifier)
                and event.key() == Qt.Key.Key_Z):
            self._canvas.redo()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        # Ctrl+wheel zooms anywhere over the panel, not only on the image.
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and self._canvas.has_image()):
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._canvas.set_zoom(self._canvas.zoom() * factor)
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, obj, event):
        # Also zoom with Ctrl+wheel while the pointer is over the gray area
        # around the image inside the scroll area.
        if (event.type() == QEvent.Type.Wheel
                and obj in (self._scroll_area, self._scroll_area.viewport())
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and self._canvas.has_image()):
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._canvas.set_zoom(self._canvas.zoom() * factor)
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------ detach
    def set_tab_widget(self, tab_widget):
        self._tab_widget = tab_widget

    def toggle_detached(self):
        if self._is_detached:
            self.attach()
        else:
            self.detach()

    def detach(self):
        if self._is_detached or self._tab_widget is None:
            return
        self._tab_widget.removeTab(self._tab_widget.indexOf(self))
        self.setParent(None)
        self._standalone_window = _ImageEditorStandaloneWindow(self, self._window_title())
        self.show()
        self._standalone_window.show()
        self._is_detached = True
        self._update_detach_button_text()

    def attach(self):
        if not self._is_detached or self._tab_widget is None:
            return
        standalone = self._standalone_window
        self._standalone_window = None
        if standalone is not None:
            standalone._editor_window = None
            standalone.hide()
            standalone.deleteLater()
        # Re-dock right after the code editor tab when present, else after the
        # scene tab (index 1).
        insert_index = min(2, self._tab_widget.count())
        self._tab_widget.insertTab(insert_index, self, self._tab_title())
        self._tab_widget.setCurrentIndex(insert_index)
        self.show()
        self._is_detached = False
        self._update_detach_button_text()

    def closeEvent(self, event):
        if self._is_detached:
            self.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def is_detached(self):
        return self._is_detached

    # ------------------------------------------------------------------ state
    def _update_enabled_state(self):
        has = self._canvas.has_image()
        for btn in (self._save_btn, self._save_as_btn, self._undo_btn,
                    self._redo_btn, self._flip_h_btn, self._flip_v_btn,
                    self._rotate_cw_btn, self._rotate_ccw_btn, self._clear_btn,
                    self._zoom_in_btn, self._zoom_out_btn, self._fit_btn,
                    self._actual_btn):
            btn.setEnabled(has)
        for btn in self._tool_buttons.values():
            btn.setEnabled(has)
        self._brush_spinbox.setEnabled(has)
        self._color_btn.setEnabled(has)

    def _file_title(self):
        if self._file_path:
            name = self._file_path.name
        else:
            name = T.tr('image.untitled', 'Untitled')
        return f'*{name}' if self._canvas.is_modified() else name

    def _tab_title(self):
        if self._file_path or self._canvas.has_image():
            return self._file_title()
        return T.tr('image.editor', 'Image Editor')

    def _window_title(self):
        return f' Pygame Studio - {self._tab_title()}'

    def _update_titles(self):
        self._file_label.setText(self._file_title())
        self._save_btn.setEnabled(self._canvas.has_image())
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.window_title.set_title_name(self._window_title())
        elif self._tab_widget is not None:
            index = self._tab_widget.indexOf(self)
            if index >= 0:
                self._tab_widget.setTabText(index, self._tab_title())

    def _update_zoom_label(self):
        self._zoom_label.setText(f'{self._canvas.zoom() * 100:.0f}%')

    def _update_detach_button_text(self):
        if self._is_detached:
            self._detach_btn.setText(T.tr('image.attach', 'Attach to Tabs'))
        else:
            self._detach_btn.setText(T.tr('image.detach', 'Detach'))

    # ------------------------------------------------------------------ theme / hooks
    def apply_theme(self, is_dark):
        pass

    def retranslate(self):
        self._update_detach_button_text()
        self._update_titles()
        self._file_label.setText(self._file_title())

    def get_ready_for_project(self):
        pass

    def clean_up(self):
        self._color_picker.close()


class _ImageEditorStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the image editor while it is
    detached from the center tab widget."""

    def __init__(self, editor_window, title):
        super().__init__()
        self._editor_window = editor_window
        self.resize(1000, 700)
        self.set_window_body(editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        if self._editor_window is not None:
            self._editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event):
        # When detached this is its own top-level window, so Ctrl+S/Z/Y must
        # be handled here (they can no longer bubble up to the main editor).
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_S:
                self._editor_window.save()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Z:
                self._editor_window._canvas.undo()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Y:
                self._editor_window._canvas.redo()
                event.accept()
                return
        super().keyPressEvent(event)
