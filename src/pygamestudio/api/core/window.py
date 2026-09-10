"""
Window manager API for generated games.

Provides a small, safe interface to the pygame window (title, icon, size,
position, fullscreen, cursor, screen saver):

    import pygamestudio as studio

    studio.set_window_title('My Game')
    studio.set_window_icon('./images/icon.png')
    studio.set_window_size((1280, 720))
    studio.center_window()
    studio.toggle_fullscreen()
    studio.set_mouse_cursor_visible(False)

Image paths are resolved relative to the project path (absolute paths are used
as-is). Every call degrades to a no-op with a printed warning when the display
is not available (for example before the game window exists), so scripts can
call them freely without extra guards.
"""

import os
import pygame
from pathlib import Path
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.path import RES_PATH

__all__ = [
    'WindowManager', 'window_manager',
    'set_window_title', 'get_window_title',
    'set_window_icon',
    'get_window_size', 'set_window_size',
    'get_window_position', 'set_window_position', 'center_window',
    'get_desktop_size',
    'set_fullscreen', 'is_fullscreen', 'toggle_fullscreen', 'minimize_window',
    'set_mouse_cursor_visible', 'is_mouse_cursor_visible',
    'set_allow_screensaver', 'is_allow_screensaver',
]


class WindowManager:
    """Thin wrapper around pygame's window / display functions.

    Keeps a small icon cache and re-publishes the display surface to
    ``studio.get_screen()`` whenever the window is re-created by
    ``set_window_size()``, so the game keeps rendering onto the current
    surface.
    """

    def __init__(self):
        self._icon_cache = {}            # absolute path -> Surface
        self._default_icon_surface = None

    # ---------- internals ----------

    @staticmethod
    def _warn(message_key, default_message, *args):
        print(T.tr(message_key, default_message).format(*args))

    def _resolve_path(self, image_path) -> Path:
        """Project-relative image paths are resolved against PROJECT_PATH."""
        path = Path(image_path)
        if path.is_absolute():
            return path
        return Path(os.environ.get('PROJECT_PATH', '')) / path

    def _load_icon(self, icon_path):
        """Load (and cache) an icon image. Returns None when it cannot be used."""
        absolute_path = self._resolve_path(icon_path)
        if not absolute_path.exists():
            self._warn('api.no_icon_path', 'The icon path {} does not exist.', absolute_path)
            return None
        key = absolute_path.as_posix()
        if key not in self._icon_cache:
            try:
                self._icon_cache[key] = pygame.image.load(str(absolute_path))
            except Exception as e:
                self._warn('api.fail_to_load_icon', 'Failed to load the icon {}: {}', absolute_path, e)
                return None
        return self._icon_cache[key]

    def _default_icon(self):
        """The engine's own icon, used when set_window_icon() gets no path."""
        if self._default_icon_surface is None:
            default_path = RES_PATH / 'images' / 'logo.png'
            if not default_path.exists():
                return None
            try:
                self._default_icon_surface = pygame.image.load(str(default_path))
            except pygame.error:
                return None
        return self._default_icon_surface

    @staticmethod
    def _window_flags() -> int:
        """Display flags the current window uses (so resizing keeps fullscreen)."""
        try:
            return pygame.FULLSCREEN if pygame.display.is_fullscreen() else 0
        except pygame.error:
            return 0

    @staticmethod
    def _publish_screen(surface):
        """Keep studio.get_screen() pointing at the surface in use.

        Re-creating the display hands out a brand new surface; the game loop
        reads it through ``studio.get_screen()`` every frame, so the running
        Game instance has to point at the new one.
        """
        from pygamestudio.api.core import game as game_module
        instance = getattr(game_module.Game, '_instance', None)
        if instance is not None:
            instance._screen = surface

    # ---------- title ----------

    def set_window_title(self, title):
        """Set the window (and taskbar) title."""
        try:
            pygame.display.set_caption(str(title))
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    def get_window_title(self) -> str:
        """The current window title ('' when the display is unavailable)."""
        try:
            return pygame.display.get_caption()[0]
        except pygame.error:
            return ''

    # ---------- icon ----------

    def set_window_icon(self, icon_path='') -> bool:
        """Set the window icon shown in the title bar / taskbar.

        :param icon_path: an image path (project-relative or absolute), a
                          ready pygame.Surface, or '' to restore the engine's
                          default icon.
        :return: True when the icon was applied
        """
        if isinstance(icon_path, pygame.Surface):
            surface = icon_path
        elif not icon_path:
            surface = self._default_icon()
            if surface is None:
                return False
        else:
            surface = self._load_icon(icon_path)
            if surface is None:
                return False

        try:
            pygame.display.set_icon(surface)
            return True
        except pygame.error as e:
            self._warn('api.fail_to_set_icon', 'Failed to set the window icon: {}', e)
            return False

    # ---------- size / position ----------

    def get_window_size(self) -> tuple:
        """The current window size as a (width, height) tuple."""
        try:
            return tuple(pygame.display.get_window_size())
        except pygame.error:
            surface = pygame.display.get_surface()
            return surface.get_size() if surface is not None else (0, 0)

    def set_window_size(self, size):
        """Resize the window to (width, height).

        The display surface is re-created, so ``studio.get_screen()`` starts
        returning the new surface right away. The scene itself is still drawn
        from the canvas origin (the extra area stays empty).
        """
        try:
            width = max(1, int(size[0]))
            height = max(1, int(size[1]))
        except (TypeError, IndexError, ValueError):
            self._warn('api.window_error', 'Window operation failed: {}', size)
            return None

        try:
            surface = pygame.display.set_mode((width, height), self._window_flags())
            self._publish_screen(surface)
            return surface
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)
            return None

    def get_window_position(self) -> tuple:
        """The window's top-left position on the desktop as (x, y)."""
        try:
            return tuple(pygame.display.get_window_position())
        except pygame.error:
            return (0, 0)

    def set_window_position(self, position):
        """Move the window so its top-left corner sits at position (x, y)."""
        try:
            pygame.display.set_window_position((int(position[0]), int(position[1])))
        except (pygame.error, TypeError, IndexError, ValueError) as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    def get_desktop_size(self) -> tuple:
        """The primary monitor size as a (width, height) tuple."""
        try:
            sizes = pygame.display.get_desktop_sizes()
        except pygame.error:
            return (0, 0)
        return tuple(sizes[0]) if sizes else (0, 0)

    def center_window(self):
        """Move the window to the centre of the primary monitor."""
        desktop_width, desktop_height = self.get_desktop_size()
        window_width, window_height = self.get_window_size()
        if not desktop_width or not desktop_height:
            return
        self.set_window_position(((desktop_width - window_width) // 2,
                                  (desktop_height - window_height) // 2))

    # ---------- fullscreen / window state ----------

    def set_fullscreen(self, enabled):
        """Switch between fullscreen and windowed mode (no-op when unchanged)."""
        try:
            if bool(pygame.display.is_fullscreen()) != bool(enabled):
                pygame.display.toggle_fullscreen()
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    def is_fullscreen(self) -> bool:
        """True while the window is fullscreen."""
        try:
            return bool(pygame.display.is_fullscreen())
        except pygame.error:
            return False

    def toggle_fullscreen(self):
        """Flip between fullscreen and windowed mode."""
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    def minimize_window(self):
        """Minimise (iconify) the window."""
        try:
            pygame.display.iconify()
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    # ---------- mouse cursor ----------

    def set_mouse_cursor_visible(self, visible):
        """Show or hide the mouse cursor inside the window."""
        try:
            pygame.mouse.set_visible(bool(visible))
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    def is_mouse_cursor_visible(self) -> bool:
        """True while the mouse cursor is shown inside the window."""
        try:
            return bool(pygame.mouse.get_visible())
        except pygame.error:
            return False

    # ---------- system ----------

    def set_allow_screensaver(self, enabled):
        """Allow or block the operating system's screen saver while playing."""
        try:
            pygame.display.set_allow_screensaver(bool(enabled))
        except pygame.error as e:
            self._warn('api.window_error', 'Window operation failed: {}', e)

    def is_allow_screensaver(self) -> bool:
        """True while the OS screen saver is allowed."""
        try:
            return bool(pygame.display.get_allow_screensaver())
        except pygame.error:
            return False


# Module-level singleton, mirroring scene_loader / audio_manager.
window_manager = WindowManager()


def set_window_title(title):
    return window_manager.set_window_title(title)


def get_window_title() -> str:
    return window_manager.get_window_title()


def set_window_icon(icon_path='') -> bool:
    return window_manager.set_window_icon(icon_path)


def get_window_size() -> tuple:
    return window_manager.get_window_size()


def set_window_size(size):
    return window_manager.set_window_size(size)


def get_window_position() -> tuple:
    return window_manager.get_window_position()


def set_window_position(position):
    return window_manager.set_window_position(position)


def center_window():
    return window_manager.center_window()


def get_desktop_size() -> tuple:
    return window_manager.get_desktop_size()


def set_fullscreen(enabled):
    return window_manager.set_fullscreen(enabled)


def is_fullscreen() -> bool:
    return window_manager.is_fullscreen()


def toggle_fullscreen():
    return window_manager.toggle_fullscreen()


def minimize_window():
    return window_manager.minimize_window()


def set_mouse_cursor_visible(visible):
    return window_manager.set_mouse_cursor_visible(visible)


def is_mouse_cursor_visible() -> bool:
    return window_manager.is_mouse_cursor_visible()


def set_allow_screensaver(enabled):
    return window_manager.set_allow_screensaver(enabled)


def is_allow_screensaver() -> bool:
    return window_manager.is_allow_screensaver()
