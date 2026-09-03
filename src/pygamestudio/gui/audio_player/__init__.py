"""Built-in audio player: preview audio assets from the asset browser in a
compact media-player panel (top-left transport icons, clickable waveform that
fills the panel), docked next to the console tab and detachable to its own
window.
"""

from .engine import AudioEngine, AUDIO_FILE_EXTENSIONS
from .widgets import AudioProgress
from .window import AudioPlayerWindow, format_size, format_time

__all__ = ['AudioEngine', 'AUDIO_FILE_EXTENSIONS', 'AudioProgress',
           'AudioPlayerWindow', 'format_size', 'format_time']
