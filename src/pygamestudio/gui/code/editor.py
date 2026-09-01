from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QTextCharFormat, QTextFormat, QTextCursor
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

    # Characters that auto-complete a closing counterpart while typing.
    _AUTO_PAIRS = {
        '(': ')',
        "'": "'",
        '"': '"',
    }

    def __init__(self):
        super().__init__()
        self._file_path = None
        self._is_modified = False
        self._is_loading = False
        self._font_size = self._load_font_size_from_config()
        self._current_line_color = QColor('#282828')
        self._error_start = None

        self._highlighter = CodeHighlighter(self.document())
        self._completer = CodeCompleter(self)

        self._line_number_area = _LineNumberArea(self)
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(self.AUTO_SAVE_DELAY_MS)
        self._auto_save_timer.timeout.connect(self.auto_save)
        self._syntax_check_timer = QTimer(self)
        self._syntax_check_timer.setSingleShot(True)
        self._syntax_check_timer.setInterval(500)
        self._syntax_check_timer.timeout.connect(self._check_syntax)

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
        self._check_syntax()

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
        self._set_error(None)
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

    # ------------------------------------------------------------------ syntax check
    def _check_syntax(self):
        """Parse the current Python source and remember the position of the
        first syntax error so it can be underlined."""
        if self._file_path is None or self._file_path.suffix.lower() != '.py':
            self._set_error(None)
            return
        source = self.toPlainText()
        try:
            compile(source, str(self._file_path), 'exec')
        except SyntaxError as e:
            self._set_error(self._syntax_error_position(e, source))
            return
        self._set_error(None)

    def _syntax_error_position(self, error, source):
        """Return the document position where the syntax error starts, or
        None when the error points past the end of the file.

        An error at the very end of the file usually means the user is still
        typing that statement (a bare 'import', an open parenthesis, an
        unclosed string...), so it is not flagged yet - mirroring how VS Code
        avoids red-squiggling incomplete code while it is being typed."""
        if error.lineno is None or error.offset is None:
            return None
        block = self.document().findBlockByNumber(error.lineno - 1)
        line_start = block.position() if block.isValid() else len(source)
        position = line_start + max(0, error.offset - 1)
        if position >= len(source.rstrip(' \t\n\r')):
            return None
        # Skip indentation so the underline starts on the offending token.
        while position < len(source) and source[position] in ' \t':
            position += 1
        return position

    def _set_error(self, start_position):
        if start_position != self._error_start:
            self._error_start = start_position
            self._update_current_line()

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

    # ------------------------------------------------------------------ auto pairing
    def _handle_auto_pair(self, char):
        """Handle auto-pairing for '(' and quotes, plus smart-close for ')'
        (step over the closing char when it is already right of the cursor)."""
        cursor = self.textCursor()
        if char == '(':
            if cursor.hasSelection():
                self._wrap_selection(cursor, '(', ')')
                return True
            return self._handle_paren(cursor, '(', ')')
        if char in ("'", '"'):
            if cursor.hasSelection():
                self._wrap_selection(cursor, char, char)
                return True
            if self.document().characterAt(cursor.position()) == char:
                # The closing quote is already right of the cursor: step over it.
                cursor.movePosition(QTextCursor.MoveOperation.Right)
                self.setTextCursor(cursor)
                return True
            return self._handle_quote(cursor, char)
        if char == ')':
            if self.document().characterAt(cursor.position()) == ')':
                cursor.movePosition(QTextCursor.MoveOperation.Right)
                self.setTextCursor(cursor)
                return True
            return False
        return False

    def _handle_paren(self, cursor, open_char, close_char):
        """'(' inserts '()' with the cursor in between; if the closing paren
        is already right of the cursor, just move past it."""
        if self.document().characterAt(cursor.position()) == close_char:
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cursor)
            return True
        cursor.insertText(open_char + close_char)
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        return True

    def _handle_quote(self, cursor, char):
        """Auto-pair a quote, keep it plain when adjacent to an existing
        quote or right after a word character (apostrophes), and build a
        triple quote when the third quote is typed."""
        doc = self.document()
        pos = cursor.position()
        prev = doc.characterAt(pos - 1)
        prev2 = doc.characterAt(pos - 2)

        if prev == char and prev2 == char:
            before = doc.characterAt(pos - 3)
            if not (before.isalnum() or before == '_'):
                # Third quote of an opening triple: complete it as 3 + 3.
                cursor.insertText(char * 4)
                cursor.movePosition(QTextCursor.MoveOperation.Left,
                                    QTextCursor.MoveMode.MoveAnchor, 3)
                self.setTextCursor(cursor)
                return True
            # Otherwise it is the closing quote of a triple already being
            # typed - keep it plain.
            cursor.insertText(char)
            return True
        if prev == char:
            # Second quote in a row: type it manually, do not pair.
            cursor.insertText(char)
            return True
        if prev.isalnum() or prev == '_':
            # A quote right after a word is likely an apostrophe.
            cursor.insertText(char)
            return True
        cursor.insertText(char + char)
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        return True

    def _wrap_selection(self, cursor, open_char, close_char):
        """Wrap the current selection in the given bracket/quote pair."""
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        selected = self.toPlainText()[start:end]
        cursor.insertText(open_char + selected + close_char)

    # ------------------------------------------------------------------ events
    def _on_text_changed(self):
        if self._is_loading:
            return
        self._set_modified(True)
        self._update_status(T.tr('code.unsaved', 'Unsaved'))
        self._completer.update_words()
        self._auto_save_timer.start()
        self._syntax_check_timer.start()

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

        # Auto-complete bracket and quote pairs while typing.
        text = event.text()
        if text and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                              | Qt.KeyboardModifier.AltModifier
                                              | Qt.KeyboardModifier.MetaModifier)) \
                and (text in self._AUTO_PAIRS or text == ')'):
            if self._handle_auto_pair(text):
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
        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete) \
                and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                              | Qt.KeyboardModifier.AltModifier
                                              | Qt.KeyboardModifier.MetaModifier)):
            # Deleting a character may shorten the identifier being typed, so
            # refresh the completion list (or dismiss it when no prefix is
            # left before the cursor).
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
        """Highlight the full line that currently holds the text cursor and
        draw a red wave underline under any syntax-error line."""
        selections = []

        # Current line highlight.
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self._current_line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        selections.append(selection)

        # Red wave underline on the syntax-error token (not the whole line).
        if self._error_start is not None:
            block = self.document().findBlock(self._error_start)
            if block.isValid():
                error_selection = QTextEdit.ExtraSelection()
                error_format = QTextCharFormat()
                error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                error_format.setUnderlineColor(QColor('#f14c4c'))
                error_selection.format = error_format
                error_selection.cursor = QTextCursor(block)
                error_selection.cursor.setPosition(self._error_start)
                error_selection.cursor.movePosition(
                    QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                selections.append(error_selection)

        self.setExtraSelections(selections)

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
