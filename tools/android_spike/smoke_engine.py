"""Headless dry run of the spike project against the staged engine.

The APK is built on a machine that has no pygame, and every CI round trip costs
half an hour - so the scene, the scripts and the engine subset are checked here
first, on a developer machine:

    py -3.10 tools/android_spike/smoke_engine.py

It stages exactly the files the APK will carry (``engine_runtime.stage``), copies
the spike project next to them, then drives the real runtime with the dummy SDL
video driver: load the scene, drag the square with the pointer, tap the pad with
a finger, render one frame. Any missing engine file, broken scene key or wrong
event signature fails here instead of on the phone.
"""
import filecmp
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SPIKE_DIR.parent.parent
APP_DIR = SPIKE_DIR / 'app'
ENGINE_ROOT = REPO_ROOT / 'src' / 'pygamestudio'

#: Files/folders of the app dir that are NOT part of the staged project.
_APP_SKIPS = {'pygamestudio', '__pycache__'}


def copy_project(destination):
    """Copy the spike project (everything but the staged engine) to ``destination``."""
    for item in sorted(APP_DIR.iterdir()):
        if item.name in _APP_SKIPS:
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(item, target)


class Checks:
    def __init__(self):
        self.results = []

    def run(self, name, func):
        try:
            detail = func()
        except Exception as exc:                       # noqa: BLE001 - report it
            self.results.append((name, False, f'{type(exc).__name__}: {exc}'))
            print(f'FAIL {name}: {type(exc).__name__}: {exc}')
            traceback.print_exc()
        else:
            self.results.append((name, True, detail or 'ok'))
            print(f'ok   {name}: {detail or "ok"}')

    def failed(self):
        return [result for result in self.results if not result[1]]


def main():
    sys.dont_write_bytecode = True
    work_dir = Path(tempfile.mkdtemp(prefix='pygs-spike3b-'))
    print(f'work dir: {work_dir}')

    project_dir = work_dir / 'app'
    project_dir.mkdir()

    import engine_runtime
    summary = engine_runtime.stage(ENGINE_ROOT, project_dir)
    copy_project(project_dir)
    print(f'staged engine: {summary["files"]} file(s), {summary["bytes"] / 1024 / 1024:.1f} MB')

    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    os.environ['PROJECT_PATH'] = str(project_dir)
    os.environ.pop('__PYGAMESTUDIO_PROJECT_PATH', None)
    sys.path.insert(0, str(project_dir))

    import pygame
    import pygamestudio as studio

    checks = Checks()
    state = {}

    def engine_import():
        return f'pygamestudio from {Path(studio.__file__).parent.name}'

    def project_config():
        config = studio.get_project_config()
        assert config['asset']['current_scene'] == 'scenes/main.scene', config['asset']
        return f'caption={config["caption"]!r} canvas={tuple(config["screen_size"])}'

    def entry_point():
        """Import the app entry point: catches a syntax/name error in main.py.

        It is not executed (``__main__`` is not set), so this only proves the
        module imports and exposes what the device will call.
        """
        import importlib.util
        path = project_dir / 'main.py'
        spec = importlib.util.spec_from_file_location('pygs_spike_entry', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ('main', 'build_game', 'set_line', 'fail_line'):
            assert callable(getattr(module, name, None)), f'main.py does not define {name}()'
        return 'main(), build_game()'

    def display():
        # Game._init_game() does this on the device; the smoke test drives the
        # runtime directly, so it initialises pygame itself (the font module is
        # what the TEXT object needs here).
        pygame.init()
        screen = pygame.display.set_mode((800, 600))
        state['screen'] = screen
        return f'{screen.get_size()[0]}x{screen.get_size()[1]}'

    def scene_load():
        studio.load_scene(state['screen'])
        names = [obj.name for obj in studio.scene_loader.get_all_objects()]
        state['objects'] = names
        assert names[0] == 'Canvas', names
        for expected in ('Title', 'Hint', 'Pad', 'Box'):
            assert expected in names, f'{expected} missing from {names}'
        return ', '.join(names)

    def scripts():
        box = studio.scene_loader.find_objects(name='Box')[0]
        pad = studio.scene_loader.find_objects(name='Pad')[0]
        state['box'] = box
        state['pad'] = pad
        assert box.script_instance is not None, 'the drag script did not load'
        assert pad.script_instance is not None, 'the touch script did not load'
        return f'{type(box.script_instance).__name__}, {type(pad.script_instance).__name__}'

    def image_object():
        box = state['box']
        box._update_surface()
        width, height = box.surface.get_size()
        colors = pygame.transform.average_color(box.surface)
        assert box.surface.get_at((box.surface.get_width() // 2,
                                   box.surface.get_height() // 2))[:3] != (0, 0, 0), \
            'the image object rendered an empty surface'
        return f'{width}x{height} avg={tuple(colors[:3])}'

    def pointer_drag():
        box = state['box']
        before = (box.x, box.y)
        centre = (box.x + box.width // 2, box.y + box.height // 2)
        studio.scene_loader.handle_pointer_down(centre, 1)
        for step in range(1, 6):
            studio.scene_loader.handle_pointer_move((centre[0] + step * 20,
                                                     centre[1] + step * 10), (1, 0, 0))
        studio.scene_loader.handle_pointer_up((centre[0] + 100, centre[1] + 50), 1)
        dragged = (box.x, box.y)
        assert dragged != before, 'the drag did not move the object'
        inner = type(box.script_instance).__name__
        assert inner == 'DragBox'
        return f'{before} -> {dragged}'

    def finger_tap():
        pad = state['pad']
        centre = (pad.x + pad.width // 2, pad.y + pad.height // 2)
        studio.scene_loader.handle_finger_down(0, centre)
        for step in range(1, 4):
            studio.scene_loader.handle_finger_move(0, (centre[0] + step * 8, centre[1]))
        studio.scene_loader.handle_finger_up(0, (centre[0] + 24, centre[1]))
        moves = getattr(pad.script_instance, 'moves', 0)
        assert moves >= 3, f'the touch script saw {moves} move(s)'
        return f'{moves} move(s) reached the script'

    def render_frame():
        studio.scene_loader._update_scene(state['screen'])
        return f'{state["screen"].get_size()}'

    def android_imports():
        """Import the engine with the pygame modules Android lacks blocked.
        p4a's pygame build has no ``_freetype`` (its recipe leaves the optional C
        extensions out), but every desktop pygame has it - so a stray
        ``import pygame.freetype`` passes here and only fails on the phone. This
        blocks those modules in a fresh interpreter and imports the runtime the
        way the device does.
        """
        import subprocess
        blocked = list(engine_runtime.ANDROID_MISSING_PYGAME_MODULES)
        code = f'''
import sys

BLOCKED = {blocked!r}


class Blocker:
    """Refuse the pygame C extensions the p4a build does not contain."""

    def find_spec(self, name, path=None, target=None):
        if name in BLOCKED:
            raise ModuleNotFoundError(f"not in the Android build: {{name}}", name=name)
        return None


sys.meta_path.insert(0, Blocker())
sys.path.insert(0, {str(project_dir)!r})
import pygame
pygame.display.init()
pygame.font.init()
import pygamestudio
from pygamestudio.api.core import game, scene, audio, physics, window
from pygamestudio.game.object import (base, button, canvas, ellipse, image, line,
                                      particle, rect, text, text_input, tile_map)
print('ok')
'''
        environment = dict(os.environ, SDL_VIDEODRIVER='dummy',
                           SDL_AUDIODRIVER='dummy')
        process = subprocess.run([sys.executable, '-c', code], cwd=str(project_dir),
                                 env=environment, capture_output=True, text=True)
        if process.returncode != 0 or 'ok' not in process.stdout:
            raise AssertionError(f'importing the engine without {blocked} failed\n'
                                 f'{process.stdout}\n{process.stderr}')
        return f'{len(blocked)} module(s) blocked'

    def scaled_display():
        """The device display path: canvas surface + scaled present rectangle.

        On a device the engine keeps the canvas as the drawing surface and
        presents it scaled into the real window, so ``get_screen()`` stays
        800x600 (editor coordinates) whatever the screen is. ``_fit_rect()`` is
        the pure function that decides where the canvas lands - it is asserted
        here for every fit mode against an 800x600 canvas on a 1920x1038 screen.
        """
        import subprocess
        code = f'''
import sys
sys.path.insert(0, {str(project_dir)!r})
import pygame
pygame.init()
import pygamestudio as studio

CASES = {{
    'show_all': ((268, 0, 1384, 1038), 'letterboxed, whole canvas visible'),
    'no_border': ((0, -201, 1920, 1440), 'filled, overflow cropped'),
    'fixed_width': ((0, -201, 1920, 1440), 'width fills'),
    'fixed_height': ((268, 0, 1384, 1038), 'height fills'),
    'exact_fit': ((0, 0, 1920, 1038), 'stretched'),
    'integer': ((560, 219, 800, 600), '1x, crisp pixels'),
    'none': ((0, 0, 800, 600), '1:1 in the corner'),
}}
for mode, (expected, why) in CASES.items():
    rect = studio.Game._fit_rect((800, 600), (1920, 1038), mode)
    got = (rect.left, rect.top, rect.width, rect.height)
    assert got == expected, f'{{mode}}: got {{got}}, expected {{expected}} ({{why}})'
print('fit modes', len(CASES))

game = studio.Game()
game._create_display((800, 600), {{'screen_scale_mode': 'show_all'}})
assert game._screen.get_size() == (800, 600), game._screen.get_size()
assert game._screen is not game._display, 'the canvas must be its own surface'
assert game._present_rect is not None, 'no present rectangle'
# a window pixel in the middle of the canvas maps back to the canvas middle
centre = (game._present_rect.centerx, game._present_rect.centery)
assert game._to_canvas(centre) == (400, 300), game._to_canvas(centre)
print('device path', game._screen.get_size(), pygame.display.get_window_size(),
      tuple(game._present_rect))

plain = studio.Game()
plain._create_display((800, 600), {{'screen_scaled': False}})
assert plain._screen is plain._display, 'opting out must keep one surface'
print('opt out', plain._screen.get_size())
'''
        environment = dict(os.environ, SDL_VIDEODRIVER='dummy',
                           SDL_AUDIODRIVER='dummy',
                           ANDROID_ARGUMENT='/data/user/0/pygs/files/app',
                           ANDROID_PRIVATE='/data/user/0/pygs/files')
        process = subprocess.run([sys.executable, '-c', code], cwd=str(project_dir),
                                 env=environment, capture_output=True, text=True)
        if process.returncode != 0:
            raise AssertionError(f'the scaled display path failed\n{process.stdout}\n'
                                 f'{process.stderr}')
        return ' '.join(process.stdout.split())

    def present_path():
        """Drive _present() on a fake window: the fit maths AND the pixels.

        Runs last because it replaces the display mode. Checks the two device
        paths that the frame rate depends on: the scaled blit (letterbox bars
        stay black, the canvas lands inside its rect) and the 1:1 shortcut.
        """
        game = studio.Game()
        display = pygame.display.set_mode((400, 300))
        display.fill((0, 0, 0))
        canvas = pygame.Surface((100, 50))
        canvas.fill((10, 200, 30))
        game._screen = canvas
        game._display = display
        game._scale_mode = 'show_all'
        game._smooth_scale = False
        game._present_window = None
        game._update_present_rect()
        game._present()

        rect = game._present_rect
        assert rect.size == (400, 200), f'show_all rect {rect}'
        assert display.get_at((rect.centerx, rect.centery))[:3] == (10, 200, 30), \
            'the canvas was not drawn inside its rect'
        assert display.get_at((5, 5))[:3] == (0, 0, 0), 'the letterbox bar is not black'
        assert game._to_canvas(rect.center) == (50, 25), game._to_canvas(rect.center)

        display.fill((0, 0, 0))
        game._scale_mode = 'none'
        game._present_window = None
        game._update_present_rect()
        game._present()
        assert display.get_at((10, 10))[:3] == (10, 200, 30), 'the 1:1 path did not draw'
        assert display.get_at((150, 60))[:3] == (0, 0, 0), 'the 1:1 path drew too much'
        return f'show_all {rect.size} at {rect.topleft}, canvas back to 1:1'

    def project_imports():
        """Reject imports the Android runtime cannot satisfy (the phone's black screen)."""
        import project_scan
        summary = project_scan.scan(project_dir)
        if summary['missing'] or summary['blocked']:
            detail = '; '.join(f'{module} ({relative}:{line})'
                               for module, relative, line
                               in summary['blocked'] + summary['missing'])
            raise AssertionError(detail)
        return f'{summary["files"]} file(s): {", ".join(summary["imports"])}'

    def run_entry_point():
        """Run the real ``main.py`` the way the device does - as the script.

        p4a executes the entrypoint with ``PyRun_SimpleFile``, so ``main.py`` is
        the outermost Python frame and ``Game._init_game()`` resolves the project
        folder from it. ``python main.py`` reproduces exactly that, with the
        dummy video driver and a frame limit so the loop terminates.
        """
        import subprocess
        environment = dict(os.environ)
        environment.update({'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
                            'SPIKE_MAX_FRAMES': '3', 'PYTHONPATH': str(project_dir)})
        environment.pop('PROJECT_PATH', None)
        process = subprocess.run([sys.executable, 'main.py'], cwd=str(project_dir),
                                 env=environment, capture_output=True, text=True,
                                 timeout=120)
        output = process.stdout + process.stderr
        if process.returncode != 0:
            raise AssertionError(f'main.py exited {process.returncode}\n{output[-1500:]}')
        if 'FAILED' in output:
            raise AssertionError(f'a spike step failed\n{output[-1500:]}')
        for needle in ('project path the engine resolved', 'scene: ',
                       'screen: '):
            if needle not in output:
                raise AssertionError(f'no "{needle}" in the output\n{output[-1500:]}')
        lines = [line for line in output.splitlines() if '[SPIKE3B]' in line
                 and ': ' in line]
        return ' | '.join(line.split('[SPIKE3B] ', 1)[1] for line in lines[:3])

    checks.run('engine import', engine_import)
    checks.run('project config', project_config)
    checks.run('entry point', entry_point)
    checks.run('display (dummy)', display)
    checks.run('scene load', scene_load)
    checks.run('behavior scripts', scripts)
    checks.run('image object', image_object)
    checks.run('pointer drag', pointer_drag)
    checks.run('finger tap', finger_tap)
    checks.run('render frame', render_frame)
    checks.run('imports without Android-missing pygame modules', android_imports)
    checks.run('scaled display', scaled_display)
    checks.run('project imports', project_imports)
    checks.run('entry point on the real path', run_entry_point)
    checks.run('present path', present_path)

    same_files = None
    if (APP_DIR / 'pygamestudio').exists():
        comparison = filecmp.dircmp(str(APP_DIR / 'pygamestudio'),
                                    str(project_dir / 'pygamestudio'))

        def diff(dircmp, found):
            for name in dircmp.diff_files + dircmp.left_only + dircmp.right_only:
                found.append(name)
            for child in dircmp.subdirs.values():
                diff(child, found)
            return found

        same_files = diff(comparison, [])
        if same_files:
            print(f'note: app/pygamestudio is stale ({len(same_files)} difference(s)), '
                  f'it is regenerated on every build')

    failed = checks.failed()
    print()
    print(f'{len(checks.results) - len(failed)}/{len(checks.results)} check(s) passed')
    if failed:
        for name, _ok, detail in failed:
            print(f'  FAIL {name}: {detail}')
        return 1
    print('RESULT : the staged engine runs the spike project headless')
    shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
