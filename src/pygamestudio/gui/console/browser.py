import re
from datetime import datetime

from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.console.type import *
from pygamestudio.gui.console.menu import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.utils.config import get_editor_config


class ConsoleLogBrowser(QTextBrowser):
    clear_log_signal = Signal()
    info_log_signal = Signal(str)
    error_log_signal = Signal(str)
    warning_log_signal = Signal(str)
    # Carries the actual per-level log counts (info, error, warning) currently
    # held in the log list, emitted whenever the log list changes.
    log_counts_changed = Signal(int, int, int)
    # Emitted when the user Ctrl+clicks an error log that references a source
    # file location (file path + 1-based line number).
    open_file_at_line_signal = Signal(str, int)

    # Upper bound for the in-memory log list, to avoid unbounded memory growth
    # during long-running sessions. Oldest entries are dropped first.
    _max_log_count = 100000

    # Number of oldest lines removed from the text browser at once when the
    # cap is exceeded. Removing lines from the top forces a full document
    # re-layout, so trimming in batches amortizes that cost: without this, a
    # re-layout would run for every single log line once the cap is reached.
    _display_trim_batch = 200

    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._context_menu = ContextMenu('', self)
        
        self._logs = []
        # Block that currently shows the hover underline (jumpable log line).
        self._hovered_block = None
        # Incrementally tracked per-level log counts (info/error/warning).
        # Kept in sync when a log is added or trimmed instead of recounting
        # the whole list from scratch on every append.
        self._log_counts = {INFO: 0, ERROR: 0, WARNING: 0}
        self._search_keyword = ''

        info_format = QTextCharFormat()
        error_format = QTextCharFormat()
        warning_format = QTextCharFormat()
        self._log_formats = {
            INFO: info_format,
            ERROR: error_format,
            WARNING: warning_format
        }

        self._log_check_states = {
            INFO: True,
            ERROR: True,
            WARNING: True
        }

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_logger()
        self._set_object_name()
        self._update_log_formats()

    def _set_widget(self):
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _set_signal(self):
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._context_menu.select_all_signal.connect(self.selectAll)
        self._context_menu.copy_signal.connect(self._copy)

    def _set_logger(self):
        Logger.set_log_widget(self)

    def _set_object_name(self):
        self.setObjectName('consoleLogBrowser')

    def mousePressEvent(self, event):
        """Ctrl+click on an error log jumps to its source location."""
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            match = self._match_file_location(event.pos())
            if match:
                self.open_file_at_line_signal.emit(match[0], match[1])
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Hand cursor + underline while Ctrl-hovering a jumpable log line."""
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and self._match_file_location(event.pos())):
            self._apply_underline(self.cursorForPosition(event.pos()).block())
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._clear_underline()
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._clear_underline()
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().leaveEvent(event)

    def _apply_underline(self, block):
        """Underline a log block to hint that Ctrl+click jumps to its source."""
        if self._hovered_block == block:
            return
        self._clear_underline()
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setFontUnderline(True)
        cursor.mergeCharFormat(fmt)
        self._hovered_block = block

    def _clear_underline(self):
        """Remove the hover underline from the previously hovered block."""
        if self._hovered_block is None:
            return
        cursor = QTextCursor(self._hovered_block)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setFontUnderline(False)
        cursor.mergeCharFormat(fmt)
        self._hovered_block = None

    def _match_file_location(self, pos):
        """Return (file_path, line) referenced by the clicked log line, or
        None. Handles Python tracebacks (File "...", line N) and common
        'path.py:N' style locations."""
        cursor = self.cursorForPosition(pos)
        block_text = cursor.block().text()

        # Python traceback:   File "C:/.../main.py", line 12, in <module>
        match = re.search(r'File "([^"]+)", line (\d+)', block_text)
        if match:
            return (match.group(1), int(match.group(2)))

        # Generic: C:/path/file.py:12 or /path/file.py:12 or ./file.py:12
        match = re.search(r'([A-Za-z]:[\\/][^:\s]+\.py|[\\/][^:\s]+\.py|\.{1,2}[\\/][^:\s]+\.py):(\d+)', block_text)
        if match:
            return (match.group(1), int(match.group(2)))

        return None

    def _add_log(self, msg, log_level):
        now = datetime.now()
        current_time = '[' + now.strftime('%Y-%m-%d %H:%M:%S') + '.%03d' % (now.microsecond // 1000) + ']'
        self._logs.append((current_time, msg, log_level))
        self._log_counts[log_level] += 1

        # Keep the in-memory log list bounded. Deletion is batched (only once
        # the list grows a whole batch past the cap), because removing lines
        # from the top of the text browser triggers a full document re-layout
        # that is expensive to run on every single append.
        if len(self._logs) >= self._max_log_count + self._display_trim_batch:
            removed_count = len(self._logs) - self._max_log_count
            # Decrement the counter of every trimmed log so the counts stay
            # accurate without recounting the list.
            for _, _, removed_log_level in self._logs[:removed_count]:
                self._log_counts[removed_log_level] -= 1
            del self._logs[:removed_count]
            self._remove_oldest_displayed_logs(removed_count)

        log_format = self._log_formats[log_level]
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.textCursor().insertText(f'{current_time} {msg}\n', log_format)
        self._emit_log_counts()

    def _emit_log_counts(self):
        """Push the per-level log counts to the UI."""
        self.log_counts_changed.emit(self._log_counts[INFO], self._log_counts[ERROR], self._log_counts[WARNING])

    def _remove_oldest_displayed_logs(self, count):
        """Remove the oldest `count` lines from the displayed log text."""
        if count <= 0:
            return

        count = min(count, self.document().blockCount() - 1)
        if count <= 0:
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor, count)
        cursor.removeSelectedText()
        cursor.endEditBlock()
    
    def _show_context_menu(self, pos):
        global_pos = self.mapToGlobal(pos)
        self._context_menu.show(global_pos)

    def _copy(self):
        selected_text = self.textCursor().selection().toPlainText()
        QApplication.clipboard().setText(selected_text)
    
    def get_ready_for_project(self):
        ...
        
    def clean_up(self):
        self._clear_log()
        self._search_keyword = ''

    def _clear_log(self):
        self.clear()
        self._logs = []
        self._log_counts = {INFO: 0, ERROR: 0, WARNING: 0}
        self.clear_log_signal.emit()
        self._emit_log_counts()
    
    def clear_log(self):
        self._clear_log()

    def info(self, msg):
        log_level = INFO
        self._add_log(msg, log_level)
        self.info_log_signal.emit(log_level)

    def error(self, msg):
        log_level = ERROR
        self._add_log(msg, log_level)
        self.error_log_signal.emit(log_level)

    def warning(self, msg):
        log_level = WARNING
        self._add_log(msg, log_level)
        self.warning_log_signal.emit(log_level)

    def _update_log_formats(self, theme_code=''):
        if not theme_code:
            theme_code = get_editor_config().get('theme')
        
        info_format = QTextCharFormat()
        error_format = QTextCharFormat()
        warning_format = QTextCharFormat()
        if theme_code == 'light':
            info_format.setForeground(QColor("#000000"))
            error_format.setForeground(QColor('#ff0000'))
            warning_format.setForeground(QColor("#ffb300"))
        else:
            info_format.setForeground(QColor("#ffffff"))
            error_format.setForeground(QColor('#ff0000'))
            warning_format.setForeground(QColor('#ffde66'))

        self._log_formats = {
            INFO: info_format,
            ERROR: error_format,
            WARNING: warning_format
        }

    def reload_logs_on_theme_changed(self, theme_code):
        scroll_bar = self.verticalScrollBar()
        current_scroll_value = scroll_bar.value() 

        self.clear()
        self._update_log_formats(theme_code)
        
        for current_time, msg, log_level in self._logs:
            log_format = self._log_formats[log_level]
            self.moveCursor(QTextCursor.MoveOperation.End)
            self.textCursor().insertText(f'{current_time} {msg}\n', log_format)

        QTimer.singleShot(10, lambda: scroll_bar.setValue(current_scroll_value))

    def _filter(self):
        self.clear()
        for current_time, msg, log_level in self._logs:
            if not self._log_check_states[log_level]:
                continue

            if self._search_keyword and self._search_keyword.lower() not in msg.lower():
                continue

            log_format = self._log_formats[log_level]
            self.textCursor().insertText(f'{current_time} {msg}\n', log_format)

    def search(self, keyword):
        self._search_keyword = keyword.strip()
        self._filter()

    def on_info_check_box_clicked(self, is_checked):
        self._log_check_states[INFO] = is_checked
        self._filter()

    def on_error_check_box_clicked(self, is_checked):
        self._log_check_states[ERROR] = is_checked
        self._filter()

    def on_warning_check_box_clicked(self, is_checked):
        self._log_check_states[WARNING] = is_checked
        self._filter()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_A:
                self.selectAll()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self._copy()
                event.accept()
                return
        
        super().keyPressEvent(event)