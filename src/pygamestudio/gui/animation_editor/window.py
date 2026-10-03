"""The animation editor panel.

Edits the keyframe timeline of the SELECTED Keyframe object: keyframe
snapshots on a timeline (drag a diamond to retime it, right-click to delete),
a per-keyframe easing curve and a preview player. The labelled value row
under the timeline edits the SELECTED keyframe's values (position, scale,
rotation, colour, image); the preview applies the timeline values to the
object transiently (no undo entries) and restores the object's own values
when it stops.

Docked as a center bottom tab between the console and the audio editor.
"""
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QMenu, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.game.object.keyframe import (EASING_CURVES,
                                               normalize_keyframes, snapshot_from_object)
from pygamestudio.game.object.type import OBJECT_KEYFRAME
from pygamestudio.gui.animation_editor.timeline import AnimationTimeline
from pygamestudio.gui.base.window import (DetachButton, WindowBase,
                                          clamp_window_size, editor_run_handler)
from pygamestudio.gui.inspector.color import ColorPicker as ColorPickerPopup
from pygamestudio.gui.inspector.component.lineedit import ImagePathLineEdit
from pygamestudio.gui.inspector.component.picker import ColorPicker as ColorSwatchButton
from pygamestudio.gui.inspector.component.spinbox import SuffixSpinBox

TAB_INDEX = 1  # between the console tab (0) and the audio editor tab (2)

PREVIEW_INTERVAL_MS = 16
TIME_EPSILON = 1e-4


class _ValueRowHost:
    """Adapter that lets the inspector's own widgets live in the animation
    editor's value row: they call back into their "container" when edited."""

    def __init__(self, window):
        self._window = window

    def show_color_picker(self, color_rgba, attr=''):
        self._window._open_color_popup(color_rgba)

    def set_object_path(self, attr, tooltip):
        self._window._on_image_path_picked(attr, tooltip)


class AnimationEditorWindow(QWidget):
    """The animation editor panel (timeline + preview for Keyframe objects)."""

    def __init__(self, game_manager=None):
        super().__init__()
        self._game_manager = game_manager
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None

        self._object_uuid = None
        self._scene_refresher = None
        self._updating = False
        self._selected_index = -1
        self._preview_time = 0.0
        self._playing = False
        self._base_values = None
        self._dirty_preview = False
        self._value_edit_pending = False

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(PREVIEW_INTERVAL_MS)
        self._preview_timer.timeout.connect(self._on_preview_tick)
        self._clock = QElapsedTimer()

        self._play_btn = QPushButton()
        self._stop_btn = QPushButton()
        self._loop_box = QCheckBox()
        self._duration_spin = SuffixSpinBox()
        self._duration_label = QLabel()
        self._add_btn = QPushButton()
        self._delete_btn = QPushButton()
        self._easing_combo = QComboBox()
        self._easing_label = QLabel()
        self._time_title_label = QLabel()
        self._time_label = QLabel()
        self._timeline = AnimationTimeline()
        self._value_spins = {}
        self._pos_label = QLabel()
        self._scale_label = QLabel()
        self._angle_label = QLabel()
        self._color_label = QLabel()
        self._image_label = QLabel()
        self._value_row_host = _ValueRowHost(self)
        self._color_btn = ColorSwatchButton(self._value_row_host,
                                            (255, 255, 255, 255))
        self._color_value = (255, 255, 255, 255)
        self._color_popup = ColorPickerPopup()
        self._image_edit = ImagePathLineEdit(self._value_row_host, '')
        self._image_edit.setProperty('component_attribute', 'image_path')
        self._detach_btn = DetachButton()
        self._hint_label = QLabel()
        self._keyframe_menu = None

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.setObjectName('animationEditorWindow')
        self.retranslate()
        self._clear_ui()

    # ------------------------------------------------------------------ widgets
    def _set_widget(self):
        self._detach_btn.setObjectName('blockEditorToolBtn')

        for button, icon_name in ((self._play_btn, 'play'), (self._stop_btn, 'stop'),
                                  (self._add_btn, 'add'), (self._delete_btn, 'delete')):
            button.setObjectName('blockEditorToolBtn')
            button.setIcon(QIcon(':/images/{}.png'.format(icon_name)))
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(26, 26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._loop_box.setObjectName('animationLoopCheckBox')

        # The duration box uses the inspector's spin style: the unit is
        # pinned to the right edge and the arrows only appear while hovered.
        self._duration_spin.setObjectName('animationDurationSpin')
        self._duration_spin.setRange(0.0, 9999.0)
        self._duration_spin.setDecimals(2)
        self._duration_spin.setSingleStep(0.1)
        self._duration_spin.set_suffix('S')
        self._duration_spin.setFixedWidth(80)

        self._easing_combo.setObjectName('animationEasingCombo')
        self._easing_combo.setFixedWidth(100)

        # Labelled value row: the very widgets the inspector uses (suffix
        # spin boxes, its colour swatch and its path line edit), one control
        # per snapshot channel, following the selected keyframe.
        for channel in ('x', 'y', 'scale_x', 'scale_y', 'angle'):
            spin = SuffixSpinBox()
            spin.setDecimals(2 if channel.startswith('scale') else 1)
            spin.setSingleStep(0.1 if channel.startswith('scale') else 1.0)
            spin.setRange(-999999.0, 999999.0)
            spin.setFixedWidth(64)
            # Keyboard tracking stays ON: the value commits while it is being
            # edited (no Enter needed), matching the inspector's spin boxes.
            spin.set_suffix({'x': 'X', 'y': 'Y',
                             'scale_x': 'X', 'scale_y': 'Y'}.get(channel, ''))
            self._value_spins[channel] = spin

        self._color_btn.setFixedWidth(56)
        self._image_edit.setMinimumWidth(120)

        self._hint_label.setObjectName('animationHintLabel')
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Long tips must wrap: a one-line hint used to force the whole panel
        # (and the tab dock next to it) to be as wide as the sentence.
        self._hint_label.setWordWrap(True)

    def _scroll_row(self, row_layout):
        """Wrap one control row in a scroll strip.

        The row keeps its natural width; a narrow panel scrolls it instead
        of being forced wide (which used to push the whole bottom tab dock
        wide for every page, because a tab widget inherits the widest
        hidden page's minimum).
        """
        content = QWidget()
        content.setLayout(row_layout)
        scroll = QScrollArea()
        scroll.setObjectName('animationRowScroll')
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumWidth(320)
        scroll.setWidget(content)
        # Reserve the scrollbar strip, so the row is never clipped when the
        # scrollbar shows up.
        scroll.setFixedHeight(content.sizeHint().height()
                              + scroll.horizontalScrollBar().sizeHint().height())
        return scroll

    def _set_signal(self):
        self._play_btn.clicked.connect(self.toggle_play)
        self._stop_btn.clicked.connect(self.stop_preview)
        self._loop_box.toggled.connect(self._on_loop_toggled)
        self._duration_spin.valueChanged.connect(self._on_duration_changed)
        self._add_btn.clicked.connect(self.add_keyframe_at_playhead)
        self._delete_btn.clicked.connect(self.delete_selected_keyframe)
        self._easing_combo.currentIndexChanged.connect(self._on_easing_changed)

        for channel, spin in self._value_spins.items():
            spin.valueChanged.connect(
                lambda value, channel=channel: self._on_value_edited(channel))
        self._color_popup.color_changed.connect(self._on_color_picked)

        self._timeline.time_scrubbed.connect(self._on_scrubbed)
        self._timeline.scrub_finished.connect(self._on_scrub_finished)
        self._timeline.keyframe_selected.connect(self._on_keyframe_selected)
        self._timeline.keyframe_context_selected.connect(self._on_keyframe_context_selected)
        self._timeline.keyframe_moved.connect(self._on_keyframe_moved)
        self._timeline.keyframe_menu_requested.connect(self._show_keyframe_menu)
        self._detach_btn.clicked.connect(self.toggle_detached)

        if self._game_manager is not None:
            self._game_manager.object_keyframe_parameter_changed.connect(
                self._on_object_parameter_changed)
            self._game_manager.object_selected.connect(self._on_object_selected)
            self._game_manager.object_deleted.connect(self._on_object_deleted)
            # While a preview runs, an edit of one of the object's OWN
            # channels must end up in the snapshot Stop restores from.
            for signal_name, channel in (('object_moved', 'pos'),
                                         ('object_scaled', 'scale'),
                                         ('object_rotated', 'angle'),
                                         ('object_color_changed', 'color'),
                                         ('object_image_path_changed', 'image_path')):
                getattr(self._game_manager, signal_name).connect(
                    lambda object_uuid, channel=channel:
                        self._merge_preview_base(channel, object_uuid))

    def _set_layout(self):
        toolbar = QHBoxLayout()
        toolbar.addSpacing(6)
        toolbar.addWidget(self._play_btn)
        toolbar.addWidget(self._stop_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._delete_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self._easing_label)
        toolbar.addWidget(self._easing_combo)
        toolbar.addSpacing(10)
        toolbar.addWidget(self._duration_label)
        toolbar.addWidget(self._duration_spin)
        toolbar.addSpacing(10)
        toolbar.addWidget(self._loop_box)
        toolbar.addStretch(1)
        toolbar.addWidget(self._time_title_label)
        toolbar.addWidget(self._time_label)
        toolbar.addSpacing(10)
        toolbar.addWidget(self._detach_btn)

        values = QHBoxLayout()
        values.setSpacing(6)
        values.addSpacing(6)
        values.addWidget(self._pos_label)
        values.addWidget(self._value_spins['x'])
        values.addWidget(self._value_spins['y'])
        values.addSpacing(10)
        values.addWidget(self._scale_label)
        values.addWidget(self._value_spins['scale_x'])
        values.addWidget(self._value_spins['scale_y'])
        values.addSpacing(10)
        values.addWidget(self._angle_label)
        values.addWidget(self._value_spins['angle'])
        values.addSpacing(10)
        values.addWidget(self._image_label)
        values.addWidget(self._image_edit)
        values.addSpacing(10)
        values.addWidget(self._color_label)
        values.addWidget(self._color_btn)
        values.addStretch(1)

        self._toolbar_scroll = self._scroll_row(toolbar)
        self._values_scroll = self._scroll_row(values)

        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self._toolbar_scroll)
        window_layout.addWidget(self._timeline)
        window_layout.addWidget(self._values_scroll)
        window_layout.addWidget(self._hint_label)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(4)

    # ------------------------------------------------------------------ object
    def _object(self):
        if self._object_uuid is None or self._game_manager is None:
            return None
        obj = self._game_manager.get_object(self._object_uuid)
        if obj is not None and getattr(obj, 'type', '') == OBJECT_KEYFRAME:
            return obj
        return None

    def set_object(self, object_uuid, raise_window=True):
        """Edit the given Keyframe object (other object types are ignored)."""
        if self._game_manager is None:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is None or getattr(obj, 'type', '') != OBJECT_KEYFRAME:
            return
        if object_uuid == self._object_uuid:
            if raise_window:
                self.raise_editor()
            return
        self._restore_preview()
        self._object_uuid = object_uuid
        self._preview_time = 0.0
        self._selected_index = -1
        self._timeline.set_selected(-1)
        self._load_from_object()
        if raise_window:
            self.raise_editor()

    def _load_from_object(self):
        """Reload every widget from the object (also used after undo/redo)."""
        obj = self._object()
        if obj is None:
            self._clear_ui()
            return
        keyframes = obj.get_keyframes()
        if not (0 <= self._selected_index < len(keyframes)):
            self._selected_index = -1

        self._updating = True
        try:
            self._timeline.set_keyframes(keyframes)
            self._timeline.set_length(obj.get_timeline_length())
            self._timeline.set_time(self._preview_time)
            self._selected_index = self._timeline.selected_index()
            self._loop_box.setChecked(bool(obj.loop))
            self._duration_spin.setValue(float(obj.duration))
            self._refresh_value_editors()
            self._update_time_label()
        finally:
            self._updating = False
        self._update_enabled_state()
        self._update_titles()

    def _clear_ui(self):
        self._object_uuid = None
        self._selected_index = -1
        self._preview_time = 0.0
        self._updating = True
        try:
            self._timeline.set_keyframes([])
            self._timeline.set_length(1.0)
            self._timeline.set_time(0.0)
            self._timeline.set_selected(-1)
            self._loop_box.setChecked(True)
            self._duration_spin.setValue(2.0)
            self._refresh_value_editors()
            self._update_time_label()
        finally:
            self._updating = False
        self._update_enabled_state()
        self._update_titles()

    def _update_enabled_state(self):
        has_object = self._object() is not None
        for widget in (self._play_btn, self._stop_btn, self._loop_box,
                       self._duration_spin, self._add_btn, self._delete_btn,
                       self._easing_combo):
            widget.setEnabled(has_object)
        self._timeline.setEnabled(has_object)
        self._hint_label.setVisible(not has_object)

    def _refresh_value_editors(self):
        """Follow the selected keyframe: every value control mirrors it and
        is disabled without a selection."""
        obj = self._object()
        frame = None
        if obj is not None:
            keyframes = obj.get_keyframes()
            if 0 <= self._selected_index < len(keyframes):
                frame = keyframes[self._selected_index]

        has_frame = frame is not None
        for channel, spin in self._value_spins.items():
            spin.blockSignals(True)
            if has_frame:
                value = float(frame[channel])
                # Only write when the value really changed: setValue()
                # reformats the text and would disturb the value being typed.
                if abs(spin.value() - value) > 1e-9:
                    spin.setValue(value)
            spin.blockSignals(False)
            spin.setEnabled(has_frame)
        if has_frame:
            self._color_value = tuple(frame['color'])
        self._color_btn.set_color(self._color_value)
        self._color_btn.setEnabled(has_frame)
        self._sync_image_edit(frame if has_frame else None)
        self._easing_combo.blockSignals(True)
        if has_frame:
            curve = frame['easing']
            self._easing_combo.setCurrentIndex(
                EASING_CURVES.index(curve) if curve in EASING_CURVES else 0)
        self._easing_combo.blockSignals(False)
        self._easing_combo.setEnabled(has_frame)

    def _sync_image_edit(self, frame):
        """The image row is the inspector's path line edit: show the
        snapshot's file (red when it is missing) and keep its state in step."""
        path = (frame or {}).get('image_path', '') or ''
        self._image_edit.blockSignals(True)
        self._image_edit._image_path = Path(path)
        self._image_edit.setText(Path(path).name if path else '')
        self._image_edit.setToolTip(Path(path).as_posix() if path else '')
        missing = bool(path) and not (Path(get_project_path()) / path).exists()
        self._image_edit.setStyleSheet('color: rgb(255, 0, 0);' if missing else '')
        self._image_edit.blockSignals(False)
        self._image_edit.setEnabled(frame is not None)

    def _update_time_label(self):
        self._time_label.setText('{:.2f} s'.format(self._preview_time))

    # ------------------------------------------------------------------ commands
    def _commit_keyframes(self, keyframes):
        if self._object() is None:
            return
        self._game_manager.set_keyframe_parameter(self._object_uuid, 'keyframes',
                                                  keyframes)

    def _show_keyframe_menu(self, index, global_pos):
        """Timeline right-click menu: new keyframe (at the playhead) and, on
        a diamond, delete for that keyframe."""
        obj = self._object()
        if obj is None:
            return
        menu = QMenu(self)
        new_action = menu.addAction(
            QIcon(':/images/add.png'),
            T.tr('animation.new_keyframe', 'New Keyframe'))
        new_action.triggered.connect(self.add_keyframe_at_playhead)
        if 0 <= index < len(obj.get_keyframes()):
            delete_action = menu.addAction(
                QIcon(':/images/delete.png'),
                T.tr('animation.delete_keyframe', 'Delete Keyframe'))
            delete_action.triggered.connect(self.delete_selected_keyframe)
        self._keyframe_menu = menu
        menu.popup(global_pos)

    def add_keyframe_at_playhead(self):
        """Snapshot the (interpolated) value at the playhead as a keyframe."""
        obj = self._object()
        if obj is None:
            return
        moment = max(0.0, float(self._preview_time))
        values = obj.evaluate_at(moment)
        if values is not None:
            snapshot = {'time': moment, 'easing': 'linear',
                        'color': list(values['color']),
                        'image_path': values.get('image_path', '')}
            for channel in ('x', 'y', 'scale_x', 'scale_y', 'angle'):
                snapshot[channel] = values[channel]
        else:
            snapshot = snapshot_from_object(obj, moment)

        frames = [frame for frame in obj.get_keyframes()
                  if abs(frame['time'] - moment) > TIME_EPSILON]
        frames.append(snapshot)
        frames = normalize_keyframes(frames)
        index = min(range(len(frames)),
                    key=lambda i: abs(frames[i]['time'] - moment))
        # Commit first: the signal chain hands the new list to the timeline,
        # so selecting the fresh index below is valid.
        self._commit_keyframes(frames)
        self._timeline.set_selected(index)
        self._load_from_object()
        # The fresh keyframe is the one being edited now: show its pose.
        self._apply_preview(moment)

    def delete_selected_keyframe(self):
        """Remove the selected keyframe (undoable)."""
        obj = self._object()
        if obj is None or self._selected_index < 0:
            return
        frames = obj.get_keyframes()
        if not (0 <= self._selected_index < len(frames)):
            return
        frames.pop(self._selected_index)
        self._selected_index = min(self._selected_index, len(frames) - 1) \
            if frames else -1
        self._timeline.set_selected(self._selected_index)
        self._commit_keyframes(frames)
        self._load_from_object()
        if self._selected_index < 0:
            # The last keyframe is gone: nothing is edited any more, so the
            # object goes back to its own values.
            self._restore_preview()

    def _on_keyframe_selected(self, index):
        self._timeline.set_selected(index)
        self._selected_index = index
        self._refresh_value_editors()
        obj = self._object()
        frames = obj.get_keyframes() if obj is not None else []
        if 0 <= index < len(frames):
            # Jump to the keyframe and show it: the value row edits that pose.
            self._apply_preview(frames[index]['time'])
        else:
            # Nothing is being edited: the scene goes back to the object's
            # own values (what the inspector edits) while the playhead stays.
            self._restore_preview()

    def _on_keyframe_context_selected(self, index):
        """Right-click pick: select for the menu WITHOUT moving the playhead
        (the menu's New Keyframe builds on the playhead)."""
        self._timeline.set_selected(index)
        self._selected_index = index
        self._refresh_value_editors()

    def _on_keyframe_moved(self, index, moment):
        obj = self._object()
        if obj is None:
            return
        frames = obj.get_keyframes()
        if not (0 <= index < len(frames)):
            return
        frames[index]['time'] = max(0.0, float(moment))
        frames = normalize_keyframes(frames)
        self._selected_index = min(range(len(frames)),
                                   key=lambda i: abs(frames[i]['time'] - moment))
        self._timeline.set_selected(self._selected_index)
        self._commit_keyframes(frames)
        self._load_from_object()

    def _on_easing_changed(self, combo_index):
        if self._updating:
            return
        obj = self._object()
        if obj is None or combo_index < 0:
            return
        frames = obj.get_keyframes()
        if not (0 <= self._selected_index < len(frames)):
            return
        frames[self._selected_index]['easing'] = EASING_CURVES[combo_index]
        self._commit_keyframes(frames)

    def _on_loop_toggled(self, checked):
        if self._updating or self._object() is None:
            return
        self._game_manager.set_keyframe_parameter(self._object_uuid, 'loop',
                                                  bool(checked))

    def _on_duration_changed(self, value):
        if self._updating or self._object() is None:
            return
        self._game_manager.set_keyframe_parameter(self._object_uuid, 'duration',
                                                  float(value))

    # -------------------------------------------------------------- values
    def _write_channel(self, channel, value):
        """Write one channel of the selected keyframe (one undo entry)."""
        obj = self._object()
        if obj is None:
            return
        frames = obj.get_keyframes()
        if not (0 <= self._selected_index < len(frames)):
            return
        frames[self._selected_index][channel] = value
        # The scene must show the keyframe being edited: the change signal
        # (fired by the command) re-applies the preview at this keyframe.
        self._value_edit_pending = True
        self._game_manager.set_keyframe_parameter(obj.uuid, 'keyframes', frames)

    def _on_value_edited(self, channel):
        if self._updating or self._object() is None:
            return
        self._write_channel(channel, float(self._value_spins[channel].value()))

    def _open_color_popup(self, color_rgba):
        """Show the editor's own colour picker next to the cursor: the very
        popup the inspector uses, never the plain Qt dialog."""
        screen = QApplication.primaryScreen()
        screen_width = screen.geometry().width()
        screen_height = screen.geometry().height()

        pos = QCursor.pos()
        x, y = pos.x(), pos.y()
        if x + self._color_popup.width() > screen_width:
            x = screen_width - self._color_popup.width()
        else:
            x = int(x - self._color_popup.width() / 4)
        if y + self._color_popup.height() > screen_height:
            y = screen_height - self._color_popup.height()
        else:
            y = y + 20

        self._color_popup.set_rgba(color_rgba)
        self._color_popup.move(x, y)
        self._color_popup.show()
        self._color_popup.raise_()

    def _on_color_picked(self, color_rgba):
        rgba = tuple(int(channel) for channel in color_rgba)
        self._write_channel('color', list(rgba))

    def _on_image_path_picked(self, attr, tooltip):
        """The inspector's path line edit reports a chosen/cleared image."""
        if attr == 'image_path':
            self._write_channel('image_path', tooltip)

    # ------------------------------------------------------------------ preview
    def toggle_play(self):
        if self._playing:
            self._pause_clock()
        else:
            self._start_clock()

    def _start_clock(self):
        obj = self._object()
        if obj is None:
            return
        self._snapshot_base()
        self._playing = True
        self._clock.restart()
        self._preview_timer.start()
        self._update_play_button()

    def _pause_clock(self):
        self._playing = False
        self._preview_timer.stop()
        self._update_play_button()

    def _on_preview_tick(self):
        obj = self._object()
        if obj is None:
            self._pause_clock()
            return
        elapsed = self._clock.restart() / 1000.0
        self._preview_time += elapsed
        length = obj.get_timeline_length()
        if length > 0:
            if obj.loop:
                self._preview_time = self._preview_time % length
            elif self._preview_time >= length:
                self._preview_time = length
                self._pause_clock()
        self._apply_preview(self._preview_time)

    def _apply_preview(self, moment):
        """Transiently show the timeline value at ``moment`` (no undo)."""
        obj = self._object()
        if obj is None:
            return
        self._snapshot_base()
        self._preview_time = max(0.0, float(moment))
        if obj.preview_at(self._preview_time):
            self._dirty_preview = True
        self._refresh_scene()
        self._timeline.set_time(self._preview_time)
        self._update_time_label()

    def stop_preview(self):
        """Stop the preview and give the object its own values back."""
        self._restore_preview()
        self._preview_time = 0.0
        self._timeline.set_time(0.0)
        self._update_time_label()

    def _snapshot_base(self):
        obj = self._object()
        if obj is None or self._base_values is not None:
            return
        self._base_values = {
            'pos': (obj.x, obj.y),
            'scale': (obj.scale_x, obj.scale_y),
            'angle': obj.angle,
            'color': list(obj.color),
            'image_path': obj.image_path,
        }

    def _restore_preview(self):
        self._pause_clock()
        obj = self._object()
        if obj is not None and self._base_values is not None and self._dirty_preview:
            obj.pos = self._base_values['pos']
            obj.scale = self._base_values['scale']
            obj.angle = self._base_values['angle']
            obj.color = list(self._base_values['color'])
            obj.image_path = self._base_values.get('image_path', obj.image_path)
            obj._refresh_surface()
            self._refresh_scene()
        self._base_values = None
        self._dirty_preview = False

    def _on_scrubbed(self, moment):
        self._pause_clock()
        if self._selected_index >= 0:
            self._apply_preview(moment)
            return
        # No keyframe is being edited: only the playhead moves, the scene
        # keeps showing the object's own (inspector) values.
        self._restore_preview()
        self._preview_time = max(0.0, float(moment))
        self._timeline.set_time(self._preview_time)
        self._update_time_label()

    def _on_scrub_finished(self, moment):
        self._preview_time = max(0.0, float(moment))
        self._update_time_label()

    def set_scene_refresher(self, callback):
        """The editor hands in a callable that repaints the scene view."""
        self._scene_refresher = callback

    def _refresh_scene(self):
        if callable(self._scene_refresher):
            self._scene_refresher()

    def _update_play_button(self):
        icon_name = 'pause' if self._playing else 'play'
        self._play_btn.setIcon(QIcon(':/images/{}.png'.format(icon_name)))
        self._play_btn.setToolTip(T.tr('animation.pause', 'Pause') if self._playing
                                  else T.tr('animation.play', 'Play'))

    # ------------------------------------------------------------------ mgr signals
    def _on_object_parameter_changed(self, object_uuid):
        if object_uuid != self._object_uuid or self._updating:
            return
        edited = self._value_edit_pending
        self._value_edit_pending = False
        self._load_from_object()
        obj = self._object()
        frames = obj.get_keyframes() if obj is not None else []
        if edited and not self._playing and 0 <= self._selected_index < len(frames):
            # A value was just written into the selected keyframe: show that
            # keyframe's pose right away (also after Stop or a scrub).
            self._apply_preview(frames[self._selected_index]['time'])
        elif self._dirty_preview:
            # Keep the preview in step with the edit (undo/redo included):
            # the inspector edits the selected keyframe, the scene shows it.
            self._apply_preview(self._preview_time)
        else:
            # No preview running: the object's own values changed, so the
            # snapshot the next preview restores from must follow them.
            self._base_values = None

    def _merge_preview_base(self, channel, object_uuid):
        """The object's OWN channel changed while a preview is running.

        The object keeps its new value as its "own" value, so the snapshot
        the preview restores from must adopt it - otherwise Stop would put
        the pre-edit value back.
        """
        if object_uuid != self._object_uuid or not self._dirty_preview:
            return
        if self._base_values is None:
            return
        obj = self._object()
        if obj is None:
            return
        if channel == 'pos':
            self._base_values['pos'] = (obj.x, obj.y)
        elif channel == 'scale':
            self._base_values['scale'] = (obj.scale_x, obj.scale_y)
        elif channel == 'angle':
            self._base_values['angle'] = obj.angle
        elif channel == 'color':
            self._base_values['color'] = list(obj.color)
        elif channel == 'image_path':
            self._base_values['image_path'] = obj.image_path

    def _on_object_selected(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        if obj is None or getattr(obj, 'type', '') != OBJECT_KEYFRAME:
            return
        if object_uuid != self._object_uuid:
            self.set_object(object_uuid, raise_window=False)

    def _on_object_deleted(self, object_uuid):
        if object_uuid == self._object_uuid:
            self._restore_preview()
            self._clear_ui()

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
        run_handler = editor_run_handler(self)
        self._tab_widget.removeTab(self._tab_widget.indexOf(self))
        self.setParent(None)
        self._standalone_window = _AnimationEditorStandaloneWindow(self, self._window_title())
        self._standalone_window.set_editor_run_handler(run_handler)
        self.show()
        self._standalone_window.show()
        self._is_detached = True
        self._update_detach_button()

    def attach(self):
        if not self._is_detached or self._tab_widget is None:
            return
        standalone = self._standalone_window
        self._standalone_window = None
        if standalone is not None:
            standalone._editor_window = None
            standalone.hide()
            standalone.deleteLater()
        # Re-dock between the console (0) and the audio editor.
        self._tab_widget.insertTab(TAB_INDEX, self, self._tab_title())
        self._tab_widget.setCurrentIndex(TAB_INDEX)
        self.show()
        self._is_detached = False
        self._update_detach_button()

    def closeEvent(self, event):
        if self._is_detached:
            self.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def is_detached(self):
        return self._is_detached

    def _raise_window(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.show()
                self._standalone_window.raise_()
                self._standalone_window.activateWindow()
        elif self._tab_widget is not None:
            self._tab_widget.setCurrentWidget(self)

    def raise_editor(self):
        """Bring this editor into view (its tab, or its detached window)."""
        self._raise_window()

    # ------------------------------------------------------------------ titles / i18n
    def _tab_title(self):
        """The tab always carries the panel name, never the object name."""
        return T.tr('animation.editor', 'Animation Editor')

    def _window_title(self):
        return ' Pygame Studio - {}'.format(self._tab_title())

    def _update_titles(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.window_title.set_title_name(self._window_title())
        elif self._tab_widget is not None:
            index = self._tab_widget.indexOf(self)
            if index >= 0:
                self._tab_widget.setTabText(index, self._tab_title())

    def _update_detach_button(self):
        self._detach_btn.set_detached(self._is_detached)

    def retranslate(self):
        self._play_btn.setToolTip(T.tr('animation.pause', 'Pause') if self._playing
                                  else T.tr('animation.play', 'Play'))
        self._stop_btn.setToolTip(T.tr('animation.stop', 'Stop'))
        self._add_btn.setToolTip(T.tr('animation.add_keyframe', 'Add Keyframe'))
        self._delete_btn.setToolTip(T.tr('animation.delete_keyframe', 'Delete Keyframe'))
        self._loop_box.setText(T.tr('animation.loop', 'Loop'))
        self._duration_label.setText(T.tr('animation.duration', 'Duration'))
        self._easing_label.setText(T.tr('animation.easing', 'Easing'))
        self._time_title_label.setText(T.tr('animation.time', 'Time'))
        self._pos_label.setText(T.tr('inspector.pos', 'Pos'))
        self._scale_label.setText(T.tr('inspector.scale', 'Scale'))
        self._angle_label.setText(T.tr('inspector.angle', 'Angle'))
        self._color_label.setText(T.tr('inspector.color', 'Color'))
        self._image_label.setText(T.tr('inspector.image_path', 'Image Path'))
        self._hint_label.setText(T.tr('animation.hint',
                                      'Tip: double-click a Keyframe object in the '
                                      'Hierarchy to open it here'))
        self._easing_combo.blockSignals(True)
        current = self._easing_combo.currentIndex()
        self._easing_combo.clear()
        for curve in EASING_CURVES:
            self._easing_combo.addItem(T.tr('animation.easing_' + curve,
                                            curve.replace('_', ' ').title()))
        if current >= 0:
            self._easing_combo.setCurrentIndex(current)
        self._easing_combo.blockSignals(False)
        self._refresh_value_editors()
        self._update_detach_button()
        self._update_titles()

    def apply_theme(self, is_dark):
        self._timeline.apply_theme(is_dark)

    # ------------------------------------------------------------------ hooks
    def get_ready_for_project(self):
        """A project switch must not leave another project's animation loaded."""
        self._restore_preview()
        self._clear_ui()

    def clean_up(self):
        self._restore_preview()
        self._color_popup.close()
        self._clear_ui()


class _AnimationEditorStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the animation editor while it is
    detached from the center bottom tab widget."""

    def __init__(self, editor_window, title):
        super().__init__()
        self._editor_window = editor_window
        clamp_window_size(self, 900, 420)
        self.set_window_body(editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        if self._editor_window is not None:
            self._editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)
