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
import sys
import pygame
from pathlib import Path
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils import assets


# Web only: the browser drives pygame's mixer from the main thread (SDL's
# emscripten audio driver fills its buffers inside a ScriptProcessorNode
# callback), so a small buffer underruns whenever a Python frame takes long
# and the playback crackles. ~4096 samples (about 93 ms at 44.1 kHz) keeps
# the music glitch-free there. Desktop keeps pygame's default.
WEB_MIXER_BUFFER = 4096


def _web_audio_frequency(default: int = 44100) -> int:
    """The browser AudioContext's native sample rate, so the mixer can open
    at that rate and SDL does no resampling. Falls back to ``default``
    outside the browser or when the rate cannot be read."""
    try:
        import js

        context = js.AudioContext.new()
        try:
            rate = int(context.sampleRate)
        finally:
            context.close()
        if 8000 <= rate <= 192000:
            return rate
    except Exception:
        pass
    return default


#: How often (ms) a blocked music start is retried until a user gesture lets
#: the browser play it (see _WebAudioBackend._install_unlock_listener).
WEB_AUDIO_RETRY_MS = 700


class _WebAudioBackend:
    """Browser-native audio playback for the web build.

    The music streams through an <audio> element and sound effects play
    through small element pools, so the BROWSER decodes the files - MP3, OGG,
    WAV, any format the browser supports - with its native codecs on its own
    thread. Other engines' web exports play through this same pipeline, while
    SDL's WASM mixer decodes and resamples on the main thread (slower, and it
    colours low-sample-rate files). The SDL path in AudioManager stays as the
    fallback when anything here fails.
    """

    #: <audio> elements created per sound effect (they may overlap)
    SFX_POOL_SIZE = 4

    def __init__(self):
        self.available = False
        self.sound_volume = 1.0         # master volume of the sound effects
        self._js = None
        self._unlock_listener = None
        self._music_element = None
        self._music_path = ''
        self._music_wants_playing = False
        self._music_volume = 1.0
        self._last_play_error = None    # last play() rejection (diagnostics)
        self._urls = {}                 # absolute path -> blob URL
        self._pools = {}                # absolute path -> [<audio> elements]
        self._round_robin = {}          # absolute path -> next pool slot
        self._slot_volumes = {}         # absolute path -> per-slot call volume
        try:
            import js

            if (getattr(js, 'Audio', None) is None
                    or getattr(js, 'URL', None) is None
                    or getattr(js, 'Blob', None) is None):
                return
            self._js = js
            self._install_unlock_listener()
            self.available = True
        except Exception:
            self.available = False

    # ---------- internals ----------

    def _install_unlock_listener(self):
        """Browsers hold audio back until the first user gesture. The game
        starts by itself, so a blocked music start is retried on the first
        click/tap/key - and, extra safety, by a slow timer, because a gesture
        anywhere in the page counts even when its event never reaches us.

        The callback MUST go through ``create_proxy``: Pyodide destroys the
        proxy it creates for a plain Python callable again as soon as a JS
        call with a non-Promise result returns, so a directly passed listener
        is dead before the first click (the music stays silent forever). The
        proxy is kept on the instance so it stays alive.
        """
        try:
            from pyodide.ffi import create_proxy

            self._unlock_listener = create_proxy(self._on_user_gesture)
        except Exception:
            self._unlock_listener = None
            return
        for target in (self._js.document, getattr(self._js, 'window', None)):
            if target is None:
                continue
            for event_name in ('pointerdown', 'keydown'):
                try:
                    target.addEventListener(event_name, self._unlock_listener, True)
                except Exception:
                    pass
        try:
            self._js.setInterval(self._unlock_listener, WEB_AUDIO_RETRY_MS)
        except Exception:
            pass

    def _on_user_gesture(self, event=None):
        element = self._music_element
        if self._music_wants_playing and element is not None:
            try:
                if element.paused or element.ended:
                    self._start(element)
            except Exception:
                pass

    def _create_element(self, absolute_path):
        """A new <audio> element playing this file (blob URLs are cached)."""
        key = str(absolute_path)
        url = self._urls.get(key)
        if url is None:
            from pyodide.ffi import to_js

            data = assets.read_bytes(absolute_path)
            blob = self._js.Blob.new([to_js(data)])
            url = str(self._js.URL.createObjectURL(blob))
            self._urls[key] = url
        element = self._js.Audio.new()
        element.src = url
        return element

    def _start(self, element):
        """play() and keep the rejection quiet: a blocked autoplay retries on
        the next gesture / timer tick, so its NotAllowedError is expected.
        The reason is kept in ``_last_play_error`` for diagnostics."""
        try:
            promise = element.play()
        except Exception:
            return
        if promise is None:
            return
        try:
            promise.catch(self._on_play_rejected)
        except AttributeError:
            # Pyodide turns a JS promise into a Python Future, which has no
            # catch() - listen through the future API instead.
            try:
                promise.add_done_callback(self._on_play_done)
            except Exception:
                pass
        except Exception:
            pass

    def _on_play_rejected(self, error=None):
        self._last_play_error = str(error)
        return None

    def _on_play_done(self, future):
        try:
            error = future.exception()
        except Exception:
            error = None
        if error is not None:
            self._last_play_error = str(error)

    # ---------- sound effects ----------

    def load_sound(self, absolute_path):
        """Pre-load a sound: create its element pool and the blob URL."""
        pool = self._pool(absolute_path)
        return pool[0] if pool else None

    def _pool(self, absolute_path):
        key = str(absolute_path)
        pool = self._pools.get(key)
        if pool is None:
            pool = [self._create_element(absolute_path)
                    for _ in range(self.SFX_POOL_SIZE)]
            self._pools[key] = pool
            self._round_robin[key] = 0
            self._slot_volumes[key] = [1.0] * self.SFX_POOL_SIZE
        return pool

    def play_sound(self, absolute_path, volume=1.0, loops=0):
        key = str(absolute_path)
        pool = self._pool(key)
        index = self._free_slot(key, pool)
        element = pool[index]
        self._slot_volumes[key][index] = max(0.0, min(1.0, float(volume)))
        element.loop = loops != 0
        self._apply_slot_volume(key, index)
        try:
            element.currentTime = 0
        except Exception:
            pass
        self._start(element)
        return element

    def _free_slot(self, key, pool):
        """First idle element from the round-robin cursor (busy ones are all
        reused once every slot plays, like pygame's channel stealing)."""
        start = self._round_robin.get(key, 0)
        index = start
        for offset in range(len(pool)):
            candidate = (start + offset) % len(pool)
            try:
                if pool[candidate].paused or pool[candidate].ended:
                    index = candidate
                    break
            except Exception:
                index = candidate
                break
        self._round_robin[key] = (index + 1) % len(pool)
        return index

    def _apply_slot_volume(self, key, index):
        try:
            pool = self._pools[key]
            pool[index].volume = self._slot_volumes[key][index] * self.sound_volume
        except Exception:
            pass

    def stop_sound(self, absolute_path):
        for element in self._pools.get(str(absolute_path), ()):
            try:
                element.pause()
                element.currentTime = 0
            except Exception:
                pass

    def is_sound_playing(self, absolute_path) -> bool:
        for element in self._pools.get(str(absolute_path), ()):
            try:
                if not element.paused and not element.ended:
                    return True
            except Exception:
                continue
        return False

    def set_sound_volume(self, volume):
        self.sound_volume = max(0.0, min(1.0, float(volume)))
        for key, pool in self._pools.items():
            for index in range(len(pool)):
                self._apply_slot_volume(key, index)

    def stop_all_sounds(self):
        for pool in self._pools.values():
            for element in pool:
                try:
                    element.pause()
                    element.currentTime = 0
                except Exception:
                    pass

    # ---------- background music ----------

    def play_music(self, absolute_path, loops=-1, volume=1.0):
        key = str(absolute_path)
        if self._music_element is None or self._music_path != key:
            self._stop_music_element(reset=True)
            self._music_element = self._create_element(absolute_path)
            self._music_path = key
        element = self._music_element
        element.loop = loops != 0
        self.set_music_volume(volume)
        try:
            element.currentTime = 0
        except Exception:
            pass
        self._music_wants_playing = True
        self._start(element)
        return True

    def _stop_music_element(self, reset=False):
        element = self._music_element
        if element is None:
            return
        try:
            element.pause()
            if reset:
                element.currentTime = 0
        except Exception:
            pass

    def stop_music(self):
        self._music_wants_playing = False
        self._stop_music_element(reset=True)

    def pause_music(self):
        self._music_wants_playing = False
        self._stop_music_element()

    def resume_music(self):
        element = self._music_element
        if element is None:
            return
        self._music_wants_playing = True
        self._start(element)

    def is_music_playing(self) -> bool:
        element = self._music_element
        if element is None:
            return False
        try:
            return not element.paused and not element.ended
        except Exception:
            return False

    def set_music_volume(self, volume):
        self._music_volume = max(0.0, min(1.0, float(volume)))
        element = self._music_element
        if element is not None:
            try:
                element.volume = self._music_volume
            except Exception:
                pass


class AudioManager:
    def __init__(self):
        self._is_available = False
        self._sounds = {}               # absolute path -> pygame.mixer.Sound
        self._looping_channels = {}     # absolute path -> Channel (looping sfx)
        self._music_volume = 1.0
        self._sound_volume = 1.0        # master volume of the sound effects
        # On the web the browser plays the audio itself (native codecs, its
        # own thread - see _WebAudioBackend); the SDL mixer below stays as the
        # fallback when anything there fails.
        self._web = None
        if sys.platform == 'emscripten':
            backend = _WebAudioBackend()
            self._web = backend if backend.available else None

    # ---------- internals ----------

    def _init_mixer(self) -> bool:
        """Initialize pygame.mixer lazily. Returns False when audio is unavailable."""
        if self._is_available:
            return True
        try:
            if not pygame.mixer.get_init():
                if sys.platform == 'emscripten':
                    # Open at the browser's own sample rate with a big buffer:
                    # no resampling in the main-thread audio callback and no
                    # underruns on slow frames (see WEB_MIXER_BUFFER).
                    pygame.mixer.init(frequency=_web_audio_frequency(), size=-16,
                                      channels=2, buffer=WEB_MIXER_BUFFER)
                else:
                    pygame.mixer.init()
            self._is_available = True
        except Exception as e:
            print(T.tr('api.fail_to_init_mixer', 'Failed to initialize audio mixer: {}').format(e))
            self._is_available = False
        return self._is_available

    def _web_failed(self, error) -> None:
        """Drop the browser backend and fall through to the SDL mixer."""
        print(T.tr('api.fail_to_use_web_audio',
                   'Browser audio is not available, using the SDL mixer: {}').format(error))
        self._web = None

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
                self._sounds[key] = pygame.mixer.Sound(file=assets.open_stream(absolute_path))
            except Exception as e:
                print(T.tr('api.fail_to_load_sound', 'Failed to load sound {}: {}').format(absolute_path, e))
                return None
        return self._sounds[key]

    # ---------- sound effects ----------

    def load_sound(self, sound_path):
        """Load (and cache) a sound effect. Returns a pygame Sound or None."""
        if self._web is not None:
            absolute_path = self._resolve_path(sound_path)
            if not absolute_path.exists():
                print(T.tr('api.no_sound_path', 'The sound path {} does not exist.').format(absolute_path))
                return None
            try:
                return self._web.load_sound(absolute_path)
            except Exception as e:
                self._web_failed(e)
        return self._load_sound(sound_path)

    def play_sound(self, sound_path, volume=1.0, loops=0, fade_ms=0):
        """
        Play a sound effect. Returns the pygame Channel, or None on failure.

        :param sound_path: path relative to the project (e.g. './audio/jump.wav')
        :param volume: playback volume in [0.0, 1.0]
        :param loops: 0 = play once, -1 = loop forever, N = play N+1 times
        :param fade_ms: fade-in duration in milliseconds (ignored on the web)
        """
        if self._web is not None:
            absolute_path = self._resolve_path(sound_path)
            if not absolute_path.exists():
                print(T.tr('api.no_sound_path', 'The sound path {} does not exist.').format(absolute_path))
                return None
            try:
                return self._web.play_sound(absolute_path, volume=volume, loops=loops)
            except Exception as e:
                self._web_failed(e)
        sound = self._load_sound(sound_path)
        if sound is None:
            return None

        try:
            channel = sound.play(loops=loops, fade_ms=fade_ms)
            if channel:
                # The per-call volume is multiplied with the master volume, so
                # set_sound_volume() works like a volume slider of the game.
                channel.set_volume(max(0.0, min(1.0, float(volume))) * self._sound_volume)
                if loops != 0:
                    self._looping_channels[self._resolve_path(sound_path).as_posix()] = channel
            return channel
        except Exception as e:
            print(T.tr('api.fail_to_play_sound', 'Failed to play sound {}: {}').format(self._resolve_path(sound_path), e))
            return None

    def stop_sound(self, sound_path):
        """Stop a sound effect (one-shot or looping) that is playing."""
        if self._web is not None:
            try:
                self._web.stop_sound(self._resolve_path(sound_path))
                return
            except Exception as e:
                self._web_failed(e)
        key = self._resolve_path(sound_path).as_posix()
        self._looping_channels.pop(key, None)
        sound = self._sounds.get(key)
        if sound is None or not self._is_available:
            return
        try:
            sound.stop()            # every channel this sound plays on
        except pygame.error as e:
            print(T.tr('api.fail_to_set_volume', 'Audio operation failed: {}').format(e))

    def is_sound_playing(self, sound_path) -> bool:
        """True while a loaded sound effect is playing on any channel."""
        if self._web is not None:
            try:
                return self._web.is_sound_playing(self._resolve_path(sound_path))
            except Exception as e:
                self._web_failed(e)
        if not self._is_available:
            return False
        sound = self._sounds.get(self._resolve_path(sound_path).as_posix())
        if sound is None:
            return False
        try:
            return bool(sound.get_num_channels())
        except pygame.error:
            return False

    def set_sound_volume(self, volume):
        """Master volume of the sound effects, in [0.0, 1.0].

        Affects the sounds that are playing right now and is multiplied with
        the per-call ``volume`` of every later play_sound().
        """
        self._sound_volume = max(0.0, min(1.0, float(volume)))
        if self._web is not None:
            try:
                self._web.set_sound_volume(self._sound_volume)
                return
            except Exception as e:
                self._web_failed(e)
        if not self._is_available:
            return
        try:
            for index in range(pygame.mixer.get_num_channels()):
                pygame.mixer.Channel(index).set_volume(self._sound_volume)
        except pygame.error as e:
            print(T.tr('api.fail_to_set_volume', 'Audio operation failed: {}').format(e))

    def get_sound_volume(self) -> float:
        return self._sound_volume

    def stop_all_sounds(self):
        """Stop every currently playing sound effect."""
        if self._web is not None:
            try:
                self._web.stop_all_sounds()
                return
            except Exception as e:
                self._web_failed(e)
        if self._is_available:
            pygame.mixer.stop()
        self._looping_channels.clear()

    # ---------- background music ----------

    def play_music(self, music_path, loops=-1, fade_ms=0):
        """
        Play a background music track (one stream at a time).

        :param music_path: path relative to the project (e.g. './audio/bgm.ogg')
        :param loops: -1 = loop forever (default), 0 = play once
        :param fade_ms: fade-in duration in milliseconds (ignored on the web)
        """
        if self._web is not None:
            absolute_path = self._resolve_path(music_path)
            if not absolute_path.exists():
                print(T.tr('api.no_sound_path', 'The sound path {} does not exist.').format(absolute_path))
                return False
            try:
                return bool(self._web.play_music(absolute_path, loops=loops,
                                                 volume=self._music_volume))
            except Exception as e:
                self._web_failed(e)
        if not self._init_mixer():
            return False

        absolute_path = self._resolve_path(music_path)
        if not absolute_path.exists():
            print(T.tr('api.no_sound_path', 'The sound path {} does not exist.').format(absolute_path))
            return False

        try:
            pygame.mixer.music.load(assets.open_stream(absolute_path))
            pygame.mixer.music.set_volume(self._music_volume)
            pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
            return True
        except Exception as e:
            print(T.tr('api.fail_to_play_music', 'Failed to play music {}: {}').format(absolute_path, e))
            return False

    def stop_music(self, fade_ms=0):
        """Stop the background music (with an optional fade-out in ms)."""
        if self._web is not None:
            try:
                self._web.stop_music()
                return
            except Exception as e:
                self._web_failed(e)
        if not self._is_available:
            return
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()

    def pause_music(self):
        if self._web is not None:
            try:
                self._web.pause_music()
                return
            except Exception as e:
                self._web_failed(e)
        if self._is_available:
            pygame.mixer.music.pause()

    def resume_music(self):
        if self._web is not None:
            try:
                self._web.resume_music()
                return
            except Exception as e:
                self._web_failed(e)
        if self._is_available:
            pygame.mixer.music.unpause()

    def is_music_playing(self) -> bool:
        if self._web is not None:
            try:
                return self._web.is_music_playing()
            except Exception as e:
                self._web_failed(e)
        if not self._is_available:
            return False
        return pygame.mixer.music.get_busy()

    def set_music_volume(self, volume):
        """Set background music volume in [0.0, 1.0]."""
        self._music_volume = max(0.0, min(1.0, float(volume)))
        if self._web is not None:
            try:
                self._web.set_music_volume(self._music_volume)
                return
            except Exception as e:
                self._web_failed(e)
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


def is_sound_playing(sound_path) -> bool:
    return audio_manager.is_sound_playing(sound_path)


def set_sound_volume(volume):
    return audio_manager.set_sound_volume(volume)


def get_sound_volume() -> float:
    return audio_manager.get_sound_volume()


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
