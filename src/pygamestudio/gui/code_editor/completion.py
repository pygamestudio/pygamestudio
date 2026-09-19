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

# ---------------------------------------------------------------------------
# Engine hints
#
# ``ENGINE_NAMES`` is the curated, hand-written list of what a game script
# usually needs (it doubles as the fallback when the engine cannot be
# inspected). ``api_names()`` adds every name the engine really exposes -
# the ``studio.*`` functions, the object API and the event constants are read
# from the modules themselves, so the popup cannot fall behind the API.
# ---------------------------------------------------------------------------

# engine classes / managers a script can touch
ENGINE_CLASSES = (
    'pygamestudio', 'pygame', 'self',
    'Game', 'SceneLoader', 'AudioManager', 'WindowManager',
    'ObjectBase', 'ObjectCanvas', 'ObjectRect', 'ObjectEllipse', 'ObjectPolygon',
    'ObjectLine', 'ObjectText', 'ObjectImage', 'ObjectButton', 'ObjectParticle',
    'ObjectFrameSequence', 'ObjectTextInput', 'ObjectProgressBar', 'ObjectSlider',
    'ObjectTileMap',
)

# object lifecycle and event callbacks (define only the ones you use)
ENGINE_EVENTS = (
    'on_start', 'on_update', 'on_destroy',
    'on_mouse_enter', 'on_mouse_leave', 'on_pressed', 'on_released', 'on_clicked',
    'on_focus', 'on_blur', 'on_text_changed', 'on_submitted',
    'on_value_changed', 'on_drag_start', 'on_drag', 'on_drag_end',
    'on_right_clicked', 'on_double_clicked', 'on_visible_changed',
    'on_collision_enter', 'on_collision_exit',
    'on_animation_start', 'on_frame_changed', 'on_animation_finished',
    'on_particles_finished', 'on_progress_changed', 'on_progress_full',
)

# object API: transform, visibility, colours, text, images, input
ENGINE_OBJECT_API = (
    # name / type / position / size / scale / angle / hierarchy
    'get_name', 'get_uuid', 'get_type', 'get_x', 'get_y', 'get_pos', 'set_pos',
    'set_x', 'set_y', 'get_width', 'get_height', 'set_width', 'set_height',
    'get_size', 'set_size', 'get_scale_x', 'set_scale_x', 'get_scale_y', 'set_scale_y',
    'get_scale', 'set_scale', 'get_angle', 'set_angle', 'move',
    'get_center', 'set_center', 'get_rect', 'get_world_rect', 'get_world_pos',
    'set_world_pos',
    # visibility / background / border
    'get_color', 'set_color', 'get_visible_state', 'set_visible_state',
    'show', 'hide', 'is_visible', 'is_shown', 'is_hidden',
    'get_background_color', 'set_background_color',
    'get_border_color', 'set_border_color',
    'get_border_radius', 'set_border_radius',
    'get_border_top_left_radius', 'set_border_top_left_radius',
    'get_border_top_right_radius', 'set_border_top_right_radius',
    'get_border_bottom_left_radius', 'set_border_bottom_left_radius',
    'get_border_bottom_right_radius', 'set_border_bottom_right_radius',
    # text / font
    'get_text', 'set_text', 'get_text_color', 'set_text_color',
    'get_text_align', 'set_text_align', 'get_text_valign', 'set_text_valign',
    'get_text_size', 'get_font_path', 'set_font_path', 'set_font',
    'get_font_size', 'set_font_size', 'get_bold_state', 'set_bold_state',
    'get_italic_state', 'set_italic_state',
    'get_underline_state', 'set_underline_state',
    'get_strikethrough_state', 'set_strikethrough_state',
    # input box
    'get_max_length', 'set_max_length', 'get_placeholder', 'set_placeholder',
    'is_password_mode', 'set_password_mode',
    'is_enter_newline', 'set_enter_newline',
    'set_caret_from_world_point',
    # image / line / polygon
    'get_image_path', 'set_image_path',
    'get_start_point', 'set_start_point', 'get_start_x', 'set_start_x',
    'get_start_y', 'set_start_y', 'get_end_point', 'set_end_point',
    'get_end_x', 'set_end_x', 'get_end_y', 'set_end_y',
    'get_thickness', 'set_thickness', 'get_length', 'get_points', 'set_points',
    # pointer helpers
    'is_pressed', 'is_point_inside',
    'distance_to', 'distance_to_object', 'get_direction_to',
    # collision queries / collision body API
    'is_colliding_with_rect', 'is_colliding_with_object', 'get_collision_rect',
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
    'get_auto_play', 'set_auto_play', 'is_auto_play',
    'get_auto_play_state', 'set_auto_play_state',
    'get_loop', 'set_loop', 'get_loop_state', 'set_loop_state',
    'get_frame_index', 'set_frame_index', 'get_frame_count',
    'play', 'pause', 'stop', 'restart', 'is_playing',
)

# studio.* runtime helpers
ENGINE_RUNTIME_API = (
    # scene / objects
    'load_scene', 'create_object', 'destroy_object', 'get_object_by_path',
    'get_object_by_uuid', 'get_parent_object', 'get_root_object', 'get_children',
    'get_all_objects', 'find_objects', 'get_scene_path',
    # game loop / state / input
    'get_screen', 'get_fps', 'set_fps', 'quit', 'is_running',
    'get_delta_time', 'get_elapsed_time', 'get_frame_count',
    'get_pressed_keys', 'get_pressed_buttons', 'is_key_pressed',
    'get_mouse_position', 'is_mouse_button_pressed',
    # audio
    'load_sound', 'play_sound', 'stop_sound', 'stop_all_sounds', 'is_sound_playing',
    'set_sound_volume', 'get_sound_volume',
    'play_music', 'stop_music', 'pause_music', 'resume_music',
    'is_music_playing', 'set_music_volume', 'get_music_volume',
    # window
    'set_window_title', 'get_window_title', 'set_window_icon',
    'get_window_size', 'set_window_size', 'get_window_position',
    'set_window_position', 'center_window', 'get_desktop_size',
    'set_fullscreen', 'is_fullscreen', 'toggle_fullscreen', 'minimize_window',
    'set_window_resizable', 'is_window_resizable',
    'set_mouse_cursor_visible', 'is_mouse_cursor_visible', 'set_mouse_position',
    'set_allow_screensaver', 'is_allow_screensaver',
    # project
    'get_project_config', 'get_project_path',
)

ENGINE_NAMES = ENGINE_CLASSES + ENGINE_EVENTS + ENGINE_OBJECT_API + ENGINE_RUNTIME_API

#: Cache of the names read from the engine (see api_names()).
_API_NAMES = None


def api_names() -> tuple:
    """Every public name the engine offers to a script.

    Reads ``studio.*``, the event constants (``K_*``, ``KMOD_*``) and the object
    API from the modules themselves, so the completion popup always matches the
    engine that is actually installed. The result is cached; if the engine
    cannot be inspected (built editor, import error) the curated
    :data:`ENGINE_NAMES` is all that is used - completion never breaks the
    editor.
    """
    global _API_NAMES
    if _API_NAMES is not None:
        return _API_NAMES

    names = set()
    try:
        import pygamestudio as studio
        from pygamestudio.api.event import constant as event_constants
        from pygamestudio.game.object.base import ObjectBase
        from pygamestudio.game import object as object_models

        names.update(name for name in dir(studio) if not name.startswith('_'))
        names.update(name for name in dir(event_constants) if not name.startswith('_'))
        # Object API: every public member of every scene-object class.
        object_classes = [ObjectBase]
        object_classes += [member for member in vars(object_models).values()
                           if isinstance(member, type) and issubclass(member, ObjectBase)]
        for object_class in object_classes:
            names.update(name for name in dir(object_class) if not name.startswith('_'))
    except Exception:  # noqa: BLE001 - hints must never break the editor
        names = set()

    _API_NAMES = tuple(sorted(names))
    return _API_NAMES


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
        """Rebuild the candidate list: keywords + engine API + document words."""
        words = set(PYTHON_KEYWORDS)
        words.update(PYTHON_BUILTINS)
        words.update(ENGINE_NAMES)
        words.update(api_names())
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
