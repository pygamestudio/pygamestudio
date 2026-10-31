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
import time
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
            self._panel = None
            self._panel_time = 0.0
            self._panel_count = 0
            self._draw_total = 0.0

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
            try:
                self._perf_probe()
            except Exception as error:              # noqa: BLE001 - report it
                fail_line('perf', error)

        def on_update(self, dt):
            self._frames += 1
            started = time.perf_counter()
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
            self._draw_total += time.perf_counter() - started
            if self._frames % 60 == 0:
                # Where the frame time goes: the scene draw is measured here,
                # everything else (events + present + flip + the 60 Hz cap) is
                # the remainder of the real frame time.
                draw_ms = self._draw_total / 60 * 1000
                fps = self._clock.get_fps()
                frame_ms = 1000.0 / fps if fps else 0.0
                set_line('frame', f'scene draw {draw_ms:.1f} ms, other '
                                  f'{max(0.0, frame_ms - draw_ms):.1f} ms, fps {fps:.0f}',
                         frame_ms == 0.0 or draw_ms < frame_ms)
                self._draw_total = 0.0
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
            """Report the canvas, the real window and where the canvas landed.

            ``surface`` is what the scene draws on (the editor's canvas size),
            ``window`` the device screen, and ``present`` the rectangle the
            canvas is scaled into - that is the one that proves the fit mode
            worked: for an 800x600 canvas on a 1920x1038 screen ``show_all``
            gives 1384x1038 centred, with 268 px bars left and right.
            """
            screen = self._screen
            width, height = screen.get_size()
            canvas_w, canvas_h = STATE['canvas']
            display = pygame.display.get_surface()
            window = display.get_size() if display is not None else (0, 0)
            try:
                # get_window_size() reports the SDL window, which on a device can
                # differ from the surface we blit into (density) - both numbers
                # are printed so the pair is never mistaken for a mismatch.
                api_window = pygame.display.get_window_size()
            except pygame.error:                        # older pygame / no window
                api_window = (0, 0)
            rect = getattr(self, '_present_rect', None)
            if rect is not None and rect.width:
                STATE['scale'] = rect.width / float(canvas_w)
                present = (f'{rect.width}x{rect.height} at ({rect.left}, {rect.top}) '
                           f'= {STATE["scale"]:.2f}x')
            else:
                STATE['scale'] = 1.0
                present = 'not scaled'
            set_line('screen', f'surface {width}x{height}, window {window[0]}x{window[1]} '
                               f'(sdl {api_window[0]}x{api_window[1]}), '
                               f'mode {getattr(self, "_scale_mode", "?")}, present {present}',
                     True)
            STATE['window'] = window

        def _perf_probe(self):
            """How fast can this device present a frame, with each scale filter?

            One frame costs the scene draw plus ``present`` (scale the canvas
            into the window) plus the flip. This probe measures present+flip on
            an empty canvas for BOTH filters, because the first device run
            showed the difference is enormous: bilinear (smoothscale) took
            ~140 ms/frame there (6 fps on its own) while nearest is a memcpy-ish
            pass. Knowing both numbers decides what the default must be.
            """
            screen = studio.get_screen()
            frames = 12
            original = self._smooth_scale
            results = {}
            for smooth in (False, True):
                self._smooth_scale = smooth
                self._present_surface = None
                start = time.perf_counter()
                for index in range(frames):
                    screen.fill((20, 20, 24) if index % 2 else (24, 22, 28))
                    self._present()
                    pygame.display.flip()
                results['smooth' if smooth else 'nearest'] = (time.perf_counter() - start) * 1000 / frames
            self._smooth_scale = original
            self._present_surface = None
            set_line('perf', f'present: nearest {results["nearest"]:.1f} ms, '
                             f'smooth {results["smooth"]:.1f} ms '
                             f'(canvas {screen.get_size()[0]}x{screen.get_size()[1]})',
                     results['nearest'] <= 20)


        def _overlay(self):
            """Draw the report on top of the frame the scene just drew.

            The panel is rebuilt once a second, not every frame: rendering ~8
            text lines per frame costs more than the whole 800x600 scene and
            would make the fps line measure the overlay instead of the engine.
            """
            screen = studio.get_screen()
            if screen is None:
                return
            now = time.perf_counter()
            if self._panel is None or now - self._panel_time > 1.0:
                self._panel_time = now
                self._panel = self._build_panel(screen)
            if self._panel is not None:
                screen.blit(self._panel, (0, 0))

        def _build_panel(self, screen):
            # The panel is drawn in CANVAS pixels and scaled up with the rest of
            # the frame, so its size must not follow the presentation scale.
            canvas_h = STATE['canvas'][1]
            size = max(11, int(canvas_h / 45))
            font = pygame.font.Font(None, size)
            line_height = size + 4
            lines = []
            for label, value, ok in REPORT:
                lines.append((f'{label}: {value}'[:150],
                              (150, 240, 190) if ok else (255, 130, 130)))
            lines.append((f'pointer {STATE["pointer_down"]}/{STATE["pointer_move"]}/'
                          f'{STATE["pointer_up"]}  finger {STATE["finger_down"]}/'
                          f'{STATE["finger_move"]}/{STATE["finger_up"]}',
                          (210, 220, 255)))
            lines.append((f'fps {self._clock.get_fps():.0f}', (200, 200, 210)))
            panel = pygame.Surface((screen.get_width(),
                                    min(screen.get_height(), line_height * len(lines) + 8)),
                                   pygame.SRCALPHA)
            panel.fill((0, 0, 0, 130))
            y = 4
            for text, color in lines:
                panel.blit(font.render(text, True, color), (8, y))
                y += line_height
            self._panel_count += 1
            if self._panel_count == 1 or self._panel_count % 5 == 0:
                log(' | '.join(text for text, _color in lines))
            return panel

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
