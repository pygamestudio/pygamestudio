import os
import sys
import pygame
import inspect
from pathlib import Path
from pygamestudio.api.core.scene import scene_loader
from pygamestudio.api.config.project import get_project_config


class Game:
    """Runtime game class used by every built/exported project.

    Subclass it in the project's main.py and override the on_* hooks. run()
    starts the main loop: it auto-detects the project root from the caller's
    file, initializes pygame, dispatches every pygame event to the matching
    on_* hook, then calls on_update(delta_time) and flips the display.
    """
    _instance = None

    def __init__(self):
        self._fps = 60
        self._clock = None
        self._screen = None
        self._project_path = ""
        self._running = False
        # Frame statistics, kept up to date by run() (see get_delta_time(),
        # get_elapsed_time() and get_frame_count()).
        self._delta_time = 0.0
        self._elapsed_time = 0.0
        self._frame_count = 0

    def _init_game(self):
        """Set up pygame and resolve the project root.

        In a frozen build (PyInstaller) the project files are bundled next to
        the executable, so the bundle folder is the project root. Otherwise the
        project path is derived from the stack frame of whoever created the
        Game (the project's main.py), so no path config is required.
        """
        if getattr(sys, 'frozen', False):
            self._project_path = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)).resolve().as_posix()
        else:
            caller_frame = inspect.stack()[-1]
            caller_file_path = caller_frame.filename
            self._project_path = Path(caller_file_path).parent.resolve().as_posix()
        # A game process must never inherit the EDITOR's project variable. The
        # editor exports __PYGAMESTUDIO_PROJECT_PATH and every process it starts
        # (the asset panel's "open externally", a terminal it opened, ...) gets
        # a copy. get_project_path() prefers that variable over PROJECT_PATH, so
        # a protected build launched this way would read its assets - and look
        # for resources.cache - in the SOURCE project and die with "this build
        # contains protected assets but no resources.cache was found next to
        # the game". A running game always knows its own root, so the editor
        # variable is dropped here (it is set again by the editor itself, per
        # process, and never crosses into a game).
        os.environ.pop('__PYGAMESTUDIO_PROJECT_PATH', None)
        os.environ['PROJECT_PATH'] = self._project_path
        project_config = get_project_config()

        pygame.init()
        pygame.display.set_caption(project_config['caption'])
        self._screen = pygame.display.set_mode(project_config['screen_size'])
        self._clock = pygame.time.Clock()

    def run(self):
        """Start the game loop. Blocks until the window is closed."""
        Game._instance = self
        self._init_game()
        self._running = True

        self.on_start()

        while self._running:
            # --- 1. Dispatch all pending pygame events to the on_* hooks. ---
            for event in pygame.event.get():
                # ---------- Quit Event ----------
                if event.type == pygame.QUIT:
                    self._running = False

                # ---------- Keyboard Event ----------
                elif event.type == pygame.KEYDOWN:
                    # A focused input box consumes the key (typing control keys).
                    if not scene_loader.handle_key_down(event.key, event.mod,
                                                        getattr(event, 'unicode', '')):
                        self.on_key_down(event.key, event.mod, getattr(event, 'unicode', ''), event.scancode, getattr(event, 'window', None))
                elif event.type == pygame.KEYUP:
                    self.on_key_up(event.key, event.mod, getattr(event, 'unicode', ''), event.scancode, getattr(event, 'window', None))

                # ---------- Mouse Event ----------
                elif event.type == pygame.MOUSEMOTION:
                    scene_loader.handle_pointer_move(event.pos, event.buttons)
                    self.on_mouse_motion(event.pos, event.rel, event.buttons, getattr(event, 'touch', 0), getattr(event, 'window', None))
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Clicking an input box focuses it (so subsequent keys type
                    # into it); clicking elsewhere blurs it. Sliders start a
                    # drag when clicked.
                    scene_loader.handle_pointer_down(event.pos, event.button)
                    self.on_mouse_button_down(event.pos, event.button, getattr(event, 'touch', 0), getattr(event, "clicks", 1), getattr(event, 'window', None))
                elif event.type == pygame.MOUSEBUTTONUP:
                    scene_loader.handle_pointer_up(event.pos, event.button,
                                                   getattr(event, 'clicks', 1))
                    self.on_mouse_button_up(event.pos, event.button, getattr(event, 'touch', 0), getattr(event, "clicks", 1), getattr(event, 'window', None))
                elif event.type == pygame.MOUSEWHEEL:
                    self.on_mouse_wheel(event.flipped, event.x, event.y, getattr(event, 'touch', 0), event.precise_x, event.precise_y, getattr(event, 'window', None))

                # ---------- Joystick Event ----------
                elif event.type == pygame.JOYAXISMOTION:
                    self.on_joy_axis_motion(event.instance_id, event.axis, event.value)
                elif event.type == pygame.JOYBALLMOTION:
                    self.on_joy_ball_motion(event.instance_id, event.ball, event.rel)
                elif event.type == pygame.JOYHATMOTION:
                    self.on_joy_hat_motion(event.instance_id, event.hat, event.value)
                elif event.type == pygame.JOYBUTTONDOWN:
                    self.on_joy_button_down(event.instance_id, event.button)
                elif event.type == pygame.JOYBUTTONUP:
                    self.on_joy_button_up(event.instance_id, event.button)
                elif event.type == pygame.JOYDEVICEADDED:
                    self.on_joy_device_added(event.device_index)
                elif event.type == pygame.JOYDEVICEREMOVED:
                    self.on_joy_device_removed(event.instance_id)
                elif event.type == pygame.CONTROLLERDEVICEADDED:
                    self.on_controller_added(event.device_index)
                elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                    self.on_controller_removed(event.instance_id)
                elif event.type == pygame.CONTROLLERDEVICEREMAPPED:
                    self.on_controller_remapped(event.instance_id)

                # ---------- Window Event ----------
                elif event.type == pygame.WINDOWSHOWN:
                    self.on_window_shown(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWHIDDEN:
                    self.on_window_hidden(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWEXPOSED:
                    self.on_window_exposed(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWMOVED:
                    self.on_window_moved(event.x, event.y, getattr(event, 'window', None))
                elif event.type == pygame.WINDOWSIZECHANGED:
                    self.on_window_size_changed(event.x, event.y, getattr(event, 'window', None))
                elif event.type == pygame.WINDOWRESIZED:
                    self.on_window_resized(event.x, event.y, getattr(event, 'window', None))
                elif event.type == pygame.WINDOWMINIMIZED:
                    self.on_window_minimized(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWMAXIMIZED:
                    self.on_window_maximized(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWRESTORED:
                    self.on_window_restored(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWENTER:
                    self.on_window_enter(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWLEAVE:
                    self.on_window_leave(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWFOCUSGAINED:
                    self.on_window_focus_gained(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWFOCUSLOST:
                    self.on_window_focus_lost(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWCLOSE:
                    self.on_window_close(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWTAKEFOCUS:
                    self.on_window_take_focus(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWHITTEST:
                    self.on_window_hit_test(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWICCPROFCHANGED:
                    self.on_window_icc_changed(getattr(event, 'window', None))
                elif event.type == pygame.WINDOWDISPLAYCHANGED:
                    self.on_window_display_changed(event.display_index, getattr(event, 'window', None))

                # ---------- Text Input Event ----------
                elif event.type == pygame.TEXTEDITING:
                    self.on_text_editing(event.text, event.start, event.length, getattr(event, 'window', None))
                elif event.type == pygame.TEXTINPUT:
                    # Focused input boxes receive the typed text first.
                    if not scene_loader.handle_text_input(event.text):
                        self.on_text_input(event.text, getattr(event, 'window', None))

                # ---------- Drop Event ----------
                elif event.type == pygame.DROPBEGIN:
                    self.on_drop_begin(getattr(event, 'window', None))
                elif event.type == pygame.DROPFILE:
                    self.on_drop_file(event.file, getattr(event, 'window', None))
                elif event.type == pygame.DROPTEXT:
                    self.on_drop_text(event.text, getattr(event, 'window', None))
                elif event.type == pygame.DROPCOMPLETE:
                    self.on_drop_complete(getattr(event, 'window', None))

                # ---------- Touch Event ----------
                elif event.type == pygame.FINGERDOWN:
                    self.on_finger_down(event.touch_id, event.finger_id, event.x, event.y, event.dx, event.dy, getattr(event, 'window', None))
                elif event.type == pygame.FINGERMOTION:
                    self.on_finger_motion(event.touch_id, event.finger_id, event.x, event.y, event.dx, event.dy, getattr(event, 'window', None))
                elif event.type == pygame.FINGERUP:
                    self.on_finger_up(event.touch_id, event.finger_id, event.x, event.y, event.dx, event.dy, getattr(event, 'window', None))
                elif event.type == pygame.MULTIGESTURE:
                    self.on_multi_gesture(event.touch_id, event.x, event.y, event.pinched, event.rotated, event.num_fingers, getattr(event, 'window', None))

                # ---------- MIDI Event ----------
                elif event.type == pygame.AUDIODEVICEADDED:
                    self.on_audio_added(event.which, event.iscapture)
                elif event.type == pygame.AUDIODEVICEREMOVED:
                    self.on_audio_removed(event.which, event.iscapture)

                # ---------- APP Event ----------
                elif event.type == pygame.APP_TERMINATING:
                    self.on_app_terminating()
                elif event.type == pygame.APP_LOWMEMORY:
                    self.on_app_low_memory()
                elif event.type == pygame.APP_WILLENTERBACKGROUND:
                    self.on_app_will_background()
                elif event.type == pygame.APP_DIDENTERBACKGROUND:
                    self.on_app_did_background()
                elif event.type == pygame.APP_WILLENTERFOREGROUND:
                    self.on_app_will_foreground()
                elif event.type == pygame.APP_DIDENTERFOREGROUND:
                    self.on_app_did_foreground()

                # ---------- Other Events ----------
                elif event.type == pygame.KEYMAPCHANGED:
                    self.on_keymap_changed()
                elif event.type == pygame.CLIPBOARDUPDATE:
                    self.on_clipboard_update()
                elif event.type == pygame.LOCALECHANGED:
                    self.on_locale_changed()
                elif event.type == pygame.RENDER_TARGETS_RESET:
                    self.on_render_target_reset()
                elif event.type == pygame.RENDER_DEVICE_RESET:
                    self.on_render_device_reset()

                # ---------- User Event ----------
                else:
                    self.on_user_event(event)


            delta_time = self._clock.tick(self._fps) / 1000
            # Make the current frame's delta time available to the scene's
            # scripts (their on_update(delta_time) hooks).
            scene_loader._set_delta_time(delta_time)
            # ... and to the scripts that ask for it instead of using the hook
            # parameter (studio.get_delta_time(), studio.get_elapsed_time()).
            self._delta_time = delta_time
            self._elapsed_time += delta_time
            self._frame_count += 1
            # --- 2. Fixed/step logic: user update + draw, then present. ---
            self.on_update(delta_time)
            pygame.display.flip()

        # Let every attached behavior script run its on_destroy() cleanup hook
        # before the game exits (mirrors on_start fired on scene load).
        scene_loader._destroy_scripts()
        self.on_quit()
        pygame.quit()
        sys.exit()
    
    # ---------- Basic Life Cycle ----------
    def on_start(self):
        pass

    def on_update(self, dt: float):
        pass

    def on_quit(self):
        pass

    # ---------- Keyboard Event Hooks ----------
    def on_key_down(self, key, mod, unicode, scancode, window=None):
        pass

    def on_key_up(self, key, mod, unicode, scancode, window=None):
        pass

    # ---------- Mouse Event Hooks ----------
    def on_mouse_motion(self, pos, rel, buttons, touch=0, window=None):
        pass

    def on_mouse_button_down(self, pos, btn, touch=0, clicks=1, window=None):
        pass

    def on_mouse_button_up(self, pos, btn, touch=0, clicks=1, window=None):
        pass

    def on_mouse_wheel(self, flipped, x, y, touch=0, precise_x=0.0, precise_y=0.0, window=None):
        pass

    # ---------- Joystick Event Hooks ----------
    def on_joy_axis_motion(self, instance_id, axis, value):
        pass

    def on_joy_ball_motion(self, instance_id, ball, rel):
        pass

    def on_joy_hat_motion(self, instance_id, hat, value):
        pass

    def on_joy_button_down(self, instance_id, button):
        pass

    def on_joy_button_up(self, instance_id, button):
        pass

    def on_joy_device_added(self, device_index):
        pass

    def on_joy_device_removed(self, instance_id):
        pass

    def on_controller_added(self, device_index):
        pass

    def on_controller_removed(self, instance_id):
        pass

    def on_controller_remapped(self, instance_id):
        pass

    # ---------- Window Event Hooks ----------
    def on_window_shown(self, window=None): 
        pass

    def on_window_hidden(self, window=None): 
        pass

    def on_window_exposed(self, window=None): 
        pass

    def on_window_moved(self, x, y, window=None): 
        pass

    def on_window_size_changed(self, x, y, window=None): 
        pass

    def on_window_resized(self, x, y, window=None): 
        pass

    def on_window_minimized(self, window=None): 
        pass

    def on_window_maximized(self, window=None): 
        pass

    def on_window_restored(self, window=None): 
        pass

    def on_window_enter(self, window=None): 
        pass

    def on_window_leave(self, window=None): 
        pass

    def on_window_focus_gained(self, window=None): 
        pass

    def on_window_focus_lost(self, window=None): 
        pass

    def on_window_close(self, window=None): 
        pass

    def on_window_take_focus(self, window=None): 
        pass

    def on_window_hit_test(self, window=None): 
        pass

    def on_window_icc_changed(self, window=None): 
        pass

    def on_window_display_changed(self, display_index, window=None): 
        pass

    # ---------- Text Input Event Hooks ----------
    def on_text_editing(self, text, start, length, window=None):
        pass

    def on_text_input(self, text, window=None):
        pass

    # ---------- Drop Event Hooks ----------
    def on_drop_begin(self, window=None): 
        pass

    def on_drop_file(self, file_path, window=None): 
        pass

    def on_drop_text(self, text, window=None): 
        pass

    def on_drop_complete(self, window=None): 
        pass

    # ---------- Touch Event Hooks ----------
    def on_finger_down(self, touch_id, finger_id, x, y, dx, dy, window=None): 
        pass

    def on_finger_motion(self, touch_id, finger_id, x, y, dx, dy, window=None): 
        pass

    def on_finger_up(self, touch_id, finger_id, x, y, dx, dy, window=None): 
        pass

    def on_multi_gesture(self, touch_id, x, y, pinched, rotated, num_fingers, window=None): 
        pass

    # ---------- MIDI Event Hooks ----------
    def on_audio_added(self, which, is_capture): 
        pass

    def on_audio_removed(self, which, is_capture): 
        pass

    # ---------- APP Event Hooks ----------
    def on_app_terminating(self): 
        pass

    def on_app_low_memory(self): 
        pass

    def on_app_will_background(self): 
        pass

    def on_app_did_background(self): 
        pass

    def on_app_will_foreground(self): 
        pass

    def on_app_did_foreground(self): 
        pass

    # ---------- Other Event Hooks ----------
    def on_keymap_changed(self): 
        pass

    def on_clipboard_update(self): 
        pass

    def on_locale_changed(self): 
        pass

    def on_render_target_reset(self): 
        pass

    def on_render_device_reset(self): 
        pass

    # ---------- User Event Hooks ----------
    def on_user_event(self, event):
        pass


def get_fps():
    return Game._instance._fps

def set_fps(value:int):
    Game._instance._fps = value

def get_screen():
    return Game._instance._screen

def quit():
    Game._instance._running = False

def get_pressed_keys():
    return pygame.key.get_pressed()

def get_pressed_buttons():
    return pygame.mouse.get_pressed()

def is_running() -> bool:
    """游戏主循环是否正在运行。True while the game loop is running."""
    instance = Game._instance
    return bool(instance._running) if instance is not None else False

def get_delta_time() -> float:
    """上一帧经过的秒数（与脚本 on_update(dt) 收到的 dt 相同）。The last frame's duration in seconds."""
    instance = Game._instance
    return instance._delta_time if instance is not None else 0.0

def get_elapsed_time() -> float:
    """游戏开始运行至今的秒数。Seconds since the game loop started."""
    instance = Game._instance
    return instance._elapsed_time if instance is not None else 0.0

def get_frame_count() -> int:
    """已经渲染的帧数。Number of frames drawn since the game loop started."""
    instance = Game._instance
    return instance._frame_count if instance is not None else 0

def is_key_pressed(key) -> bool:
    """某个键当前是否被按住，例如 studio.is_key_pressed(studio.K_SPACE)。True while that key is held."""
    try:
        return bool(pygame.key.get_pressed()[key])
    except (pygame.error, IndexError, KeyError, TypeError):
        return False

def get_mouse_position() -> tuple:
    """鼠标指针在窗口内的位置 (x, y)，无窗口时返回 (0, 0)。The pointer position inside the window."""
    try:
        return tuple(pygame.mouse.get_pos())
    except pygame.error:
        return (0, 0)

def is_mouse_button_pressed(button:int=1) -> bool:
    """某个鼠标键当前是否被按住：1 = 左键，2 = 中键，3 = 右键。True while that mouse button is held."""
    try:
        return bool(pygame.mouse.get_pressed()[int(button) - 1])
    except (pygame.error, IndexError, ValueError, TypeError):
        return False
    