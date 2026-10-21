"""Bridge between the MCP server (background thread) and the running editor.

The editor is a Qt application: every scene edit has to happen on the **main
thread** (the undo stack, the models and the widgets all live there). The MCP
server, however, serves requests on worker threads. This module is the single
place where the two meet:

* ``attach()`` is called by the editor once its window exists. It remembers the
  editor objects and installs a small timer that drains a queue of pending
  calls on the main thread.
* ``call_in_main_thread()`` hands a callable over to that timer and waits for
  its result (used by every tool handler and resource reader).
* ``detach()`` is called when the project window is closed/cleaned up, so
  pending calls fail instead of hanging forever.

When no editor is attached (headless use, tests, ``python -m pygamestudio.mcp
--serve``) the queue is bypassed and calls run inline in the caller thread.
"""

import queue
import threading
import time

#: How long a tool call may wait for the main thread before giving up. A modal
#: dialog (file chooser, message box) blocks the timer, which is a real
#: possibility, so this must not be too short or the editor looks broken.
CALL_TIMEOUT = 60.0

#: A game window an AI agent started for testing is closed again once the agent
#: has not called any tool for this long (the agent is done with its run).
AGENT_GAME_IDLE_SECONDS = 25.0

#: How often the main-thread pump looks for an idle agent test run.
_WATCH_INTERVAL = 1.0


class EditorNotAttached(RuntimeError):
    """Raised when a tool needs the editor but no window is attached."""


class _Job:
    __slots__ = ('func', 'args', 'kwargs', 'done', 'result', 'error', 'cancelled')

    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.cancelled = False

    def run(self):
        if self.cancelled:
            return
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except BaseException as e:  # noqa: BLE001 - forwarded to the caller
            self.error = e
        finally:
            self.done.set()


class EditorBridge:
    """Holds the running editor and marshals calls onto its main thread."""

    def __init__(self):
        self._lock = threading.RLock()
        self._pending = queue.Queue()
        self._timer = None
        self._editor = None
        self._editor_body = None
        self._game_manager = None
        self._project_ready = False
        self._main_thread_id = None
        self._last_activity = time.monotonic()
        self._last_watch = 0.0
        #: True once an MCP call changed the scene (see registry.autosave_scene).
        self._scene_touched_by_agent = False
        #: Idle time after which an agent's test run is closed (tests shorten it).
        self.agent_game_idle_seconds = AGENT_GAME_IDLE_SECONDS

    # ------------------------------------------------------------- lifecycle
    def attach(self, editor=None, editor_body=None, game_manager=None, project_ready=True):
        """Register the running editor and start the main-thread pump.

        Must be called on the main thread (it creates a ``QTimer``).
        """
        with self._lock:
            self._editor = editor
            self._editor_body = editor_body
            self._game_manager = game_manager
            self._project_ready = project_ready
            # Remember who the main thread is: it may call tools itself (the
            # in-editor agent will), and such a call must NOT be queued back to
            # the thread that is waiting for it.
            self._main_thread_id = threading.get_ident()
            self._last_activity = time.monotonic()
            self._scene_touched_by_agent = False
            if self._timer is None:
                self._timer = self._create_pump()

    def _create_pump(self):
        """Install the QTimer that drains the job queue on the main thread."""
        try:
            from PySide6.QtCore import QTimer
        except ImportError:
            return None

        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(self._drain)
        timer.start()
        return timer

    def detach(self):
        """Forget the editor and fail every pending call."""
        # A test run the agent left open must not outlive the editor (the
        # user's own game window is kept).
        manager = self.game_manager_or_none()
        if manager is not None:
            try:
                manager.stop_project(agent_only=True)
            except Exception:  # noqa: BLE001 - closing must never fail
                pass
        with self._lock:
            self._editor = None
            self._editor_body = None
            self._game_manager = None
            self._project_ready = False
            self._main_thread_id = None
            self._scene_touched_by_agent = False
            if self._timer is not None:
                try:
                    self._timer.stop()
                except RuntimeError:
                    pass
                self._timer = None
        while True:
            try:
                job = self._pending.get_nowait()
            except queue.Empty:
                return
            job.error = EditorNotAttached('The editor was closed before the call finished')
            job.done.set()

    # ---------------------------------------------------------------- state
    @property
    def is_attached(self) -> bool:
        with self._lock:
            return self._game_manager is not None

    @property
    def is_project_ready(self) -> bool:
        with self._lock:
            return bool(self._project_ready and self._game_manager is not None)

    @property
    def manager(self):
        """The ``GameManager`` of the open project, or raise."""
        manager = self.game_manager_or_none()
        if manager is None:
            raise EditorNotAttached(
                'No Pygame Studio project is open in the editor right now.')
        return manager

    def game_manager_or_none(self):
        with self._lock:
            return self._game_manager

    def editor_or_none(self):
        with self._lock:
            return self._editor

    def editor_body_or_none(self):
        with self._lock:
            return self._editor_body

    def set_project_ready(self, ready=True):
        with self._lock:
            self._project_ready = bool(ready)

    def note_activity(self):
        """Remember that the MCP client is still working.

        Called for every tool call/resource read: the watchdog closes a game
        window the agent started once this timestamp goes stale.
        """
        self._last_activity = time.monotonic()

    @property
    def scene_touched_by_agent(self) -> bool:
        """Whether a tool call (rather than the user) changed the scene."""
        return self._scene_touched_by_agent

    def mark_scene_touched(self):
        """Remember that an MCP call modified the scene (autosave is due)."""
        self._scene_touched_by_agent = True

    def clear_scene_touched(self):
        """The scene is on disk again (after the autosave)."""
        self._scene_touched_by_agent = False

    def stop_agent_game(self) -> int:
        """Close the game windows an AI agent opened for testing.

        Only runs the agent started (``run_project(started_by_agent=True)``)
        are stopped; a game the user started himself keeps running.
        """
        manager = self.game_manager_or_none()
        if manager is None:
            return 0
        return self.call_in_main_thread(lambda: manager.stop_project(agent_only=True))

    # ------------------------------------------------------------ execution
    def call_in_main_thread(self, func, *args, **kwargs):
        """Run ``func`` on the editor's main thread and return its result.

        Without an attached editor - or when the caller already *is* the main
        thread (tests, the in-editor agent panel) - the call simply runs here.
        """
        with self._lock:
            attached = self._timer is not None or self._game_manager is not None
            on_main_thread = (self._main_thread_id is not None
                              and threading.get_ident() == self._main_thread_id)
        if not attached or on_main_thread:
            return func(*args, **kwargs)

        job = _Job(func, args, kwargs)
        self._pending.put(job)
        if not job.done.wait(CALL_TIMEOUT):
            # Never let the abandoned call run later: it could mutate the scene
            # long after the client gave up on it.
            job.cancelled = True
            raise TimeoutError(
                'The editor did not answer within {:.0f}s. A modal dialog '
                '(file chooser, message box, ...) is probably open in it.'.format(CALL_TIMEOUT))
        if job.error is not None:
            raise job.error
        return job.result

    def _drain(self):
        """Main thread: run every queued call (bounded, to stay responsive)."""
        for _ in range(20):
            try:
                job = self._pending.get_nowait()
            except queue.Empty:
                break
            job.run()
        self._watch_agent_game()

    def _watch_agent_game(self):
        """Close a test run the AI agent started once the agent is done.

        Runs on the main thread from the pump timer: when no tool call arrived
        for ``agent_game_idle_seconds``, the game windows the agent opened for
        debugging are closed. A game the user started is never touched.
        """
        now = time.monotonic()
        if now - self._last_watch < _WATCH_INTERVAL:
            return
        self._last_watch = now
        manager = self._game_manager
        if manager is None:
            return
        if now - self._last_activity < self.agent_game_idle_seconds:
            return
        try:
            manager.stop_project(agent_only=True)
        except Exception:  # noqa: BLE001 - the watchdog must never break the pump
            pass


#: The one bridge the editor, the server and the tools all share.
bridge = EditorBridge()


def attach(editor=None, editor_body=None, game_manager=None, project_ready=True):
    """Shortcut for ``bridge.attach(...)``."""
    bridge.attach(editor=editor, editor_body=editor_body,
                  game_manager=game_manager, project_ready=project_ready)


def detach():
    """Shortcut for ``bridge.detach()``."""
    bridge.detach()


def call_in_main_thread(func, *args, **kwargs):
    """Shortcut for ``bridge.call_in_main_thread(...)``."""
    return bridge.call_in_main_thread(func, *args, **kwargs)


def require_manager():
    """The open project's ``GameManager``; raises :class:`EditorNotAttached`."""
    return bridge.manager


def in_main_thread(func):
    """Run ``func`` on the editor's main thread. Tools use this everywhere."""
    return call_in_main_thread(func)


def stop_agent_game():
    """Shortcut for ``bridge.stop_agent_game()`` (agent test windows only)."""
    return bridge.stop_agent_game()
