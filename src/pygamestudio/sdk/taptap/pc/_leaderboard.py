"""Leaderboard: submit scores, load boards, show the leaderboard page."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import Event, LeaderboardCollection

_handle = None


def _object():
    """The cached TapLeaderboard singleton (obtained once, cleared on shutdown)."""
    global _handle
    if _handle is None:
        _handle = _core.require_initialized().TapLeaderboard()
        if not _handle:
            raise _ffi.TapSDKError('TapLeaderboard() returned NULL - is the SDK initialized?')
    return _handle


def _reset():
    global _handle
    _handle = None


_core.register_reset(_reset)
_dispatcher.dispatcher.register_parser(Event.LeaderboardSubmitScores, _ffi.parse_leaderboard_submitted)
_dispatcher.dispatcher.register_parser(Event.LeaderboardLoadScores, _ffi.parse_leaderboard_loaded)
_dispatcher.dispatcher.register_parser(Event.LeaderboardLoadMyScores, _ffi.parse_leaderboard_my_scores)
_dispatcher.dispatcher.register_parser(Event.LeaderboardLoadMyCenteredScores, _ffi.parse_leaderboard_centered)


def submit(scores):
    """批量上报分数（异步，一次最多 5 条）。结果经 'leaderboard.submitted' 返回。

    scores 可写成 [(榜单ID, 分数), ...] 或 [{'leaderboard_id': .., 'score': ..}, ..]；
    负载的 data['results'] 会给出每个榜单是否新纪录（new_best）。
    Submit up to 5 scores; completes as 'leaderboard.submitted'.
    """
    entries = _normalize_scores(scores)
    request = _dispatcher.dispatcher.new_request('leaderboard.submitted')

    items = (_ffi.TapLeaderboardScoreItem * len(entries))()
    encoded = []
    for index, (leaderboard_id, score) in enumerate(entries):
        value = _ffi.encode(leaderboard_id)
        encoded.append(value)
        items[index].leaderboard_id = value
        items[index].score = int(score)

    data = _ffi.TapLeaderboardSubmitScoresRequest()
    data.item_count = len(entries)
    data.items = items
    code = _core.require_initialized().TapLeaderboard_AsyncSubmitScores(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapLeaderboard_AsyncSubmitScores')
    return request


def load(leaderboard_id, collection=LeaderboardCollection.Public,
         continuation_token=None, period_token=None):
    """拉取排行榜数据（异步）。结果经 'leaderboard.loaded' 返回。

    分页：用负载里的 continuation_token 再请求下一页（is_truncated=True 表示还有）。
    Async load; completes as 'leaderboard.loaded' with scores and the next
    continuation_token (pass it back for the following page).
    """
    request = _dispatcher.dispatcher.new_request('leaderboard.loaded')
    data = _ffi.TapLeaderboardLoadScoresRequest()
    encoded = {
        'id': _ffi.encode(leaderboard_id),
        'token': _ffi.encode(continuation_token),
        'period': _ffi.encode(period_token),
    }
    data.leaderboard_id = encoded['id']
    data.collection = int(collection)
    data.continuation_token = encoded['token']
    data.period_token = encoded['period']
    code = _core.require_initialized().TapLeaderboard_AsyncLoadScores(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapLeaderboard_AsyncLoadScores')
    return request


def load_mine(leaderboard_id, collection=LeaderboardCollection.Public, period_token=None):
    """获取当前用户的排名（异步）。结果经 'leaderboard.my_scores' 返回。

    Async: the user's own rank; completes as 'leaderboard.my_scores'
    (data['score'] is None when the user has no score yet).
    """
    request = _dispatcher.dispatcher.new_request('leaderboard.my_scores')
    data = _ffi.TapLeaderboardLoadMyScoresRequest()
    encoded = {'id': _ffi.encode(leaderboard_id), 'period': _ffi.encode(period_token)}
    data.leaderboard_id = encoded['id']
    data.collection = int(collection)
    data.period_token = encoded['period']
    code = _core.require_initialized().TapLeaderboard_AsyncLoadMyScores(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapLeaderboard_AsyncLoadMyScores')
    return request


def load_centered(leaderboard_id, collection=LeaderboardCollection.Public, max_results=0):
    """获取围绕当前用户的分数（异步）。结果经 'leaderboard.my_centered_scores' 返回。

    Async: scores centered on the user; max_results 0 = the server default.
    Completes as 'leaderboard.my_centered_scores'.
    """
    request = _dispatcher.dispatcher.new_request('leaderboard.my_centered_scores')
    data = _ffi.TapLeaderboardLoadMyCenteredScoresRequest()
    encoded = _ffi.encode(leaderboard_id)
    data.leaderboard_id = encoded
    data.collection = int(collection)
    data.max_results = int(max_results)
    code = _core.require_initialized().TapLeaderboard_AsyncLoadMyCenteredScores(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapLeaderboard_AsyncLoadMyCenteredScores')
    return request


def show(leaderboard_id, collection=LeaderboardCollection.Public):
    """在 TapTap 客户端打开排行榜页面。Open the leaderboard page in TapTap."""
    request = _ffi.TapLeaderboardShowRequest()
    encoded = _ffi.encode(leaderboard_id)
    request.leaderboard_id = encoded
    request.collection = int(collection)
    code = _core.require_initialized().TapLeaderboard_ShowLeaderboards(_object(),
                                                                       ctypes.byref(request))
    _core.check_result(code, 'TapLeaderboard_ShowLeaderboards')


def _normalize_scores(scores):
    entries = []
    for entry in scores:
        if isinstance(entry, dict):
            entries.append((entry['leaderboard_id'], entry['score']))
        else:
            leaderboard_id, score = entry
            entries.append((leaderboard_id, score))
    if not entries:
        raise ValueError('scores must not be empty')
    if len(entries) > 5:
        raise ValueError('the SDK accepts at most 5 scores per submit')
    return entries
