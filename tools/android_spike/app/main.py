"""Spike 3b: does the *engine* run on the device, not just pygame?

Spike 1 (``spike1_pygame_only.py``) answered "pygame works". This app answers the
questions that decide whether the real Android build can reuse the engine as-is:

1. does ``import pygamestudio`` work with no PySide6 anywhere (the editor's Qt
   modules are stripped from the runtime subset, see ``engine_runtime.py``)?
2. does the runtime find its project (``project.pygs`` + ``.scene``) when the app
   runs out of the APK's private folder?
3. do the scene, the object scripts and touch input work - and what is the
   relationship between the window size Android hands us and the 800x600 canvas
   the editor works in?

Everything is printed with the ``[SPIKE3B]`` prefix (``adb logcat -s python``)
and mirrored on screen, so a screenshot is enough evidence. Each step is wrapped
so a failure shows up as a red line instead of a black screen.
"""

import os
import sys
import traceback
from pathlib import Path

import pygame

PREFIX = '[SPIKE3B]'
#: On-screen report lines: [label, value, ok].
REPORT = []
#: Stop after this many frames (0 = run until the user quits). The headless
#: smoke test sets ``SPIKE_MAX_FRAMES`` so the real entry point can be executed
#: end-to-end on a developer machine instead of only on the phone.
MAX_FRAMES = int(os.environ.get('SPIKE_MAX_FRAMES') or 0)
#: Measurements shared between the hooks.
STATE = {'canvas': (800, 600), 'scale': 1.0,
         'pointer_down': 0, 'pointer_move': 0, 'pointer_up': 0,
         'finger_down': 0, 'finger_move': 0, 'finger_up': 0}


def log(message):
    print(f'{PREFIX} {message}', flush=True)


def set_line(label, value, ok=True):
    for index, (existing, _value, _ok) in enumerate(REPORT):
        if existing == label:
            REPORT[index] = [label, value, ok]
            break
    else:
        REPORT.append([label, value, ok])
    log(f'{label}: {value}')


def fail_line(label, error):
    set_line(label, f'{type(error).__name__}: {error}', False)
    log(f'{label} FAILED\n{traceback.format_exc()}')


def environment():
    """Everything that differs from a desktop run, printed once."""
    log(f'python {sys.version.split()[0]}')
    log(f'argv   {sys.argv}')
    log(f'cwd    {os.getcwd()}')
    log(f'file   {__file__}')
    log(f'frozen {getattr(sys, "frozen", False)}')
    log(f'path   {sys.path}')
    log(f'ANDROID_ARGUMENT={os.environ.get("ANDROID_ARGUMENT")!r} '
        f'ANDROID_PRIVATE={os.environ.get("ANDROID_PRIVATE")!r}')


def show_failure(lines):
    """Fallback screen for a failure that happens before the engine runs."""
    try:
        pygame.init()
        screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption('PyGS spike - engine failed')
        font = pygame.font.Font(None, 18)
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or event.type in (
                        pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN, pygame.KEYDOWN):
                    running = False
            screen.fill((40, 0, 0))
            y = 8
            for line in lines:
                for start in range(0, max(len(line), 1), 96):
                    screen.blit(font.render(line[start:start + 96], True,
                                            (255, 200, 200)), (8, y))
                    y += 16
                    if y > 576:
                        break
                if y > 576:
                    break
            screen.blit(font.render('tap to exit', True, (255, 255, 255)), (8, 582))
            pygame.display.flip()
            clock.tick(30)
    except Exception:                                  # noqa: BLE001 - last resort
        log(f'could not even show the failure screen:\n{traceback.format_exc()}')
    finally:
        pygame.quit()


def build_game(studio):
    """The real engine Game, subclassed with the spike's checks and report."""

    class SpikeGame(studio.Game):
        def __init__(self):
            super().__init__()
            self._frames = 0
            self._scene_loaded = False

        # ------------------------------------------------------- life cycle
        def on_start(self):
            log(f'project path the engine resolved: {os.environ.get("PROJECT_PATH")!r}')
            log(f'folder of this file             : {Path(__file__).parent}')
            try:
                config = studio.get_project_config()
            except Exception as error:              # noqa: BLE001 - report it
                fail_line('project', error)
            else:
                STATE['canvas'] = tuple(config.get('screen_size') or (800, 600))
                set_line('project', f'{config.get("caption")!r} '
                                    f'canvas {STATE["canvas"]}', True)
            try:
                self._basic_checks()
            except Exception as error:              # noqa: BLE001 - report it
                fail_line('pygame', error)
            self._measure()

        def on_update(self, dt):
            self._frames += 1
            try:
                studio.load_scene(studio.get_screen())
            except Exception as error:              # noqa: BLE001 - report it
                fail_line('scene', error)
            else:
                if not self._scene_loaded:
                    self._scene_loaded = True
                    objects = studio.scene_loader.get_all_objects()
                    names = ', '.join(obj.name for obj in objects)
                    scripts = sum(1 for obj in objects
                                  if getattr(obj, 'script_instance', None))
                    set_line('scene', f'{len(objects)} object(s), '
                                      f'{scripts} script(s): {names}', True)
            if MAX_FRAMES and self._frames >= MAX_FRAMES:
                log(f'SPIKE_MAX_FRAMES={MAX_FRAMES} reached, stopping')
                self._running = False
            self._overlay()

        # ----------------------------------------------------------- input
        def on_mouse_button_down(self, pos, btn, touch=0, clicks=1, window=None):
            STATE['pointer_down'] += 1
            log(f'pointer down {pos} button={btn} touch={touch}')

        def on_mouse_motion(self, pos, rel, buttons, touch=0, window=None):
            if buttons and buttons[0]:
                STATE['pointer_move'] += 1

        def on_mouse_button_up(self, pos, btn, touch=0, clicks=1, window=None):
            STATE['pointer_up'] += 1
            log(f'pointer up {pos} button={btn} touch={touch}')

        def on_finger_down(self, touch_id, finger_id, x, y, dx, dy, window=None):
            STATE['finger_down'] += 1
            log(f'finger down id={finger_id} at ({x:.3f}, {y:.3f})')

        def on_finger_motion(self, touch_id, finger_id, x, y, dx, dy, window=None):
            STATE['finger_move'] += 1

        def on_finger_up(self, touch_id, finger_id, x, y, dx, dy, window=None):
            STATE['finger_up'] += 1
            log(f'finger up id={finger_id}')

        # ---------------------------------------------------------- report
        def _basic_checks(self):
            """The three spike-1 checks, kept as a regression canary."""
            results = []
            surface = pygame.Surface((32, 32))
            surface.fill((0, 200, 120))
            path = str(Path(os.environ.get('PROJECT_PATH') or '.') / '_spike.png')
            pygame.image.save(surface, path)
            results.append(f'image {pygame.image.load(path).get_size()}')
            font = pygame.font.Font(None, 24)
            results.append(f'font {font.size("spike")}')
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            pygame.mixer.quit()
            results.append('mixer')
            set_line('pygame', ', '.join(results), True)

        def _measure(self):
            screen = self._screen
            width, height = screen.get_size()
            canvas_w, canvas_h = STATE['canvas']
            STATE['scale'] = min(width / float(canvas_w), height / float(canvas_h))
            set_line('screen', f'{width}x{height} window for a {canvas_w}x{canvas_h} '
                               f'canvas -> scale {STATE["scale"]:.2f}', True)

        def _overlay(self):
            """Draw the report on top of the frame the scene just drew."""
            screen = studio.get_screen()
            if screen is None:
                return
            size = max(14, int(16 * STATE['scale']))
            font = pygame.font.Font(None, size)
            line_height = size + 6
            panel = pygame.Surface((screen.get_width(),
                                    min(screen.get_height(),
                                        line_height * (len(REPORT) + 3))),
                                   pygame.SRCALPHA)
            panel.fill((0, 0, 0, 130))
            y = 4
            for label, value, ok in REPORT:
                color = (150, 240, 190) if ok else (255, 130, 130)
                panel.blit(font.render(f'{label}: {value}'[:150], True, color), (8, y))
                y += line_height
            counts = (f'pointer {STATE["pointer_down"]}/{STATE["pointer_move"]}/'
                      f'{STATE["pointer_up"]}  finger {STATE["finger_down"]}/'
                      f'{STATE["finger_move"]}/{STATE["finger_up"]}')
            panel.blit(font.render(counts, True, (210, 220, 255)), (8, y))
            y += line_height
            panel.blit(font.render(f'fps {self._clock.get_fps():.0f}', True,
                                   (200, 200, 210)), (8, y))
            screen.blit(panel, (0, 0))

    return SpikeGame()


def main():
    environment()

    try:
        import pygamestudio as studio
    except Exception:                                   # noqa: BLE001 - report it
        log(f'engine import FAILED\n{traceback.format_exc()}')
        show_failure(['engine import failed'] + traceback.format_exc().splitlines())
        return 3

    set_line('engine', 'imported', True)

    try:
        game = build_game(studio)
    except Exception:                                   # noqa: BLE001 - report it
        log(f'the spike game could not be built\n{traceback.format_exc()}')
        show_failure(['the spike game could not be built'] +
                     traceback.format_exc().splitlines())
        return 4

    game.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
