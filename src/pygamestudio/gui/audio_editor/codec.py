"""Decoding and encoding for the audio editor (soundfile / libsndfile).

The editor works on raw samples, so it needs a real decoder/encoder pair:

* ``soundfile`` (libsndfile) decodes AND encodes WAV / FLAC / OGG / MP3 (and
  a few more container formats). The PyPI wheels bundle libsndfile for
  Windows, macOS and Linux, so ``pip install soundfile`` is all a user needs;
* the pygame mixer also decodes anything a game can play, but it cannot write
  compressed files back. It is only used to DECODE formats the editor cannot
  save (m4a and friends), so they can be converted to WAV.

Saving keeps the file's own shape: same major format, same subtype for the
lossless formats, the original sample rate and channel count. Formats with
lossy encoding (OGG / MP3) are re-encoded with a quality close to a normal
source file - every save re-encodes, exactly like every other audio editor.
"""

from pathlib import Path

import numpy as np

from pygamestudio.gui.audio_editor.buffer import AudioBuffer

try:                                        # the editor also runs without it
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except Exception:                           # noqa: BLE001 - optional dependency
    sf = None
    SOUNDFILE_AVAILABLE = False


class CodecError(Exception):
    """Decoding or encoding failed (format, missing library, bad file)."""


#: suffix -> (libsndfile major format, default quality kwargs)
#: ``None`` quality kwargs = lossless, no extra settings needed.
_FORMATS = {
    '.wav': ('WAV', None),
    '.wave': ('WAV', None),
    '.flac': ('FLAC', None),
    '.ogg': ('OGG', {'compression_level': 0.4}),
    '.oga': ('OGG', {'compression_level': 0.4}),
    '.mp3': ('MP3', {'bitrate_mode': 'VARIABLE', 'compression_level': 0.35}),
    '.aif': ('AIFF', None),
    '.aiff': ('AIFF', None),
    '.au': ('AU', None),
    '.caf': ('CAF', None),
    '.w64': ('W64', None),
}

#: Formats whose subtype is worth carrying over from the source file.
_LOSSLESS = ('WAV', 'FLAC', 'AIFF', 'AU', 'CAF', 'W64')

#: Suffixes the Save-As dialog offers (the formats that can be written).
SAVE_SUFFIXES = ('.wav', '.flac', '.ogg', '.mp3')


def can_edit(path) -> bool:
    """True when the editor can decode AND save this file's format."""
    if not SOUNDFILE_AVAILABLE:
        return False
    return Path(str(path)).suffix.lower() in _FORMATS


def decode(path) -> AudioBuffer:
    """Read a file into an :class:`AudioBuffer` (float32, frames x channels)."""
    if not SOUNDFILE_AVAILABLE:
        raise CodecError('soundfile is not installed - cannot decode "{}".'.format(path))
    try:
        info = sf.info(str(path))
        data, samplerate = sf.read(str(path), dtype='float32', always_2d=True)
    except Exception as exc:                # noqa: BLE001 - report as codec error
        raise CodecError(str(exc)) from exc
    return AudioBuffer(data, samplerate, source_path=str(path),
                       source_format=info.format, source_subtype=info.subtype)


def save(buffer, path):
    """Write ``buffer`` to ``path`` in the format implied by its suffix.

    The source subtype is kept for the lossless formats; OGG / MP3 are
    re-encoded with the default quality of :data:`_FORMATS`. The buffer's
    source metadata is refreshed afterwards, so a Save As changes where (and
    in which format) later saves go.
    """
    if not SOUNDFILE_AVAILABLE:
        raise CodecError('soundfile is not installed - cannot save "{}".'.format(path))
    suffix = Path(str(path)).suffix.lower()
    entry = _FORMATS.get(suffix)
    if entry is None:
        raise CodecError('Cannot save "{}": unknown audio format.'.format(suffix))
    major, quality = entry
    subtype = None
    if major in _LOSSLESS and buffer.source_subtype:
        try:
            if sf.check_format(major, buffer.source_subtype):
                subtype = buffer.source_subtype
        except Exception:                   # noqa: BLE001 - fall back to default
            subtype = None
    try:
        sf.write(str(path), buffer.samples, buffer.samplerate,
                 format=major, subtype=subtype, **(quality or {}))
    except Exception as exc:                # noqa: BLE001 - report as codec error
        raise CodecError(str(exc)) from exc
    try:
        info = sf.info(str(path))
        buffer.source_path = str(path)
        buffer.source_format = info.format
        buffer.source_subtype = info.subtype
    except Exception:                       # noqa: BLE001 - metadata is a nicety
        pass


def write_wav(samples, samplerate, path):
    """Write raw samples as 16-bit PCM WAV (used by the convert-to-WAV flow)."""
    if not SOUNDFILE_AVAILABLE:
        raise CodecError('soundfile is not installed - cannot write "{}".'.format(path))
    try:
        sf.write(str(path), np.asarray(samples, dtype=np.float32),
                 int(samplerate), format='WAV', subtype='PCM_16')
    except Exception as exc:                # noqa: BLE001 - report as codec error
        raise CodecError(str(exc)) from exc


def decode_playable(path):
    """Decode any format the game mixer can play: ``(samples, samplerate)``.

    Only used to convert formats the editor cannot edit (m4a, ...) into a WAV
    the editor understands - decoding goes through the same SDL_mixer the
    generated games use.
    """
    try:
        import pygame
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=44100, size=-16, channels=2)
        frequency, size, channels = pygame.mixer.get_init()
        if abs(int(size)) != 16:
            raise CodecError('The mixer runs in an unsupported sample format.')
        sound = pygame.mixer.Sound(str(path))
        raw = bytes(sound.get_raw())
    except CodecError:
        raise
    except Exception as exc:                # noqa: BLE001 - report as codec error
        raise CodecError(str(exc)) from exc
    samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    channels = max(1, int(channels))
    if channels > 2:
        samples = samples.reshape(-1, channels)[:, :2]
        channels = 2
    samples = samples.reshape(-1, channels)
    return samples, int(frequency)


def wav_target(path):
    """A non-existing ``stem.wav`` next to ``path`` (for the conversion)."""
    path = Path(str(path))
    target = path.with_suffix('.wav')
    index = 1
    while target.exists():
        target = path.with_name('{} ({}).wav'.format(path.stem, index))
        index += 1
    return target
