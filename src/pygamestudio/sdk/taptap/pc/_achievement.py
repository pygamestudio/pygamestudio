"""Achievements: unlock, step increment and the achievement page."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import Event

_handle = None


def _object():
    """The cached TapAchievement singleton (obtained once, cleared on shutdown)."""
    global _handle
    if _handle is None:
        _handle = _core.require_initialized().TapAchievement()
        if not _handle:
            raise _ffi.TapSDKError('TapAchievement() returned NULL - is the SDK initialized?')
    return _handle


def _reset():
    global _handle
    _handle = None


_core.register_reset(_reset)
_dispatcher.dispatcher.register_parser(Event.AchievementUnlock, _ffi.parse_achievement_unlock)
_dispatcher.dispatcher.register_parser(Event.AchievementIncrement, _ffi.parse_achievement_increment)


def unlock(achievement_id):
    """解锁成就（异步）。结果经 'achievement.unlocked' 到达；返回 Request。

    完成后 request.data['achievement'] 含 id/name/current_steps/
    newly_unlocked；首次解锁白金成就时另有 'platinum_achievement'。
    Unlock an achievement; the Request completes as 'achievement.unlocked'.
    """
    request = _dispatcher.dispatcher.new_request('achievement.unlocked')
    data = _ffi.TapAchievementUnlockRequest()
    encoded = _ffi.encode(achievement_id)
    data.achievement_id = encoded
    code = _core.require_initialized().TapAchievement_AsyncUnlock(_object(), request.id,
                                                                  ctypes.byref(data))
    _core.check_result(code, 'TapAchievement_AsyncUnlock')
    return request


def increment(achievement_id, steps=1):
    """分步成就增加步长（异步）。结果经 'achievement.incremented' 到达。

    Add steps to a step achievement; completes the returned Request the same
    way unlock() does. Returns the Request.
    """
    request = _dispatcher.dispatcher.new_request('achievement.incremented')
    data = _ffi.TapAchievementIncrementRequest()
    encoded = _ffi.encode(achievement_id)
    data.achievement_id = encoded
    data.steps = int(steps)
    code = _core.require_initialized().TapAchievement_AsyncIncrement(_object(), request.id,
                                                                     ctypes.byref(data))
    _core.check_result(code, 'TapAchievement_AsyncIncrement')
    return request


def show():
    """打开 TapTap 成就展示页。Open the achievement page in the TapTap client."""
    code = _core.require_initialized().TapAchievement_ShowAchievements(_object())
    _core.check_result(code, 'TapAchievement_ShowAchievements')
