"""The sprite-sheet slicer of the animation editor.

Cuts a sheet image into single-frame PNG files by a fixed cell size (with an
optional offset and spacing) - e.g. 32x32 pixel cells. The files are named
after the sheet (``player_000.png``, ...) inside an output folder, so they
can be used directly as keyframe images or as a frame-sequence folder,
without an external tool. The animation editor toolbar's scissors button
opens :class:`SpriteSheetDialog`; :func:`slice_sprite_sheet` is the pure
cutting function the dialog (and tests) drive.
"""
import re
from pathlib import Path

from PySide6.QtCore import QLineF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QSizePolicy, QVBoxLayout)

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.gui.inspector.component.spinbox import SuffixSpinBox

#: Formats a sheet image may use; the slices are always written as PNG.
SHEET_FILTER = 'Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tga *.tiff)'

#: The preview canvas fills the dialog's width; these are its minimums.
PREVIEW_WIDTH = 320
PREVIEW_HEIGHT = 200

#: Highest pixel value the spin boxes accept.
_MAX_CELL = 99999


def resolve_sheet_path(path_text):
    """A path field value: absolute stays as-is, relative is project-relative."""
    text = str(path_text or '').strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        project = get_project_path()
        if project:
            path = Path(project) / path
    return path


def display_path(path):
    """Project-relative posix text when the path is inside the project."""
    path = Path(path)
    project = get_project_path()
    if project:
        try:
            return path.absolute().relative_to(Path(project).absolute()).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def slice_rects(image_width, image_height, cell_width, cell_height,
                offset_x=0, offset_y=0, spacing_x=0, spacing_y=0):
    """Row-major top-left corner of every cell that fully fits the image.

    A cell starts at ``offset + index * (cell + spacing)``; it counts only
    while its whole box stays inside the image, so a sheet may carry a
    border or a half-cut last row without breaking the grid. Raises
    ValueError when not even one cell fits.
    """
    cell_width = int(cell_width)
    cell_height = int(cell_height)
    if cell_width < 1 or cell_height < 1:
        raise ValueError('invalid frame size')
    start_x = max(0, int(offset_x))
    start_y = max(0, int(offset_y))
    step_x = cell_width + max(0, int(spacing_x))
    step_y = cell_height + max(0, int(spacing_y))
    width = int(image_width)
    height = int(image_height)
    if width < start_x + cell_width or height < start_y + cell_height:
        raise ValueError('no frames')
    columns = (width - start_x - cell_width) // step_x + 1
    rows = (height - start_y - cell_height) // step_y + 1
    return [(start_x + column * step_x, start_y + row * step_y)
            for row in range(rows) for column in range(columns)]


def slice_sprite_sheet(image_path, cell_width, cell_height,
                       offset_x=0, offset_y=0, spacing_x=0, spacing_y=0,
                       output_folder=None):
    """Cut the sheet into ``<name>_000.png`` files; returns the written paths.

    Files of an earlier slice with the same name pattern in the target
    folder are removed first, so re-slicing with a different cell size never
    leaves stale frames behind.
    """
    image_path = Path(image_path)
    image = QImage(str(image_path))
    if image.isNull():
        raise ValueError('the sheet could not be loaded')
    rects = slice_rects(image.width(), image.height(), cell_width, cell_height,
                        offset_x, offset_y, spacing_x, spacing_y)

    folder = Path(output_folder) if output_folder else \
        image_path.parent / '{}_frames'.format(image_path.stem)
    folder.mkdir(parents=True, exist_ok=True)

    prefix = image_path.stem
    stale_pattern = re.compile(r'^{}_\d+\.png$'.format(re.escape(prefix)))
    for old_file in folder.iterdir():
        if old_file.is_file() and stale_pattern.match(old_file.name):
            old_file.unlink()

    cell_width = int(cell_width)
    cell_height = int(cell_height)
    digits = max(3, len(str(len(rects) - 1)))
    written = []
    for index, (x, y) in enumerate(rects):
        out_path = folder / '{}_{:0{width}d}.png'.format(
            prefix, index, width=digits)
        if not image.copy(x, y, cell_width, cell_height).save(
                str(out_path), 'PNG'):
            raise IOError('could not write {}'.format(out_path.as_posix()))
        written.append(out_path)
    return written


def slice_done_text(count, folder_text):
    """The 'Sliced N frame(s) to <folder>' line, shared with the console log."""
    return T.tr('animation.slice_done',
                'Sliced {count} frame(s) to {folder}').format(
                    count=count, folder=folder_text)


def _paint_checkerboard(painter, width, height, size=8):
    """Transparency backdrop: alternating light/dark squares."""
    dark = QColor(58, 58, 62)
    light = QColor(76, 76, 82)
    for top in range(0, height, size):
        for left in range(0, width, size):
            color = dark if ((left // size) + (top // size)) % 2 == 0 else light
            painter.fillRect(left, top, size, size, color)


class _SheetPreview(QLabel):
    """The preview canvas: checkerboard backdrop, the sheet, the red cell
    grid - with wheel zoom and middle-drag panning.

    The canvas always fills the dialog's width (it repaints itself on every
    resize) and a new sheet starts fitted to it; the wheel zooms around the
    cursor, the middle button pans and a double-click goes back to the
    fit. A frame around the sheet and the size text in the bottom-left
    corner keep its real extent visible even when the image is mostly
    transparent (it would otherwise blend into the checkerboard). The grid
    lines are clamped INSIDE the canvas: an exactly-divisible sheet ends at
    the canvas edge, and a line drawn exactly on the edge would be clipped.
    """

    ZOOM_STEP = 1.25
    MIN_ZOOM = 0.1
    MAX_ZOOM = 32.0

    def __init__(self):
        super().__init__()
        self._image = QImage()
        self._rects = None
        self._cell = (32, 32)
        #: Zoom on top of the fit-to-canvas scale and pan in canvas pixels.
        self._zoom = 1.0
        self._pan = (0.0, 0.0)
        self._panning = False
        self._pan_start = None
        self._pan_origin = (0.0, 0.0)
        #: Where the displayed sheet sits on the canvas + its scale (the
        #: tests read these to probe the exact grid-line pixels).
        self._offset = (0.0, 0.0)
        self._scale = (1.0, 1.0)
        self.setObjectName('spriteSlicerPreview')
        self.setMinimumSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_state(self, image, rects, cell_width, cell_height):
        if image is not self._image:
            # A new sheet is shown fitted again.
            self._zoom = 1.0
            self._pan = (0.0, 0.0)
        self._image = image
        self._rects = rects
        self._cell = (int(cell_width), int(cell_height))
        self.update()

    # ------------------------------------------------------------ view state
    def _fit_scale(self):
        """Scale that fits the whole sheet into the canvas."""
        if self._image.isNull():
            return 1.0
        return min(max(1, self.width()) / self._image.width(),
                   max(1, self.height()) / self._image.height())

    def _offset_at(self, scale, width, height):
        disp_w = self._image.width() * scale
        disp_h = self._image.height() * scale
        return ((width - disp_w) / 2.0 + self._pan[0],
                (height - disp_h) / 2.0 + self._pan[1])

    def reset_view(self):
        """Back to fitted + centred."""
        self._zoom = 1.0
        self._pan = (0.0, 0.0)
        self.update()

    def zoom_at(self, factor, pos=None):
        """Zoom by ``factor`` keeping the point under ``pos`` (default:
        the canvas centre) in place."""
        if self._image.isNull():
            return
        old_zoom = self._zoom
        new_zoom = min(self.MAX_ZOOM, max(self.MIN_ZOOM, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-9:
            return
        width = max(1, self.width())
        height = max(1, self.height())
        base = self._fit_scale()
        old_scale = base * old_zoom
        new_scale = base * new_zoom
        old_x0, old_y0 = self._offset_at(old_scale, width, height)
        if pos is None:
            pos_x, pos_y = width / 2.0, height / 2.0
        else:
            pos_x, pos_y = float(pos.x()), float(pos.y())
        image_x = (pos_x - old_x0) / old_scale
        image_y = (pos_y - old_y0) / old_scale
        self._zoom = new_zoom
        disp_w = self._image.width() * new_scale
        disp_h = self._image.height() * new_scale
        self._pan = (pos_x - image_x * new_scale - (width - disp_w) / 2.0,
                     pos_y - image_y * new_scale - (height - disp_h) / 2.0)
        self.update()

    # ------------------------------------------------------------ interaction
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            factor = self.ZOOM_STEP if delta > 0 else 1.0 / self.ZOOM_STEP
            self.zoom_at(factor, event.position())
        event.accept()

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.MiddleButton
                and not self._image.isNull()):
            self._panning = True
            self._pan_start = event.position()
            self._pan_origin = self._pan
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            pos = event.position()
            self._pan = (self._pan_origin[0] + pos.x() - self._pan_start.x(),
                         self._pan_origin[1] + pos.y() - self._pan_start.y())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.reset_view()
        event.accept()

    # --------------------------------------------------------------- painting
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            width = max(1, self.width())
            height = max(1, self.height())
            _paint_checkerboard(painter, width, height)
            self._offset = (0.0, 0.0)
            self._scale = (1.0, 1.0)
            if self._image.isNull():
                return
            scale = self._fit_scale() * self._zoom
            pixmap = QPixmap.fromImage(self._image)
            # The sheet is rendered through a pre-scaled pixmap and blitted
            # in one go - smooth while shrunk, crisp pixels while magnified.
            method = (Qt.TransformationMode.FastTransformation if scale >= 1.0
                      else Qt.TransformationMode.SmoothTransformation)
            scaled = pixmap.scaled(
                max(1, int(round(self._image.width() * scale))),
                max(1, int(round(self._image.height() * scale))),
                Qt.AspectRatioMode.IgnoreAspectRatio, method)
            disp_w = scaled.width()
            disp_h = scaled.height()
            offset_x = (width - disp_w) / 2.0 + self._pan[0]
            offset_y = (height - disp_h) / 2.0 + self._pan[1]
            scale_x = disp_w / self._image.width()
            scale_y = disp_h / self._image.height()
            self._offset = (offset_x, offset_y)
            self._scale = (scale_x, scale_y)
            painter.drawPixmap(int(offset_x), int(offset_y), scaled)
            # A frame around the sheet: a mostly transparent image would
            # blend into the checkerboard and its extent would be invisible.
            painter.setPen(QPen(QColor(150, 150, 150, 220), 1))
            painter.drawRect(QRectF(offset_x, offset_y, disp_w, disp_h))
            if self._rects:
                painter.setPen(QPen(QColor(255, 60, 60), 1))
                columns = sorted({x for x, _ in self._rects})
                rows = sorted({y for _, y in self._rects})
                right = columns[-1] + self._cell[0]
                bottom = rows[-1] + self._cell[1]
                canvas_bottom = offset_y + disp_h
                canvas_right = offset_x + disp_w
                for x in columns + [right]:
                    line_x = min(max(offset_x + x * scale_x, 0.5), width - 0.5)
                    painter.drawLine(QLineF(line_x, offset_y, line_x,
                                            canvas_bottom))
                for y in rows + [bottom]:
                    line_y = min(max(offset_y + y * scale_y, 0.5), height - 0.5)
                    painter.drawLine(QLineF(offset_x, line_y, canvas_right,
                                            line_y))
            self._draw_size_label(painter, height)
        except Exception:  # a paint error must never leave the painter open
            import traceback
            traceback.print_exc()
        finally:
            painter.end()

    def _draw_size_label(self, painter, height):
        """The sheet size (and the zoom, when not 100%) in the bottom-left
        corner of the canvas."""
        text = '{} × {}'.format(self._image.width(), self._image.height())
        if abs(self._zoom - 1.0) > 1e-6:
            text += '   {}%'.format(int(round(self._zoom * 100)))
        metrics = painter.fontMetrics()
        text_size = metrics.size(0, text)
        pad = 4
        box = QRectF(6, height - text_size.height() - pad * 2 - 6,
                     text_size.width() + pad * 2, text_size.height() + pad * 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter.value, text)


class SpriteSheetDialog(QDialog):
    """Slice a sheet image into single-frame PNGs by pixel cell size.

    The preview draws the computed grid over the scaled sheet, so the cell
    size / offset / spacing can be checked before cutting, and the result
    line under it counts the frames. A successful slice writes
    ``<name>_000.png`` ... into the output folder and emits :attr:`sliced`
    (folder text, frame count).
    """

    #: Emitted after a successful slice: (output folder text, frame count).
    sliced = Signal(str, int)

    def __init__(self, parent=None, image_path=''):
        super().__init__(parent)
        self._image = QImage()
        self._image_path = Path()
        self._output_touched = False
        self.sliced_paths = []
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.setObjectName('spriteSheetDialog')
        self.retranslate()
        # The dialog opens at its natural size (QDialog adjusts itself when
        # it is shown). Resizing it here - before Windows has applied the
        # frame - made QWindowsWindow log 'Unable to set geometry' warnings.
        if image_path:
            self.set_image_path(image_path)
        self._refresh()

    # ------------------------------------------------------------------ widgets
    def _make_spin(self, suffix, minimum, value):
        """The editor's spin style: inspector SuffixSpinBox, whole pixels.

        New value boxes always use this widget (suffix label at the end +
        the hover arrow buttons), never a plain QSpinBox.
        """
        spin = SuffixSpinBox()
        spin.setDecimals(0)
        spin.setSingleStep(1)
        spin.setRange(minimum, _MAX_CELL)
        spin.setValue(value)
        spin.set_suffix(suffix)
        spin.setFixedWidth(64)
        return spin

    def _set_widget(self):
        self.setModal(True)

        self._source_edit = QLineEdit()
        self._cell_w_spin = self._make_spin('W', 1, 32)
        self._cell_h_spin = self._make_spin('H', 1, 32)
        self._offset_x_spin = self._make_spin('X', 0, 0)
        self._offset_y_spin = self._make_spin('Y', 0, 0)
        self._spacing_x_spin = self._make_spin('X', 0, 0)
        self._spacing_y_spin = self._make_spin('Y', 0, 0)
        self._output_edit = QLineEdit()

        self._source_label = QLabel()
        self._cell_label = QLabel()
        self._offset_label = QLabel()
        self._spacing_label = QLabel()
        self._output_label = QLabel()

        self._choose_source_btn = QPushButton()
        self._choose_output_btn = QPushButton()
        # The editor's browse button style: icon only, no text.
        for button in (self._choose_source_btn, self._choose_output_btn):
            button.setObjectName('imageEditorToolBtn')
            button.setIcon(QIcon(':/images/browse.png'))
            button.setIconSize(QSize(18, 18))
            button.setFixedSize(28, 28)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn = QPushButton()
        self._clear_btn = QPushButton()
        self._close_btn = QPushButton()

        self._preview_label = _SheetPreview()

        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setObjectName('spriteSlicerInfo')

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.setObjectName('spriteSlicerStatus')

    def _all_spins(self):
        return (self._cell_w_spin, self._cell_h_spin,
                self._offset_x_spin, self._offset_y_spin,
                self._spacing_x_spin, self._spacing_y_spin)

    def _set_signal(self):
        self._choose_source_btn.clicked.connect(self._choose_image)
        self._choose_output_btn.clicked.connect(self._choose_output_folder)
        self._source_edit.editingFinished.connect(
            lambda: self.set_image_path(self._source_edit.text()))
        self._output_edit.textEdited.connect(self._on_output_edited)
        for spin in self._all_spins():
            spin.valueChanged.connect(self._refresh)
        self._run_btn.clicked.connect(self.run_slice)
        self._clear_btn.clicked.connect(self.clear_all)
        self._close_btn.clicked.connect(self.close)

    def _picker_row(self, label, edit, button):
        """One file/folder row: [label][edit ..stretch..][button]."""
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(label)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return row

    def _param_group(self, label, first_spin, second_spin):
        """One labelled spin PAIR; the two boxes sit right next to each
        other (the pair itself is what a row separates from the next)."""
        group = QHBoxLayout()
        group.setSpacing(4)
        group.addWidget(label)
        group.addWidget(first_spin)
        group.addWidget(second_spin)
        return group

    def _set_layout(self):
        source_row = self._picker_row(self._source_label, self._source_edit,
                                      self._choose_source_btn)
        output_row = self._picker_row(self._output_label, self._output_edit,
                                      self._choose_output_btn)

        params = QHBoxLayout()
        params.setSpacing(14)
        params.addLayout(self._param_group(self._cell_label, self._cell_w_spin,
                                           self._cell_h_spin))
        params.addLayout(self._param_group(self._offset_label, self._offset_x_spin,
                                           self._offset_y_spin))
        params.addLayout(self._param_group(self._spacing_label, self._spacing_x_spin,
                                           self._spacing_y_spin))
        params.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._run_btn)
        buttons.addWidget(self._clear_btn)
        buttons.addWidget(self._close_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(source_row)
        layout.addLayout(output_row)
        layout.addLayout(params)
        layout.addWidget(self._preview_label)
        # The result line ('352×32 · 11 × 1 = 11 frames') sits centred right
        # below the preview canvas.
        layout.addWidget(self._info_label)
        layout.addWidget(self._status_label)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ state
    def has_image(self):
        return not self._image.isNull()

    def set_image_path(self, path_text):
        """Load a sheet (project-relative or absolute text) into the dialog."""
        path = resolve_sheet_path(path_text)
        self._image = QImage(str(path)) if path else QImage()
        self._image_path = Path(path) if path else Path()
        # A new sheet re-suggests its own '..._frames' folder.
        self._output_touched = False
        text = display_path(path) if path else ''
        self._source_edit.setText('' if text == '.' else text)
        self._status_label.clear()
        self._refresh()

    def _on_output_edited(self, _text):
        self._output_touched = True

    def _suggested_folder(self):
        if not self._image_path.name:
            return None
        return self._image_path.parent / '{}_frames'.format(self._image_path.stem)

    def output_folder(self):
        """The folder the slices go to (the edit's text, or the suggestion)."""
        path = resolve_sheet_path(self._output_edit.text())
        return path if path is not None else self._suggested_folder()

    # ------------------------------------------------------------------ preview
    def _refresh(self):
        if not self._output_touched:
            suggested = self._suggested_folder()
            self._output_edit.setText(display_path(suggested) if suggested else '')

        rects = None
        error = ''
        is_hint = self._image.isNull()
        if is_hint:
            error = T.tr('animation.slice_no_image', 'Choose a sheet image first')
        else:
            try:
                rects = slice_rects(
                    self._image.width(), self._image.height(),
                    self._cell_w_spin.value(), self._cell_h_spin.value(),
                    self._offset_x_spin.value(), self._offset_y_spin.value(),
                    self._spacing_x_spin.value(), self._spacing_y_spin.value())
            except ValueError:
                rects = None
                error = T.tr('animation.slice_too_big',
                             'The frame size does not fit the image')

        self._update_preview(rects)
        if rects is None:
            self._info_label.setText(error)
            # 'Choose a sheet first' is a hint, in the same colour as the
            # result text; only the frame-size error turns red.
            self._info_label.setStyleSheet(
                '' if is_hint else 'color: rgb(255, 0, 0);')
            self._run_btn.setEnabled(False)
            return
        columns = len({x for x, _ in rects})
        rows = len({y for _, y in rects})
        self._info_label.setStyleSheet('')
        self._info_label.setText(
            T.tr('animation.slice_info',
                 'Sheet {size}, {cols} × {rows} grid, {count} frames').format(
                     size='{}×{}'.format(self._image.width(), self._image.height()),
                     cols=columns, rows=rows, count=len(rects)))
        self._run_btn.setEnabled(True)

    def _update_preview(self, rects):
        """Hand the image + computed grid to the preview canvas."""
        cell = (self._cell_w_spin.value(), self._cell_h_spin.value())
        self._preview_label.set_state(self._image, rects, *cell)

    # ------------------------------------------------------------------ commands
    def _choose_image(self):
        start = get_project_path() or str(self._image_path.parent)
        file_path, _ = QFileDialog.getOpenFileName(
            self, T.tr('animation.slice_source', 'Sheet'), start, SHEET_FILTER)
        if file_path:
            self.set_image_path(file_path)

    def _choose_output_folder(self):
        current = self.output_folder()
        start = str(current) if current else (get_project_path() or '')
        folder = QFileDialog.getExistingDirectory(
            self, T.tr('animation.slice_output', 'Output'), start)
        if folder:
            self._output_touched = True
            self._output_edit.setText(display_path(folder))

    def run_slice(self):
        """Cut the sheet now; returns the written paths ([] on failure)."""
        if self._image.isNull():
            return []
        folder = self.output_folder()
        try:
            self.sliced_paths = slice_sprite_sheet(
                self._image_path, self._cell_w_spin.value(),
                self._cell_h_spin.value(),
                self._offset_x_spin.value(), self._offset_y_spin.value(),
                self._spacing_x_spin.value(), self._spacing_y_spin.value(),
                output_folder=str(folder) if folder else None)
        except (ValueError, OSError) as error:
            self._status_label.setStyleSheet('color: rgb(255, 0, 0);')
            self._status_label.setText(
                T.tr('animation.slice_failed',
                     'Slicing failed: {error}').format(error=error))
            return []
        folder_text = display_path(self.sliced_paths[0].parent) \
            if self.sliced_paths else ''
        message = slice_done_text(len(self.sliced_paths), folder_text)
        self._status_label.clear()
        self._status_label.setStyleSheet('')
        # The result pops up in a message box: a text line under a
        # full-width list of controls was too easy to miss.
        QMessageBox.information(
            self, T.tr('animation.slice_done_title', 'Slice complete'), message)
        self.sliced.emit(folder_text, len(self.sliced_paths))
        return self.sliced_paths

    def clear_all(self):
        """Reset the dialog - sheet, output folder and every parameter.

        Asks first (a stray click would throw away the current setup) and
        returns True only when it really cleared.
        """
        choice = QMessageBox.question(
            self, T.tr('animation.slice_clear', 'Clear'),
            T.tr('animation.slice_clear_confirm',
                 'Clear the sheet, the output folder and every parameter?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice != QMessageBox.StandardButton.Yes:
            return False
        self._image = QImage()
        self._image_path = Path()
        self._output_touched = False
        self._source_edit.clear()
        self.sliced_paths = []
        for spin, value in ((self._cell_w_spin, 32), (self._cell_h_spin, 32),
                            (self._offset_x_spin, 0), (self._offset_y_spin, 0),
                            (self._spacing_x_spin, 0), (self._spacing_y_spin, 0)):
            spin.setValue(value)
        self._status_label.clear()
        self._status_label.setStyleSheet('')
        self._refresh()
        return True

    # ------------------------------------------------------------------ i18n
    def retranslate(self):
        self.setWindowTitle(T.tr('animation.slice_title',
                                 'Slice a sheet PNG into frames'))
        self._source_label.setText(T.tr('animation.slice_source', 'Sheet'))
        self._cell_label.setText(T.tr('animation.slice_cell', 'Frame Size'))
        self._offset_label.setText(T.tr('animation.slice_offset', 'Offset'))
        self._spacing_label.setText(T.tr('animation.slice_spacing', 'Spacing'))
        self._output_label.setText(T.tr('animation.slice_output', 'Output'))
        self._choose_source_btn.setToolTip(T.tr('animation.slice_choose', 'Choose...'))
        self._choose_output_btn.setToolTip(T.tr('animation.slice_folder', 'Folder...'))
        self._run_btn.setText(T.tr('animation.slice_run', 'Slice'))
        self._clear_btn.setText(T.tr('animation.slice_clear', 'Clear'))
        self._close_btn.setText(T.tr('animation.slice_close', 'Close'))
        self._source_edit.setToolTip(T.tr('animation.slice_tip_source',
                                          'The sheet image to cut into frames'))
        self._preview_label.setToolTip(T.tr(
            'animation.slice_tip_preview',
            'Wheel: zoom - middle-drag: move - double-click: reset'))
        self._cell_w_spin.setToolTip(T.tr('animation.slice_tip_cell',
                                          'Size of one frame, in pixels'))
        self._cell_h_spin.setToolTip(self._cell_w_spin.toolTip())
        self._offset_x_spin.setToolTip(T.tr('animation.slice_tip_offset',
                                            'Pixels skipped at the image edge'))
        self._offset_y_spin.setToolTip(self._offset_x_spin.toolTip())
        self._spacing_x_spin.setToolTip(T.tr('animation.slice_tip_spacing',
                                             'Empty pixels between two cells'))
        self._spacing_y_spin.setToolTip(self._spacing_x_spin.toolTip())
        self._output_edit.setToolTip(T.tr('animation.slice_tip_output',
                                          'Folder the frame files are written to'))
        self._run_btn.setToolTip(T.tr('animation.slice_tip_run',
                                      'Cut the sheet into frame files now'))
