"""Enums of the TapTap PC SDK (mirrors the v4.6.1 headers name for name).

Every enum is a plain ``IntEnum``: the values are exactly the numbers the DLL
returns, and they still compare equal to plain ints (so payloads can carry
ints and user code can compare against these members).
"""

from enum import IntEnum


class InitResult(IntEnum):
    """TapSDK_Init() result (TapSDK_Init_Result)."""

    OK = 0
    FailedGeneric = 1
    NoPlatform = 2                     # TapTap client not found
    NotLaunchedByPlatform = 3          # started without the TapTap client
    PlatformVersionMismatch = 4        # user should update TapTap / the game


class AuthorizeResult(IntEnum):
    """Immediate result of user.login() (TapUser_AsyncAuthorize_Result)."""

    Unknown = 0                        # SDK not initialized
    OK = 1                             # flow started, wait for authorize_finished
    Failed = 2
    InFlight = 3                       # a previous authorize is still running


class Result(IntEnum):
    """General immediate call result (TapSDK_Result)."""

    OK = 0
    Uninitialized = 1
    NoTapTapClient = 2
    TapTapClientOutdated = 3
    InvalidArgument = 4
    SdkFailed = 5
    TapTapClientNotLoggedIn = 6
    UnknownError = 7
    NetworkError = 8
    ForbiddenError = 9


class ErrorCode(IntEnum):
    """Error code inside a response payload (TapSDK_ErrorCode)."""

    Success = 0
    Unknown = 1
    Unauthorized = 2                   # log in again
    MethodNotAllowed = 3
    Unimplemented = 4
    InvalidArguments = 5
    Forbidden = 6
    UserIsDeactivated = 7
    InternalServerError = 8
    InternalSdkError = 9
    NetworkError = 10
    NotFound = 11
    InsufficientScope = 12

    CloudSave_InvalidFileSize = 400000
    CloudSave_UploadRateLimit = 400001
    CloudSave_FileNotFound = 400002
    CloudSave_FileCountLimitPerClient = 400003
    CloudSave_StorageSizeLimitPerClient = 400004
    CloudSave_TotalStorageSizeLimit = 400005
    CloudSave_Timeout = 400006
    CloudSave_ConcurrentCallDisallowed = 400007
    CloudSave_StorageServerError = 400008
    CloudSave_InvalidName = 400009

    Leaderboard_PeriodExpired = 500000
    Leaderboard_NotFound = 500001
    Leaderboard_InvalidArgument = 500002

    OnlineBattle_RequestRateLimitExceeded = 600001
    OnlineBattle_MaliciousUser = 600002
    OnlineBattle_TooManyConnections = 600003
    OnlineBattle_InvalidAuthorization = 600004
    OnlineBattle_Unauthorized = 600005
    OnlineBattle_AlreadyConnected = 600006
    OnlineBattle_PreviousRequestInProgress = 600007
    OnlineBattle_NotInRoom = 600009
    OnlineBattle_AlreadyInRoom = 600010
    OnlineBattle_NotRoomOwner = 600011
    OnlineBattle_RoomFull = 600012
    OnlineBattle_RoomNotExist = 600013
    OnlineBattle_FrameSyncNotStarted = 600014
    OnlineBattle_FrameSyncAlreadyStarted = 600015
    OnlineBattle_FrameInputSizeLimitExceeded = 600016
    OnlineBattle_FrameInputCountLimitExceeded = 600017
    OnlineBattle_PlayerNotFound = 600018


class Event(IntEnum):
    """Registered main-SDK events (TapEventID)."""

    SystemStateChanged = 1
    AuthorizeFinished = 2002
    UserGetApprovedScopes = 2003
    GamePlayableStatusChanged = 4001
    DLCPlayableStatusChanged = 4002
    CloudSaveList = 6001
    CloudSaveCreate = 6002
    CloudSaveUpdate = 6003
    CloudSaveDelete = 6004
    CloudSaveGetData = 6005
    CloudSaveGetCover = 6006
    AchievementUnlock = 7001
    AchievementIncrement = 7002
    ComplianceEnsureRealName = 8001
    ComplianceActions = 8002
    LeaderboardSubmitScores = 9001
    LeaderboardLoadScores = 9002
    LeaderboardLoadMyScores = 9003
    LeaderboardLoadMyCenteredScores = 9004
    RelationGetFriendList = 10001
    RelationGetFollowingList = 10002
    RelationGetFanList = 10003
    RelationSyncRelationshipWithOpenID = 10004
    RelationSyncRelationshipWithUnionID = 10005
    RelationUnreadMessageCountChanged = 10101
    RelationNewFanCountChanged = 10102
    RelationGameInviteReceived = 10103
    RelationTeamInviteReceived = 10104


class SystemState(IntEnum):
    """TapTap client state (TapSystemState)."""

    Unknown = 0
    PlatformOnline = 1
    PlatformOffline = 2
    PlatformShutdown = 3               # save the game and quit
    DupGameSession = 4                 # started again on another device


class CloudSaveResult(IntEnum):
    """Immediate result of a cloud save call (TapCloudSave_Result)."""

    OK = 0
    Uninitialized = 1
    NoTapTapClient = 2
    TapTapClientOutdated = 3
    InvalidArgument = 4
    SdkFailed = 5
    FailedToReadSaveFile = 6
    SaveFileTooLarge = 7               # over 10 MB
    FailedToReadCoverFile = 8
    CoverFileTooLarge = 9              # over 512 KB


class ComplianceActionType(IntEnum):
    """Anti-addiction popup action (TapComplianceActionType)."""

    None_ = 0
    Toast = 1
    Alert = 2
    Exit = 3


class RealNameStatus(IntEnum):
    """Result of compliance.ensure_real_name() (TapComplianceRealNameStatus)."""

    None_ = 0
    Success = 1
    Canceled = 2
    Failed = 3


class LeaderboardCollection(IntEnum):
    """TapLeaderboardCollection."""

    Public = 0
    Friends = 1


class RelationAction(IntEnum):
    """Friend sync action (TapRelation_SyncRelationshipActionType)."""

    Add = 0
    Remove = 1


class OnlineBattleEvent(IntEnum):
    """Online battle event ids (TapOnlineBattleEventID)."""

    # Responses to async requests.
    ConnectResponse = 1
    DisconnectResponse = 2
    CreateRoomResponse = 3
    MatchRoomResponse = 4
    GetRoomListResponse = 5
    JoinRoomResponse = 6
    LeaveRoomResponse = 7
    UpdatePlayerCustomStatusResponse = 8
    UpdatePlayerCustomPropertiesResponse = 9
    UpdateRoomPropertiesResponse = 10
    SendCustomMessageResponse = 11
    KickRoomPlayerResponse = 12
    StartFrameSyncResponse = 13
    SendFrameInputResponse = 14
    StopFrameSyncResponse = 15

    # Server-pushed notifications.
    ServiceErrorNotification = 1000
    DisconnectNotification = 1001
    PlayerOfflineNotification = 1002
    PlayerEnterRoomNotification = 1003
    PlayerLeaveRoomNotification = 1004
    PlayerCustomStatusNotification = 1005
    PlayerCustomPropertiesNotification = 1006
    RoomPropertiesNotification = 1007
    CustomMessageNotification = 1008
    RoomPlayerKickedNotification = 1009
    FrameSyncStartNotification = 1010
    FrameNotification = 1011
    FrameSyncStopNotification = 1012
