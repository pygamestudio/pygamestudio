"""Built-in audio editor: preview and edit audio assets from the asset
browser in a docked panel - transport controls, a waveform with selection /
zoom / pan, and undoable edits (delete, silence, trim, fade, volume,
reverse, copy/paste) that save back in the file's own format.
"""

from .buffer import AudioBuffer
from .engine import AudioEngine, AUDIO_FILE_EXTENSIONS
from .widgets import AudioProgress, AudioWaveformView
from .window import AudioEditorWindow, format_size, format_time

__all__ = ['AudioBuffer', 'AudioEngine', 'AUDIO_FILE_EXTENSIONS',
           'AudioProgress', 'AudioWaveformView',
           'AudioEditorWindow', 'format_size', 'format_time']
