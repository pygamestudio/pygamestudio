"""
Audio manager API for generated games.

Provides a simple interface to play sound effects and background music:

    import pygamestudio as studio

    studio.play_sound('./audio/jump.wav')
    studio.play_music('./audio/bgm.ogg', loops=-1)
    studio.set_music_volume(0.5)
    studio.stop_sound('./audio/jump.wav')

Sound files are resolved relative to the project path (the project's `audio/`
folder). The audio mixer is initialized lazily on first use; if no audio device
is available, all calls become no-ops with a warning instead of crashing.
"""

import os
import pygame
from pathlib import Path
from pygamestudio.common.i18n.translator import Translator as T


class AudioManager:
    def __init__(self):
        self._is_available = False
        self._sounds = {}               # absolute path -> pygame.mixer.Sound
        self._looping_channels = {}     # absolute path -> Channel (looping sfx)
        self._music_volume = 1.0

    # ---------- internals ----------

    def _init_mixer(self) -> bool:
        """Initialize pygame.mixer lazily. Returns False when audio is unavailable."""
        if self._is_available:
            return True
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._is_available = True
        except Exception as e:
            print(T.tr('api.fail_to_init_mixer', 'Failed to initialize audio mixer: {}').format(e))
            self._is_available = False
        return self._is_available

    def _resolve_path(self, sound_path) -> Path:
        path = Path(sound_path)
        if path.is_absolute():
            return path
        return Path(os.environ.get('PROJECT_PATH', '')) / path

    def _load_sound(self, sound_path):
        if not self._init_mixer():
            return None

        absolute_path = self._resolve_path(sound_path)
        if not absolute_path.exists():
            print(T.tr('api.no_sound_path', 'The sound path {} does not exist.').format(absolute_path))
            return None

        key = absolute_path.as_posix()
        if key not in self._sounds:
            try:
                self._sounds[key] = pygame.mixer.Sound(str(absolute_path))
            except Exception as e:
                print(T.tr('api.fail_to_load_sound', 'Failed to load sound {}: {}').format(absolute_path, e))
                return None
        return self._sounds[key]

    # ---------- sound effects ----------

    def load_sound(self, sound_path):
        """Load (and cache) a sound effect. Returns a pygame Sound or None."""
        return self._load_sound(sound_path)

    def play_sound(self, sound_path, volume=1.0, loops=0, fade_ms=0):
        """
        Play a sound effect. Returns the pygame Channel, or None on failure.

        :param sound_path: path relative to the project (e.g. './audio/jump.wav')
        :param volume: playback volume in [0.0, 1.0]
        :param loops: 0 = play once, -1 = loop forever, N = play N+1 times
        :param fade_ms: fade-in duration in milliseconds
        """
        sound = self._load_sound(sound_path)
        if sound is None:
            return None

        try:
            channel = sound.play(loops=loops, fade_ms=fade_ms)
            if channel:
                channel.set_volume(max(0.0, min(1.0, float(volume))))
                if loops != 0:
                    self._looping_channels[self._resolve_path(sound_path).as_posix()] = channel
            return channel
        except Exception as e:
            print(T.tr('api.fail_to_play_sound', 'Failed to play sound {}: {}').format(self._resolve_path(sound_path), e))
            return None

    def stop_sound(self, sound_path):
        """Stop a looping sound effect started with play_sound(loops=...)."""
        key = self._resolve_path(sound_path).as_posix()
        channel = self._looping_channels.pop(key, None)
        if channel:
            channel.stop()

    def stop_all_sounds(self):
        """Stop every currently playing sound effect."""
        if self._is_available:
            pygame.mixer.stop()
        self._looping_channels.clear()

    # ---------- background music ----------

    def play_music(self, music_path, loops=-1, fade_ms=0):
        """
        Play a background music track (one stream at a time).

        :param music_path: path relative to the project (e.g. './audio/bgm.ogg')
        :param loops: -1 = loop forever (default), 0 = play once
        :param fade_ms: fade-in duration in milliseconds
        """
        if not self._init_mixer():
            return False

        absolute_path = self._resolve_path(music_path)
        if not absolute_path.exists():
            print(T.tr('api.no_sound_path', 'The sound path {} does not exist.').format(absolute_path))
            return False

        try:
            pygame.mixer.music.load(str(absolute_path))
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
            return True
        except Exception as e:
            print(T.tr('api.fail_to_play_music', 'Failed to play music {}: {}').format(absolute_path, e))
            return False

    def stop_music(self, fade_ms=0):
        """Stop the background music (with an optional fade-out in ms)."""
        if not self._is_available:
            return
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()

    def pause_music(self):
        if self._is_available:
            pygame.mixer.music.pause()

    def resume_music(self):
        if self._is_available:
            pygame.mixer.music.unpause()

    def is_music_playing(self) -> bool:
        if not self._is_available:
            return False
        return pygame.mixer.music.get_busy()

    def set_music_volume(self, volume):
        """Set background music volume in [0.0, 1.0]."""
        self._music_volume = max(0.0, min(1.0, float(volume)))
        if self._is_available:
            pygame.mixer.music.set_volume(self._music_volume)

    def get_music_volume(self) -> float:
        return self._music_volume


# Module-level singleton, mirroring scene_loader.
audio_manager = AudioManager()


def load_sound(sound_path):
    return audio_manager.load_sound(sound_path)


def play_sound(sound_path, volume=1.0, loops=0, fade_ms=0):
    return audio_manager.play_sound(sound_path, volume, loops, fade_ms)


def stop_sound(sound_path):
    return audio_manager.stop_sound(sound_path)


def stop_all_sounds():
    return audio_manager.stop_all_sounds()


def play_music(music_path, loops=-1, fade_ms=0):
    return audio_manager.play_music(music_path, loops, fade_ms)


def stop_music(fade_ms=0):
    return audio_manager.stop_music(fade_ms)


def pause_music():
    return audio_manager.pause_music()


def resume_music():
    return audio_manager.resume_music()


def is_music_playing() -> bool:
    return audio_manager.is_music_playing()


def set_music_volume(volume):
    return audio_manager.set_music_volume(volume)


def get_music_volume() -> float:
    return audio_manager.get_music_volume()
