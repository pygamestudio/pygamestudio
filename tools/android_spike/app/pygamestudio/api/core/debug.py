"""Debug info overlay for the running game.

A game script turns it on with ``studio.show_debug_info()`` (and off with
``studio.hide_debug_info()``): while enabled, the main loop draws a small
panel in the bottom-left corner of the game window with the measured frame
rate, the frame time and the number of objects in the current scene. The
panel looks the same when the game runs from the editor, as a built desktop
app or in the web build.
"""
import sys

import pygame

__all__ = ['show_debug_info', 'hide_debug_info', 'is_debug_info_enabled']

#: Seconds between two text re-renders; the panel itself is blitted every
#: frame (a cached surface, nearly free).
_REFRESH_INTERVAL = 0.25

#: Whether the game loop draws the panel. Module level (not bound to the Game
#: instance) so a script can call show_debug_info() before run() AND switch it
#: while the game is running.
_enabled = False

#: Smoothed frame duration (seconds, exponential moving average) - the raw
#: per-frame delta jumps around too much to read.
_smooth_delta = None
#: Seconds since the panel text was last re-rendered.
_text_age = _REFRESH_INTERVAL
#: Cached panel surface (background + text of the last re-render).
_panel = None
#: Font of the panel text, created on first use.
_font = None
#: The numbers currently on the panel (read by tests and tools).
_stats = {'fps': 0.0, 'frame_ms': 0.0, 'objects': 0}


def show_debug_info() -> None:
    """开启调试信息：运行游戏时，窗口左下角会显示帧率等性能数据。
    Show the debug info: while enabled, running the game shows the frame
    rate and other performance data in the window's bottom-left corner.
    """
    global _enabled
    _enabled = True


def hide_debug_info() -> None:
    """关闭调试信息（隐藏窗口左下角的性能面板）。
    Hide the debug info: the performance panel in the bottom-left corner
    disappears again.
    """
    global _enabled
    _enabled = False


def is_debug_info_enabled() -> bool:
    """调试信息当前是否已开启。True while the debug info panel is shown."""
    return _enabled


def _draw_debug_info(screen, delta_time: float) -> None:
    """Draw the panel while enabled. Called by the game loop, not by scripts.

    Any rendering failure (no font data, ...) turns the overlay off with a
    single stderr note - a debug tool must never take the game down.
    """
    global _smooth_delta, _text_age, _panel, _font
    if not _enabled or screen is None:
        return
    try:
        delta_time = max(float(delta_time), 1e-6)
        if _smooth_delta is None:
            _smooth_delta = delta_time
        else:
            _smooth_delta += (delta_time - _smooth_delta) * 0.1

        _text_age += delta_time
        if _panel is None or _text_age >= _REFRESH_INTERVAL:
            _text_age = 0.0
            from pygamestudio.api.core.scene import scene_loader
            _stats['fps'] = 1.0 / _smooth_delta
            _stats['frame_ms'] = _smooth_delta * 1000.0
            _stats['objects'] = len(scene_loader.get_all_objects())
            text = 'FPS {}  |  {:.1f} ms  |  objects {}'.format(
                round(_stats['fps']), _stats['frame_ms'], _stats['objects'])
            if _font is None:
                _font = pygame.font.Font(None, 16)
            text_surface = _font.render(text, True, (255, 255, 255))
            _panel = pygame.Surface((text_surface.get_width() + 12,
                                     text_surface.get_height() + 8),
                                    pygame.SRCALPHA)
            _panel.fill((0, 0, 0, 140))
            _panel.blit(text_surface, (6, 4))

        screen.blit(_panel, (8, max(screen.get_height() - _panel.get_height() - 8, 0)))
    except Exception as error:  # a debug aid must never crash the game
        hide_debug_info()
        print('[pygamestudio] debug info disabled: {}: {}'.format(
            type(error).__name__, error), file=sys.stderr)
