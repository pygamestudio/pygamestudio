"""Relation: friends / following / fans, friend sync, IM window and invites."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import Event, RelationAction

_handle = None


def _object():
    """The cached TapRelation singleton (obtained once, cleared on shutdown)."""
    global _handle
    if _handle is None:
        _handle = _core.require_initialized().TapRelation()
        if not _handle:
            raise _ffi.TapSDKError('TapRelation() returned NULL - is the SDK initialized?')
    return _handle


def _reset():
    global _handle
    _handle = None


_core.register_reset(_reset)
_dispatcher.dispatcher.register_parser(Event.RelationGetFriendList, _ffi.parse_relation_friends)
_dispatcher.dispatcher.register_parser(Event.RelationGetFollowingList, _ffi.parse_relation_following)
_dispatcher.dispatcher.register_parser(Event.RelationGetFanList, _ffi.parse_relation_fans)
_dispatcher.dispatcher.register_parser(Event.RelationSyncRelationshipWithOpenID, _ffi.parse_relation_sync)
_dispatcher.dispatcher.register_parser(Event.RelationSyncRelationshipWithUnionID, _ffi.parse_relation_sync)
_dispatcher.dispatcher.register_parser(Event.RelationUnreadMessageCountChanged, _ffi.parse_relation_count)
_dispatcher.dispatcher.register_parser(Event.RelationNewFanCountChanged, _ffi.parse_relation_count)
_dispatcher.dispatcher.register_parser(Event.RelationGameInviteReceived, _ffi.parse_relation_invite)
_dispatcher.dispatcher.register_parser(Event.RelationTeamInviteReceived, _ffi.parse_relation_invite)


def friends(continuation_token=None):
    """拉取好友列表（互关，异步）。结果经 'relation.friend_list' 返回。

    负载 data['friends'] 为列表；还有下一页时 data['continuation_token'] 非空。
    Async friend list (mutual follows); completes as 'relation.friend_list'.
    """
    return _list_request('relation.friend_list', 'TapRelation_AsyncGetFriendList',
                         continuation_token)


def following(continuation_token=None):
    """拉取关注列表（我关注的，异步）。结果经 'relation.following_list' 返回。

    Async following list; completes as 'relation.following_list'.
    """
    return _list_request('relation.following_list', 'TapRelation_AsyncGetFollowingList',
                         continuation_token)


def fans(continuation_token=None):
    """拉取粉丝列表（关注我的，异步）。结果经 'relation.fan_list' 返回。

    Async fan list; completes as 'relation.fan_list'.
    """
    return _list_request('relation.fan_list', 'TapRelation_AsyncGetFanList',
                         continuation_token)


def sync_friend(friend_open_id, nickname, friend_nickname, action=RelationAction.Add):
    """同步好友关系（按 OpenID，异步）。结果经 'relation.sync_result' 返回。

    Telegram 风格的好友同步：把游戏里的好友关系告诉 TapTap。action 取
    RelationAction.Add / Remove。
    Sync a friendship by OpenID; completes as 'relation.sync_result'.
    """
    request = _dispatcher.dispatcher.new_request('relation.sync_result')
    data = _ffi.TapRelationSyncRelationshipWithOpenIDRequest()
    encoded = {
        'nickname': _ffi.encode(nickname),
        'friend_nickname': _ffi.encode(friend_nickname),
        'friend_id': _ffi.encode(friend_open_id),
    }
    data.action = int(action)
    data.nickname = encoded['nickname']
    data.friend_nickname = encoded['friend_nickname']
    data.friend_open_id = encoded['friend_id']
    code = _core.require_initialized().TapRelation_AsyncSyncRelationshipWithOpenID(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapRelation_AsyncSyncRelationshipWithOpenID')
    return request


def sync_friend_by_union_id(friend_union_id, nickname, friend_nickname, action=RelationAction.Add):
    """同步好友关系（按 UnionID，异步）。结果经 'relation.sync_result' 返回。

    Same as sync_friend() but keyed by UnionID.
    """
    request = _dispatcher.dispatcher.new_request('relation.sync_result')
    data = _ffi.TapRelationSyncRelationshipWithUnionIDRequest()
    encoded = {
        'nickname': _ffi.encode(nickname),
        'friend_nickname': _ffi.encode(friend_nickname),
        'friend_id': _ffi.encode(friend_union_id),
    }
    data.action = int(action)
    data.nickname = encoded['nickname']
    data.friend_nickname = encoded['friend_nickname']
    data.friend_union_id = encoded['friend_id']
    code = _core.require_initialized().TapRelation_AsyncSyncRelationshipWithUnionID(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapRelation_AsyncSyncRelationshipWithUnionID')
    return request


def unread_message_count():
    """未读消息数（同步，出错时返回 None）；建议改用 'relation.unread_count_changed' 事件。

    The unread message count, or None on failure; prefer the
    'relation.unread_count_changed' event for live updates.
    """
    count = ctypes.c_uint32(0)
    code = _core.require_initialized().TapRelation_GetUnreadMessageCount(
        _object(), ctypes.byref(count))
    return int(count.value) if int(code) == 0 else None


def new_fan_count():
    """新增粉丝数（同步，出错时返回 None）；建议改用 'relation.new_fan_count_changed' 事件。

    The new-fan count, or None on failure; prefer the
    'relation.new_fan_count_changed' event for live updates.
    """
    count = ctypes.c_uint32(0)
    code = _core.require_initialized().TapRelation_GetNewFanCount(_object(), ctypes.byref(count))
    return int(count.value) if int(code) == 0 else None


def show_im():
    """打开 TapTap IM 窗口（聊天/好友管理）。Open the TapTap IM window."""
    _core.check_result(_core.require_initialized().TapRelation_ShowIM(_object()),
                       'TapRelation_ShowIM')


def show_profile(open_id=None, union_id=None):
    """展示用户名片（open_id / union_id 二选一，同时传递会报错）。

    Show a TapTap user profile; pass exactly one of open_id / union_id.
    """
    if (open_id is None) == (union_id is None):
        raise ValueError('pass exactly one of open_id / union_id')
    request = _ffi.TapRelationShowUserProfileRequest()
    encoded = {'open': _ffi.encode(open_id), 'union': _ffi.encode(union_id)}
    request.open_id = encoded['open']
    request.union_id = encoded['union']
    code = _core.require_initialized().TapRelation_ShowUserProfile(_object(),
                                                                   ctypes.byref(request))
    _core.check_result(code, 'TapRelation_ShowUserProfile')


def invite_game():
    """打开邀请好友进入游戏的窗口。Invite friends into the running game (IM window)."""
    _core.check_result(_core.require_initialized().TapRelation_InviteGame(_object()),
                       'TapRelation_InviteGame')


def invite_team(team_id):
    """打开邀请好友加入队伍的窗口；team_id 为组队参数（ASCII，无空格/引号/换行）。

    Invite friends into a team; team_id must be ASCII without spaces/quotes.
    """
    request = _ffi.TapRelationInviteTeamRequest()
    encoded = _ffi.encode(team_id)
    request.team_id = encoded
    code = _core.require_initialized().TapRelation_InviteTeam(_object(), ctypes.byref(request))
    _core.check_result(code, 'TapRelation_InviteTeam')


def handle_invite_scheme(invite_scheme):
    """把冷启动参数里的邀请 scheme 原样交给 SDK，触发邀请事件。

    游戏被启动器以 ``--tap_invite_scheme=<scheme>`` 冷启动时，解析出 scheme
    后调用本接口，SDK 会触发 'relation.game_invite_received' /
    'relation.team_invite_received' 事件。
    Replay a cold-start invite scheme so the SDK raises the invite events.
    """
    encoded = _ffi.encode(invite_scheme)
    code = _core.require_initialized().TapRelation_HandleInviteScheme(_object(), encoded)
    _core.check_result(code, 'TapRelation_HandleInviteScheme')


def _list_request(event, api_name, continuation_token):
    request = _dispatcher.dispatcher.new_request(event)
    data = _ffi.TapRelationGetFriendListRequest()
    encoded = _ffi.encode(continuation_token)
    data.continuation_token = encoded
    function = getattr(_core.require_initialized(), api_name)
    code = function(_object(), request.id, ctypes.byref(data))
    _core.check_result(code, api_name)
    return request
