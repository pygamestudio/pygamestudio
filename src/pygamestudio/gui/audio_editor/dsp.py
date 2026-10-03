"""Pitch / speed processing for the audio editor (pure numpy).

The editor adds no DSP dependency, so the two operations that need one are
implemented here:

* :func:`time_stretch` - WSOLA (waveform-similarity overlap-add) changes the
  duration while keeping the pitch. It backs the "change speed" action.
* :func:`pitch_shift` - time-stretch plus resampling: changes the pitch while
  keeping the duration. It backs the "change pitch" action.
* :func:`resample` / :func:`match_format` - linear resampling and
  sample-rate / channel conversion. Used by both actions above and by the
  "append audio files" action (an appended file rarely has the same rate or
  channel count as the one being edited).

Every function works on ``(frames, channels)`` float32 arrays; multi-channel
input is aligned with a single offset search on the mono mix so the channels
never drift apart.
"""

import numpy as np


def _as_2d(samples):
    """float32 (frames, channels); 1-d input becomes one channel."""
    array = np.asarray(samples, dtype=np.float32)
    if array.ndim == 1:
        array = array[:, None]
    return array


def resample(samples, ratio):
    """Linear resampling: output length = ``len / ratio``.

    ``ratio > 1`` reads the samples faster, so the result is shorter and has a
    higher pitch (the "tape speed" behaviour); ``ratio < 1`` is longer and
    deeper.
    """
    array = _as_2d(samples)
    if len(array) == 0 or abs(float(ratio) - 1.0) < 1e-9:
        return array.copy()
    ratio = float(ratio)
    target = max(1, int(round(len(array) / ratio)))
    positions = np.arange(target, dtype=np.float64) * ratio
    positions = np.clip(positions, 0.0, len(array) - 1.0)
    base = np.floor(positions).astype(np.int64)
    fraction = (positions - base).astype(np.float32)[:, None]
    following = np.clip(base + 1, 0, len(array) - 1)
    blended = array[base] * (1.0 - fraction) + array[following] * fraction
    return blended.astype(np.float32)


def _sliding_energy(segment, window_len):
    """Energy of every ``window_len`` window of ``segment`` (vectorised)."""
    squared = np.asarray(segment, dtype=np.float64) ** 2
    cumulative = np.concatenate([[0.0], np.cumsum(squared)])
    return cumulative[window_len:] - cumulative[:-window_len]


def time_stretch(samples, factor, samplerate):
    """Change the duration by ``factor`` (2.0 = twice as long) - pitch kept.

    WSOLA: Hann-windowed frames are read with an analysis hop and written with
    a fixed synthesis hop (always 50 % overlap, so the output geometry never
    changes); before taking each frame the read position is nudged within a
    few milliseconds so the new frame's head lines up with the tail of the
    previous one - that alignment is what keeps the result free of the
    metallic phasing a plain overlap-add would produce.
    """
    array = _as_2d(samples)
    factor = float(factor)
    if len(array) == 0 or factor <= 0.0 or abs(factor - 1.0) < 1e-3:
        return array.copy()

    frame = int(round(float(samplerate) * 0.05))        # 50 ms window
    frame = max(64, frame - frame % 2)
    hop = frame // 2                                    # synthesis hop
    in_hop = max(1, int(round(hop / factor)))           # analysis hop
    search = max(1, int(round(float(samplerate) * 0.005)))   # +/- 5 ms
    if len(array) < frame * 2:
        # Too short for windowed overlap-add: fall back to a plain resample
        # (the pitch follows the speed, but there is no room for artefacts).
        return resample(array, 1.0 / factor)

    window = np.hanning(frame + 1)[:frame].astype(np.float32)[:, None]
    mono = array.mean(axis=1)
    target = max(1, int(round(len(array) * factor)))
    output = np.zeros((target + frame, array.shape[1]), dtype=np.float32)
    weight = np.zeros(target + frame, dtype=np.float32)
    in_pos = 0
    out_pos = 0
    written = 0
    previous_tail = None
    while out_pos < target:
        offset = 0
        if previous_tail is not None and in_pos - search >= 0 \
                and in_pos + search + hop <= len(mono):
            segment = mono[in_pos - search:in_pos + search + hop]
            correlation = np.correlate(segment, previous_tail, mode='valid')
            energy = _sliding_energy(segment, hop)
            scale = float(np.dot(previous_tail, previous_tail))
            denominator = np.sqrt(np.maximum(energy * scale, 1e-12))
            offset = int(np.argmax(correlation / denominator)) - search
        start = max(0, min(len(array) - frame, in_pos + offset))
        piece = array[start:start + frame]
        if len(piece) < frame:
            break
        output[out_pos:out_pos + frame] += piece * window
        weight[out_pos:out_pos + frame] += window[:, 0]
        previous_tail = mono[start + hop:start + frame]
        written = min(out_pos + frame, len(output))
        in_pos += in_hop
        out_pos += hop

    length = min(target, written)
    if length <= 0:
        return resample(array, 1.0 / factor)
    output = output[:length]
    weight = weight[:length]
    valid = weight > 1e-6
    output[valid] /= weight[valid, None]
    return output


def pitch_shift(samples, semitones, samplerate):
    """Shift the pitch by ``semitones`` (12 = one octave) - length kept."""
    factor = float(2.0 ** (float(semitones) / 12.0))
    array = _as_2d(samples)
    if abs(factor - 1.0) < 1e-4:
        return array.copy()
    # Stretch first (pitch unchanged, length x factor), then resample by the
    # same factor (length back to the original, pitch x factor).
    return resample(time_stretch(array, factor, samplerate), factor)


def match_format(samples, samplerate, target_rate, target_channels):
    """Convert samples to another sample rate / channel count.

    Used before appending: the incoming file is resampled to the buffer's
    rate and folded or duplicated to its channel layout.
    """
    array = _as_2d(samples)
    channels = array.shape[1]
    if channels != target_channels:
        if target_channels <= 1:
            array = array.mean(axis=1, keepdims=True)
        elif channels == 1:
            array = np.repeat(array, target_channels, axis=1)
        elif channels > target_channels:
            array = array[:, :target_channels]
        else:
            extra = np.repeat(array[:, -1:], target_channels - channels, axis=1)
            array = np.concatenate([array, extra], axis=1)
    if len(array) and int(samplerate) != int(target_rate):
        array = resample(array, float(samplerate) / float(target_rate))
    return array.astype(np.float32, copy=False)
