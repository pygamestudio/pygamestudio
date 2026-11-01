"""Check the window -> canvas pointer mapping (the maths behind touch input).

A device reports pointer positions in WINDOW pixels while every object lives in
CANVAS pixels; ``Game._to_canvas`` is the bridge. A bug here looks like "I tap
the top-left and something at the bottom-right reacts", so the maths is pinned
down by a test instead of by a phone.

    py -3.10 tools/android_spike/check_pointer_mapping.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'src'))

from pygamestudio.api.core.game import Game                      # noqa: E402

results = []


def check(name, condition, detail=''):
    results.append((name, bool(condition), detail))
    print(f'  [{"ok  " if condition else "FAIL"}] {name}{(" - " + str(detail)) if detail else ""}')


class FakeSurface:
    """Only what _to_canvas / _present ask of a surface."""

    def __init__(self, width, height):
        self._size = (width, height)

    def get_size(self):
        return self._size

    def get_width(self):
        return self._size[0]

    def get_height(self):
        return self._size[1]


def device(canvas, window, mode):
    """A Game instance wired like an Android run, without creating a window."""
    game = Game.__new__(Game)
    game._screen = FakeSurface(*canvas)
    game._display = FakeSurface(*window)          # a different object: mapping on
    game._scale_mode = mode
    game._present_window = window
    game._present_rect = Game._fit_rect(canvas, window, mode)
    return game


def main():
    canvas = (960, 540)
    window = (2400, 1080)                          # 20:9 phone

    print('1) stretch to the screen (exact_fit)')
    game = device(canvas, window, 'exact_fit')
    check('rect covers the window', tuple(game._present_rect) == (0, 0, 2400, 1080),
          tuple(game._present_rect))
    check('top-left maps to the canvas origin', game._to_canvas((0, 0)) == (0, 0),
          game._to_canvas((0, 0)))
    check('bottom-right maps to the canvas corner',
          game._to_canvas((2399, 1079)) == (959, 539), game._to_canvas((2399, 1079)))
    check('centre maps to the canvas centre',
          game._to_canvas((1200, 540)) == (480, 270), game._to_canvas((1200, 540)))
    check('x grows to the right, never mirrored',
          game._to_canvas((1800, 270))[0] > game._to_canvas((600, 270))[0])
    check('y grows downwards, never mirrored',
          game._to_canvas((1200, 810))[1] > game._to_canvas((1200, 270))[1])

    print('2) letterbox (show_all)')
    game = device(canvas, window, 'show_all')
    rect = game._present_rect
    check('canvas is centred', rect.center == (1200, 540), tuple(rect))
    check('the left bar maps outside the canvas', game._to_canvas((10, 540))[0] < 0,
          game._to_canvas((10, 540)))
    check('the canvas top-left maps from the rect corner',
          game._to_canvas((rect.left, rect.top)) == (0, 0),
          game._to_canvas((rect.left, rect.top)))

    print('3) cover (no_border)')
    game = device(canvas, window, 'no_border')
    rect = game._present_rect
    check('the canvas overflows the window', rect.width >= window[0], tuple(rect))

    print('4) integer scale')
    game = device(canvas, window, 'integer')
    rect = game._present_rect
    check('whole multiple of the canvas', rect.width % canvas[0] == 0, tuple(rect))

    print('5) desktop / no fit')
    game = device(canvas, canvas, 'none')
    check('identity when the canvas is the window', game._to_canvas((12, 34)) == (12, 34))
    game._display = game._screen
    check('identity when one surface plays both roles',
          game._to_canvas((12, 34)) == (12, 34))

    print('6) no stale cache')
    game = device(canvas, window, 'exact_fit')
    before = game._to_canvas((1200, 540))
    game._present_window = None                    # forces a recompute
    game._display = FakeSurface(1200, 540)
    game._present_rect = Game._fit_rect(canvas, (1200, 540), 'exact_fit')
    check('a resized window remaps correctly', game._to_canvas((600, 270)) == (480, 270),
          game._to_canvas((600, 270)))
    check('the old mapping was the same point of the canvas', before == (480, 270), before)

    passed = sum(1 for _name, ok, _detail in results if ok)
    failed = [name for name, ok, _detail in results if not ok]
    print(f'\n{passed}/{len(results)} check(s) passed')
    if failed:
        print('FAILED: ' + ', '.join(failed))
        print('RESULT : the pointer mapping is broken')
        return 1
    print('RESULT : window pixels map to canvas pixels in every fit mode')
    return 0


if __name__ == '__main__':
    sys.exit(main())
