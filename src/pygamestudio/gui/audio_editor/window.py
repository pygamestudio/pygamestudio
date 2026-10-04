from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from pygamestudio.gui.audio_editor import codec, dsp
from pygamestudio.gui.audio_editor.engine import (AudioEngine, STATE_PLAYING,
                                                  STATE_PAUSED)
from pygamestudio.gui.audio_editor.widgets import AudioWaveformView
from pygamestudio.gui.base.window import (DetachButton, WindowBase,
                                          clamp_window_size, editor_run_handler)
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.console.logger import Logger

AUDIO_OPEN_FILTER = ('Audio (*.wav *.mp3 *.ogg *.flac *.aif *.aiff *.m4a)')

#: Containers the game mixer cannot decode (m4a/AAC, wma, ...): opening one
#: says so instead of offering a conversion that cannot work.
UNPLAYABLE_SUFFIXES = ('.m4a', '.m4b', '.aac', '.wma')

AUDIO_SAVE_FILTER = ';;'.join('{} (*{})'.format(suffix[1:].upper(), suffix)
                              for suffix in codec.SAVE_SUFFIXES)


def format_time(ms):
    """Milliseconds -> 'm:ss'."""
    ms = max(0, int(ms))
    seconds = ms // 1000
    return f'{seconds // 60}:{seconds % 60:02d}'


def format_size(num_bytes):
    """Bytes -> human readable size string."""
    size = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            if unit == 'B':
                return f'{int(size)} {unit}'
            return f'{size:.1f} {unit}'
        size /= 1024.0
    return f'{int(num_bytes)} B'


class AudioEditorWindow(QWidget):
    """The built-in audio editor.

    Transport buttons (previous / play-pause / stop / next) and the file
    controls sit on the first toolbar row; the second row holds the editing
    tools: undo/redo plus the grouped selection operations (delete + trim,
    silence + volume, fade in/out, reverse, copy/paste). Below them the
    waveform fills the space: drag to select, click to seek, wheel to zoom
    around the cursor, middle-drag to pan, double click to see the whole
    file.

    Edits work on an in-memory float32 buffer (numpy) and are undoable. Save
    writes back in the file's own format (WAV/FLAC lossless; OGG/MP3 are
    re-encoded with a quality close to a normal source file). Formats the
    editor cannot save (m4a, ...) are offered to be converted to WAV first;
    if the user declines they load in play-only mode.

    The tab and the floating window always keep the panel name; a '\*' in
    the toolbar's file name marks unsaved changes.
    """

    def __init__(self, game_manager=None):
        super().__init__()
        self._game_manager = game_manager
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None
        self._current_path = None
        self._current_size = 0
        self._buffer = None                 # AudioBuffer while the format is editable
        self._clipboard = None              # copied samples (numpy)

        self._engine = AudioEngine()
        self._ticker = QTimer(self)
        self._ticker.setInterval(100)

        self._detach_btn = DetachButton()
        self._open_btn = QPushButton()
        self._save_btn = QPushButton()
        self._save_as_btn = QPushButton()
        self._prev_btn = QPushButton()
        self._play_btn = QPushButton()
        self._next_btn = QPushButton()
        self._stop_btn = QPushButton()
        self._undo_btn = QPushButton()
        self._redo_btn = QPushButton()
        self._delete_btn = QPushButton()
        self._silence_btn = QPushButton()
        self._trim_btn = QPushButton()
        self._fade_in_btn = QPushButton()
        self._fade_out_btn = QPushButton()
        self._gain_btn = QPushButton()
        self._reverse_btn = QPushButton()
        self._copy_btn = QPushButton()
        self._paste_btn = QPushButton()
        self._append_btn = QPushButton()
        self._pitch_btn = QPushButton()
        self._speed_btn = QPushButton()
        self._waveform = AudioWaveformView()
        self._size_label = QLabel()
        self._file_label = QLabel()
        self._time_label = QLabel()

        self._play_icon = QIcon(':/images/play.png')
        self._pause_icon = QIcon(':/images/pause.png')

        self._set_up()

    # ------------------------------------------------------------------ setup
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.setObjectName('audioEditorWindow')

    def _set_widget(self):
        self._update_detach_button()

        # Open / save any audio file from disk (not only project files).
        for btn, icon, key, default in (
            (self._open_btn, ':/images/browse.png', 'audio.open', 'Open Audio File'),
            (self._save_btn, ':/images/save.png', 'audio.save', 'Save (Ctrl+S)'),
            (self._save_as_btn, ':/images/save_as.png', 'audio.save_as', 'Save As'),
        ):
            btn.setObjectName('imageEditorToolBtn')
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            btn.setToolTip(T.tr(key, default))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Transport buttons, styled like the image editor's icon buttons.
        for btn, icon, key, default in (
            (self._prev_btn, ':/images/previous.png', 'audio.previous', 'Previous'),
            (self._stop_btn, ':/images/stop.png', 'audio.stop', 'Stop'),
            (self._next_btn, ':/images/next.png', 'audio.next', 'Next'),
        ):
            btn.setObjectName('imageEditorToolBtn')
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            btn.setToolTip(T.tr(key, default))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._play_btn.setObjectName('imageEditorToolBtn')
        self._play_btn.setIcon(self._play_icon)
        self._play_btn.setIconSize(QSize(18, 18))
        self._play_btn.setFixedSize(28, 28)
        self._play_btn.setToolTip(T.tr('audio.play', 'Play'))
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Editing tools (second toolbar row). They stay gray while a format
        # the editor cannot save is loaded for preview only.
        for btn, icon, key, default in (
            (self._undo_btn, ':/images/undo.png', 'audio.undo', 'Undo (Ctrl+Z)'),
            (self._redo_btn, ':/images/redo.png', 'audio.redo', 'Redo (Ctrl+Y)'),
            (self._delete_btn, ':/images/delete.png',
             'audio.delete_selection', 'Delete Selection'),
            (self._trim_btn, ':/images/cut_clip.png', 'audio.trim', 'Trim to Selection'),
            (self._silence_btn, ':/images/mute.png', 'audio.silence', 'Silence'),
            (self._fade_in_btn, ':/images/fade_in.png', 'audio.fade_in', 'Fade In'),
            (self._fade_out_btn, ':/images/fade_out.png', 'audio.fade_out', 'Fade Out'),
            (self._gain_btn, ':/images/volume_up.png', 'audio.gain', 'Increase Volume'),
            (self._reverse_btn, ':/images/reverse.png', 'audio.reverse', 'Reverse'),
            (self._copy_btn, ':/images/copy.png', 'audio.copy', 'Copy'),
            (self._paste_btn, ':/images/paste.png', 'audio.paste', 'Paste'),
            (self._append_btn, ':/images/add.png', 'audio.append', 'Append Audio Files'),
            (self._pitch_btn, ':/images/pitch.png', 'audio.pitch', 'Change Pitch'),
            (self._speed_btn, ':/images/speed.png', 'audio.speed', 'Change Speed'),
        ):
            btn.setObjectName('imageEditorToolBtn')
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            btn.setToolTip(T.tr(key, default))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._size_label.setObjectName('audioEditorSizeLabel')
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._file_label.setObjectName('audioEditorFileLabel')
        self._file_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._time_label.setObjectName('audioEditorTimeLabel')
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._time_label.setMinimumWidth(88)
        self._time_label.setText('0:00 / 0:00')

        # Empty state: ask the user to pick an audio file instead of a gray bar.
        self._waveform.set_placeholder(T.tr('audio.empty_hint', 'Choose an audio file'))

        self._update_controls()
        self._update_edit_controls()
        self._update_time_display()

    def _set_signal(self):
        self._ticker.timeout.connect(self._on_tick)
        self._waveform.seek_requested.connect(self._on_seek)
        self._waveform.selection_changed.connect(self._update_edit_controls)

        self._detach_btn.clicked.connect(self.toggle_detached)
        self._open_btn.clicked.connect(self.choose_audio)
        self._save_btn.clicked.connect(self.save)
        self._save_as_btn.clicked.connect(self.save_as)
        self._prev_btn.clicked.connect(self._play_previous)
        self._play_btn.clicked.connect(self._toggle_play)
        self._stop_btn.clicked.connect(self._stop_playback)
        self._next_btn.clicked.connect(self._play_next)
        self._undo_btn.clicked.connect(self._undo)
        self._redo_btn.clicked.connect(self._redo)
        self._delete_btn.clicked.connect(self._delete_selection)
        self._silence_btn.clicked.connect(self._silence_selection)
        self._trim_btn.clicked.connect(self._trim_selection)
        self._fade_in_btn.clicked.connect(lambda: self._fade(True))
        self._fade_out_btn.clicked.connect(lambda: self._fade(False))
        self._gain_btn.clicked.connect(self._change_gain)
        self._reverse_btn.clicked.connect(self._reverse)
        self._copy_btn.clicked.connect(self._copy)
        self._paste_btn.clicked.connect(self._paste)
        self._append_btn.clicked.connect(self._append_audio)
        self._pitch_btn.clicked.connect(self._change_pitch)
        self._speed_btn.clicked.connect(self._change_speed)

    def _set_layout(self):
        # Row 1: file + transport buttons, time, then size + file + detach
        # pushed to the right.
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._open_btn)
        toolbar.addWidget(self._save_btn)
        toolbar.addWidget(self._save_as_btn)
        toolbar.addWidget(self._prev_btn)
        toolbar.addWidget(self._play_btn)
        toolbar.addWidget(self._stop_btn)
        toolbar.addWidget(self._next_btn)
        toolbar.addWidget(self._time_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self._size_label)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._file_label)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._detach_btn)

        # Row 2: the editing tools, grouped - undo/redo, the selection edits
        # (delete + trim kept together), the loudness edits (silence +
        # volume), the fades/reverse, then the clipboard.
        edit_toolbar = QHBoxLayout()
        edit_toolbar.addWidget(self._undo_btn)
        edit_toolbar.addWidget(self._redo_btn)
        for btn in (self._delete_btn, self._trim_btn):
            edit_toolbar.addWidget(btn)
        for btn in (self._silence_btn, self._gain_btn):
            edit_toolbar.addWidget(btn)
        for btn in (self._fade_in_btn, self._fade_out_btn, self._reverse_btn):
            edit_toolbar.addWidget(btn)
        for btn in (self._copy_btn, self._paste_btn):
            edit_toolbar.addWidget(btn)
        for btn in (self._append_btn, self._pitch_btn, self._speed_btn):
            edit_toolbar.addWidget(btn)
        edit_toolbar.addStretch(1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 4)
        main_layout.setSpacing(4)
        main_layout.addLayout(toolbar)
        main_layout.addLayout(edit_toolbar)
        main_layout.addWidget(self._waveform, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_labels()

    def _update_responsive_labels(self):
        """Low-priority labels step aside when the panel gets narrow.

        The full information stays reachable through the labels' tooltips,
        so nothing is lost - the toolbar just stops forcing a wide panel on
        small screens.
        """
        width = self.width()
        self._time_label.setVisible(width >= 420)
        self._size_label.setVisible(width >= 520)
        self._file_label.setVisible(width >= 620)

    # ------------------------------------------------------------------ state
    def _update_controls(self):
        loaded = self._engine.is_loaded()
        self._play_btn.setEnabled(loaded)
        self._stop_btn.setEnabled(self._engine.state() != 'stopped')
        self._update_navigation_buttons()

    def _update_navigation_buttons(self):
        neighbours = len(self._playlist())
        self._prev_btn.setEnabled(neighbours > 1)
        self._next_btn.setEnabled(neighbours > 1)

    def _update_edit_controls(self):
        """Enable the second toolbar row for the current editing state.

        Everything needs an editable buffer; the selection operations also
        need a real selection and paste needs something to paste.
        """
        buffer = self._buffer
        has = buffer is not None
        selection = self._waveform.selection() if has else None
        for btn in (self._save_btn, self._save_as_btn, self._fade_in_btn,
                    self._fade_out_btn, self._gain_btn,
                    self._reverse_btn, self._copy_btn,
                    self._append_btn, self._pitch_btn, self._speed_btn):
            btn.setEnabled(has)
        for btn in (self._delete_btn, self._silence_btn, self._trim_btn):
            btn.setEnabled(has and selection is not None)
        self._paste_btn.setEnabled(has and self._clipboard is not None)
        self._undo_btn.setEnabled(has and buffer.can_undo())
        self._redo_btn.setEnabled(has and buffer.can_redo())

    def _toggle_play(self):
        self._engine.toggle()
        self._sync_ui_from_state()
        if self._engine.state() == STATE_PLAYING:
            self._ticker.start()
        else:
            self._ticker.stop()
        self._update_time_display()

    def _stop_playback(self):
        self._engine.stop()
        self._sync_ui_from_state()
        self._update_time_display()
        self._ticker.stop()

    def _sync_ui_from_state(self):
        if self._engine.state() == STATE_PLAYING:
            self._play_btn.setIcon(self._pause_icon)
            self._play_btn.setToolTip(T.tr('audio.pause', 'Pause'))
        else:
            self._play_btn.setIcon(self._play_icon)
            self._play_btn.setToolTip(T.tr('audio.play', 'Play'))
        self._update_controls()

    def _on_seek(self, fraction):
        duration = self._engine.duration_ms()
        if duration <= 0:
            return
        target = int(fraction * duration)
        self._engine.seek(target)
        if self._engine.state() == STATE_PLAYING:
            # Seek restarted the audio; keep ticking.
            if not self._ticker.isActive():
                self._ticker.start()
            self._update_time_display()
        else:
            # Paused / stopped: just move the playhead (state is preserved).
            self._ticker.stop()
            self._update_time_display(target)

    def _on_tick(self):
        if not self._engine.is_loaded() or self._engine.state() != STATE_PLAYING:
            self._ticker.stop()
            return
        if not self._engine.is_busy():
            # Track reached its end.
            self._engine.stop()
            self._sync_ui_from_state()
            self._update_time_display()
            self._ticker.stop()
            return
        self._update_time_display()

    def _update_time_display(self, position_ms=None):
        duration = self._engine.duration_ms()
        if position_ms is None:
            position_ms = self._engine.position_ms()
        position_ms = max(0, min(duration, int(position_ms)))
        if duration > 0:
            self._waveform.set_progress(position_ms / duration)
        else:
            self._waveform.set_progress(0.0)
        self._time_label.setText(f'{format_time(position_ms)} / {format_time(duration)}')
        self._time_label.setToolTip(self._time_label.text())

    # ------------------------------------------------------------------ editing
    def _region(self, whole_without_selection=True):
        """Frame range for an edit: the selection or (optionally) the whole file."""
        if self._buffer is None:
            return None
        selection = self._waveform.selection()
        if selection is None:
            if not whole_without_selection:
                return None
            return 0, self._buffer.frames
        total = self._buffer.frames
        start = max(0, min(total, int(round(selection[0]))))
        end = max(start, min(total, int(round(selection[1]))))
        return start, end

    def _edit(self, operation):
        """Run one buffer operation and refresh everything around it."""
        if self._buffer is None:
            return
        frames_before = self._buffer.frames
        operation(self._buffer)
        self._after_edit(frames_before)

    def _after_edit(self, frames_before):
        if self._buffer is None:
            return
        if self._buffer.frames != frames_before:
            self._waveform.clear_selection()
        self._waveform.refresh_samples(self._buffer.samples)
        self._reload_preview()
        self._update_file_label()
        self._update_edit_controls()
        self._update_time_display()

    def _reload_preview(self):
        """The buffer changed: restart the preview at the same position."""
        was_playing = self._engine.state() == STATE_PLAYING
        position = self._engine.position_ms()
        self._engine.load_buffer(self._buffer.samples, self._buffer.samplerate)
        self._engine.seek(position)
        if was_playing:
            self._engine.play()
            self._ticker.start()
        self._sync_ui_from_state()

    def _undo(self):
        if self._buffer is None or not self._buffer.can_undo():
            return
        frames_before = self._buffer.frames
        self._buffer.undo()
        self._after_edit(frames_before)

    def _redo(self):
        if self._buffer is None or not self._buffer.can_redo():
            return
        frames_before = self._buffer.frames
        self._buffer.redo()
        self._after_edit(frames_before)

    def _delete_selection(self):
        region = self._region(whole_without_selection=False)
        if region is not None:
            self._edit(lambda buffer: buffer.delete_range(*region))

    def _silence_selection(self):
        region = self._region(whole_without_selection=False)
        if region is not None:
            self._edit(lambda buffer: buffer.silence_range(*region))

    def _trim_selection(self):
        region = self._region(whole_without_selection=False)
        if region is not None:
            self._edit(lambda buffer: buffer.trim_to(*region))

    def _fade(self, fade_in):
        region = self._region()
        if region is None:
            return
        if fade_in:
            self._edit(lambda buffer: buffer.fade_in(*region))
        else:
            self._edit(lambda buffer: buffer.fade_out(*region))

    def _change_gain(self):
        region = self._region()
        if region is None:
            return
        value, accepted = QInputDialog.getDouble(
            self, T.tr('audio.gain', 'Increase Volume'),
            T.tr('audio.gain_prompt', 'Change gain (dB):'),
            0.0, -60.0, 24.0, 1)
        if not accepted or value == 0:
            return
        self._edit(lambda buffer: buffer.change_gain(region[0], region[1], value))

    def _reverse(self):
        region = self._region()
        if region is not None:
            self._edit(lambda buffer: buffer.reverse(*region))

    def _copy(self):
        region = self._region()
        if region is None:
            return
        self._clipboard = self._buffer.copy_range(*region)
        self._update_edit_controls()

    def _paste(self):
        if self._buffer is None or self._clipboard is None:
            return
        if self._clipboard.shape[1] != self._buffer.channels:
            Logger.error(T.tr('audio.paste_mismatch',
                              'Cannot paste: the copied audio has a different channel count.'))
            return
        selection = self._waveform.selection()
        if selection is not None:
            start = int(round(selection[0]))
            end = int(round(selection[1]))
            self._edit(lambda buffer: buffer.replace_range(start, end, self._clipboard))
        else:
            position = int(round(self._engine.position_ms() / 1000.0
                                 * self._buffer.samplerate))
            self._edit(lambda buffer: buffer.insert(position, self._clipboard))

    def _append_audio(self):
        """Concatenate one or more audio files to the end of the current one.

        Every file is resampled to the buffer's rate and folded or duplicated
        to its channel layout, then the whole selection is appended as ONE
        undo step.
        """
        if self._buffer is None:
            return
        start_dir = str(self._current_path.parent) if self._current_path else ''
        paths, _ = QFileDialog.getOpenFileNames(
            self, T.tr('audio.append', 'Append Audio Files'), start_dir,
            AUDIO_OPEN_FILTER)
        if not paths:
            return
        _added, failed = self.append_files(paths)
        if failed:
            QMessageBox.warning(
                self, T.tr('message_box.warning_title', 'Warning'),
                T.tr('audio.append_failed', 'Could not append: {}').format(
                    ', '.join(failed)))

    def append_files(self, paths):
        """Concatenate the given files onto the buffer.

        Returns ``(added_count, failed_names)``: every file is decoded
        (soundfile first, then the mixer), converted to the buffer's rate and
        channel layout, and all of them land in ONE undo step.
        """
        if self._buffer is None:
            return 0, []
        pieces = []
        failed = []
        for path in paths:
            file_path = Path(str(path))
            if file_path.suffix.lower() in UNPLAYABLE_SUFFIXES:
                Logger.error(self._unsupported_message(file_path))
                failed.append(file_path.name)
                continue
            try:
                if codec.can_edit(file_path):
                    decoded = codec.decode(str(file_path))
                    samples, samplerate = decoded.samples, decoded.samplerate
                else:
                    samples, samplerate = codec.decode_playable(str(file_path))
            except codec.CodecError as exc:
                Logger.error(T.tr('audio.load_failed',
                                  'Failed to load audio {}').format(exc))
                failed.append(file_path.name)
                continue
            pieces.append(dsp.match_format(samples, samplerate,
                                           self._buffer.samplerate,
                                           self._buffer.channels))
        if pieces:
            combined = np.concatenate(pieces, axis=0)
            frames_before = self._buffer.frames
            self._edit(lambda buffer: buffer.append(combined))
            Logger.info(T.tr('audio.appended',
                             'Appended {} file(s), {} frames').format(
                                 len(pieces), self._buffer.frames - frames_before))
        return len(pieces), failed

    def _change_pitch(self):
        region = self._region()
        if region is None:
            return
        semitones, accepted = QInputDialog.getDouble(
            self, T.tr('audio.pitch', 'Change Pitch'),
            T.tr('audio.pitch_prompt', 'Adjust pitch (-12, 12)'), 0.0, -12.0, 12.0, 1)
        if not accepted or abs(semitones) < 1e-6:
            return
        self._edit(lambda buffer: buffer.change_pitch(region[0], region[1], semitones))

    def _change_speed(self):
        region = self._region()
        if region is None:
            return
        percent, accepted = QInputDialog.getDouble(
            self, T.tr('audio.speed', 'Change Speed'),
            T.tr('audio.speed_prompt', 'Speed (%):'),
            100.0, 25.0, 400.0, 0)
        if not accepted or abs(percent - 100.0) < 1e-6:
            return
        self._edit(lambda buffer: buffer.change_speed(region[0], region[1],
                                                      percent / 100.0))

    # ------------------------------------------------------------------ saving
    def save(self):
        """Write the buffer back to the file it came from. True on success."""
        if self._buffer is None:
            return False
        if self._current_path is None:
            return self.save_as()
        try:
            codec.save(self._buffer, str(self._current_path))
        except codec.CodecError as exc:
            Logger.error(T.tr('audio.save_failed', 'Failed to save audio: {}').format(exc))
            return False
        self._buffer.mark_saved()
        self._refresh_size()
        self._update_file_label()
        self._update_edit_controls()
        Logger.info(T.tr('audio.saved', 'Audio saved: {}').format(self._current_path.name))
        return True

    def save_as(self):
        """Pick a target file and write the buffer there (format by suffix)."""
        if self._buffer is None:
            return False
        start_dir = str(self._current_path.parent) if self._current_path else ''
        path, _ = QFileDialog.getSaveFileName(
            self, T.tr('audio.save_as', 'Save As'), start_dir, AUDIO_SAVE_FILTER)
        if not path:
            return False
        return self.save_to(path)

    def save_to(self, path):
        """Write the buffer to ``path`` (format by suffix) and follow it."""
        if self._buffer is None:
            return False
        path = Path(path)
        if path.suffix.lower() not in codec.SAVE_SUFFIXES:
            path = path.with_suffix('.wav')
        try:
            codec.save(self._buffer, str(path))
        except codec.CodecError as exc:
            Logger.error(T.tr('audio.save_failed', 'Failed to save audio: {}').format(exc))
            return False
        self._current_path = path
        self._buffer.mark_saved()
        self._refresh_size()
        self._update_file_label()
        self._update_edit_controls()
        Logger.info(T.tr('audio.saved', 'Audio saved: {}').format(path.name))
        return True

    def _refresh_size(self):
        try:
            self._current_size = self._current_path.stat().st_size
        except (OSError, AttributeError):
            self._current_size = 0
        self._size_label.setText(
            T.tr('audio.size', 'Size: {}').format(format_size(self._current_size)))
        self._size_label.setToolTip(self._size_label.text())

    def _update_file_label(self):
        if self._current_path is None:
            self._file_label.setText('')
            return
        name = self._current_path.name
        if self._buffer is not None and self._buffer.is_modified():
            name = '*' + name
        self._file_label.setText(T.tr('audio.file_name', 'File Name: {}').format(name))
        self._file_label.setToolTip(self._current_path.name)

    # -------------------------------------------------------------- converting
    def _confirm_before_replacing(self):
        """Ask to save before another file replaces the edited one."""
        if self._buffer is None or not self._buffer.is_modified():
            return True
        choice = QMessageBox.warning(
            self, T.tr('message_box.warning_title', 'Warning'),
            T.tr('audio.unsaved_content',
                 'The current audio has unsaved changes. Do you want to save it?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Yes:
            return self.save()
        return True

    def _convert_to_wav(self, file_path):
        """Decode a format the editor cannot save and store it as WAV.

        Returns the new path, or None when the conversion failed.
        """
        try:
            samples, samplerate = codec.decode_playable(str(file_path))
            target = codec.wav_target(file_path)
            codec.write_wav(samples, samplerate, str(target))
        except codec.CodecError as exc:
            Logger.error(T.tr('audio.convert_failed',
                              'Could not convert {}: {}').format(file_path.name, exc))
            return None
        Logger.info(T.tr('audio.converted', 'Converted to {}').format(target.name))
        return target

    # ------------------------------------------------------------------ playlist
    def _playlist(self):
        """Audio files in the same folder as the current one (sorted), so the
        previous / next buttons have something real to step through."""
        if not self._current_path or not self._current_path.parent.is_dir():
            return []
        from pygamestudio.gui.audio_editor.engine import AUDIO_FILE_EXTENSIONS
        try:
            files = [p for p in self._current_path.parent.iterdir()
                     if p.is_file() and p.suffix.lower() in AUDIO_FILE_EXTENSIONS]
        except OSError:
            return []
        return sorted(files, key=lambda p: p.name.lower())

    def _play_neighbor(self, offset):
        """Play the previous / next audio file in the same folder. Files that
        fail to load are skipped automatically."""
        playlist = self._playlist()
        count = len(playlist)
        if count < 2 or self._current_path is None:
            return
        try:
            index = playlist.index(self._current_path)
        except ValueError:
            index = 0
        for step in range(1, count):
            target = playlist[(index + offset * step) % count]
            if self.open_audio(str(target), raise_window=False, interactive=False):
                return

    def _play_previous(self):
        self._play_neighbor(-1)

    def _play_next(self):
        self._play_neighbor(1)

    # ------------------------------------------------------------------ file
    def choose_audio(self):
        """Pick any audio file from disk and play it."""
        start_dir = str(self._current_path.parent) if self._current_path else ''
        path, _ = QFileDialog.getOpenFileName(
            self, T.tr('audio.open', 'Open Audio File'), start_dir, AUDIO_OPEN_FILTER)
        if path:
            self.open_audio(path)

    def _unsupported_message(self, file_path):
        """The 'convert it first' text used for m4a / wma / ... files."""
        return T.tr(
            'audio.unsupported_format',
            'The {} format cannot be edited or played. '
            'Please convert the file to another format.').format(
                Path(str(file_path)).suffix.lower().lstrip('.'))

    def _warn_unsupported(self, file_path):
        """Log and (in the GUI) show why a file cannot be decoded."""
        message = self._unsupported_message(file_path)
        Logger.error(message)
        self._raise_window()
        QMessageBox.warning(self, T.tr('message_box.warning_title', 'Warning'),
                            message)

    def open_audio(self, file_path, raise_window=True, interactive=True):
        """Load an audio file for editing and play it once.

        Editable formats (WAV/FLAC/OGG/MP3/...) go through soundfile and get
        the full editor. Other formats (m4a, ...) are offered to be converted
        to WAV first; if the user declines (or ``interactive`` is False, e.g.
        playlist stepping or MCP) they load in play-only mode: the waveform is
        shown, the edit tools stay disabled.
        """
        file_path = Path(str(file_path))
        if not file_path.is_file():
            Logger.error(T.tr('audio.no_audio_path', 'The audio file {} does not exist.').format(file_path))
            return False
        if file_path.suffix.lower() in UNPLAYABLE_SUFFIXES:
            if interactive:
                self._warn_unsupported(file_path)
            else:
                Logger.error(self._unsupported_message(file_path))
            return False
        if not self._confirm_before_replacing():
            return False

        buffer = None
        if codec.can_edit(file_path):
            try:
                buffer = codec.decode(str(file_path))
            except codec.CodecError as exc:
                Logger.error(T.tr('audio.load_failed', 'Failed to load audio {}').format(exc))
                return False
        elif interactive and codec.SOUNDFILE_AVAILABLE:
            choice = QMessageBox.question(
                self, T.tr('message_box.warning_title', 'Warning'),
                T.tr('audio.convert_question',
                     'This format cannot be edited. Convert it to WAV and edit that?\n{}').format(
                         file_path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if choice == QMessageBox.StandardButton.Yes:
                target = self._convert_to_wav(file_path)
                if target is None:
                    return False
                return self.open_audio(str(target), raise_window=raise_window,
                                       interactive=False)
        return self._load_into_panel(file_path, buffer, raise_window)

    def _load_into_panel(self, file_path, buffer, raise_window):
        """Show one file in the panel (``buffer`` None = play-only)."""
        if buffer is not None:
            loaded = self._engine.load_buffer(buffer.samples, buffer.samplerate)
        else:
            loaded = self._engine.load(str(file_path))
        if not loaded:
            Logger.error(T.tr('audio.load_failed', 'Failed to load audio {}').format(file_path))
            return False

        self._buffer = buffer
        self._current_path = file_path
        try:
            self._current_size = file_path.stat().st_size
        except OSError:
            self._current_size = 0

        self._waveform.set_placeholder('')
        if buffer is not None:
            self._waveform.set_samples(buffer.samples, buffer.samplerate)
            self._waveform.setToolTip('')
        else:
            self._waveform.set_envelope(self._engine.envelope())
            self._waveform.setToolTip(T.tr('audio.play_only_tip',
                                           'This format cannot be edited - convert it to WAV first.'))
        self._waveform.set_progress(0.0)
        self._size_label.setText(
            T.tr('audio.size', 'Size: {}').format(format_size(self._current_size)))
        self._size_label.setToolTip(self._size_label.text())
        self._update_file_label()
        self._update_time_display()
        self._update_controls()
        self._update_edit_controls()
        self._update_titles()

        self._engine.play()
        self._sync_ui_from_state()
        if self._engine.state() == STATE_PLAYING:
            self._ticker.start()

        if raise_window:
            self._raise_window()
        return True

    # ------------------------------------------------------ keys / shortcuts
    def keyPressEvent(self, event):
        # The usual editor shortcuts work while the panel has the focus; the
        # waveform keeps its own zoom/pan/wheel behaviour.
        modifiers = event.modifiers()
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_S:
                self.save()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Z:
                self._undo()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Y:
                self._redo()
                event.accept()
                return
        elif modifiers == (Qt.KeyboardModifier.ControlModifier
                            | Qt.KeyboardModifier.ShiftModifier):
            if event.key() == Qt.Key.Key_Z:
                self._redo()
                event.accept()
                return
            if event.key() == Qt.Key.Key_S:
                self.save_as()
                event.accept()
                return
        super().keyPressEvent(event)

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
        # Read the run entry point while the panel is still docked: the
        # floating window forwards Ctrl+R to it (WindowBase.keyPressEvent).
        run_handler = editor_run_handler(self)
        self._tab_widget.removeTab(self._tab_widget.indexOf(self))
        self.setParent(None)
        self._standalone_window = _AudioEditorStandaloneWindow(self, self._window_title())
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
        # Re-dock right after the console and the animation editor tabs
        # (the animation editor sits at index 1, so the player follows it).
        self._tab_widget.insertTab(2, self, self._tab_title())
        self._tab_widget.setCurrentIndex(2)
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

    # ------------------------------------------------------------------ titles
    def _tab_title(self):
        """The tab always carries the panel name, never the file name."""
        return T.tr('audio.player', 'Audio Editor')

    def _window_title(self):
        return f' Pygame Studio - {self._tab_title()}'

    def _update_titles(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.window_title.set_title_name(self._window_title())
        elif self._tab_widget is not None:
            index = self._tab_widget.indexOf(self)
            if index >= 0:
                self._tab_widget.setTabText(index, self._tab_title())

    def _update_detach_button(self):
        """Show the attach icon while the player floats in its own window."""
        self._detach_btn.set_detached(self._is_detached)

    # ------------------------------------------------------------------ hooks
    def retranslate(self):
        state = self._engine.state()
        self._play_btn.setToolTip(T.tr('audio.pause', 'Pause') if state == STATE_PLAYING
                                  else T.tr('audio.play', 'Play'))
        self._stop_btn.setToolTip(T.tr('audio.stop', 'Stop'))
        self._prev_btn.setToolTip(T.tr('audio.previous', 'Previous'))
        self._next_btn.setToolTip(T.tr('audio.next', 'Next'))
        self._open_btn.setToolTip(T.tr('audio.open', 'Open Audio File'))
        self._save_btn.setToolTip(T.tr('audio.save', 'Save (Ctrl+S)'))
        self._save_as_btn.setToolTip(T.tr('audio.save_as', 'Save As'))
        for btn, key, default in (
            (self._undo_btn, 'audio.undo', 'Undo (Ctrl+Z)'),
            (self._redo_btn, 'audio.redo', 'Redo (Ctrl+Y)'),
            (self._delete_btn, 'audio.delete_selection', 'Delete Selection'),
            (self._silence_btn, 'audio.silence', 'Silence'),
            (self._trim_btn, 'audio.trim', 'Trim to Selection'),
            (self._fade_in_btn, 'audio.fade_in', 'Fade In'),
            (self._fade_out_btn, 'audio.fade_out', 'Fade Out'),
            (self._gain_btn, 'audio.gain', 'Increase Volume'),
            (self._reverse_btn, 'audio.reverse', 'Reverse'),
            (self._copy_btn, 'audio.copy', 'Copy'),
            (self._paste_btn, 'audio.paste', 'Paste'),
            (self._append_btn, 'audio.append', 'Append Audio Files'),
            (self._pitch_btn, 'audio.pitch', 'Change Pitch'),
            (self._speed_btn, 'audio.speed', 'Change Speed'),
        ):
            btn.setToolTip(T.tr(key, default))
        if self._buffer is None:
            self._waveform.setToolTip(T.tr(
                'audio.play_only_tip',
                'This format cannot be edited - convert it to WAV first.'))
        if not self._engine.is_loaded():
            self._waveform.set_placeholder(T.tr('audio.empty_hint', 'Choose an audio file'))
        if self._current_size:
            self._size_label.setText(
                T.tr('audio.size', 'Size: {}').format(format_size(self._current_size)))
            self._size_label.setToolTip(self._size_label.text())
        self._update_file_label()
        self._update_edit_controls()
        self._update_detach_button()
        self._update_titles()

    def get_ready_for_project(self):
        """Called when the editor is (re)opened for a project.

        The previously loaded audio is kept across editor close/open, so the
        waveform is still visible when re-entering. If the file no longer
        exists on disk the panel falls back to its empty state."""
        if self._current_path is not None and not self._current_path.is_file():
            self._engine.unload()
            self._buffer = None
            self._current_path = None
            self._size_label.setText('')
            self._file_label.setText('')
            self._waveform.set_envelope([])
            self._waveform.set_placeholder(T.tr('audio.empty_hint', 'Choose an audio file'))
            self._waveform.setToolTip('')
            self._update_time_display()
            self._update_controls()
            self._update_edit_controls()

    def clean_up(self):
        """Silence the panel when leaving the editor, but keep the loaded
        audio (file name, size and waveform) so re-opening the project shows
        it again instead of an empty gray panel."""
        self._ticker.stop()
        self._engine.stop()
        self._waveform.set_progress(0.0)
        self._update_time_display()
        self._update_controls()


class _AudioEditorStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the audio editor while it is
    detached from the center bottom tab widget."""

    def __init__(self, editor_window, title):
        super().__init__()
        self._editor_window = editor_window
        clamp_window_size(self, 760, 240)
        self.set_window_body(editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        if self._editor_window is not None:
            self._editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)

