"""ctypes structs of the TapTap PC SDK, mirroring the official headers.

Every struct is a verbatim mirror (same field order and types) of the
``taptap_*.h`` files of SDK v4.6.1. The headers wrap them in
``#pragma pack(push, 8)``, which is the x64 default ctypes already uses.

``const char*`` fields are ``c_char_p`` (reading gives ``bytes``, use the
``_decode*`` helpers), fixed ``char[N]`` buffers are ``c_char * N``, response
payload pointers are typed - parse functions copy everything into plain
Python dicts *while the C callback is running*, because the SDK only keeps
the data alive during the callback.
"""

import ctypes

# =============================================================================
# Core (taptap_api.h)
# =============================================================================


class TapSDK_Error(ctypes.Structure):
    _fields_ = [
        ('code', ctypes.c_int64),
        ('message', ctypes.c_char_p),
    ]


class TapSystemStateNotification(ctypes.Structure):
    _fields_ = [
        ('state', ctypes.c_uint32),
        ('detail', ctypes.c_void_p),
    ]


class TapSystemStateNotificationGameSessionInfo(ctypes.Structure):
    _fields_ = [
        ('device_name', ctypes.c_char_p),
    ]


class AuthorizeFinishedResponse(ctypes.Structure):
    _fields_ = [
        ('is_cancel', ctypes.c_bool),
        ('error', ctypes.c_char * 1024),
        ('token_type', ctypes.c_char * 32),
        ('kid', ctypes.c_char * (8 * 1024)),
        ('mac_key', ctypes.c_char * (8 * 1024)),
        ('mac_algorithm', ctypes.c_char * 32),
        ('scope', ctypes.c_char * 1024),
    ]


class TapUserGetApprovedScopesResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('scope_count', ctypes.c_uint32),
        ('scopes', ctypes.POINTER(ctypes.c_char_p)),
    ]


class GamePlayableStatusChangedResponse(ctypes.Structure):
    _fields_ = [
        ('is_playable', ctypes.c_bool),
    ]


class DLCPlayableStatusChangedResponse(ctypes.Structure):
    _fields_ = [
        ('dlc_id', ctypes.c_char * 32),
        ('is_playable', ctypes.c_bool),
    ]


class TapDLCQueryDetailsRequest(ctypes.Structure):
    _fields_ = [
        ('id_count', ctypes.c_int32),
        ('ids', (ctypes.c_char * 32) * 50),
    ]


class TapDLCDetails(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char * 32),
        ('name', ctypes.c_char * 64),
        ('type', ctypes.c_int32),
        ('owned', ctypes.c_bool),
        ('original_price', ctypes.c_int32),
        ('discounted_price', ctypes.c_int32),
        ('discount_start_time', ctypes.c_int64),
        ('discount_end_time', ctypes.c_int64),
    ]


class TapDLCQueryDetailsResponse(ctypes.Structure):
    _fields_ = [
        ('detail_count', ctypes.c_int32),
        ('details', TapDLCDetails * 50),
    ]


# =============================================================================
# Achievements (taptap_achievement.h)
# =============================================================================


class TapAchievementInfo(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('current_steps', ctypes.c_int64),
        ('newly_unlocked', ctypes.c_bool),
    ]


class TapAchievementUnlockRequest(ctypes.Structure):
    _fields_ = [
        ('achievement_id', ctypes.c_char_p),
    ]


class TapAchievementUnlockResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('achievement', ctypes.POINTER(TapAchievementInfo)),
        ('platinum_achievement', ctypes.POINTER(TapAchievementInfo)),
    ]


class TapAchievementIncrementRequest(ctypes.Structure):
    _fields_ = [
        ('achievement_id', ctypes.c_char_p),
        ('steps', ctypes.c_int64),
    ]


class TapAchievementIncrementResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('achievement', ctypes.POINTER(TapAchievementInfo)),
        ('platinum_achievement', ctypes.POINTER(TapAchievementInfo)),
    ]


# =============================================================================
# Cloud save (taptap_cloudsave.h)
# =============================================================================


class TapCloudSaveInfo(ctypes.Structure):
    _fields_ = [
        ('uuid', ctypes.c_char_p),
        ('file_id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('save_size', ctypes.c_int32),
        ('cover_size', ctypes.c_int32),
        ('summary', ctypes.c_char_p),
        ('extra', ctypes.c_char_p),
        ('playtime', ctypes.c_int32),
        ('created_time', ctypes.c_uint32),
        ('modified_time', ctypes.c_uint32),
    ]


class TapCloudSaveListResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('save_count', ctypes.c_int32),
        ('saves', ctypes.POINTER(TapCloudSaveInfo)),
    ]


class TapCloudSaveCreateRequest(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char_p),
        ('summary', ctypes.c_char_p),
        ('extra', ctypes.c_char_p),
        ('playtime', ctypes.c_int32),
        ('data_file_path', ctypes.c_char_p),
        ('cover_file_path', ctypes.c_char_p),
    ]


class TapCloudSaveCreateResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('save', ctypes.POINTER(TapCloudSaveInfo)),
    ]


class TapCloudSaveUpdateRequest(ctypes.Structure):
    _fields_ = [
        ('uuid', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('summary', ctypes.c_char_p),
        ('extra', ctypes.c_char_p),
        ('playtime', ctypes.c_int32),
        ('data_file_path', ctypes.c_char_p),
        ('cover_file_path', ctypes.c_char_p),
    ]


#: The update response is the create response (typedef in the header).
TapCloudSaveUpdateResponse = TapCloudSaveCreateResponse


class TapCloudSaveDeleteResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('uuid', ctypes.c_char_p),
    ]


class TapCloudSaveGetFileRequest(ctypes.Structure):
    _fields_ = [
        ('uuid', ctypes.c_char_p),
        ('file_id', ctypes.c_char_p),
    ]


class TapCloudSaveGetFileResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('size', ctypes.c_int32),
        ('data', ctypes.c_void_p),
    ]


# =============================================================================
# Compliance (taptap_compliance.h)
# =============================================================================


class TapComplianceAction(ctypes.Structure):
    _fields_ = [
        ('action_type', ctypes.c_uint32),
        ('title', ctypes.c_char_p),
        ('description', ctypes.c_char_p),
        ('display_duration_seconds', ctypes.c_uint32),
    ]


class TapComplianceActionsEvent(ctypes.Structure):
    _fields_ = [
        ('count', ctypes.c_uint32),
        ('actions', ctypes.POINTER(TapComplianceAction)),
    ]


class TapComplianceEnsureRealNameResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('status', ctypes.c_uint32),
    ]


class TapComplianceCheckPaymentLimitRequest(ctypes.Structure):
    _fields_ = [
        ('amount', ctypes.c_uint32),
    ]


class TapComplianceCheckPaymentLimitResponse(ctypes.Structure):
    _fields_ = [
        ('allow', ctypes.c_bool),
        ('title', ctypes.c_char * 256),
        ('description', ctypes.c_char * 4096),
    ]


class TapComplianceSubmitPaymentRequest(ctypes.Structure):
    _fields_ = [
        ('amount', ctypes.c_uint32),
    ]


# =============================================================================
# Leaderboard (taptap_leaderboard.h)
# =============================================================================


class TapLeaderboardPeriod(ctypes.Structure):
    _fields_ = [
        ('period_token', ctypes.c_char_p),
        ('display', ctypes.c_char_p),
    ]


class TapLeaderboardUserInfo(ctypes.Structure):
    _fields_ = [
        ('open_id', ctypes.c_char_p),
        ('union_id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('avatar', ctypes.c_char_p),
    ]


class TapLeaderboardScore(ctypes.Structure):
    _fields_ = [
        ('rank', ctypes.c_uint32),
        ('score', ctypes.c_int64),
        ('user', TapLeaderboardUserInfo),
        ('score_submitted_time', ctypes.c_uint64),
    ]


class TapLeaderboardInfo(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('period', ctypes.POINTER(TapLeaderboardPeriod)),
        ('available_period_count', ctypes.c_uint32),
        ('available_periods', ctypes.POINTER(TapLeaderboardPeriod)),
    ]


class TapLeaderboardScoreItem(ctypes.Structure):
    _fields_ = [
        ('leaderboard_id', ctypes.c_char_p),
        ('score', ctypes.c_int64),
    ]


class TapLeaderboardSubmitScoresRequest(ctypes.Structure):
    _fields_ = [
        ('item_count', ctypes.c_uint32),
        ('items', ctypes.POINTER(TapLeaderboardScoreItem)),
    ]


class TapLeaderboardSubmitScoreResultData(ctypes.Structure):
    _fields_ = [
        ('new_best', ctypes.c_bool),
        ('raw_score', ctypes.c_int64),
    ]


class TapLeaderboardSubmitScoreResult(ctypes.Structure):
    _fields_ = [
        ('leaderboard_id', ctypes.c_char_p),
        ('period_token', ctypes.c_char_p),
        ('score_result', ctypes.POINTER(TapLeaderboardSubmitScoreResultData)),
        ('open_id', ctypes.c_char_p),
        ('union_id', ctypes.c_char_p),
    ]


class TapLeaderboardSubmitScoresResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('result_count', ctypes.c_uint32),
        ('results', ctypes.POINTER(TapLeaderboardSubmitScoreResult)),
    ]


class TapLeaderboardLoadScoresRequest(ctypes.Structure):
    _fields_ = [
        ('leaderboard_id', ctypes.c_char_p),
        ('collection', ctypes.c_uint32),
        ('continuation_token', ctypes.c_char_p),
        ('period_token', ctypes.c_char_p),
    ]


class TapLeaderboardLoadScoresResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('leaderboard', ctypes.POINTER(TapLeaderboardInfo)),
        ('score_count', ctypes.c_uint32),
        ('scores', ctypes.POINTER(TapLeaderboardScore)),
        ('continuation_token', ctypes.c_char_p),
        ('is_truncated', ctypes.c_bool),
    ]


class TapLeaderboardLoadMyScoresRequest(ctypes.Structure):
    _fields_ = [
        ('leaderboard_id', ctypes.c_char_p),
        ('collection', ctypes.c_uint32),
        ('period_token', ctypes.c_char_p),
    ]


class TapLeaderboardLoadMyScoresResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('leaderboard', ctypes.POINTER(TapLeaderboardInfo)),
        ('score', ctypes.POINTER(TapLeaderboardScore)),
    ]


class TapLeaderboardLoadMyCenteredScoresRequest(ctypes.Structure):
    _fields_ = [
        ('leaderboard_id', ctypes.c_char_p),
        ('collection', ctypes.c_uint32),
        ('max_results', ctypes.c_uint32),
    ]


class TapLeaderboardLoadMyCenteredScoresResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('leaderboard', ctypes.POINTER(TapLeaderboardInfo)),
        ('score_count', ctypes.c_uint32),
        ('scores', ctypes.POINTER(TapLeaderboardScore)),
    ]


class TapLeaderboardShowRequest(ctypes.Structure):
    _fields_ = [
        ('leaderboard_id', ctypes.c_char_p),
        ('collection', ctypes.c_uint32),
    ]


# =============================================================================
# Relation / friends (taptap_relation.h)
# =============================================================================


class TapRelationFollowStatus(ctypes.Structure):
    _fields_ = [
        ('following', ctypes.c_bool),
        ('followed', ctypes.c_bool),
        ('blocking', ctypes.c_bool),
        ('blocked', ctypes.c_bool),
    ]


class TapRelationFriendInfo(ctypes.Structure):
    _fields_ = [
        ('open_id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('alias', ctypes.c_char_p),
        ('avatar', ctypes.c_char_p),
        ('follow_status', TapRelationFollowStatus),
        ('created_at', ctypes.c_int64),
    ]


class TapRelationGetFriendListRequest(ctypes.Structure):
    _fields_ = [
        ('continuation_token', ctypes.c_char_p),
    ]


class TapRelationGetFriendListResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('friend_count', ctypes.c_uint32),
        ('friends', ctypes.POINTER(TapRelationFriendInfo)),
        ('continuation_token', ctypes.c_char_p),
    ]


class TapRelationGetFollowingListResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('following_count', ctypes.c_uint32),
        ('followings', ctypes.POINTER(TapRelationFriendInfo)),
        ('continuation_token', ctypes.c_char_p),
    ]


class TapRelationGetFanListResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('fan_count', ctypes.c_uint32),
        ('fans', ctypes.POINTER(TapRelationFriendInfo)),
        ('continuation_token', ctypes.c_char_p),
    ]


class TapRelationShowUserProfileRequest(ctypes.Structure):
    _fields_ = [
        ('open_id', ctypes.c_char_p),
        ('union_id', ctypes.c_char_p),
    ]


class TapRelationSyncRelationshipWithOpenIDRequest(ctypes.Structure):
    _fields_ = [
        ('action', ctypes.c_uint32),
        ('nickname', ctypes.c_char_p),
        ('friend_nickname', ctypes.c_char_p),
        ('friend_open_id', ctypes.c_char_p),
    ]


class TapRelationSyncRelationshipWithUnionIDRequest(ctypes.Structure):
    _fields_ = [
        ('action', ctypes.c_uint32),
        ('nickname', ctypes.c_char_p),
        ('friend_nickname', ctypes.c_char_p),
        ('friend_union_id', ctypes.c_char_p),
    ]


class TapRelationSyncRelationshipResponse(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
    ]


class TapRelationInviteTeamRequest(ctypes.Structure):
    _fields_ = [
        ('team_id', ctypes.c_char_p),
    ]


class TapRelationInviteReceivedNotification(ctypes.Structure):
    _fields_ = [
        ('open_id', ctypes.c_char_p),
        ('union_id', ctypes.c_char_p),
        ('team_id', ctypes.c_char_p),
    ]


class TapRelationUnreadMessageCountNotification(ctypes.Structure):
    _fields_ = [
        ('count', ctypes.c_uint32),
    ]


#: The new-fan notification is the unread-count notification (typedef).
TapRelationNewFanCountNotification = TapRelationUnreadMessageCountNotification


# =============================================================================
# Online battle (taptap_onlinebattle.h)
# =============================================================================


class TapOnlineBattleEvent(ctypes.Structure):
    _fields_ = [
        ('request_id', ctypes.c_int64),
        ('error', ctypes.POINTER(TapSDK_Error)),
        ('event_id', ctypes.c_uint32),
        ('event_data', ctypes.c_void_p),
    ]


class TapOnlineBattleConnectResponse(ctypes.Structure):
    _fields_ = [
        ('player_id', ctypes.c_char_p),
    ]


class TapOnlineBattleMatchParam(ctypes.Structure):
    _fields_ = [
        ('key', ctypes.c_char_p),
        ('value', ctypes.c_char_p),
    ]


class TapOnlineBattleRoomConfig(ctypes.Structure):
    _fields_ = [
        ('max_player_count', ctypes.c_uint32),
        ('room_type', ctypes.c_char_p),
        ('match_param_count', ctypes.c_uint32),
        ('match_params', ctypes.POINTER(TapOnlineBattleMatchParam)),
        ('name', ctypes.c_char_p),
        ('custom_properties', ctypes.c_char_p),
    ]


class TapOnlineBattlePlayerConfig(ctypes.Structure):
    _fields_ = [
        ('custom_status', ctypes.c_int32),
        ('custom_properties', ctypes.c_char_p),
    ]


class TapOnlineBattleCreateRoomRequest(ctypes.Structure):
    _fields_ = [
        ('room_cfg', TapOnlineBattleRoomConfig),
        ('player_cfg', TapOnlineBattlePlayerConfig),
    ]


class TapOnlineBattlePlayerInfo(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char_p),
        ('status', ctypes.c_int32),
        ('custom_status', ctypes.c_int32),
        ('custom_properties', ctypes.c_char_p),
    ]


class TapOnlineBattleRoomInfo(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('room_type', ctypes.c_char_p),
        ('owner_id', ctypes.c_char_p),
        ('status', ctypes.c_int32),
        ('custom_properties', ctypes.c_char_p),
        ('max_player_count', ctypes.c_uint32),
        ('player_count', ctypes.c_uint32),
        ('players', ctypes.POINTER(TapOnlineBattlePlayerInfo)),
        ('create_time', ctypes.c_int64),
    ]


class TapOnlineBattleCreateRoomResponse(ctypes.Structure):
    _fields_ = [
        ('room_info', ctypes.POINTER(TapOnlineBattleRoomInfo)),
    ]


class TapOnlineBattleMatchRoomRequest(ctypes.Structure):
    _fields_ = [
        ('room_cfg', TapOnlineBattleRoomConfig),
        ('player_cfg', TapOnlineBattlePlayerConfig),
    ]


class TapOnlineBattleMatchRoomResponse(ctypes.Structure):
    _fields_ = [
        ('room_info', ctypes.POINTER(TapOnlineBattleRoomInfo)),
    ]


class TapOnlineBattleGetRoomListRequest(ctypes.Structure):
    _fields_ = [
        ('room_type', ctypes.c_char_p),
        ('offset', ctypes.c_uint32),
        ('limit', ctypes.c_uint32),
    ]


class TapOnlineBattleRoomBasicInfo(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('room_type', ctypes.c_char_p),
        ('status', ctypes.c_int32),
        ('custom_properties', ctypes.c_char_p),
        ('max_player_count', ctypes.c_uint32),
        ('player_count', ctypes.c_uint32),
        ('create_time', ctypes.c_int64),
    ]


class TapOnlineBattleGetRoomListResponse(ctypes.Structure):
    _fields_ = [
        ('room_count', ctypes.c_uint32),
        ('rooms', ctypes.POINTER(TapOnlineBattleRoomBasicInfo)),
        ('offset', ctypes.c_uint32),
        ('has_more', ctypes.c_bool),
    ]


class TapOnlineBattleJoinRoomRequest(ctypes.Structure):
    _fields_ = [
        ('room_id', ctypes.c_char_p),
        ('player_cfg', TapOnlineBattlePlayerConfig),
    ]


class TapOnlineBattleJoinRoomResponse(ctypes.Structure):
    _fields_ = [
        ('room_info', ctypes.POINTER(TapOnlineBattleRoomInfo)),
    ]


class TapOnlineBattleUpdateRoomPropertiesRequest(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char_p),
        ('custom_properties', ctypes.c_char_p),
    ]


class TapOnlineBattleSendCustomMessageRequest(ctypes.Structure):
    _fields_ = [
        ('msg', ctypes.c_char_p),
        ('receiver_type', ctypes.c_uint32),
        ('receiver_count', ctypes.c_uint32),
        ('receivers', ctypes.POINTER(ctypes.c_char_p)),
    ]


class TapOnlineBattleSendFrameInputRequest(ctypes.Structure):
    _fields_ = [
        ('data', ctypes.c_char_p),
    ]


class TapOnlineBattlePlayerOfflineNotification(ctypes.Structure):
    _fields_ = [
        ('room_id', ctypes.c_char_p),
        ('room_owner_id', ctypes.c_char_p),
        ('player_id', ctypes.c_char_p),
    ]


class TapOnlineBattlePlayerEnterRoomNotification(ctypes.Structure):
    _fields_ = [
        ('room_id', ctypes.c_char_p),
        ('player_info', ctypes.POINTER(TapOnlineBattlePlayerInfo)),
    ]


class TapOnlineBattlePlayerLeaveRoomNotification(ctypes.Structure):
    _fields_ = [
        ('room_id', ctypes.c_char_p),
        ('room_owner_id', ctypes.c_char_p),
        ('player_id', ctypes.c_char_p),
    ]


class TapOnlineBattlePlayerCustomStatusNotification(ctypes.Structure):
    _fields_ = [
        ('player_id', ctypes.c_char_p),
        ('status', ctypes.c_int32),
    ]


class TapOnlineBattlePlayerCustomPropertiesNotification(ctypes.Structure):
    _fields_ = [
        ('player_id', ctypes.c_char_p),
        ('properties', ctypes.c_char_p),
    ]


class TapOnlineBattleRoomPropertiesNotification(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_char_p),
        ('name', ctypes.c_char_p),
        ('custom_properties', ctypes.c_char_p),
    ]


class TapOnlineBattleCustomMessageNotification(ctypes.Structure):
    _fields_ = [
        ('player_id', ctypes.c_char_p),
        ('msg', ctypes.c_char_p),
    ]


class TapOnlineBattleRoomPlayerKickedNotification(ctypes.Structure):
    _fields_ = [
        ('room_id', ctypes.c_char_p),
        ('player_id', ctypes.c_char_p),
    ]


class TapOnlineBattleFrameSyncStartNotification(ctypes.Structure):
    _fields_ = [
        ('room_info', ctypes.POINTER(TapOnlineBattleRoomInfo)),
        ('frame_sync_id', ctypes.c_int32),
        ('seed', ctypes.c_int32),
        ('server_tms', ctypes.c_int64),
    ]


class TapOnlineBattleFrameInput(ctypes.Structure):
    _fields_ = [
        ('player_id', ctypes.c_char_p),
        ('data', ctypes.c_char_p),
        ('server_tms', ctypes.c_int64),
    ]


class TapOnlineBattleFrame(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_uint32),
        ('input_count', ctypes.c_uint32),
        ('inputs', ctypes.POINTER(TapOnlineBattleFrameInput)),
    ]


class TapOnlineBattleFrameSyncStopNotification(ctypes.Structure):
    _fields_ = [
        ('room_id', ctypes.c_char_p),
        ('frame_sync_id', ctypes.c_int32),
        ('reason', ctypes.c_int32),
    ]


#: Callback types (kept alive by the dispatcher for as long as they're registered).
MainCallback = ctypes.CFUNCTYPE(None, ctypes.c_uint32, ctypes.c_void_p)
OnlineBattleCallback = ctypes.CFUNCTYPE(None, ctypes.POINTER(TapOnlineBattleEvent))


# =============================================================================
# Helpers
# =============================================================================


def encode(value):
    """UTF-8 bytes for a ``const char*`` argument (None passes NULL)."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return str(value).encode('utf-8')


def text(pointer):
    """UTF-8 string behind a raw ``const char*`` (None when NULL)."""
    if not pointer:
        return None
    raw = ctypes.cast(pointer, ctypes.c_char_p).value
    return None if raw is None else raw.decode('utf-8', 'replace')


def _decode(value):
    """str from a ``c_char_p`` field value (None stays None)."""
    if value is None:
        return None
    return value.decode('utf-8', 'replace')


def _decode_fixed(value):
    """str from a fixed ``char[N]`` field - ctypes reads those as bytes."""
    if value is None:
        return ''
    return value.decode('utf-8', 'replace')


def parse_error(pointer):
    """``{'code', 'message'}`` of a ``TapSDK_Error*`` (None when NULL)."""
    if not pointer:
        return None
    error = pointer.contents
    return {'code': int(error.code), 'message': _decode(error.message)}


def _parse_achievement_info(pointer):
    if not pointer:
        return None
    info = pointer.contents
    return {
        'id': _decode(info.id),
        'name': _decode(info.name),
        'current_steps': int(info.current_steps),
        'newly_unlocked': bool(info.newly_unlocked),
    }


def parse_system_state(pointer):
    """TapSystemStateNotification -> dict (detail parsed for DupGameSession)."""
    if not pointer:
        return None
    notification = ctypes.cast(pointer, ctypes.POINTER(TapSystemStateNotification)).contents
    result = {'state': int(notification.state)}
    if notification.detail and int(notification.state) == 4:      # DupGameSession
        session = ctypes.cast(notification.detail,
                              ctypes.POINTER(TapSystemStateNotificationGameSessionInfo)).contents
        result['device_name'] = _decode(session.device_name)
    return result


def parse_authorize_finished(pointer):
    """AuthorizeFinishedResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(AuthorizeFinishedResponse)).contents
    return {
        'is_cancel': bool(response.is_cancel),
        'error': _decode_fixed(response.error),
        'token_type': _decode_fixed(response.token_type),
        'kid': _decode_fixed(response.kid),
        'mac_key': _decode_fixed(response.mac_key),
        'mac_algorithm': _decode_fixed(response.mac_algorithm),
        'scope': _decode_fixed(response.scope),
    }


def parse_approved_scopes(pointer):
    """TapUserGetApprovedScopesResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapUserGetApprovedScopesResponse)).contents
    scopes = [text(response.scopes[index]) for index in range(response.scope_count)] \
        if response.scopes else []
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'scopes': scopes,
    }


def parse_game_playable(pointer):
    response = ctypes.cast(pointer, ctypes.POINTER(GamePlayableStatusChangedResponse)).contents
    return {'is_playable': bool(response.is_playable)}


def parse_dlc_playable(pointer):
    response = ctypes.cast(pointer, ctypes.POINTER(DLCPlayableStatusChangedResponse)).contents
    return {'dlc_id': _decode_fixed(response.dlc_id), 'is_playable': bool(response.is_playable)}


def parse_achievement_unlock(pointer):
    """TapAchievementUnlockResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapAchievementUnlockResponse)).contents
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'achievement': _parse_achievement_info(response.achievement),
        'platinum_achievement': _parse_achievement_info(response.platinum_achievement),
    }


def parse_achievement_increment(pointer):
    """TapAchievementIncrementResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapAchievementIncrementResponse)).contents
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'achievement': _parse_achievement_info(response.achievement),
        'platinum_achievement': _parse_achievement_info(response.platinum_achievement),
    }


def _parse_save_info(info):
    return {
        'uuid': _decode(info.uuid),
        'file_id': _decode(info.file_id),
        'name': _decode(info.name),
        'save_size': int(info.save_size),
        'cover_size': int(info.cover_size),
        'summary': _decode(info.summary),
        'extra': _decode(info.extra),
        'playtime': int(info.playtime),
        'created_time': int(info.created_time),
        'modified_time': int(info.modified_time),
    }


def parse_cloud_save_list(pointer):
    """TapCloudSaveListResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapCloudSaveListResponse)).contents
    saves = [_parse_save_info(response.saves[index]) for index in range(response.save_count)] \
        if response.saves else []
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'saves': saves,
    }


def parse_cloud_save_created(pointer):
    """TapCloudSaveCreate/UpdateResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapCloudSaveCreateResponse)).contents
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'save': _parse_save_info(response.save.contents) if response.save else None,
    }


def parse_cloud_save_deleted(pointer):
    """TapCloudSaveDeleteResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapCloudSaveDeleteResponse)).contents
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'uuid': _decode(response.uuid),
    }


def parse_cloud_save_file(pointer):
    """TapCloudSaveGetFileResponse -> dict (the bytes are copied here)."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapCloudSaveGetFileResponse)).contents
    data = b''
    if response.data and int(response.size) > 0:
        data = ctypes.string_at(response.data, int(response.size))
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'size': int(response.size),
        'data': data,
    }


def parse_real_name_result(pointer):
    """TapComplianceEnsureRealNameResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapComplianceEnsureRealNameResponse)).contents
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'status': int(response.status),
    }


def parse_compliance_actions(pointer):
    """TapComplianceActionsEvent -> dict."""
    event = ctypes.cast(pointer, ctypes.POINTER(TapComplianceActionsEvent)).contents
    actions = []
    if event.actions:
        for index in range(event.count):
            action = event.actions[index]
            actions.append({
                'action_type': int(action.action_type),
                'title': _decode(action.title),
                'description': _decode(action.description),
                'display_duration_seconds': int(action.display_duration_seconds),
            })
    return {'actions': actions}


def _parse_period(period):
    return {'period_token': _decode(period.period_token), 'display': _decode(period.display)}


def _parse_leaderboard_info(pointer):
    if not pointer:
        return None
    info = pointer.contents
    periods = [_parse_period(info.available_periods[index])
               for index in range(info.available_period_count)] if info.available_periods else []
    return {
        'id': _decode(info.id),
        'name': _decode(info.name),
        'period': _parse_period(info.period.contents) if info.period else None,
        'available_periods': periods,
    }


def _parse_leaderboard_user(user):
    return {
        'open_id': _decode(user.open_id),
        'union_id': _decode(user.union_id),
        'name': _decode(user.name),
        'avatar': _decode(user.avatar),
    }


def _parse_leaderboard_score(score):
    return {
        'rank': int(score.rank),
        'score': int(score.score),
        'user': _parse_leaderboard_user(score.user),
        'score_submitted_time': int(score.score_submitted_time),
    }


def parse_leaderboard_submitted(pointer):
    """TapLeaderboardSubmitScoresResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapLeaderboardSubmitScoresResponse)).contents
    results = []
    if response.results:
        for index in range(response.result_count):
            result = response.results[index]
            data = None
            if result.score_result:
                entry = result.score_result.contents
                data = {'new_best': bool(entry.new_best), 'raw_score': int(entry.raw_score)}
            results.append({
                'leaderboard_id': _decode(result.leaderboard_id),
                'period_token': _decode(result.period_token),
                'result': data,
                'open_id': _decode(result.open_id),
                'union_id': _decode(result.union_id),
            })
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'results': results,
    }


def parse_leaderboard_loaded(pointer):
    """TapLeaderboardLoadScoresResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapLeaderboardLoadScoresResponse)).contents
    scores = [_parse_leaderboard_score(response.scores[index])
              for index in range(response.score_count)] if response.scores else []
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'leaderboard': _parse_leaderboard_info(response.leaderboard),
        'scores': scores,
        'continuation_token': _decode(response.continuation_token),
        'is_truncated': bool(response.is_truncated),
    }


def parse_leaderboard_my_scores(pointer):
    """TapLeaderboardLoadMyScoresResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapLeaderboardLoadMyScoresResponse)).contents
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'leaderboard': _parse_leaderboard_info(response.leaderboard),
        'score': _parse_leaderboard_score(response.score.contents) if response.score else None,
    }


def parse_leaderboard_centered(pointer):
    """TapLeaderboardLoadMyCenteredScoresResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapLeaderboardLoadMyCenteredScoresResponse)).contents
    scores = [_parse_leaderboard_score(response.scores[index])
              for index in range(response.score_count)] if response.scores else []
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'leaderboard': _parse_leaderboard_info(response.leaderboard),
        'scores': scores,
    }


def _parse_friend(info):
    return {
        'open_id': _decode(info.open_id),
        'name': _decode(info.name),
        'alias': _decode(info.alias),
        'avatar': _decode(info.avatar),
        'follow_status': {
            'following': bool(info.follow_status.following),
            'followed': bool(info.follow_status.followed),
            'blocking': bool(info.follow_status.blocking),
            'blocked': bool(info.follow_status.blocked),
        },
        'created_at': int(info.created_at),
    }


def _parse_friend_list_response(pointer, structure, count_field, array_field):
    response = ctypes.cast(pointer, ctypes.POINTER(structure)).contents
    array = getattr(response, array_field)
    entries = [_parse_friend(array[index]) for index in range(getattr(response, count_field))] \
        if array else []
    return {
        'request_id': int(response.request_id),
        'error': parse_error(response.error),
        'friends': entries,
        'continuation_token': _decode(response.continuation_token),
    }


def parse_relation_friends(pointer):
    """TapRelationGetFriendListResponse -> dict."""
    return _parse_friend_list_response(pointer, TapRelationGetFriendListResponse,
                                       'friend_count', 'friends')


def parse_relation_following(pointer):
    """TapRelationGetFollowingListResponse -> dict."""
    return _parse_friend_list_response(pointer, TapRelationGetFollowingListResponse,
                                       'following_count', 'followings')


def parse_relation_fans(pointer):
    """TapRelationGetFanListResponse -> dict."""
    return _parse_friend_list_response(pointer, TapRelationGetFanListResponse,
                                       'fan_count', 'fans')


def parse_relation_sync(pointer):
    """TapRelationSyncRelationshipResponse -> dict."""
    response = ctypes.cast(pointer, ctypes.POINTER(TapRelationSyncRelationshipResponse)).contents
    return {'request_id': int(response.request_id), 'error': parse_error(response.error)}


def parse_relation_invite(pointer):
    """TapRelationInviteReceivedNotification -> dict."""
    notification = ctypes.cast(pointer, ctypes.POINTER(TapRelationInviteReceivedNotification)).contents
    return {
        'open_id': _decode(notification.open_id),
        'union_id': _decode(notification.union_id),
        'team_id': _decode(notification.team_id),
    }


def parse_relation_count(pointer):
    """TapRelationUnreadMessageCountNotification -> dict."""
    notification = ctypes.cast(pointer, ctypes.POINTER(TapRelationUnreadMessageCountNotification)).contents
    return {'count': int(notification.count)}


# =============================================================================
# Online battle payloads
# =============================================================================


def _parse_player_info(info):
    """TapOnlineBattlePlayerInfo (struct by value / from an array) -> dict."""
    return {
        'player_id': _decode(info.id),
        'status': int(info.status),
        'custom_status': int(info.custom_status),
        'custom_properties': _decode(info.custom_properties),
    }


def _parse_room_info(pointer):
    if not pointer:
        return None
    info = pointer.contents
    players = [_parse_player_info(info.players[index])
               for index in range(info.player_count)] if info.players else []
    return {
        'room_id': _decode(info.id),
        'name': _decode(info.name),
        'room_type': _decode(info.room_type),
        'owner_id': _decode(info.owner_id),
        'status': int(info.status),
        'custom_properties': _decode(info.custom_properties),
        'max_player_count': int(info.max_player_count),
        'player_count': int(info.player_count),
        'players': players,
        'create_time': int(info.create_time),
    }


def _parse_room_basic(info):
    """TapOnlineBattleRoomBasicInfo (struct from an array) -> dict."""
    return {
        'room_id': _decode(info.id),
        'name': _decode(info.name),
        'room_type': _decode(info.room_type),
        'status': int(info.status),
        'custom_properties': _decode(info.custom_properties),
        'max_player_count': int(info.max_player_count),
        'player_count': int(info.player_count),
        'create_time': int(info.create_time),
    }


def _parse_ob_connect(pointer):
    response = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleConnectResponse)).contents
    return {'player_id': _decode(response.player_id)}


def _parse_ob_room(pointer):
    response = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleCreateRoomResponse)).contents
    return {'room': _parse_room_info(response.room_info)}


def _parse_ob_room_list(pointer):
    response = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleGetRoomListResponse)).contents
    rooms = [_parse_room_basic(response.rooms[index])
             for index in range(response.room_count)] if response.rooms else []
    return {'rooms': rooms, 'offset': int(response.offset), 'has_more': bool(response.has_more)}


def _parse_ob_player_offline(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattlePlayerOfflineNotification)).contents
    return {
        'room_id': _decode(data.room_id),
        'room_owner_id': _decode(data.room_owner_id),
        'player_id': _decode(data.player_id),
    }


def _parse_ob_player_enter(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattlePlayerEnterRoomNotification)).contents
    player = _parse_player_info(data.player_info.contents) if data.player_info else None
    return {'room_id': _decode(data.room_id), 'player': player}


def _parse_ob_player_leave(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattlePlayerLeaveRoomNotification)).contents
    return {
        'room_id': _decode(data.room_id),
        'room_owner_id': _decode(data.room_owner_id),
        'player_id': _decode(data.player_id),
    }


def _parse_ob_player_status(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattlePlayerCustomStatusNotification)).contents
    return {'player_id': _decode(data.player_id), 'status': int(data.status)}


def _parse_ob_player_properties(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattlePlayerCustomPropertiesNotification)).contents
    return {'player_id': _decode(data.player_id), 'properties': _decode(data.properties)}


def _parse_ob_room_properties(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleRoomPropertiesNotification)).contents
    return {
        'room_id': _decode(data.id),
        'name': _decode(data.name),
        'custom_properties': _decode(data.custom_properties),
    }


def _parse_ob_message(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleCustomMessageNotification)).contents
    return {'player_id': _decode(data.player_id), 'msg': _decode(data.msg)}


def _parse_ob_kicked(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleRoomPlayerKickedNotification)).contents
    return {'room_id': _decode(data.room_id), 'player_id': _decode(data.player_id)}


def _parse_ob_frame_sync_start(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleFrameSyncStartNotification)).contents
    return {
        'room': _parse_room_info(data.room_info),
        'frame_sync_id': int(data.frame_sync_id),
        'seed': int(data.seed),
        'server_tms': int(data.server_tms),
    }


def _parse_ob_frame(pointer):
    frame = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleFrame)).contents
    inputs = []
    if frame.inputs:
        for index in range(frame.input_count):
            entry = frame.inputs[index]
            inputs.append({
                'player_id': _decode(entry.player_id),
                'data': _decode(entry.data),
                'server_tms': int(entry.server_tms),
            })
    return {'frame_id': int(frame.id), 'inputs': inputs}


def _parse_ob_frame_sync_stop(pointer):
    data = ctypes.cast(pointer, ctypes.POINTER(TapOnlineBattleFrameSyncStopNotification)).contents
    return {
        'room_id': _decode(data.room_id),
        'frame_sync_id': int(data.frame_sync_id),
        'reason': int(data.reason),
    }


#: event_data parser per TapOnlineBattleEventID (missing = no payload).
ONLINE_BATTLE_DATA_PARSERS = {
    1: _parse_ob_connect,
    3: _parse_ob_room,
    4: _parse_ob_room,
    5: _parse_ob_room_list,
    6: _parse_ob_room,
    1002: _parse_ob_player_offline,
    1003: _parse_ob_player_enter,
    1004: _parse_ob_player_leave,
    1005: _parse_ob_player_status,
    1006: _parse_ob_player_properties,
    1007: _parse_ob_room_properties,
    1008: _parse_ob_message,
    1009: _parse_ob_kicked,
    1010: _parse_ob_frame_sync_start,
    1011: _parse_ob_frame,
    1012: _parse_ob_frame_sync_stop,
}


def parse_online_battle_event(pointer):
    """TapOnlineBattleEvent* -> {'request_id', 'error', 'event_id', 'data'}."""
    event = pointer.contents
    event_id = int(event.event_id)
    parser = ONLINE_BATTLE_DATA_PARSERS.get(event_id)
    data = parser(event.event_data) if parser and event.event_data else None
    return {
        'request_id': int(event.request_id),
        'error': parse_error(event.error),
        'event_id': event_id,
        'data': data,
    }
