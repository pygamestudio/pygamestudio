import re

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QCompleter


PYTHON_KEYWORDS = (
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
    'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global',
    'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
    'raise', 'return', 'try', 'while', 'with', 'yield',
)

PYTHON_BUILTINS = (
    'abs', 'all', 'any', 'bool', 'dict', 'dir', 'enumerate', 'filter', 'float',
    'format', 'getattr', 'hasattr', 'int', 'isinstance', 'issubclass', 'iter',
    'len', 'list', 'map', 'max', 'min', 'next', 'object', 'open', 'ord', 'pow',
    'print', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
    'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars',
    'zip',
)

# Words frequently used with the engine's object API (nice completion hints).
ENGINE_NAMES = (
    'pygamestudio', 'ObjectBase', 'ObjectRect', 'ObjectText', 'ObjectImage',
    'ObjectButton', 'ObjectLine', 'ObjectPolygon', 'ObjectEllipse', 'self',
    'get_x', 'get_y', 'get_pos', 'set_pos', 'get_width', 'get_height',
    'get_size', 'set_size', 'get_angle', 'set_angle', 'get_color', 'set_color',
    'set_visible', 'get_visible', 'on_start', 'on_update', 'on_destroy',
    'is_point_inside', 'get_center', 'move', 'distance_to', 'show', 'hide',
)


class CodeCompleter(QCompleter):
    """Popup autocompletion for the code editor.

    Offers Python keywords/builtins plus every identifier already present in
    the document, so completion adapts to the user's own code.
    """

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self._model = QStringListModel(self)
        self.setModel(self._model)
        self.setWidget(editor)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(10)
        self.popup().setObjectName('codeEditorCompletionPopup')
        self.activated.connect(self._insert_completion)
        self._all_words = []

    def update_words(self):
        """Rebuild the candidate list: keywords + identifiers in the doc."""
        words = set(PYTHON_KEYWORDS)
        words.update(PYTHON_BUILTINS)
        words.update(ENGINE_NAMES)
        text = self._editor.toPlainText()
        for match in re.finditer(r'\b[A-Za-z_]\w*\b', text):
            words.add(match.group())
        self._all_words = sorted(words)
        self._model.setStringList(self._all_words)

    def complete_prefix(self):
        """Show the popup under the cursor for the identifier being typed."""
        cursor = self._editor.textCursor()
        text_before = self._editor.toPlainText()[:cursor.position()]
        match = re.search(r'[A-Za-z_]\w*$', text_before)
        if not match:
            self.popup().hide()
            return False

        prefix = match.group()
        self.setCompletionPrefix(prefix)
        # Most relevant first: words that start with the prefix come before
        # words that merely contain it (alphabetical within each group).
        prefix_lower = prefix.lower()
        starts = [w for w in self._all_words if w.lower().startswith(prefix_lower)]
        contains = [w for w in self._all_words if prefix_lower in w.lower() and w not in starts]
        self._model.setStringList(starts + contains)
        self._show_popup_at_cursor()
        return True

    def _show_popup_at_cursor(self):
        """Position the popup right below the text cursor and show it."""
        if self.completionCount() == 0:
            self.popup().hide()
            return

        cursor_rect = self._editor.cursorRect()
        global_pos = self._editor.viewport().mapToGlobal(cursor_rect.topLeft())
        popup = self.popup()
        popup.setCurrentIndex(self.completionModel().index(0, 0))
        popup.setGeometry(global_pos.x(),
                          global_pos.y() + self._editor.fontMetrics().height() + 2,
                          popup.sizeHint().width(),
                          popup.sizeHint().height())
        popup.show()
        return True

    def _insert_completion(self, completion):
        """Replace the word under the cursor with the chosen completion."""
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor)
        # Expand the selection to the whole identifier being completed.
        text = self._editor.toPlainText()
        start = cursor.selectionStart()
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == '_'):
            start -= 1
        cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfWord, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(completion)
        self._editor.setTextCursor(cursor)

    def activate_current(self):
        """Insert the currently highlighted completion into the document.
        Used when Enter is pressed while the popup is open."""
        index = self.popup().currentIndex()
        if index.isValid():
            self._insert_completion(index.data())
            return True
        return False

    def navigate(self, down=True):
        """Move the popup selection up/down (arrow keys)."""
        model = self.completionModel()
        count = model.rowCount()
        if count == 0:
            return
        row = self.popup().currentIndex().row()
        if down:
            row = (row + 1) % count
        else:
            row = (row - 1) % count
        self.popup().setCurrentIndex(model.index(row, 0))
