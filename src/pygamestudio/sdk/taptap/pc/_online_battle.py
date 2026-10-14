"""Online battle: connect, rooms, matchmaking, messages and frame sync.

The SDK delivers these events through its own callback pump
(``TapOnlineBattle_RunCallbacks``); the dispatcher feeds them into the same
queue as the main SDK events, so one ``pc.run_callbacks()`` per frame covers
everything. Response events complete the Request an async call returned;
notifications (e.g. 'online_battle.frame') arrive through ``pc.on``.
"""

import ctypes

from . import _core, _dispatcher, _ffi

_handle = None


def _object():
    """The cached TapOnlineBattle singleton (created by the first call, cleared on shutdown)."""
    global _handle
    if _handle is None:
        _handle = _core.require_initialized().TapOnlineBattle()
        if not _handle:
            raise _ffi.TapSDKError('TapOnlineBattle() returned NULL - is the SDK initialized?')
    return _handle


def _reset():
    global _handle
    _handle = None


_core.register_reset(_reset)


def pump():
    """处理联机对战事件（pc.run_callbacks() 已自动调用）；返回 SDK 本次处理的事件数。

    Process pending online battle events. ``pc.run_callbacks()`` already calls
    this every frame after the first online battle call.
    """
    if not _core.is_initialized() or _handle is None:
        return 0
    left = ctypes.c_uint32(0)
    processed = _core.require_initialized().TapOnlineBattle_RunCallbacks(
        _handle, _dispatcher.dispatcher.online_battle_trampoline(), 0, ctypes.byref(left))
    return int(processed)


_dispatcher.dispatcher.register_pump(pump)


def connect():
    """连接联机服务（异步，成功后才能建房/匹配）。结果经 'online_battle.connected' 返回。

    负载 data['player_id'] 是本机玩家 ID。
    Async connect; completes as 'online_battle.connected' (local player id).
    """
    return _call('online_battle.connected', 'TapOnlineBattle_AsyncConnect')


def disconnect():
    """断开联机服务（异步）。结果经 'online_battle.disconnected' 返回。

    Async disconnect; completes as 'online_battle.disconnected'.
    """
    return _call('online_battle.disconnected', 'TapOnlineBattle_AsyncDisconnect')


def create_room(max_players, room_type, name='', custom_properties='',
                match_params=None, custom_status=0, player_properties=''):
    """创建房间（异步）。结果经 'online_battle.room_created' 返回（data['room']）。

    max_players 1-20；match_params 最多 3 条匹配规则（[{'key':.., 'value':..}]
    或 [(key, value)]），匹配时人数+类型+规则完全相同才会匹配上。
    Async create; completes as 'online_battle.room_created'.
    """
    data, _keep = _room_request(_ffi.TapOnlineBattleCreateRoomRequest, max_players, room_type,
                                name, custom_properties, match_params, custom_status,
                                player_properties)
    return _call('online_battle.room_created', 'TapOnlineBattle_AsyncCreateRoom', data)


def match_room(max_players, room_type, name='', custom_properties='',
               match_params=None, custom_status=0, player_properties=''):
    """匹配房间（异步，匹配不到时按参数创建）。结果经 'online_battle.room_matched' 返回。

    Parameters are the same as create_room(); completes as
    'online_battle.room_matched' (data['room']).
    """
    data, _keep = _room_request(_ffi.TapOnlineBattleMatchRoomRequest, max_players, room_type,
                                name, custom_properties, match_params, custom_status,
                                player_properties)
    return _call('online_battle.room_matched', 'TapOnlineBattle_AsyncMatchRoom', data)


def get_room_list(room_type='', offset=0, limit=0):
    """拉取可加入的房间列表（异步）。结果经 'online_battle.room_list' 返回。

    limit 0 = 服务端默认（20，最大 100）；负载含 rooms / offset / has_more。
    Async room list; completes as 'online_battle.room_list'.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.room_list')
    data = _ffi.TapOnlineBattleGetRoomListRequest()
    encoded = _ffi.encode(room_type)
    data.room_type = encoded
    data.offset = int(offset)
    data.limit = int(limit)
    code = _core.require_initialized().TapOnlineBattle_AsyncGetRoomList(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapOnlineBattle_AsyncGetRoomList')
    return request


def join_room(room_id, custom_status=0, custom_properties=''):
    """加入房间（异步）。结果经 'online_battle.room_joined' 返回（data['room']）。

    Async join; completes as 'online_battle.room_joined'.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.room_joined')
    data = _ffi.TapOnlineBattleJoinRoomRequest()
    encoded_id = _ffi.encode(room_id)
    encoded_props = _ffi.encode(custom_properties)
    data.room_id = encoded_id
    data.player_cfg.custom_status = int(custom_status)
    data.player_cfg.custom_properties = encoded_props
    code = _core.require_initialized().TapOnlineBattle_AsyncJoinRoom(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapOnlineBattle_AsyncJoinRoom')
    return request


def leave_room():
    """离开房间（异步；帧同步中不允许）。结果经 'online_battle.room_left' 返回。

    Async leave (refused while frame sync runs); completes as
    'online_battle.room_left'.
    """
    return _call('online_battle.room_left', 'TapOnlineBattle_AsyncLeaveRoom')


def update_player_status(status):
    """更新玩家自定义状态（异步）。结果经 'online_battle.player_status_updated' 返回。

    Async; completes as 'online_battle.player_status_updated'. Shares the
    15-calls-per-second budget with the other room updates.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.player_status_updated')
    code = _core.require_initialized().TapOnlineBattle_AsyncUpdatePlayerCustomStatus(
        _object(), request.id, int(status))
    _core.check_result(code, 'TapOnlineBattle_AsyncUpdatePlayerCustomStatus')
    return request


def update_player_properties(properties):
    """更新玩家自定义属性（异步）。结果经 'online_battle.player_properties_updated' 返回。

    Async; completes as 'online_battle.player_properties_updated'.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.player_properties_updated')
    encoded = _ffi.encode(properties)
    code = _core.require_initialized().TapOnlineBattle_AsyncUpdatePlayerCustomProperties(
        _object(), request.id, encoded)
    _core.check_result(code, 'TapOnlineBattle_AsyncUpdatePlayerCustomProperties')
    return request


def update_room_properties(name=None, custom_properties=None):
    """更新房间属性（异步；仅房主、非帧同步时）。结果经 'online_battle.room_properties_updated' 返回。

    Async update of the room name / custom properties (room owner only);
    completes as 'online_battle.room_properties_updated'.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.room_properties_updated')
    data = _ffi.TapOnlineBattleUpdateRoomPropertiesRequest()
    encoded_name = _ffi.encode(name)
    encoded_props = _ffi.encode(custom_properties)
    data.name = encoded_name
    data.custom_properties = encoded_props
    code = _core.require_initialized().TapOnlineBattle_AsyncUpdateRoomProperties(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapOnlineBattle_AsyncUpdateRoomProperties')
    return request


def send_message(msg, receivers=None):
    """发送自定义消息（异步）。结果经 'online_battle.message_sent' 返回。

    receivers 为 None 时发给房间内所有人（不含自己）；否则传入玩家 ID 列表
    （最多 20 个）。消息必须是 UTF-8 字符串（≤2048 字节）。
    Async custom message; None receivers = everyone in the room but yourself.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.message_sent')
    data = _ffi.TapOnlineBattleSendCustomMessageRequest()
    encoded_msg = _ffi.encode(msg)
    data.msg = encoded_msg
    keep = [encoded_msg]

    if receivers:
        values = [str(item) for item in receivers]
        if len(values) > 20:
            raise ValueError('the SDK accepts at most 20 receivers')
        array = (ctypes.c_char_p * len(values))()
        for index, value in enumerate(values):
            encoded = _ffi.encode(value)
            keep.append(encoded)
            array[index] = encoded
        data.receiver_type = 1
        data.receiver_count = len(values)
        data.receivers = array
        keep.append(array)
    else:
        data.receiver_type = 0
        data.receiver_count = 0
        data.receivers = None

    code = _core.require_initialized().TapOnlineBattle_AsyncSendCustomMessage(
        _object(), request.id, ctypes.byref(data))
    _core.check_result(code, 'TapOnlineBattle_AsyncSendCustomMessage')
    return request


def kick_player(player_id):
    """把玩家踢出房间（异步；仅房主、非帧同步时）。结果经 'online_battle.player_kicked' 返回。

    Async kick (room owner only); completes as 'online_battle.player_kicked'.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.player_kicked')
    encoded = _ffi.encode(player_id)
    code = _core.require_initialized().TapOnlineBattle_AsyncKickRoomPlayer(
        _object(), request.id, encoded)
    _core.check_result(code, 'TapOnlineBattle_AsyncKickRoomPlayer')
    return request


def start_frame_sync():
    """开始帧同步（异步，房主发起）。结果经 'online_battle.frame_sync_started' 返回。

    开始后每帧通过 'online_battle.frame' 事件收到对战帧
    （data['frame_id'] / data['inputs']），并可用 send_frame_input() 提交操作。
    Start frame sync (room owner); frames arrive as 'online_battle.frame'.
    """
    return _call('online_battle.frame_sync_started', 'TapOnlineBattle_AsyncStartFrameSync')


def send_frame_input(data):
    """发送本帧操作（异步；同一帧最多 5 次）。结果经 'online_battle.frame_input_sent' 返回。

    data 是 UTF-8 字符串（格式由游戏自定义，例如按键指令），≤ 限制大小。
    Async frame input; completes as 'online_battle.frame_input_sent'.
    """
    request = _dispatcher.dispatcher.new_request('online_battle.frame_input_sent')
    payload = _ffi.TapOnlineBattleSendFrameInputRequest()
    encoded = _ffi.encode(data)
    payload.data = encoded
    code = _core.require_initialized().TapOnlineBattle_AsyncSendFrameInput(
        _object(), request.id, ctypes.byref(payload))
    _core.check_result(code, 'TapOnlineBattle_AsyncSendFrameInput')
    return request


def stop_frame_sync():
    """停止帧同步（异步，房主发起）。结果经 'online_battle.frame_sync_stopped' 返回。

    Async stop (room owner); completes as 'online_battle.frame_sync_stopped'.
    """
    return _call('online_battle.frame_sync_stopped', 'TapOnlineBattle_AsyncStopFrameSync')


def _call(event, api_name, request_data=None):
    """Fire one of the argument-less async calls and return its Request."""
    request = _dispatcher.dispatcher.new_request(event)
    function = getattr(_core.require_initialized(), api_name)
    if request_data is None:
        code = function(_object(), request.id)
    else:
        code = function(_object(), request.id, ctypes.byref(request_data))
    _core.check_result(code, api_name)
    return request


def _room_request(cls, max_players, room_type, name, custom_properties, match_params,
                  custom_status, player_properties):
    """Fill a create/match room request; returns (struct, keep-alive objects)."""
    data = cls()
    keep = []

    room_type_value = _ffi.encode(room_type)
    name_value = _ffi.encode(name)
    properties_value = _ffi.encode(custom_properties)
    keep += [room_type_value, name_value, properties_value]
    data.room_cfg.max_player_count = int(max_players)
    data.room_cfg.room_type = room_type_value
    data.room_cfg.name = name_value
    data.room_cfg.custom_properties = properties_value

    params = list(match_params or [])
    if len(params) > 3:
        raise ValueError('the SDK accepts at most 3 match rules')
    if params:
        array = (_ffi.TapOnlineBattleMatchParam * len(params))()
        for index, param in enumerate(params):
            key, value = (param['key'], param['value']) if isinstance(param, dict) else param
            key_value = _ffi.encode(key)
            value_value = _ffi.encode(value)
            keep += [key_value, value_value]
            array[index].key = key_value
            array[index].value = value_value
        data.room_cfg.match_params = array
        data.room_cfg.match_param_count = len(params)
        keep.append(array)

    player_properties_value = _ffi.encode(player_properties)
    keep.append(player_properties_value)
    data.player_cfg.custom_status = int(custom_status)
    data.player_cfg.custom_properties = player_properties_value
    return data, keep
