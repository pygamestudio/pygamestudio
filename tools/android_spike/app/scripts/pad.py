"""Spike script: the pad owns raw touch (FINGER) events.

Only the touch hooks are implemented, so the engine hands the finger to this
object and swallows the mouse events SDL derives from the same finger - the
dedupe that keeps a tap from firing both ``on_touch_down`` and ``on_pressed``.
"""


def log(message):
    print(f'[ENGINE] {message}', flush=True)


class TouchPad:
    def __init__(self, owner):
        self.owner = owner
        self.moves = 0
        log(f'touch script attached to {owner.name!r}')

    def on_touch_down(self, finger_id, pos):
        self.moves = 0
        log(f'touch_down finger={finger_id} pos={pos}')

    def on_touch_move(self, finger_id, pos):
        self.moves += 1
        if self.moves == 1 or self.moves % 10 == 0:
            log(f'touch_move #{self.moves} finger={finger_id} pos={pos}')

    def on_touch_up(self, finger_id, pos):
        log(f'touch_up finger={finger_id} pos={pos} after {self.moves} move(s)')

    def on_tap(self, finger_id, pos):
        log(f'tap finger={finger_id} pos={pos}')
