"""Spike script: the object is dragged with the pointer.

A finger on Android arrives twice - once as a FINGER event and once as the
mouse events SDL synthesizes from it - so this script deliberately implements
ONLY the mouse drag family. It therefore proves that a finger drag still reaches
the classic ``on_drag_*`` hooks, because the engine keeps the mouse fallback for
objects that do not implement the touch hooks (see ``SceneLoader._TOUCH_EVENTS``).

Everything is printed with the ``[ENGINE]`` prefix so `adb logcat -s python`
shows it next to the spike's own checks.
"""


def log(message):
    print(f'[ENGINE] {message}', flush=True)


class DragBox:
    def __init__(self, owner):
        self.owner = owner
        self._origin = None
        self.drag_count = 0
        log(f'drag script attached to {owner.name!r} ({owner.image_path})')

    # ---------------------------------------------------------------- mouse
    def on_pressed(self):
        log(f'box pressed at ({self.owner.x}, {self.owner.y})')

    def on_drag_start(self):
        self._origin = (self.owner.x, self.owner.y)
        log(f'drag_start from {self._origin}')

    def on_drag(self, pos):
        self.drag_count += 1
        # Centre the object on the pointer: the drag then visibly follows the
        # finger instead of jumping by the grab offset.
        self.owner.x = int(pos[0] - self.owner.width / 2)
        self.owner.y = int(pos[1] - self.owner.height / 2)
        if self.drag_count == 1 or self.drag_count % 10 == 0:
            log(f'drag #{self.drag_count} pos={pos} -> ({self.owner.x}, {self.owner.y})')

    def on_drag_end(self):
        log(f'drag_end at ({self.owner.x}, {self.owner.y}) after {self.drag_count} move(s)')
        self._origin = None
        self.drag_count = 0

    def on_clicked(self):
        log('box clicked')
