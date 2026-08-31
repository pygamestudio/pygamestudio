from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QTextFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from pygamestudio.gui.code.highlighter import CodeHighlighter
from pygamestudio.gui.code.completion import CodeCompleter
from pygamestudio.gui.code.menu import CodeEditorMenu
from pygamestudio.common.utils.config import get_editor_config, update_editor_config
from pygamestudio.common.i18n.translator import Translator as T


class _LineNumberArea(QWidget):
    """Left margin that paints the line numbers next to the editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_number_area(event)


class CodeEditor(QPlainTextEdit):
    """The built-in code editor: syntax highlighting, autocompletion,
    auto-save and line numbers, styled to match the current app theme."""

    save_status_changed = Signal(str)      # human-readable status text
    run_requested = Signal()               # user clicked Run in the context menu
    modified_changed = Signal(bool)        # True while there are unsaved edits
    font_size_changed = Signal(int)        # editor font size changed

    AUTO_SAVE_DELAY_MS = 1500
    DEFAULT_FONT_SIZE = 10
    MIN_FONT_SIZE = 8
    MAX_FONT_SIZE = 26
    INDENT_WIDTH = 4

    def __init__(self):
        super().__init__()
        self._file_path = None
        self._is_modified = False
        self._is_loading = False
        self._font_size = self._load_font_size_from_config()
        self._current_line_color = QColor('#282828')

        self._highlighter = CodeHighlighter(self.document())
        self._completer = CodeCompleter(self)

        self._line_number_area = _LineNumberArea(self)
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(self.AUTO_SAVE_DELAY_MS)
        self._auto_save_timer.timeout.connect(self.auto_save)

        self._set_up()

    def _set_up(self):
        self.setObjectName('codeEditor')
        self._apply_font()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._update_current_line)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._on_update_request)

        self._update_line_number_area_width()

    # ------------------------------------------------------------------ file
    def open_file(self, file_path):
        """Load a text file into the editor and pick the highlighter language."""
        file_path = Path(file_path)
        try:
            content = file_path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            content = file_path.read_text(encoding='utf-8', errors='replace')

        self._is_loading = True
        self.setPlainText(content)
        self._is_loading = False

        self._file_path = file_path
        self._highlighter.set_language(file_path.suffix)
        self.document().setModified(False)
        self._set_modified(False)
        self._update_status(T.tr('code.saved', 'Saved'))

    def save(self):
        """Write the current content to disk (Ctrl+S or auto-save)."""
        if self._file_path is None:
            return
        try:
            self._file_path.write_text(self.toPlainText(), encoding='utf-8')
            self.document().setModified(False)
            self._set_modified(False)
            self._update_status(T.tr('code.saved', 'Saved'))
        except OSError:
            self._update_status(T.tr('code.save_failed', 'Save failed'))

    def auto_save(self):
        """Debounced auto-save triggered shortly after the last edit."""
        if self._file_path is not None and self._is_modified:
            self.save()

    def close_file(self):
        """Flush any pending changes and reset the editor state."""
        self.auto_save()
        self._file_path = None
        self._is_loading = True
        self.clear()
        self._is_loading = False
        self.document().setModified(False)
        self._set_modified(False)
        self._update_status('')

    # ------------------------------------------------------------------ theme
    def apply_theme(self, is_dark):
        """Re-color the highlighter and the current-line highlight after the
        app theme changes."""
        self._highlighter.apply_theme(is_dark)
        self._current_line_color = QColor('#282828' if is_dark else '#f2f2f2')
        self._update_current_line()

    # ------------------------------------------------------------------ font size
    def font_size(self):
        """Current editor font size in points."""
        return self._font_size

    def zoom_in(self):
        """Increase the editor font size (clamped to MAX_FONT_SIZE)."""
        self.set_font_size(self._font_size + 1)

    def zoom_out(self):
        """Decrease the editor font size (clamped to MIN_FONT_SIZE)."""
        self.set_font_size(self._font_size - 1)

    def set_font_size(self, size):
        """Set the editor font size, clamped between MIN and MAX."""
        size = max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, int(size)))
        if size == self._font_size:
            return
        self._font_size = size
        self._apply_font()
        self.font_size_changed.emit(self._font_size)
        update_editor_config('code_editor_font_size', self._font_size)

    def _load_font_size_from_config(self):
        """Read the persisted font size from the editor config, clamped and
        falling back to DEFAULT_FONT_SIZE when missing or invalid."""
        try:
            size = int(get_editor_config().get('code_editor_font_size', self.DEFAULT_FONT_SIZE))
        except (TypeError, ValueError):
            size = self.DEFAULT_FONT_SIZE
        return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))

    def _apply_font(self):
        """Apply the current font size to the editor, its tab stops and the
        line-number margin."""
        self.setFont(QFont('Consolas', self._font_size))
        self.setTabStopDistance(QFontMetrics(self.font()).horizontalAdvance(' ') * 4)
        self._update_line_number_area_width()
        self._line_number_area.update()

    # ------------------------------------------------------------------ indentation
    def _indent(self):
        """Tab: insert spaces up to the next indent stop, or indent every
        selected line by one level when there is a selection."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            self._indent_selection(cursor, 1)
            return
        column = cursor.positionInBlock()
        spaces = self.INDENT_WIDTH - (column % self.INDENT_WIDTH)
        cursor.insertText(' ' * spaces)

    def _unindent(self):
        """Shift+Tab: remove one indent level, or unindent every selected
        line by one level when there is a selection."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            self._indent_selection(cursor, -1)
            return
        block = cursor.block()
        leading = len(block.text()) - len(block.text().lstrip(' '))
        position = cursor.positionInBlock()
        if 0 < position <= leading:
            remove = min(self.INDENT_WIDTH, leading)
            cursor.setPosition(block.position())
            cursor.setPosition(block.position() + remove, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Left,
                                QTextCursor.MoveMode.MoveAnchor,
                                min(self.INDENT_WIDTH, position))
            self.setTextCursor(cursor)

    def _insert_newline_with_indent(self):
        """Enter: start a new line that keeps the current line's leading
        whitespace, adding one extra indent level after a ':'."""
        cursor = self.textCursor()
        line_text = cursor.block().text()
        indent = line_text[:len(line_text) - len(line_text.lstrip(' '))]
        if line_text.strip().endswith(':'):
            indent += ' ' * self.INDENT_WIDTH
        cursor.insertText('\n' + indent)

    def _backspace_unindent(self):
        """Backspace inside the leading whitespace removes a whole indent
        level instead of a single space. Returns True when handled."""
        cursor = self.textCursor()
        block = cursor.block()
        line_text = block.text()
        leading = len(line_text) - len(line_text.lstrip(' '))
        position = cursor.positionInBlock()
        if 0 < position <= leading:
            remove = position % self.INDENT_WIDTH
            remove = remove if remove else self.INDENT_WIDTH
            # Select the whitespace right before the cursor (not the start of
            # the line) and delete it, so the cursor lands on the previous
            # indent stop.
            cursor.setPosition(block.position() + position)
            cursor.setPosition(block.position() + position - remove,
                               QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            return True
        return False

    def _indent_selection(self, cursor, direction):
        """Indent (direction=1) or unindent (direction=-1) every line touched
        by the selection by one indent level."""
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        doc = self.document()
        first = doc.findBlock(start)
        last = doc.findBlock(end)
        if end == last.position() and last.blockNumber() > first.blockNumber():
            last = last.previous()
        cursor.beginEditBlock()
        block = first
        while True:
            if direction > 0:
                QTextCursor(block).insertText(' ' * self.INDENT_WIDTH)
            else:
                leading = len(block.text()) - len(block.text().lstrip(' '))
                if leading:
                    c = QTextCursor(block)
                    remove = min(self.INDENT_WIDTH, leading)
                    c.setPosition(block.position())
                    c.setPosition(block.position() + remove, QTextCursor.MoveMode.KeepAnchor)
                    c.removeSelectedText()
            if block == last:
                break
            block = block.next()
        cursor.endEditBlock()

    # ------------------------------------------------------------------ events
    def _on_text_changed(self):
        if self._is_loading:
            return
        self._set_modified(True)
        self._update_status(T.tr('code.unsaved', 'Unsaved'))
        self._completer.update_words()
        self._auto_save_timer.start()

    def keyPressEvent(self, event):
        if self._completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                # Accept the currently highlighted completion.
                self._completer.activate_current()
                self._completer.popup().hide()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._completer.popup().hide()
                return
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                # Navigate the completion list with the arrow keys.
                self._completer.navigate(event.key() == Qt.Key.Key_Down)
                event.accept()
                return
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.ignore()
                return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Space:
                # Ctrl+Space: force the autocomplete popup.
                self._completer.update_words()
                self._completer.complete_prefix()
                return
            if event.key() == Qt.Key.Key_S:
                # Ctrl+S: save the file (consume it so the global scene save
                # shortcut does not also fire).
                self.save()
                return
            if event.key() == Qt.Key.Key_R:
                # Ctrl+R: run the current project.
                self.run_requested.emit()
                return

        # Indentation: Tab indents with spaces (never a literal tab), Enter
        # keeps the current indentation and Backspace removes a whole level
        # while the cursor is inside the leading whitespace.
        if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) \
                and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                              | Qt.KeyboardModifier.AltModifier
                                              | Qt.KeyboardModifier.MetaModifier)):
            if event.key() == Qt.Key.Key_Backtab:
                self._unindent()
            else:
                self._indent()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._insert_newline_with_indent()
            return
        if event.key() == Qt.Key.Key_Backspace \
                and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if self._backspace_unindent():
                return
        super().keyPressEvent(event)

        # Show completion only while actually typing a word character (not on
        # clicks, cursor moves, Enter, spaces or other control keys).
        text = event.text()
        if text and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                              | Qt.KeyboardModifier.AltModifier
                                              | Qt.KeyboardModifier.MetaModifier)) \
                and (text.isalnum() or text == '_'):
            self._completer.update_words()
            self._completer.complete_prefix()

    def contextMenuEvent(self, event):
        # Replace the default QPlainTextEdit menu with our custom one that
        # also offers a Run Project entry.
        menu = CodeEditorMenu(self, self)
        menu.run_requested.connect(self.run_requested)
        menu.update_actions()
        menu.exec(event.globalPos())
        menu.deleteLater()

    # ------------------------------------------------------------------ status
    def _set_modified(self, modified):
        if modified != self._is_modified:
            self._is_modified = modified
            self.modified_changed.emit(modified)

    def _update_status(self, text):
        self.save_status_changed.emit(text)

    def is_modified(self):
        return self._is_modified

    def current_file_path(self):
        return self._file_path

    # ------------------------------------------------------------------ current line
    def _update_current_line(self):
        """Highlight the full line that currently holds the text cursor."""
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self._current_line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def jump_to_line(self, line):
        """Move the cursor to a 1-based line, scroll it to center and focus."""
        line = max(1, int(line))
        block = self.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.centerCursor()
        self.setFocus()

    # ------------------------------------------------------------------ line numbers
    def line_number_area_width(self):
        digits = max(2, len(str(self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_number_area_width(self, *args):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _on_update_request(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def paint_line_number_area(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(0, 0, 0, 0))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(128, 128, 128))
                painter.drawText(0, top, self._line_number_area.width() - 6, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
