"""Keyframe (timeline) animation object.

The frame-sequence object plays image frames from a folder; this object
instead animates ITS OWN channels - position (x, y), scale, angle and color -
along a timeline of keyframe snapshots, edited in the Animation Editor.

Design notes:

* A keyframe is a full snapshot of the animated channels (``KEYFRAME_CHANNELS``)
  plus a ``time`` and an ``easing``. The easing of a keyframe shapes the
  segment that STARTS at it.
* The timeline is authoritative while the game runs: every frame the object
  advances its clock, evaluates the timeline and applies the values to its own
  attributes (like any other object, so nested objects, collision, physics and
  scripts all see the animated state).
* In the EDITOR the playback clock stays still (``_advance`` is runtime-only),
  so incidental scene refreshes can never silently rewrite the saved values.
  The Animation Editor drives previews explicitly through ``preview_at``.
"""
import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.utils import assets

#: The animated channels of one keyframe snapshot, in a fixed order. The
#: numeric channels and the colour interpolate; ``image_path`` switches at the
#: start of a segment (an image cannot be blended).
KEYFRAME_CHANNELS = ('x', 'y', 'scale_x', 'scale_y', 'angle', 'color', 'image_path')

#: Named easing curves (dropdown order). A curve maps linear segment progress
#: 0..1 to eased progress.
EASING_CURVES = ('linear', 'ease_in', 'ease_out', 'ease_in_out')
DEFAULT_EASING = 'linear'


def ease_progress(kind, t):
    """Map linear progress 0..1 through the named easing curve."""
    t = max(0.0, min(1.0, float(t)))
    if kind == 'ease_in':
        return t * t
    if kind == 'ease_out':
        return 1.0 - (1.0 - t) * (1.0 - t)
    if kind == 'ease_in_out':
        if t < 0.5:
            return 2.0 * t * t
        return 1.0 - 2.0 * (1.0 - t) * (1.0 - t)
    return t


def _number(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _keyframe_time(value):
    """The numeric time of one keyframe entry, or None when unusable.

    A keyframe whose time cannot be read has no place on the timeline, so
    ``normalize_keyframes`` drops it instead of silently snapping it to 0.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _color(value):
    try:
        items = list(value)
    except TypeError:
        items = []
    while len(items) < 4:
        items.append(255)
    return [max(0, min(255, int(round(_number(item, 255))))) for item in items[:4]]


def _image_path(value):
    """Canonical keyframe image path: project-relative posix, or ''.

    A relative path is project-relative (never relative to the process
    directory); an absolute one is stored relative to the project when it
    lives inside it. Keeps the saved snapshots portable.
    """
    text = '' if value is None else str(value)
    if not text:
        return ''
    project_path = Path(get_project_path() or '')
    if str(project_path) == '.':
        return text
    path = Path(text)
    if not path.is_absolute():
        path = project_path / path
    try:
        return path.resolve().relative_to(project_path.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def normalize_keyframes(keyframes):
    """Sanitise + sort a keyframe list (shared with the Animation Editor).

    Builds fresh dicts, so the caller's data is never aliased or mutated.
    """
    result = []
    for entry in keyframes or []:
        if not isinstance(entry, dict):
            continue
        moment = _keyframe_time(entry.get('time', 0.0))
        if moment is None:
            continue
        easing = entry.get('easing')
        frame = {
            'time': max(0.0, moment),
            'easing': easing if easing in EASING_CURVES else DEFAULT_EASING,
            'x': _number(entry.get('x', 0.0)),
            'y': _number(entry.get('y', 0.0)),
            'scale_x': _number(entry.get('scale_x', 1.0), 1.0),
            'scale_y': _number(entry.get('scale_y', 1.0), 1.0),
            'angle': _number(entry.get('angle', 0.0)),
            'color': _color(entry.get('color', (255, 255, 255, 255))),
            'image_path': _image_path(entry.get('image_path', '')),
        }
        result.append(frame)
    result.sort(key=lambda frame: frame['time'])
    return result


def snapshot_from_object(obj, time=0.0, easing=DEFAULT_EASING):
    """A keyframe snapshot of the object's CURRENT channel values."""
    return {
        'time': max(0.0, _number(time)),
        'easing': easing if easing in EASING_CURVES else DEFAULT_EASING,
        'x': float(obj.x),
        'y': float(obj.y),
        'scale_x': float(obj.scale_x),
        'scale_y': float(obj.scale_y),
        'angle': float(obj.angle),
        'color': _color(obj.color),
        'image_path': _image_path(obj.image_path),
    }


def _channels(frame):
    """A copy of one snapshot's channel values."""
    values = {channel: frame[channel] for channel in KEYFRAME_CHANNELS}
    values['color'] = list(frame['color'])
    return values


def _blend(start, end, progress):
    """Interpolate the channels between two snapshots."""
    values = {}
    for channel in ('x', 'y', 'scale_x', 'scale_y', 'angle'):
        values[channel] = start[channel] + (end[channel] - start[channel]) * progress
    values['color'] = [
        max(0, min(255, int(round(start['color'][index]
                                  + (end['color'][index] - start['color'][index])
                                  * progress))))
        for index in range(4)
    ]
    # An image cannot be blended: it switches at the start of the segment.
    values['image_path'] = start['image_path']
    return values


class ObjectKeyframe(ObjectBase):
    """A keyframe (timeline) animation object.

    Renders like an image object - an optional ``image_path`` tinted by the
    object color, a plain color rect when the path is empty - and animates
    x, y, scale, angle and color along its keyframe timeline.
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/key_sequence.png'

        common_properties = {
            'name': 'Keyframe',
            'type': OBJECT_KEYFRAME,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 128,
            'height': 128,
            'size': (128, 128),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            # Keyframe-animation parameters.
            'image_path': '',      # optional base image; '' draws a plain color rect
            'keyframes': [],       # snapshots sorted by time (see KEYFRAME_CHANNELS)
            'duration': 2.0,       # timeline length in seconds
            'auto_play': True,
            'loop': True,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)

        # Transient runtime state (excluded from serialization).
        self._anim_time = 0.0
        self._last_update_time = pygame.time.get_ticks()
        self._run_started = False        # on_animation_start fired for this run
        self._finished_emitted = False   # on_animation_finished fired for this run
        self._base_image_cache = (None, None, None)  # path, mtime, decoded surface

        self._is_initialized = True
        # Run the loaded values through the sanitising setters once.
        self.keyframes = self.keyframes
        self.duration = self.duration

        self._start()

    # ---------------------------------------------------------------- API
    def get_image_path(self):
        """The optional base image ('' = plain color rect)."""
        return self.image_path

    def set_image_path(self, image_path):
        self.image_path = image_path

    def get_keyframes(self):
        """The keyframe snapshots (a copy - editing it does not change the
        object; assign a new list with set_keyframes)."""
        return [dict(frame, color=list(frame['color'])) for frame in self.keyframes]

    def set_keyframes(self, keyframes):
        self.keyframes = keyframes

    def get_duration(self):
        """Timeline length in seconds (may exceed the last keyframe)."""
        return self.duration

    def set_duration(self, duration):
        self.duration = duration

    def get_timeline_length(self):
        """The effective timeline length: max(duration, last keyframe time)."""
        length = float(self.duration)
        if self.keyframes:
            length = max(length, float(self.keyframes[-1]['time']))
        return max(0.0, length)

    def get_time(self):
        """Playback time in seconds."""
        return self._anim_time

    def set_time(self, time):
        """Jump to a time in seconds (playback continues from there)."""
        length = self.get_timeline_length()
        value = max(0.0, _number(time))
        if length > 0 and self.loop:
            value = value % length
        elif length > 0:
            value = min(value, length)
        self._anim_time = value
        self._finished_emitted = False

    def get_auto_play_state(self):
        """Whether the timeline advances automatically."""
        return self.auto_play

    def set_auto_play_state(self, auto_play):
        self.auto_play = bool(auto_play)

    def get_loop_state(self):
        """True = loop the timeline, False = play once and hold the end."""
        return self.loop

    def set_loop_state(self, loop):
        self.loop = bool(loop)

    def play(self):
        """Start (or resume) automatic playback."""
        if not self.auto_play:
            self.auto_play = True
            self._finished_emitted = False
            self._run_started = True
            self._emit_event('on_animation_start')

    def pause(self):
        """Freeze on the current time."""
        self.auto_play = False

    def stop(self):
        """Pause and rewind to the start of the timeline."""
        self.auto_play = False
        self.set_time(0.0)

    def restart(self):
        """Rewind to the start and play."""
        self.set_time(0.0)
        self.auto_play = True
        self._finished_emitted = False
        self._run_started = True
        self._emit_event('on_animation_start')

    def is_auto_play(self):
        return self.auto_play

    # ------------------------------------------------------------ evaluation
    def evaluate_at(self, time):
        """The interpolated channel values at ``time`` (None without keyframes).

        Before the first / after the last keyframe the nearest snapshot is
        held; inside a segment the easing of the segment's FIRST keyframe
        shapes the progress.
        """
        frames = self.keyframes
        if not frames:
            return None
        moment = max(0.0, _number(time))
        if moment <= frames[0]['time']:
            return _channels(frames[0])
        if moment >= frames[-1]['time']:
            return _channels(frames[-1])
        for index in range(len(frames) - 1):
            start, end = frames[index], frames[index + 1]
            if start['time'] <= moment < end['time']:
                span = end['time'] - start['time']
                progress = 0.0 if span <= 0 else (moment - start['time']) / span
                return _blend(start, end, ease_progress(start['easing'], progress))
        return _channels(frames[-1])

    def preview_at(self, time):
        """Apply the timeline value at ``time`` without playing the clock.

        Used by the Animation Editor to scrub and to preview playback: the
        values are written to the live attributes (no undo entry) and the
        surface is rebuilt, so the scene view shows the result. The editor
        restores the object's own values when it stops previewing.
        Returns True when something was applied.
        """
        values = self.evaluate_at(time)
        if values is None:
            return False
        self._anim_time = max(0.0, _number(time))
        self._apply_values(values)
        self._refresh_surface()
        return True

    # ------------------------------------------------------------ user hooks
    def on_animation_start(self):
        """User hook: called when the animation (re)starts at runtime."""
        ...

    def on_animation_finished(self):
        """User hook: called when a play-once animation reaches the end."""
        ...

    def _to_dict(self):
        """Serialize the timeline, excluding the transient runtime state
        (playback clock, timers, finish flags)."""
        data = super()._to_dict()
        for key in ('_anim_time', '_last_update_time', '_run_started',
                    '_finished_emitted', '_base_image_cache'):
            data.pop(key, None)
        data['keyframes'] = normalize_keyframes(data.get('keyframes'))
        data['duration'] = float(data.get('duration', 2.0))
        return data

    # ---------------------------------------------------------------- internals
    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'image_path':
            super().__setattr__('image_path', _image_path(value))
        elif name == 'keyframes':
            super().__setattr__('keyframes', normalize_keyframes(value))
        elif name == 'duration':
            super().__setattr__('duration', max(0.0, _number(value, 2.0)))
        elif name == 'auto_play':
            # Pausing re-arms the start notification: the animation reports
            # itself as started again when it resumes (including through a
            # plain `auto_play = True` assignment).
            super().__setattr__('auto_play', value)
            if not value:
                super().__setattr__('_run_started', False)
        else:
            super().__setattr__(name, value)

    def _advance(self):
        """Advance the playback clock by the real elapsed time (capped, so a
        long pause between redraws does not jump the animation).

        Runtime only: in the editor the clock stays still so incidental scene
        refreshes never rewrite the saved values (the Animation Editor drives
        previews itself).
        """
        if not self._is_for_api:
            return
        now = pygame.time.get_ticks()
        elapsed = min((now - self._last_update_time) / 1000.0, 0.25)
        self._last_update_time = now

        if not self.auto_play:
            return

        if not self._run_started:
            # The animation is running: report the start once, so an object
            # that enters the scene already playing fires on_animation_start
            # as well (the first frame is advanced after the scripts' own
            # on_start hooks have run).
            self._run_started = True
            self._emit_event('on_animation_start')

        length = self.get_timeline_length()
        if length <= 0:
            return

        self._anim_time += elapsed
        if self.loop:
            self._anim_time = self._anim_time % length
            self._finished_emitted = False
        elif self._anim_time >= length:
            self._anim_time = length
            if not self._finished_emitted:
                self._finished_emitted = True
                self._emit_event('on_animation_finished')

    def _apply_values(self, values):
        """Write evaluated channel values onto the live attributes.

        Pos / scale are written as tuples so the base class updates x/y and
        scale_x/scale_y through the supported direction. The image only
        changes when the timeline actually moved to another one (the setter
        is cheap, but rebuilding the surface constantly is not).
        """
        self.pos = (values['x'], values['y'])
        self.scale = (values['scale_x'], values['scale_y'])
        self.angle = values['angle']
        self.color = list(values['color'])
        image_path = values.get('image_path', '')
        if image_path != self.image_path:
            self.image_path = image_path

    def _update_surface(self):
        if self._is_for_api:
            self._advance()
            values = self.evaluate_at(self._anim_time)
            if values is not None:
                self._apply_values(values)
        self._refresh_surface()

    def _refresh_surface(self):
        """Rebuild the rendered surface from the object's own style fields
        (size, color, image, scale, angle). The channel values are expected
        to be applied already."""
        self._rebuild_base_surface()
        scaled_size = (max(1, int(self.surface.get_width() * self.scale_x)),
                       max(1, int(self.surface.get_height() * self.scale_y)))
        scaled = pygame.transform.scale(self.surface, scaled_size)
        rotated = pygame.transform.rotate(scaled, self.angle)
        self.surface = self._apply_alpha(rotated)
        super()._update_surface()

    def _rebuild_base_surface(self):
        """Plain color rect (empty image path), or the image tinted by the
        object color; a missing image renders nothing (like the image
        object)."""
        if self.image_path:
            image_absolute_path = Path(get_project_path()) / self.image_path
            if image_absolute_path.exists():
                base = pygame.transform.scale(
                    self._load_base_image(image_absolute_path),
                    (max(1, self.width), max(1, self.height))).copy()
                # Tint with RGB; the alpha channel travels through
                # _apply_alpha below (same model as the image object).
                base.fill(tuple(self.color)[:3], special_flags=pygame.BLEND_RGBA_MULT)
                self.surface = base
                return
            self.surface = pygame.Surface((max(1, self.width),
                                           max(1, self.height)), pygame.SRCALPHA)
            return

        self.surface = pygame.Surface((max(1, self.width), max(1, self.height)),
                                      pygame.SRCALPHA)
        self.surface.fill(tuple(_color(self.color)))

    def _load_base_image(self, image_absolute_path):
        """The decoded source image, cached by path + mtime.

        A keyframe animation can switch images and the surface is rebuilt on
        every frame, so decoding the file each time would be wasteful; the
        mtime keeps a replaced image hot-reloadable.
        """
        try:
            mtime = image_absolute_path.stat().st_mtime
        except OSError:
            mtime = None
        cache_path, cache_mtime, cache_surface = self._base_image_cache
        if (cache_surface is not None and cache_path == str(image_absolute_path)
                and cache_mtime == mtime):
            return cache_surface
        loaded = pygame.image.load(assets.open_stream(image_absolute_path))
        try:
            loaded = loaded.convert_alpha()
        except pygame.error:
            pass
        self._base_image_cache = (str(image_absolute_path), mtime, loaded)
        return loaded
