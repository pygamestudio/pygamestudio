#pragma once

#include "taptap_api.h"

// 注意：所有接口的字符串参数（char *）都必须是 UTF-8 编码

//------------------------------------------------------------------------------
// 常量定义
//------------------------------------------------------------------------------

// 同步好友关系动作类型枚举值
enum {
	TapRelation_SyncRelationshipActionType_Add = 0, // 新增好友关系
	TapRelation_SyncRelationshipActionType_Remove = 1, // 移除好友关系
};
// 同步好友关系动作类型，取值请参考枚举值 TapRelation_SyncRelationshipActionType_*
typedef uint32_t TapRelation_SyncRelationshipActionType;

//------------------------------------------------------------------------------
// 结构体定义
//------------------------------------------------------------------------------
#pragma pack(push, 8)

// 关注关系
typedef struct {
	bool following;  // 是否关注了对方
	bool followed;   // 是否被对方关注（粉丝）
	bool blocking;   // 是否拉黑了对方
	bool blocked;    // 是否被对方拉黑
} TapRelationFollowStatus;

// 好友信息
typedef struct {
	const char* open_id;  // 好友 OpenId
	const char* name;     // 用户名
	const char* alias;    // 备注名
	const char* avatar;   // 头像 URL
	TapRelationFollowStatus follow_status;
	int64_t created_at;   // 关系创建时间戳，1970年开始的秒数
} TapRelationFriendInfo;

// 拉取好友列表（互关）请求
typedef struct {
	const char* continuation_token; // 用于拉取下一页。拉第一页时传NULL
} TapRelationGetFriendListRequest;

// 拉取好友列表响应
typedef struct {
	int64_t                       request_id;
	const TapSDK_Error*           error;
	uint32_t                      friend_count;
	const TapRelationFriendInfo*  friends;
	const char*                   continuation_token; // 用于拉取下一页。没有下一页时为NULL
} TapRelationGetFriendListResponse;

// 拉取关注列表（我关注的）请求
typedef TapRelationGetFriendListRequest TapRelationGetFollowingListRequest;

// 拉取关注列表响应
typedef struct {
	int64_t                       request_id;
	const TapSDK_Error*           error;
	uint32_t                      following_count;
	const TapRelationFriendInfo*  followings;
	const char*                   continuation_token; // 用于拉取下一页。没有下一页时为NULL
} TapRelationGetFollowingListResponse;

// 拉取粉丝列表（关注我的）请求
typedef TapRelationGetFriendListRequest TapRelationGetFanListRequest;

// 拉取粉丝列表响应
typedef struct {
	int64_t                       request_id;
	const TapSDK_Error*           error;
	uint32_t                      fan_count;
	const TapRelationFriendInfo*  fans;
	const char*                   continuation_token; // 用于拉取下一页。没有下一页时为NULL
} TapRelationGetFanListResponse;

// 展示用户名片请求
typedef struct {
	const char* open_id;  // 用户 OpenID
	const char* union_id; // 用户 UnionID。二选一，同时传递会报错
} TapRelationShowUserProfileRequest;

// 同步好友关系（按 OpenID）请求
typedef struct {
	TapRelation_SyncRelationshipActionType action;
	const char* nickname;        // 本人昵称，不允许NULL，不允许空字符串
	const char* friend_nickname; // 对方昵称，不允许NULL，不允许空字符串
	const char* friend_open_id;  // 对方 OpenID
} TapRelationSyncRelationshipWithOpenIDRequest;

// 同步好友关系（按 UnionID）请求
typedef struct {
	TapRelation_SyncRelationshipActionType action;
	const char* nickname;        // 本人昵称，不允许NULL，不允许空字符串
	const char* friend_nickname; // 对方昵称，不允许NULL，不允许空字符串
	const char* friend_union_id; // 对方 UnionID
} TapRelationSyncRelationshipWithUnionIDRequest;

// 同步好友关系响应
typedef struct {
	int64_t             request_id;
	const TapSDK_Error* error;
} TapRelationSyncRelationshipResponse;

// 邀请好友加入队伍请求
typedef struct {
	const char* team_id; // 组队参数，必须为ASCII，且不能包含空格、双引号、换行符等特殊符号
} TapRelationInviteTeamRequest;

// 被邀请方接受邀请时，如果游戏正在运行中，游戏内会收到该事件通知；
// 接受进入游戏邀请（邀上线）对应 TapEventID::RelationGameInviteReceived，接受组队邀请对应 TapEventID::RelationTeamInviteReceived。
typedef struct {
	const char* open_id;  // 发起邀请的好友 OpenID
	const char* union_id; // 发起邀请的好友 UnionID
	const char* team_id;  // 仅组队邀请（RelationTeamInviteReceived）有效，进入游戏邀请时为 NULL
} TapRelationInviteReceivedNotification;

// 未读消息数变化通知
typedef struct {
	uint32_t count; // 最新未读消息数
} TapRelationUnreadMessageCountNotification;

// 新增粉丝数变化通知
typedef TapRelationUnreadMessageCountNotification TapRelationNewFanCountNotification;

#pragma pack(pop)

//------------------------------------------------------------------------------
// 好友功能
//------------------------------------------------------------------------------

// 好友接口对象，通过 TapRelation() 获取
typedef struct ITapRelation ITapRelation;

/**
 * 获取好友单例对象
 * @return 好友单例对象
 */
T_API ITapRelation* T_CALLTYPE TapRelation();

/**
 * 异步获取好友列表（互关）。如果请求发起成功，结果会通过 TapEventID::RelationGetFriendList 回调返回。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_AsyncGetFriendList(
	ITapRelation* self,
	int64_t request_id,
	const TapRelationGetFriendListRequest* request
);

/**
 * 异步获取关注列表（我关注的）。如果请求发起成功，结果会通过 TapEventID::RelationGetFollowingList 回调返回。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_AsyncGetFollowingList(
	ITapRelation* self,
	int64_t request_id,
	const TapRelationGetFollowingListRequest* request
);

/**
 * 异步获取粉丝列表（关注我的）。如果请求发起成功，结果会通过 TapEventID::RelationGetFanList 回调返回。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_AsyncGetFanList(
	ITapRelation* self,
	int64_t request_id,
	const TapRelationGetFanListRequest* request
);

/**
 * 异步同步好友关系（按 OpenID）。如果请求发起成功，结果会通过 TapEventID::RelationSyncRelationshipWithOpenID 回调返回。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_AsyncSyncRelationshipWithOpenID(
	ITapRelation* self,
	int64_t request_id,
	const TapRelationSyncRelationshipWithOpenIDRequest* request
);

/**
 * 异步同步好友关系（按 UnionID）。如果请求发起成功，结果会通过 TapEventID::RelationSyncRelationshipWithUnionID 回调返回。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_AsyncSyncRelationshipWithUnionID(
	ITapRelation* self,
	int64_t request_id,
	const TapRelationSyncRelationshipWithUnionIDRequest* request
);

/**
 * 同步获取未读消息数。建议通过监听 TapEventID::RelationUnreadMessageCountChanged 事件来实时获知未读消息数变化，而不是频繁调用该接口。
 * @param self TapRelation()返回的好友模块单例对象
 * @param count 出参，调用成功时写入当前未读消息总数；返回非 TapSDK_Result_OK 时不修改
 *
 * @return 请求结果，TapSDK_Result_OK 表示成功
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_GetUnreadMessageCount(
	ITapRelation* self,
	uint32_t* count
);

/**
 * 同步获取新增粉丝数。建议通过监听 TapEventID::RelationNewFanCountChanged 事件来实时获知新增粉丝数变化，而不是频繁调用该接口。
 * @param self TapRelation()返回的好友模块单例对象
 * @param count 出参，调用成功时写入当前新增粉丝数；返回非 TapSDK_Result_OK 时不修改
 *
 * @return 请求结果，TapSDK_Result_OK 表示成功
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_GetNewFanCount(
	ITapRelation* self,
	uint32_t* count
);

/**
 * 打开TapPC IM窗口，可在窗口中给好友发消息和管理好友。
 * @param self TapRelation()返回的好友模块单例对象
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_ShowIM(
	ITapRelation* self
);

/**
 * 请求 TapPC 展示用户名片。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是 TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_ShowUserProfile(
	ITapRelation* self,
	const TapRelationShowUserProfileRequest* request
);

/**
 * 打开TapPC IM好友邀请窗口，邀请好友进入游戏。
 * @param self TapRelation()返回的好友模块单例对象
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_InviteGame(
	ITapRelation* self
);

/**
 * 打开TapPC IM好友邀请窗口，邀请好友加入队伍。
 * @param self TapRelation()返回的好友模块单例对象
 * @param request 请求信息
 *
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_InviteTeam(
	ITapRelation* self,
	const TapRelationInviteTeamRequest* request
);

/**
 * 通过邀请 scheme 主动触发邀请到达回调（用于游戏冷启动场景）。
 *
 * 当游戏从命令行被冷启动时（启动器以 "--tap_invite_scheme=<scheme>" 形式传参），
 * SDK 自身无法解析进程命令行参数，需要由游戏开发者在解析到该参数后，
 * 把 scheme 字符串原样传入此接口，由 SDK 触发对应的事件回调：
 *   - "invite_game" → TapEventID::RelationGameInviteReceived
 *   - "invite_team" → TapEventID::RelationTeamInviteReceived
 *
 * scheme 格式：
 *   tds<client_id>://<action>?open_id=...&union_id=...&team_id=...
 *
 * @param self TapRelation()返回的好友模块单例对象
 * @param invite_scheme 完整的 invite scheme 字符串（不含 "--tap_invite_scheme=" 前缀）
 *
 * @return TapSDK_Result_OK 表示解析成功并会触发回调；
 *         TapSDK_Result_InvalidArgument 表示 scheme 为空或格式不合法
 */
T_API TapSDK_Result T_CALLTYPE TapRelation_HandleInviteScheme(
	ITapRelation* self,
	const char* invite_scheme
);
