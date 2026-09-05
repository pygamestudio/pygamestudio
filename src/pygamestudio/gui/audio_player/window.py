from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from pygamestudio.gui.audio_player.engine import (AudioEngine, STATE_PLAYING,
                                                  STATE_PAUSED)
from pygamestudio.gui.audio_player.widgets import AudioProgress
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.console.logger import Logger

AUDIO_OPEN_FILTER = ('Audio (*.wav *.mp3 *.ogg *.flac *.aif *.aiff *.m4a)')


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


class AudioPlayerWindow(QWidget):
    """The built-in audio player.

    A compact media-player panel: transport buttons (previous / play-pause /
    stop / next) sit top-left styled like the image editor's icon buttons, the
    file name is shown by the tab itself, and a clickable waveform fills the
    remaining space (current / total time drawn inside it).

    Clicking anywhere on the waveform seeks: while paused it only moves the
    playhead (still paused - the next Play starts there); while playing the
    audio restarts from that spot. There is deliberately no volume control and
    nothing is ever persisted.

    Docked in the center bottom tab widget (right after the console); it can
    detach into its own window and re-dock again.
    """

    def __init__(self, game_manager=None):
        super().__init__()
        self._game_manager = game_manager
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None
        self._current_path = None
        self._current_size = 0

        self._engine = AudioEngine()
        self._ticker = QTimer(self)
        self._ticker.setInterval(100)

        self._detach_btn = QPushButton()
        self._open_btn = QPushButton()
        self._prev_btn = QPushButton()
        self._play_btn = QPushButton()
        self._next_btn = QPushButton()
        self._stop_btn = QPushButton()
        self._progress = AudioProgress()
        self._size_label = QLabel()
        self._time_label = QLabel()

        self._play_icon = QIcon(':/images/play.png')
        self._pause_icon = QIcon(':/images/pause.png')

        self._set_up()

    # ------------------------------------------------------------------ setup
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.setObjectName('audioPlayerWindow')

    def _set_widget(self):
        self._detach_btn.setObjectName('codeEditorDetachBtn')
        self._detach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_detach_button_text()

        # Open any audio file from disk (not only project files).
        self._open_btn.setObjectName('imageEditorToolBtn')
        self._open_btn.setIcon(QIcon(':/images/browse.png'))
        self._open_btn.setIconSize(QSize(18, 18))
        self._open_btn.setFixedSize(28, 28)
        self._open_btn.setToolTip(T.tr('audio.open', 'Open Audio File'))
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)

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

        self._size_label.setObjectName('audioPlayerSizeLabel')
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._time_label.setObjectName('audioPlayerTimeLabel')
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._time_label.setMinimumWidth(88)
        self._time_label.setText('0:00 / 0:00')

        # Empty state: ask the user to pick an audio file instead of a gray bar.
        self._progress.set_placeholder(T.tr('audio.empty_hint', 'Choose an audio file'))

        self._update_controls()
        self._update_time_display()

    def _set_signal(self):
        self._ticker.timeout.connect(self._on_tick)
        self._progress.seek_requested.connect(self._on_seek)

        self._detach_btn.clicked.connect(self.toggle_detached)
        self._open_btn.clicked.connect(self.choose_audio)
        self._prev_btn.clicked.connect(self._play_previous)
        self._play_btn.clicked.connect(self._toggle_play)
        self._stop_btn.clicked.connect(self._stop_playback)
        self._next_btn.clicked.connect(self._play_next)

    def _set_layout(self):
        # Top-left toolbar: open + transport buttons ... time right of the
        # buttons, then size + detach pushed to the right.
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._open_btn)
        toolbar.addWidget(self._prev_btn)
        toolbar.addWidget(self._play_btn)
        toolbar.addWidget(self._stop_btn)
        toolbar.addWidget(self._next_btn)
        toolbar.addSpacing(6)
        toolbar.addWidget(self._time_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self._size_label)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._detach_btn)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 4)
        main_layout.setSpacing(4)
        main_layout.addLayout(toolbar)
        main_layout.addWidget(self._progress, 1)

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
            self._progress.set_progress(position_ms / duration)
        else:
            self._progress.set_progress(0.0)
        self._time_label.setText(f'{format_time(position_ms)} / {format_time(duration)}')

    # ------------------------------------------------------------------ playlist
    def _playlist(self):
        """Audio files in the same folder as the current one (sorted), so the
        previous / next buttons have something real to step through."""
        if not self._current_path or not self._current_path.parent.is_dir():
            return []
        from pygamestudio.gui.audio_player.engine import AUDIO_FILE_EXTENSIONS
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
            if self.open_audio(str(target), raise_window=False):
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

    def open_audio(self, file_path, raise_window=True):
        """Load an audio file and play it once (the file name is shown by the
        tab itself)."""
        file_path = Path(str(file_path))
        if not file_path.is_file():
            Logger.error(T.tr('audio.no_audio_path', 'The audio file {} does not exist.').format(file_path))
            return False
        if not self._engine.load(str(file_path)):
            Logger.error(T.tr('audio.load_failed', 'Failed to load audio {}').format(file_path))
            return False

        self._current_path = file_path
        try:
            self._current_size = file_path.stat().st_size
        except OSError:
            self._current_size = 0

        self._progress.set_placeholder('')
        self._size_label.setText(
            T.tr('audio.size', 'Size: {}').format(format_size(self._current_size)))

        self._progress.set_envelope(self._engine.envelope())
        self._update_time_display()
        self._update_controls()
        self._update_titles()

        self._engine.play()
        self._sync_ui_from_state()
        if self._engine.state() == STATE_PLAYING:
            self._ticker.start()

        if raise_window:
            self._raise_window()
        return True

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
        self._standalone_window = _AudioPlayerStandaloneWindow(self, self._window_title())
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
        # Re-dock right after the console tab (index 1).
        self._tab_widget.insertTab(1, self, self._tab_title())
        self._tab_widget.setCurrentIndex(1)
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
        if self._current_path:
            return self._current_path.name
        return T.tr('audio.player', 'Audio Player')

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

    def _update_detach_button_text(self):
        if self._is_detached:
            self._detach_btn.setText(T.tr('audio.attach', 'Attach to Tabs'))
        else:
            self._detach_btn.setText(T.tr('audio.detach', 'Detach'))

    # ------------------------------------------------------------------ hooks
    def retranslate(self):
        state = self._engine.state()
        self._play_btn.setToolTip(T.tr('audio.pause', 'Pause') if state == STATE_PLAYING
                                  else T.tr('audio.play', 'Play'))
        self._stop_btn.setToolTip(T.tr('audio.stop', 'Stop'))
        self._prev_btn.setToolTip(T.tr('audio.previous', 'Previous'))
        self._next_btn.setToolTip(T.tr('audio.next', 'Next'))
        self._open_btn.setToolTip(T.tr('audio.open', 'Open Audio File'))
        if not self._engine.is_loaded():
            self._progress.set_placeholder(T.tr('audio.empty_hint', 'Choose an audio file'))
        if self._current_size:
            self._size_label.setText(
                T.tr('audio.size', 'Size: {}').format(format_size(self._current_size)))
        self._update_detach_button_text()
        self._update_titles()

    def get_ready_for_project(self):
        """Called when the editor is (re)opened for a project.

        The previously loaded audio is kept across editor close/open, so the
        waveform is still visible when re-entering. If the file no longer
        exists on disk the player falls back to its empty state."""
        if self._current_path is not None and not self._current_path.is_file():
            self._engine.unload()
            self._current_path = None
            self._size_label.setText('')
            self._progress.set_envelope([])
            self._progress.set_placeholder(T.tr('audio.empty_hint', 'Choose an audio file'))
            self._update_time_display()
            self._update_controls()

    def clean_up(self):
        """Silence the player when leaving the editor, but keep the loaded
        audio (file name, size and waveform) so re-opening the project shows
        it again instead of an empty gray panel."""
        self._ticker.stop()
        self._engine.stop()
        self._progress.set_progress(0.0)
        self._update_time_display()
        self._update_controls()


class _AudioPlayerStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the audio player while it is
    detached from the center bottom tab widget."""

    def __init__(self, editor_window, title):
        super().__init__()
        self._editor_window = editor_window
        self.resize(640, 200)
        self.set_window_body(editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        if self._editor_window is not None:
            self._editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)

