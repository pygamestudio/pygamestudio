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

# Words frequently used with the engine's object / runtime API (nice
# completion hints). Kept as a set so duplicates with the document words or
# between entries collapse.
ENGINE_NAMES = (
    # engine / object classes
    'pygamestudio', 'ObjectBase', 'ObjectCanvas', 'ObjectRect', 'ObjectEllipse',
    'ObjectPolygon', 'ObjectLine', 'ObjectText', 'ObjectImage', 'ObjectButton',
    'ObjectParticle', 'ObjectFrameSequence', 'self',
    # common transform / query helpers
    'on_start', 'on_update', 'on_destroy',
    'get_name', 'get_uuid', 'get_type', 'get_x', 'get_y', 'get_pos', 'set_pos',
    'set_x', 'set_y', 'get_width', 'get_height', 'set_width', 'set_height',
    'get_size', 'set_size', 'get_scale_x', 'get_scale_y', 'get_scale', 'set_scale',
    'get_angle', 'set_angle', 'get_color', 'set_color', 'get_visible_state',
    'set_visible_state', 'show', 'hide', 'is_visible',
    'get_center', 'set_center', 'move', 'get_rect', 'get_world_rect',
    'get_world_pos', 'is_pressed', 'is_point_inside', 'is_shown', 'is_hidden',
    'distance_to', 'distance_to_object', 'get_direction_to',
    'is_colliding_with_rect', 'is_colliding_with_object', 'get_collision_rect',
    # collision body API
    'is_collision_enabled', 'set_collision_enabled', 'get_collision_type',
    'set_collision_type', 'set_collision_offset', 'get_collision_offset',
    'set_collision_size', 'get_collision_size', 'get_collision_radius',
    'set_collision_ellipse', 'set_collision_polygon', 'get_collision_polygon',
    'reset_collision_shape', 'get_collision_center', 'collides_with_point',
    'collides_with_rect', 'collides_with_object',
    # particle emitter API
    'get_emission_rate', 'set_emission_rate', 'get_max_particles',
    'set_max_particles', 'get_particle_lifetime', 'set_particle_lifetime',
    'get_particle_speed', 'set_particle_speed', 'get_particle_size',
    'set_particle_size', 'get_particle_image', 'set_particle_image',
    'get_gravity', 'set_gravity', 'get_spread_angle', 'set_spread_angle',
    'get_particle_count', 'emit_particles', 'clear_particles',
    # frame-sequence API
    'get_frame_folder', 'set_frame_folder', 'get_frame_rate', 'set_frame_rate',
    'get_auto_play', 'set_auto_play', 'get_loop', 'set_loop', 'get_frame_index',
    'set_frame_index', 'get_frame_count', 'play', 'pause', 'stop', 'restart',
    'is_playing',
    # runtime top-level helpers
    'get_object_by_path', 'get_object_by_uuid', 'get_parent_object',
    'get_screen', 'get_fps', 'set_fps', 'quit',
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
        # Only look at the current line up to the cursor, so a word on a
        # previous line can never act as the completion prefix (e.g. right
        # after deleting a word on an empty line).
        line_prefix = cursor.block().text()[:cursor.positionInBlock()]
        match = re.search(r'[A-Za-z_]\w*$', line_prefix)
        if not match:
            self.popup().hide()
            return False

        prefix = match.group()
        self.setCompletionPrefix(prefix)
        # Rank candidates:
        #   1. words that START with the prefix (before words that only contain
        #      it), and
        #   2. within each group respect the case the user is typing - words
        #      whose spelling matches the typed prefix exactly come first, then
        #      words starting with the same case (uppercase input prefers
        #      uppercase starts, lowercase input prefers lowercase starts).
        #      Without this a lowercase input could put "Text" before "text".
        prefix_lower = prefix.lower()
        prefix_is_upper = prefix[0].isupper()

        def rank(word):
            exact = 0 if word.startswith(prefix) else 1
            same_case = 0 if (word[0].isupper() == prefix_is_upper) else 1
            return (exact, same_case, word.lower(), word)

        starts = [w for w in self._all_words if w.lower().startswith(prefix_lower)]
        contains = [w for w in self._all_words
                    if prefix_lower in w.lower() and w not in starts]
        self._model.setStringList(sorted(starts, key=rank) + sorted(contains, key=rank))
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
