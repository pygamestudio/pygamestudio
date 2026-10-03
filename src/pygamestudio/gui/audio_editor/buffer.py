"""The audio edit buffer of the audio editor.

Keeps the whole file in memory as a float32 numpy array (frames x channels)
and applies every edit to that array. Undo entries store only what they
replaced: the changed region (plus a small operation), so a few edits on a
long song do not multiply the memory - only changing the WHOLE file stores a
full copy, exactly like the edit itself already needs.

All editing operations go through :meth:`replace_range` (or the small
convenience wrappers around it), so undo/redo stays symmetric by
construction: undo puts the old region back, redo puts the new region back.
"""

import numpy as np

from pygamestudio.gui.audio_editor.dsp import pitch_shift, time_stretch

#: How many edits stay undoable (each entry keeps its replaced region).
MAX_UNDO = 40

#: Samples are clipped to [-1, 1] after gain/normalize style operations, so a
#: later 16-bit save cannot wrap around.
CLIP_MIN = -1.0
CLIP_MAX = 1.0


def db_to_gain(db):
    """Decibels -> linear gain factor (0 dB = 1.0, -6 dB ~ 0.5)."""
    return float(10.0 ** (float(db) / 20.0))


def _as_channels(samples, channels=None):
    """Normalise an array to float32 (frames x channels)."""
    array = np.asarray(samples, dtype=np.float32)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2:
        raise ValueError('samples must be 1- or 2-dimensional')
    if channels is not None and array.shape[1] != channels:
        raise ValueError('samples have {} channels, expected {}'.format(
            array.shape[1], channels))
    return array


class AudioBuffer:
    """One audio file in memory, with a region-based undo stack."""

    def __init__(self, samples, samplerate, source_path=None, source_format=None,
                 source_subtype=None, editable=True):
        self._samples = _as_channels(samples)
        self.samplerate = max(1, int(samplerate))
        self.source_path = str(source_path) if source_path else None
        self.source_format = source_format
        self.source_subtype = source_subtype
        self.editable = bool(editable)
        self._undo = []
        self._redo = []
        self._modified = False

    # ------------------------------------------------------------------ state
    @property
    def samples(self):
        """The working array (read-only use; do not modify in place)."""
        return self._samples

    @property
    def frames(self):
        return int(self._samples.shape[0])

    @property
    def channels(self):
        return int(self._samples.shape[1])

    def duration_seconds(self):
        return self.frames / float(self.samplerate)

    def duration_ms(self):
        return int(round(self.duration_seconds() * 1000))

    def is_modified(self):
        return self._modified

    def mark_saved(self):
        self._modified = False

    # ------------------------------------------------------------ undo stack
    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def _push(self, undo, redo):
        self._undo.append((undo, redo))
        if len(self._undo) > MAX_UNDO:
            self._undo.pop(0)
        self._redo.clear()
        self._modified = True

    def undo(self):
        if not self._undo:
            return False
        undo, redo = self._undo.pop()
        undo()
        self._redo.append((undo, redo))
        self._modified = True
        return True

    def redo(self):
        if not self._redo:
            return False
        undo, redo = self._redo.pop()
        redo()
        self._undo.append((undo, redo))
        self._modified = True
        return True

    # -------------------------------------------------------------- helpers
    def _clamp_range(self, start, end):
        start = max(0, min(self.frames, int(start)))
        end = max(start, min(self.frames, int(end)))
        return start, end

    # -------------------------------------------------------------- editing
    def replace_range(self, start, end, data):
        """The single edit primitive: swap samples[start:end] for ``data``.

        Empty ``data`` deletes, empty range inserts, everything else replaces.
        Sizes may differ; undo/redo stay symmetric by rebuilding the array.
        """
        start, end = self._clamp_range(start, end)
        data = _as_channels(data, self.channels)
        if start == end and data.shape[0] == 0:
            return
        old = self._samples[start:end].copy()
        new = data.copy()

        def undo():
            self._samples = np.concatenate(
                [self._samples[:start], old, self._samples[start + len(new):]], axis=0)

        def redo():
            self._samples = np.concatenate(
                [self._samples[:start], new, self._samples[start + len(old):]], axis=0)

        self._samples = np.concatenate(
            [self._samples[:start], new, self._samples[end:]], axis=0)
        self._push(undo, redo)

    def delete_range(self, start, end):
        """Remove the samples in [start, end)."""
        start, end = self._clamp_range(start, end)
        if start >= end:
            return
        self.replace_range(start, end, np.zeros((0, self.channels), dtype=np.float32))

    def insert(self, position, data):
        """Insert ``data`` at ``position``."""
        self.replace_range(position, position, data)

    def _region_op(self, start, end, mutate):
        """Same-length region edit: undo restores, redo recomputes."""
        start, end = self._clamp_range(start, end)
        if start >= end:
            return
        old = self._samples[start:end].copy()

        def assign(region):
            self._samples[start:start + len(region)] = region

        self._samples[start:end] = mutate(old)
        self._push(lambda: assign(old), lambda: assign(mutate(old)))

    def silence_range(self, start, end):
        """Zero the samples in [start, end)."""
        self._region_op(start, end, lambda region: np.zeros_like(region))

    def change_gain(self, start, end, db):
        """Scale [start, end) by ``db`` decibels (clipped to [-1, 1])."""
        gain = db_to_gain(db)
        self._region_op(start, end, lambda region: np.clip(region * gain, CLIP_MIN, CLIP_MAX))

    def fade_in(self, start, end):
        """Linear fade from silence to the original level over [start, end)."""
        def apply(region):
            ramp = np.linspace(0.0, 1.0, len(region), dtype=np.float32)[:, None]
            return region * ramp
        self._region_op(start, end, apply)

    def fade_out(self, start, end):
        """Linear fade from the original level to silence over [start, end)."""
        def apply(region):
            ramp = np.linspace(1.0, 0.0, len(region), dtype=np.float32)[:, None]
            return region * ramp
        self._region_op(start, end, apply)

    def normalize(self, start, end, peak=1.0):
        """Scale [start, end) so its loudest sample hits ``peak``."""
        def apply(region):
            current = float(np.abs(region).max()) if region.size else 0.0
            if current <= 0:
                return region
            return np.clip(region * (peak / current), CLIP_MIN, CLIP_MAX)
        self._region_op(start, end, apply)

    def reverse(self, start, end):
        """Play the samples in [start, end) backwards."""
        self._region_op(start, end, lambda region: np.flip(region, axis=0))

    def change_pitch(self, start, end, semitones):
        """Shift the pitch of [start, end) by ``semitones`` - length kept."""
        start, end = self._clamp_range(start, end)
        if start >= end or abs(float(semitones)) < 1e-6:
            return
        shifted = pitch_shift(self._samples[start:end], semitones, self.samplerate)
        self.replace_range(start, end, shifted)

    def change_speed(self, start, end, speed):
        """Play [start, end) ``speed`` times as fast - pitch kept.

        ``2.0`` halves the duration, ``0.5`` doubles it.
        """
        start, end = self._clamp_range(start, end)
        speed = float(speed)
        if start >= end or speed <= 0.0 or abs(speed - 1.0) < 1e-6:
            return
        stretched = time_stretch(self._samples[start:end], 1.0 / speed,
                                 self.samplerate)
        self.replace_range(start, end, stretched)

    def append(self, data):
        """Concatenate ``data`` (frames x channels) at the end of the buffer."""
        self.insert(self.frames, data)

    def trim_to(self, start, end):
        """Keep only [start, end); everything before/after is dropped."""
        start, end = self._clamp_range(start, end)
        if start == 0 and end == self.frames:
            return
        if start >= end:
            return
        head = self._samples[:start].copy()
        tail = self._samples[end:].copy()
        keep = end - start

        def undo():
            self._samples = np.concatenate([head, self._samples, tail], axis=0)

        def redo():
            self._samples = self._samples[len(head):len(head) + keep].copy()

        self._samples = self._samples[start:end].copy()
        self._push(undo, redo)

    def copy_range(self, start, end):
        """A detached copy of [start, end) (nothing is changed)."""
        start, end = self._clamp_range(start, end)
        return self._samples[start:end].copy()
