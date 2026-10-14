#ifndef TAPSDK_H
#define TAPSDK_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
#define T_API extern "C"
#else
#define T_API
#endif

#ifdef _WIN32
#define T_CALLTYPE __cdecl
#else
#define T_CALLTYPE
#endif

//------------------------------------------------------------------------------
// 常量定义
//------------------------------------------------------------------------------

#ifdef __cplusplus

// SDK 初始化结果枚举
enum class TapSDK_Init_Result : uint32_t {
    OK = 0,                     // 初始化成功
    FailedGeneric = 1,          // 其他错误
    NoPlatform = 2,             // 未找到 TapTap 平台
    NotLaunchedByPlatform = 3,  // 未通过 TapTap 启动
    PlatformVersionMismatch = 4 // 平台版本不匹配，请引导用户升级 TapTap 与游戏至最新版本，再重新运行游戏
};

// 授权结果枚举
enum class TapUser_AsyncAuthorize_Result : uint32_t {
    Unknown = 0,    // 未知错误，无法请求授权，请检查 SDK 是否完成初始化 (调用 TapSDK_Init 并返回 TapSDK_Init_Result::OK)
    OK = 1,         // 成功发起授权流程，等待用户确认或者自动授权完成（此时授权流程还未完成）
    Failed = 2,     // 发起授权流程失败，可能的原因：1. 用户网络问题，2. TapTap 平台内部错误。请引导用户稍后重试
    InFlight = 3    // 授权流程正在执行中，请等待授权流程完成
};

#else

// SDK 初始化结果枚举值
enum {
    TapSDK_Init_Result_OK = 0,                      // 初始化成功
    TapSDK_Init_Result_FailedGeneric = 1,           // 其他错误
    TapSDK_Init_Result_NoPlatform = 2,              // 未找到 TapTap 平台
    TapSDK_Init_Result_NotLaunchedByPlatform = 3,   // 未通过 TapTap 启动
    TapSDK_Init_Result_PlatformVersionMismatch = 4  // 平台版本不匹配，请引导用户升级 TapTap 与游戏至最新版本，再重新运行游戏
};
// SDK 初始化结果，取值请参考枚举值 TapSDK_Init_Result_*
typedef uint32_t TapSDK_Init_Result;

// 授权结果枚举值
enum {
    TapUser_AsyncAuthorize_Result_Unknown = 0, // 未知错误，无法请求授权，请检查 SDK 是否完成初始化 (调用 TapSDK_Init 并返回 TapSDK_Init_Result::OK)
    TapUser_AsyncAuthorize_Result_OK = 1,      // 成功发起授权流程，等待用户确认或者自动授权完成（此时授权流程还未完成）
    TapUser_AsyncAuthorize_Result_Failed = 2,  // 发起授权流程失败，可能的原因：1. 用户网络问题，2. TapTap 平台内部错误。请引导用户稍后重试
    TapUser_AsyncAuthorize_Result_InFlight = 3 // 授权流程正在执行中，请等待授权流程完成
};
// 授权结果，取值请参考枚举值 TapUser_AsyncAuthorize_Result_*
typedef uint32_t TapUser_AsyncAuthorize_Result;

#endif

// 长度、个数、数值大小等限制
enum {
	TapDLC_IdMaxLength = 32,   // DLC ID最大长度，包括'\0'
	TapDLC_NameMaxLength = 64, // DLC 名称最大长度，包括'\0'
	TapDLC_MaxRequestedIdCount = 50, // 一次请求最多允许DLC ID个数。当前代码限制20，但数组定义成50，便于以后扩展
};

// TapSDK 接口返回值枚举值
enum {
	// [0, 1000) 预留给通用错误
	TapSDK_Result_OK = 0,
	TapSDK_Result_Uninitialized = 1, // SDK 未初始化，请调用 TapSDK_Init 并确保返回为 TapSDK_Init_Result::OK
	TapSDK_Result_NoTapTapClient = 2, // TapTap 客户端尚未运行
	TapSDK_Result_TapTapClientOutdated = 3, // TapTap 客户端版本过旧，请引导用户更新最新版 TapTap 客户端
	TapSDK_Result_InvalidArgument = 4, // 参数错误，比如不允许 NULL 的参数传了 NULL
	TapSDK_Result_SdkFailed = 5, // SDK内部错误
	TapSDK_Result_TapTapClientNotLoggedIn = 6, // TapTap 客户端未登录
	TapSDK_Result_UnknownError = 7, // 未知错误
	TapSDK_Result_NetworkError = 8, // 网络错误
	TapSDK_Result_ForbiddenError = 9, // 用户没有当前动作的权限（如对应游戏服务未开通）
};
// TapSDK 接口返回值，取值请参考枚举值 TapSDK_Result_*
//   - 注意：由于历史原因，部分接口（如初始化、授权、云存档）的返回值不是 TapSDK_Result 类型，请参考对应接口的文档说明
typedef uint32_t TapSDK_Result;

// 错误码枚举值
enum {
	TapSDK_ErrorCode_Success = 0,              // 请求执行成功
	TapSDK_ErrorCode_Unknown = 1,              // 未知错误
	TapSDK_ErrorCode_Unauthorized = 2,         // 用户凭证失效，请引导用户重新登录 TapTap
	TapSDK_ErrorCode_MethodNotAllowed = 3,     // 不允许的接口请求
	TapSDK_ErrorCode_Unimplemented = 4,        // 接口未实现
	TapSDK_ErrorCode_InvalidArguments = 5,     // 参数错误
	TapSDK_ErrorCode_Forbidden = 6,            // 用户没有当前动作的权限
	TapSDK_ErrorCode_UserIsDeactivated = 7,    // 用户被冻结
	TapSDK_ErrorCode_InternalServerError = 8,  // 服务器内部错误
	TapSDK_ErrorCode_InternalSdkError = 9,     // SDK内部错误
	TapSDK_ErrorCode_NetworkError = 10,        // 网络错误
	TapSDK_ErrorCode_NotFound = 11,            // 数据不存在
	TapSDK_ErrorCode_InsufficientScope = 12,   // 当前用户未授权获取此产品/服务，提示权限不足

	// reserved 200000 ~ 299999 防沉迷使用

	// reserved 400000 ~ 499999 云存档使用
	TapSDK_ErrorCode_CloudSave_InvalidFileSize = 400000,               // 非法的存档文件/封面大小
	TapSDK_ErrorCode_CloudSave_UploadRateLimit = 400001,               // 存档上传频率超限
	TapSDK_ErrorCode_CloudSave_FileNotFound = 400002,                  // 存档文件不存在
	TapSDK_ErrorCode_CloudSave_FileCountLimitPerClient = 400003,       // 用户在该应用下存档文件数量超限
	TapSDK_ErrorCode_CloudSave_StorageSizeLimitPerClient = 400004,     // 用户在该应用下使用存储空间超限
	TapSDK_ErrorCode_CloudSave_TotalStorageSizeLimit = 400005,         // 用户总使用存储空间超限
	TapSDK_ErrorCode_CloudSave_Timeout = 400006,                       // 请求超时，通常是由于网络卡顿，创建/更新存档耗时过长导致
	TapSDK_ErrorCode_CloudSave_ConcurrentCallDisallowed = 400007,      // 不允许并发调用的请求
	TapSDK_ErrorCode_CloudSave_StorageServerError = 400008,            // 存储服务故障
	TapSDK_ErrorCode_CloudSave_InvalidName = 400009,                   // 存档名称不合法

	// reserved 500000 ~ 599999 排行榜使用
	TapSDK_ErrorCode_Leaderboard_PeriodExpired       = 500000, // 排行榜周期已过期，提示用户查看其他周期
	TapSDK_ErrorCode_Leaderboard_NotFound            = 500001, // 排行榜 ID 未找到，检查 ID 是否正确
	TapSDK_ErrorCode_Leaderboard_InvalidArgument     = 500002, // 参数错误，如 leaderboard_id 与 client_id 不匹配

	// 联机游戏：600000 ~ 699999
	TapSDK_ErrorCode_OnlineBattle_RequestRateLimitExceeded     = 600001, // 请求频率超限
	TapSDK_ErrorCode_OnlineBattle_MaliciousUser                = 600002, // 被认定为恶意用户，拒绝请求或关闭连接。建议不要重连
	TapSDK_ErrorCode_OnlineBattle_TooManyConnections           = 600003, // 因同时连接数过多而被踢下线。建议不要重连，避免互踢，导致重连死循环
	TapSDK_ErrorCode_OnlineBattle_InvalidAuthorization         = 600004, // 认证信息不合法，通常不会发生。如果发生，可以尝试重连
	TapSDK_ErrorCode_OnlineBattle_Unauthorized                 = 600005, // 尚未完成建连认证，通常不会发生。如果发生，可以尝试重连
	TapSDK_ErrorCode_OnlineBattle_AlreadyConnected             = 600006, // 已经建连，不能重复建连。Connect成功后，二次调用Connect会返回此错误
	TapSDK_ErrorCode_OnlineBattle_PreviousRequestInProgress    = 600007, // 上一个请求未完成，不接受新的请求
	TapSDK_ErrorCode_OnlineBattle_NotInRoom                    = 600009, // 尚未加入房间
	TapSDK_ErrorCode_OnlineBattle_AlreadyInRoom                = 600010, // 已经在房间中，不能重复加入
	TapSDK_ErrorCode_OnlineBattle_NotRoomOwner                 = 600011, // 不是房主，不能执行此操作
	TapSDK_ErrorCode_OnlineBattle_RoomFull                     = 600012, // 房间已满，不能加入
	TapSDK_ErrorCode_OnlineBattle_RoomNotExist                 = 600013, // 房间不存在
	TapSDK_ErrorCode_OnlineBattle_FrameSyncNotStarted          = 600014, // 帧同步未开始，不能执行此操作
	TapSDK_ErrorCode_OnlineBattle_FrameSyncAlreadyStarted      = 600015, // 帧同步已开始，不能执行此操作
	TapSDK_ErrorCode_OnlineBattle_FrameInputSizeLimitExceeded  = 600016, // 对战帧数据大小超过限制
	TapSDK_ErrorCode_OnlineBattle_FrameInputCountLimitExceeded = 600017, // 每帧可接受的输入数量超过限制
	TapSDK_ErrorCode_OnlineBattle_PlayerNotFound               = 600018  // 玩家不存在
};
// 错误码，取值请参考枚举值 TapSDK_ErrorCode_*
typedef int64_t TapSDK_ErrorCode;

// TapPC系统状态枚举
enum {
	TapSystemState_Unknown = 0,

	// TapTap客户端当前可以正常访问TapTap服务端。
	// 开发者收到这个状态通知时，可以解除之前收到TapSystemState_PlatformOffline状态通知时对游戏做的限制。
	TapSystemState_PlatformOnline = 1,
	// TapTap客户端当前无法访问TapTap服务端：网络异常或者TapTap服务端故障。
	// 当TapTap客户端处于这个状态时，无法实时获得游戏/DLC所有权变化通知，比如已退款。
	// 开发者收到这个状态通知时，可以提醒玩家检查网络状态，或者做其他游戏限制。
	TapSystemState_PlatformOffline = 2,
	// TapTap客户端退出。
	// 开发者收到这个状态通知时，应该立刻保存游戏存档，然后退出游戏。
	TapSystemState_PlatformShutdown = 3,
	// 同一用户在多个设备启动同一游戏时，较早启动的游戏进程会收到该状态通知。
	// 收到该通知时，可以用结构体 TapSystemStateNotificationGameSessionInfo
	// 解析 TapSystemStateNotification::detail，获取最新启动的游戏会话的信息，比如设备名称
	TapSystemState_DupGameSession = 4,
};
// TapPC系统状态，取值请参考枚举值TapSystemState_*
typedef uint32_t TapSystemState;

//------------------------------------------------------------------------------
// 基础类型定义
//------------------------------------------------------------------------------

typedef char ErrMsg[1024];       // 错误信息，最大长度 1023 字节 + '\0'

//------------------------------------------------------------------------------
// 回调相关定义
//------------------------------------------------------------------------------

#ifdef __cplusplus

// 事件 ID 枚举
enum class TapEventID : uint32_t {
  Unknown = 0,

  // [1, 2000), reserved for TapTap platform events

  // TapTap客户端系统状态变化通知，SDK初始化成功后注册此事件的回调函数，以便及时获知TapTap客户端状态变化
  // 使用 TapSystemStateNotification 结构体解析
  SystemStateChanged = 1,

  // [2001, 4000), reserved for TapTap user events
  AuthorizeFinished = 2002,
  UserGetApprovedScopes = 2003, // 获取用户当前授权范围回调，使用 TapUserGetApprovedScopesResponse 结构体解析

  // [4001, 6000), reserved for TapTap ownership events
  GamePlayableStatusChanged = 4001,
  DLCPlayableStatusChanged = 4002,

  // [6001, 7000), reserved for TapTap CloudSave events
  CloudSaveList = 6001,     // 获取云存档列表
  CloudSaveCreate = 6002,   // 创建云存档
  CloudSaveUpdate = 6003,   // 更新云存档
  CloudSaveDelete = 6004,   // 删除云存档
  CloudSaveGetData = 6005,  // 获取云存档数据
  CloudSaveGetCover = 6006, // 获取云存档封面

  // [7001, 8000), reserved for TapTap Achievement events
  AchievementUnlock = 7001,    // 解锁成就
  AchievementIncrement = 7002, // 分步成就增长步长

  // [8001, 9000), reserved for TapTap Compliance events
  ComplianceEnsureRealName = 8001, // 检查实名
  ComplianceActionsEvent = 8002, // 防沉迷动作推送

  // [9001, 10000), reserved for TapTap Leaderboard events
  LeaderboardSubmitScores = 9001,        // 提交分数回调
  LeaderboardLoadScores = 9002,          // 获取排行榜数据回调
  LeaderboardLoadMyScores = 9003,        // 获取当前用户分数回调
  LeaderboardLoadMyCenteredScores = 9004, // 获取用户相近分数回调

  // [10001, 11000), reserved for TapTap Relation events
  RelationGetFriendList = 10001,    // 获取好友列表回调，使用 TapRelationGetFriendListResponse 结构体解析
  RelationGetFollowingList = 10002, // 获取关注列表回调，使用 TapRelationGetFollowingListResponse 结构体解析
  RelationGetFanList = 10003,       // 获取粉丝列表回调，使用 TapRelationGetFanListResponse 结构体解析
  RelationSyncRelationshipWithOpenID = 10004, // 同步好友关系（按 OpenID）回调，使用 TapRelationSyncRelationshipResponse 结构体解析
  RelationSyncRelationshipWithUnionID = 10005, // 同步好友关系（按 UnionID）回调，使用 TapRelationSyncRelationshipResponse 结构体解析
  // 未读消息数变化通知，SDK初始化成功后注册此事件的回调函数，以便及时获知未读消息数变化。
  // 使用 TapRelationUnreadMessageCountNotification 结构体解析
  RelationUnreadMessageCountChanged = 10101,
  // 新增粉丝数变化通知，SDK初始化成功后注册此事件的回调函数，以便及时获知新增粉丝数变化。
  // 使用 TapRelationNewFanCountNotification 结构体解析
  RelationNewFanCountChanged = 10102,
  // 被邀请方接受「进入游戏」邀请后，如果游戏正在运行，会收到该事件通知
  RelationGameInviteReceived = 10103,
  // 被邀请方接受「加入队伍」邀请后，如果游戏正在运行，会收到该事件通知
  RelationTeamInviteReceived = 10104,
};

#else

// 事件 ID 枚举值
enum {
  TapEventID_Unknown = 0,

  // [1, 2000), reserved for TapTap platform events

  // TapTap客户端系统状态变化通知，SDK初始化成功后注册此事件的回调函数，以便及时获知TapTap客户端状态变化。
  // 使用 TapSystemStateNotification 结构体解析
  TapEventID_SystemStateChanged = 1,

  // [2001, 4000), reserved for TapTap user events
  TapEventID_AuthorizeFinished = 2002,
  TapEventID_UserGetApprovedScopes = 2003, // 获取用户当前授权范围回调，使用 TapUserGetApprovedScopesResponse 结构体解析

  // [4001, 6000), reserved for TapTap ownership events
  TapEventID_GamePlayableStatusChanged = 4001,
  TapEventID_DLCPlayableStatusChanged = 4002,

  // [6001, 7000), reserved for TapTap CloudSave events
  TapEventID_CloudSaveList = 6001,     // 获取云存档列表回调，使用 TapCloudSaveListResponse 结构体解析
  TapEventID_CloudSaveCreate = 6002,   // 创建云存档回调，使用 TapCloudSaveCreateResponse 结构体解析
  TapEventID_CloudSaveUpdate = 6003,   // 更新云存档回调，使用 TapCloudSaveUpdateResponse 结构体解析
  TapEventID_CloudSaveDelete = 6004,   // 删除云存档回调，使用 TapCloudSaveDeleteResponse 结构体解析
  TapEventID_CloudSaveGetData = 6005,  // 获取云存档数据回调，使用 TapCloudSaveGetFileResponse 结构体解析
  TapEventID_CloudSaveGetCover = 6006, // 获取云存档封面回调，使用 TapCloudSaveGetFileResponse 结构体解析

  // [7001, 8000), reserved for TapTap Achievement events
  TapEventID_AchievementUnlock = 7001,  // 获取成就解锁回调，使用 TapAchievementUnlockResponse 结构体解析
  TapEventID_AchievementIncrement = 7002, // 获取分步成就步长增长回调，使用 TapAchievementIncrementResponse 结构体解析

  // [8001, 9000), reserved for TapTap Compliance events
  TapEventID_ComplianceEnsureRealName = 8001, // 检查实名回调，使用 TapComplianceEnsureRealNameResponse 结构体解析
  TapEventID_ComplianceActionsEvent = 8002,   // 防沉迷动作推送，使用 TapComplianceActionsEvent 结构体解析

  // [9001, 10000), reserved for TapTap Leaderboard events
  TapEventID_LeaderboardSubmitScores = 9001,        // 提交分数回调，使用 TapLeaderboardSubmitScoresResponse 结构体解析
  TapEventID_LeaderboardLoadScores = 9002,          // 获取排行榜数据回调，使用 TapLeaderboardLoadScoresResponse 结构体解析
  TapEventID_LeaderboardLoadMyScores = 9003,        // 获取当前用户分数回调，使用 TapLeaderboardLoadMyScoresResponse 结构体解析
  TapEventID_LeaderboardLoadMyCenteredScores = 9004, // 获取用户相近分数回调，使用 TapLeaderboardLoadMyCenteredScoresResponse 结构体解析

  // [10001, 11000), reserved for TapTap Relation events
  TapEventID_RelationGetFriendList = 10001,    // 获取好友列表回调，使用 TapRelationGetFriendListResponse 结构体解析
  TapEventID_RelationGetFollowingList = 10002, // 获取关注列表回调，使用 TapRelationGetFollowingListResponse 结构体解析
  TapEventID_RelationGetFanList = 10003,       // 获取粉丝列表回调，使用 TapRelationGetFanListResponse 结构体解析
  TapEventID_RelationSyncRelationshipWithOpenID = 10004, // 同步好友关系（按 OpenID）回调，使用 TapRelationSyncRelationshipResponse 结构体解析
  TapEventID_RelationSyncRelationshipWithUnionID = 10005, // 同步好友关系（按 UnionID）回调，使用 TapRelationSyncRelationshipResponse 结构体解析
  // 未读消息数变化通知，SDK初始化成功后注册此事件的回调函数，以便及时获知未读消息数变化。
  // 使用 TapRelationUnreadMessageCountNotification 结构体解析
  TapEventID_RelationUnreadMessageCountChanged = 10101,
  // 新增粉丝数变化通知，SDK初始化成功后注册此事件的回调函数，以便及时获知新增粉丝数变化。
  // 使用 TapRelationNewFanCountNotification 结构体解析
  TapEventID_RelationNewFanCountChanged = 10102,
  // 被邀请方接受「进入游戏」邀请后，如果游戏正在运行，会收到该事件通知
  TapEventID_RelationGameInviteReceived = 10103,
  // 被邀请方接受「加入队伍」邀请后，如果游戏正在运行，会收到该事件通知
  TapEventID_RelationTeamInviteReceived = 10104,
};
// 事件 ID
typedef uint32_t TapEventID;

#endif

// 回调函数类型定义
typedef void (T_CALLTYPE *callback_t)(TapEventID, void *);

//------------------------------------------------------------------------------
// 结构体定义
//------------------------------------------------------------------------------

#pragma pack(push, 8)

// 错误信息结构体
typedef struct {
    TapSDK_ErrorCode code; // 错误码
    const char* message;   // 错误信息
} TapSDK_Error;

// TapPC系统状态通知
typedef struct {
    TapSystemState state; // TapPC当前系统状态
	const void* detail;   // 通知详情，部分通知会有值。如无，则为 NULL
} TapSystemStateNotification;

// 最新启动的游戏会话的信息。当 TapSystemStateNotification::state
// 为 TapSystemState_DupGameSession 时，可以用该结构体解析 TapSystemStateNotification::detail
typedef struct {
	const char* device_name; // 启动游戏的设备名称
} TapSystemStateNotificationGameSessionInfo;

struct AuthorizeFinishedResponse {
    bool is_cancel;
    char error[1024];

    char token_type[32];
    char kid[8*1024];
    char mac_key[8*1024];
    char mac_algorithm[32];
    char scope[1024];
};

// 拉取用户授权范围的响应
typedef struct {
    int64_t request_id;        // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
    const TapSDK_Error* error; // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
    uint32_t scope_count;      // 授权范围数量
    const char** scopes;       // 用户当前授权范围数组
} TapUserGetApprovedScopesResponse;

//  游戏本体可玩状态变更事件响应结构体
struct GamePlayableStatusChangedResponse {
    bool is_playable;            // 游戏本体是否可玩
};

// DLC 可玩状态变更事件响应结构体
struct DLCPlayableStatusChangedResponse {
    char dlc_id[TapDLC_IdMaxLength]; // DLC ID
    bool is_playable;                // 是否可玩，当用户购买 DLC （外置 DLC 为购买且下载完成后），此值返回 true。其他情况返回 false
};

// 查询DLC商品明细请求
typedef struct {
	int32_t id_count; // 商品ID数量，一次最多20个
	char ids[TapDLC_MaxRequestedIdCount][TapDLC_IdMaxLength]; // 商品ID列表
} TapDLCQueryDetailsRequest;

// DLC商品明细
typedef struct {
	char id[TapDLC_IdMaxLength];     // 商品ID
	char name[TapDLC_NameMaxLength]; // 商品名称
	int32_t type;                // 0 未知、1 DLC、2 完整版
	bool owned;                  // true 已购、false 未购
	int32_t original_price;      // 原价，分
	int32_t discounted_price;    // 折后价，分。如果当前没有打折，和original_price相等
	int64_t discount_start_time; // 1970年开始的秒数。如果当前没有打折，0
	int64_t discount_end_time;   // 1970年开始的秒数。如果当前没有打折，0
} TapDLCDetails;

// 查询DLC商品明细返回
typedef struct {
	int32_t detail_count; // 实际查到的商品明细数量
	TapDLCDetails details[TapDLC_MaxRequestedIdCount]; // 商品明细
} TapDLCQueryDetailsResponse;

#pragma pack(pop)

//------------------------------------------------------------------------------
// SDK 核心功能
//------------------------------------------------------------------------------

/**
 * 检查是否需要重启应用
 * 此函数应该在初始化 (TapSDK_Init) 前调用，用于检查是否需要重启应用
 * @param clientID 客户端 ID
 * @return true 表示需要重启，此时 TapTap 将会重新打开游戏，请尽快退出游戏进程
 */
T_API bool T_CALLTYPE TapSDK_RestartAppIfNecessary(const char *clientID);

/**
 * 初始化 SDK，除 TapSDK_RestartAppIfNecessary 外，其他函数都应该在初始化完成后调用
 * @param errMsg 错误信息缓冲区，长度为 1024 字节。错误信息以 \0 结尾
 * @param pubKey 从 TapTap 开发者中心获取的公钥
 * @return SDK 初始化结果
 */
T_API TapSDK_Init_Result T_CALLTYPE TapSDK_Init(ErrMsg *errMsg, const char *pubKey);

/**
 * 关闭 SDK，释放资源
 * @return 是否成功关闭
 */
T_API bool T_CALLTYPE TapSDK_Shutdown();

/**
 * 获取当前客户端 ID
 * @param buffer 用于存储客户端 ID 的缓冲区，以 \0 结尾，固定长度为 256 字节
 * @return 是否成功获取客户端 ID
 */
T_API bool T_CALLTYPE TapSDK_GetClientID(char *buffer);

//------------------------------------------------------------------------------
// 回调相关功能
//------------------------------------------------------------------------------

/**
 * 注册事件回调
 * @param eventID 事件 ID
 * @param callback 回调函数
 */
T_API void T_CALLTYPE TapSDK_RegisterCallback(TapEventID eventID, callback_t callback);

/**
 * 注销事件回调
 * @param eventID 事件 ID
 * @param callback 要注销的回调函数
 */
T_API void T_CALLTYPE TapSDK_UnregisterCallback(TapEventID eventID, callback_t callback);

/**
 * 处理回调事件，建议每帧调用
 */
T_API void T_CALLTYPE TapSDK_RunCallbacks();

//------------------------------------------------------------------------------
// 一致性随机数生成器
//------------------------------------------------------------------------------

/**
 * 创建新的随机数生成器，线程安全
 * @note 使用相同种子创建的随机数生成器，生成的随机数序列是相同的
 * @param seed 随机数生成器的种子
 * @return 返回随机数生成器ID，如果创建失败返回 0
 */
T_API int64_t T_CALLTYPE TapSDK_CreateRandomNumberGenerator(int32_t seed);

/**
 * 生成[0, 0x7fffffff]的随机整数，线程安全
 * @param rand_generator_id TapSDK_CreateRandomNumberGenerator()返回的随机数生成器ID
 * @return 返回随机正整数[0, 0x7fffffff]，如果随机数生成器已销毁返回 -1
 */
T_API int32_t T_CALLTYPE TapSDK_RandomInt(int64_t rand_generator_id);

/**
 * 销毁随机数生成器，线程安全。如果传入的随机数生成器ID无效/已销毁，则不做任何操作
 * @param rand_generator_id TapSDK_CreateRandomNumberGenerator()返回的随机数生成器ID
 */
T_API void T_CALLTYPE TapSDK_DestroyRandomNumberGenerator(int64_t rand_generator_id);

//------------------------------------------------------------------------------
// App 相关功能
//------------------------------------------------------------------------------

/**
 * 检查是否拥有当前游戏
 * @return true 表示拥有当前游戏，false 表示未拥有
 */
T_API bool T_CALLTYPE TapApps_IsOwned();

//------------------------------------------------------------------------------
// 用户相关功能
//------------------------------------------------------------------------------

/**
 * 异步请求用户授权（简化版本）
 * @param scopes 权限范围字符串，多个权限用逗号分隔，如 "public_profile,user_friends"
 * @return 授权请求结果
 */
T_API TapUser_AsyncAuthorize_Result T_CALLTYPE TapUser_AsyncAuthorize(const char* scopes);

/**
 * 异步获取用户当前的授权范围
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @return 请求发起结果，如果不是 TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapUser_AsyncGetApprovedScopes(int64_t request_id);

/**
 * 获取用户 OpenID
 * @param buffer 用于存储用户 OpenID 的缓冲区，以 \0 结尾，固定长度为 256 字节
 * @return 是否成功获取用户 OpenID
 */
T_API bool T_CALLTYPE TapUser_GetOpenID(char *buffer);

//------------------------------------------------------------------------------
// DLC 相关功能
//------------------------------------------------------------------------------

/**
 * 显示指定 DLC 的商店页面
 * @param dlc_id DLC ID
 * @return 是否成功显示商店页面
 */
T_API bool T_CALLTYPE TapDLC_ShowStore(const char *dlc_id);

/**
 * 查询用户是否拥有指定的 DLC
 * @param dlc_id DLC ID
 * @return true 表示用户拥有该 DLC，false 表示未拥有
 */
T_API bool T_CALLTYPE TapDLC_IsOwned(const char *dlc_id);

/**
 * 查询指定 DLC 商品的明细，包括是否已购
 * @param request DLC ID列表，不允许为空，一次最多20个
 * @param response DLC 商品明细，包括是否已购。如果ID列表对应的商品都不存在，则response->detail_count为0
 * @return 请求发起结果，如果不是 TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapDLC_QueryDetails(
  const TapDLCQueryDetailsRequest* request,
  TapDLCQueryDetailsResponse* response
);

#endif // TAPSDK_H
