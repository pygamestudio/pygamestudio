import re
import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path

# Image formats pygame can load; these are picked out of the frame folder.
_FRAME_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp',
                     '.tga', '.pcx', '.qoi', '.xpm', '.lbm'}


def _natural_key(text):
    """Sort key so 'frame2.png' comes before 'frame10.png'."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', str(text))]


class ObjectFrameSequence(ObjectBase):
    """A frame-sequence (sprite) animation object.

    Points at a project folder whose image files are the frames of an
    animation, played in file-name order at a given frame rate. It can loop or
    play once, be paused/resumed, scrubbed to a specific frame and is fully
    drivable from a behavior script at runtime.
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/frame_sequence.png'

        common_properties = {
            'name': 'Frame Sequence',
            'type': OBJECT_FRAME_SEQUENCE,
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
            # Frame sequence parameters.
            'frame_folder': '',       # project-relative folder holding the frames
            'frame_rate': 8.0,        # frames per second
            'auto_play': True,        # advances automatically while True
            'loop': True,             # True = wrap, False = play once & hold last
            'frame_index': 0,         # current frame (persisted starting frame)
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)

        # Transient runtime state (excluded from serialization).
        self._frames_cache = {}       # frame_folder -> [Surface, ...]
        self._frames_cache_folder = None
        self._anim_time = float(self.frame_index) / max(float(self.frame_rate), 0.001)
        self._last_update_time = pygame.time.get_ticks()

        self._is_initialized = True

        self._start()

    # ---------------------------------------------------------------- API
    def get_frame_folder(self):
        """Project-relative folder whose images are the animation frames."""
        return self.frame_folder

    def set_frame_folder(self, frame_folder):
        self.frame_folder = frame_folder

    def get_frame_rate(self):
        """Playback speed in frames per second."""
        return self.frame_rate

    def set_frame_rate(self, frame_rate):
        self.frame_rate = max(0.0, float(frame_rate))

    def get_auto_play_state(self):
        """Whether the animation advances automatically."""
        return self.auto_play

    def set_auto_play_state(self, auto_play):
        self.auto_play = bool(auto_play)

    def get_loop_state(self):
        """True = loop forever, False = play once then hold the last frame."""
        return self.loop

    def set_loop_state(self, loop):
        self.loop = bool(loop)

    def get_frame_index(self):
        """Index of the currently displayed frame."""
        return self.frame_index

    def set_frame_index(self, frame_index):
        """Show the given frame (playback continues from there)."""
        count = self.get_frame_count()
        if count > 0:
            index = int(frame_index)
            if self.loop:
                index = index % count
            else:
                index = max(0, min(index, count - 1))
        else:
            index = 0
        self.frame_index = index
        self._anim_time = index / max(float(self.frame_rate), 0.001)

    def get_frame_count(self):
        """Number of frames loaded from the frame folder (0 when unset)."""
        return len(self._load_frames())

    def play(self):
        """Start (or resume) automatic playback."""
        self.auto_play = True

    def pause(self):
        """Freeze on the current frame."""
        self.auto_play = False

    def stop(self):
        """Pause and rewind to the first frame."""
        self.auto_play = False
        self.set_frame_index(0)

    def restart(self):
        """Rewind to the first frame and start playing."""
        self.set_frame_index(0)
        self.auto_play = True

    def is_auto_play(self):
        return self.auto_play

    def _to_dict(self):
        """Serialize the animation config, excluding the transient runtime
        state (loaded frame surfaces, playback clock, timers) so the scene
        file stays small and reloadable."""
        data = super()._to_dict()
        for key in ('_frames_cache', '_frames_cache_folder', '_anim_time',
                    '_last_update_time'):
            data.pop(key, None)
        data['frame_index'] = int(data.get('frame_index', 0))
        data['frame_rate'] = float(data.get('frame_rate', 8.0))
        return data

    # ---------------------------------------------------------------- internals
    def __setattr__(self, name, value):
        """Keep frame_folder stored as a project-relative path (like the
        image object does with image_path)."""
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'frame_folder':
            if not value:
                super().__setattr__('frame_folder', '')
            else:
                project_path = Path(get_project_path())
                new_path = Path(value).absolute()
                try:
                    super().__setattr__('frame_folder', new_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('frame_folder', new_path.as_posix())
        else:
            super().__setattr__(name, value)

    def _load_frames(self):
        """Return the loaded frame surfaces for the configured folder. The
        result is cached per folder path and rebuilt when the folder changes
        (or its files change between edits)."""
        folder = self.frame_folder
        if folder == self._frames_cache_folder and folder in self._frames_cache:
            return self._frames_cache[folder]

        frames = []
        if folder:
            folder_path = Path(get_project_path()) / folder
            if folder_path.is_dir():
                image_files = sorted(
                    (p for p in folder_path.iterdir()
                     if p.is_file() and p.suffix.lower() in _FRAME_EXTENSIONS),
                    key=lambda p: _natural_key(p.stem))
                for image_path in image_files:
                    try:
                        frame = pygame.image.load(str(image_path))
                        try:
                            frame = frame.convert_alpha()
                        except pygame.error:
                            pass
                        frames.append(frame)
                    except pygame.error:
                        continue

        self._frames_cache[folder] = frames
        self._frames_cache_folder = folder
        return frames

    def _advance(self):
        """Advance the playback clock by the real elapsed time (capped, so a
        long pause between redraws does not jump the animation) and update the
        current frame index."""
        now = pygame.time.get_ticks()
        elapsed = min((now - self._last_update_time) / 1000.0, 0.25)
        self._last_update_time = now

        if not self.auto_play:
            return

        self._anim_time += elapsed
        count = len(self._load_frames())
        if count <= 0:
            self.frame_index = 0
            return

        index = int(self._anim_time * max(float(self.frame_rate), 0.001))
        if self.loop:
            self.frame_index = index % count
        else:
            self.frame_index = min(index, count - 1)

    def _update_surface(self):
        self._advance()
        frames = self._load_frames()

        base = None
        if frames:
            base = frames[max(0, min(len(frames) - 1, self.frame_index))]

        if base is None:
            # No frames configured/available: render nothing (fully
            # transparent, like an image object whose file is missing).
            self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        else:
            # Fit the current frame into the object's box (same as the image
            # object), tint it with the object color (self.color may be a list
            # after loading from JSON - no tuple concatenation here), then
            # apply scale / rotation / alpha.
            scaled = pygame.transform.scale(
                base, (max(1, self.width), max(1, self.height))).copy()
            scaled.fill(self.color[:3], special_flags=pygame.BLEND_RGBA_MULT)

            scaled_size = (max(1, int(scaled.get_width() * self.scale_x)),
                           max(1, int(scaled.get_height() * self.scale_y)))
            scaled_surface = pygame.transform.scale(scaled, scaled_size)
            rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
            self.surface = self._apply_alpha(rotated_surface)

        super()._update_surface()
