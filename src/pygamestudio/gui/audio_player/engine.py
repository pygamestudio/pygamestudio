"""Playback + waveform for the built-in audio player.

Uses pygame.mixer (the same engine the generated games use) so every format
the mixer can decode - wav / ogg / mp3 / flac ... - just works in the editor.

Seeking works by slicing the decoded raw buffer (Sound.get_raw(), in the
mixer's own format): starting from an arbitrary millisecond simply builds a
new Sound from ``raw[offset:]``. Positions are tracked with a monotonic clock
so the progress always updates. The decoded samples also feed a peak envelope
so the UI can draw a real waveform.

The editor is not an audio editor: nothing here persists volume or any other
setting.
"""

import time
from array import array

import pygame

# Audio suffixes the built-in audio player can preview (kept in sync with the
# asset browser routing in gui/asset/tree.py).
AUDIO_FILE_EXTENSIONS = {
    '.wav', '.mp3', '.ogg', '.flac', '.aif', '.aiff', '.m4a',
}

STATE_STOPPED = 'stopped'
STATE_PLAYING = 'playing'
STATE_PAUSED = 'paused'


def build_envelope_from_raw(raw, bucket_count=140):
    """Return a list of ``bucket_count`` floats in [0, 1] describing the
    audio energy over time (a real waveform envelope). Returns [] when the
    samples cannot be decoded (caller should fall back to a plain bar)."""
    if not raw:
        return []
    try:
        samples = array('h')            # int16, native byte order
        samples.frombytes(raw)
    except Exception:
        return []

    total = len(samples)
    if total <= bucket_count:
        bucket_count = max(1, total)

    peaks = [0] * bucket_count
    # Inspect at most ~1500 samples per bucket (a coarse but honest envelope),
    # so even long songs build the waveform quickly.
    examined = bucket_count * 1500
    stride = max(1, total // examined) if total > examined else 1

    for idx in range(0, total, stride):
        value = abs(samples[idx])
        bucket = (idx * bucket_count) // total
        if value > peaks[bucket]:
            peaks[bucket] = value

    maximum = max(peaks)
    if maximum <= 0:
        return []
    return [peak / maximum for peak in peaks]


class AudioEngine:
    """Plays one audio file at a time (no looping, no persistence)."""

    def __init__(self, volume=0.8):
        self._raw = b''
        self._sound = None          # full-length Sound (duration / waveform)
        self._channel = None        # currently playing (sliced) channel
        self._path = None
        self._duration_ms = 0
        self._volume = volume
        self._envelope = []
        self._freq = 44100
        self._bytes_per_sample = 2  # mixer is initialised as signed 16-bit
        self._channels = 2

        self._state = STATE_STOPPED
        self._start_ms = 0          # where playback starts / paused position
        self._playing_since = None  # monotonic() when the current run started

    # ------------------------------------------------------------- mixer
    @staticmethod
    def _ensure_mixer():
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=2)
            return True
        except Exception:
            return False

    def _mixer_params(self):
        try:
            freq, size, channels = pygame.mixer.get_init()
        except Exception:
            return
        if freq:
            self._freq = int(freq)
        self._channels = int(channels)
        self._bytes_per_sample = abs(int(size)) // 8 or 2

    # ------------------------------------------------------------- file io
    def load(self, file_path):
        """Load an audio file. Returns True on success."""
        self.stop()
        if not self._ensure_mixer():
            return False
        self._mixer_params()
        try:
            sound = pygame.mixer.Sound(str(file_path))
            raw = bytes(sound.get_raw())
        except Exception:
            return False
        if not raw:
            return False

        self._sound = sound
        self._raw = raw
        self._path = str(file_path)
        self._duration_ms = int(round(sound.get_length() * 1000))
        self._envelope = build_envelope_from_raw(raw)
        self._state = STATE_STOPPED
        self._channel = None
        self._start_ms = 0
        self._playing_since = None
        return True

    def unload(self):
        self.stop()
        self._sound = None
        self._raw = b''
        self._path = None
        self._duration_ms = 0
        self._envelope = []

    # ------------------------------------------------------------- state
    @property
    def path(self):
        return self._path

    def is_loaded(self):
        return self._sound is not None

    def state(self):
        return self._state

    def duration_ms(self):
        return self._duration_ms

    def envelope(self):
        return self._envelope

    # ------------------------------------------------------------- playback
    def _raw_offset(self, ms):
        """Byte offset inside the raw buffer for ``ms`` into the file."""
        frames = int(self._freq * (ms / 1000.0))
        return frames * self._bytes_per_sample * self._channels

    def _sound_at(self, ms):
        """A Sound that starts playing at ``ms`` (slices the raw buffer)."""
        ms = max(0, min(self._duration_ms, int(ms)))
        offset = self._raw_offset(ms)
        if offset >= len(self._raw):
            return None
        try:
            return pygame.mixer.Sound(buffer=self._raw[offset:])
        except Exception:
            return None

    def _start_channel(self, ms):
        """Play from ``ms``. Returns True on success."""
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass
            self._channel = None
        sound = self._sound_at(ms)
        if sound is None:
            return False
        channel = sound.play(loops=0)
        if channel is None:
            return False
        channel.set_volume(self._volume)
        self._channel = channel
        self._start_ms = max(0, min(self._duration_ms, int(ms)))
        self._playing_since = time.monotonic()
        self._state = STATE_PLAYING
        return True

    def play(self):
        """Start (or resume) from the current start position."""
        if self._sound is None or not self._ensure_mixer():
            return False
        return self._start_channel(self._start_ms)

    def pause(self):
        """Freeze at the current position (the audio itself is stopped)."""
        if self._state != STATE_PLAYING:
            return
        self._start_ms = self.position_ms()
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass
        self._channel = None
        self._state = STATE_PAUSED

    def stop(self):
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass
        self._channel = None
        self._state = STATE_STOPPED
        self._start_ms = 0
        self._playing_since = None

    def toggle(self):
        if self._state == STATE_PLAYING:
            self.pause()
        else:
            # Both paused and stopped (re)start from the stored position.
            self.play()

    def seek(self, position_ms):
        """Jump to ``position_ms``.

        While playing the audio restarts from there immediately; while paused
        or stopped it only stores the position so the next ``play()`` starts
        there (a paused state stays paused).
        """
        if self._sound is None:
            return
        position_ms = max(0, min(self._duration_ms, int(position_ms)))
        if self._state == STATE_PLAYING:
            self._start_channel(position_ms)
        else:
            self._start_ms = position_ms

    def is_busy(self):
        """True while the mixer is still producing sound for this file."""
        return self._channel is not None and self._channel.get_busy()

    # ------------------------------------------------------------- position
    def position_ms(self):
        if self._state == STATE_STOPPED:
            return 0
        if self._state == STATE_PAUSED:
            return max(0, min(self._duration_ms, self._start_ms))
        elapsed = self._start_ms + (time.monotonic() - self._playing_since) * 1000
        return max(0, min(self._duration_ms, int(elapsed)))
