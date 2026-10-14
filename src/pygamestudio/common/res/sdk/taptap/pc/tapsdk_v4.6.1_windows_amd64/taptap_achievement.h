#pragma once

#include "taptap_api.h"

// 注意：所有接口的字符串参数（char *）都必须是 UTF-8 编码

//------------------------------------------------------------------------------
// 结构体定义
//------------------------------------------------------------------------------
#pragma pack(push, 8)

// 成就解锁信息
typedef struct  {
    const char* id;         // 成就 id
    const char* name;       // 成就 name
    int64_t current_steps; // 当前步数
    bool newly_unlocked;    // 是否新解锁
} TapAchievementInfo;

// 解锁成就请求
typedef struct {
    const char* achievement_id; // 成就 id
} TapAchievementUnlockRequest;
// 解锁成就响应
typedef struct {
    int64_t request_id;                             // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
    const TapSDK_Error* error;                      // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
    const TapAchievementInfo* achievement;          // 成就解锁情况
    const TapAchievementInfo* platinum_achievement; // 白金成就解锁情况。如果不是第一次解锁白金成就，该节点为 NULL
} TapAchievementUnlockResponse;

// 分步成就增长请求
typedef struct {
    const char* achievement_id; // 成就 id
    int64_t steps;              // 步长
} TapAchievementIncrementRequest;
// 分步成就增长响应
typedef struct {
    int64_t request_id;                             // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
    const TapSDK_Error* error;                      // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
    const TapAchievementInfo* achievement;          // 成就解锁情况
    const TapAchievementInfo* platinum_achievement; // 白金成就解锁情况。如果不是第一次解锁白金成就，该节点为 NULL
} TapAchievementIncrementResponse;

#pragma pack(pop)

//------------------------------------------------------------------------------
// 成就功能
//------------------------------------------------------------------------------

// 成就接口对象，通过 TapAchievement() 获取
typedef struct ITapAchievement ITapAchievement;

/**
 * 获取成就单例对象
 * @return 成就单例对象
 */
T_API ITapAchievement* T_CALLTYPE TapAchievement();

/**
 * 发起成就解锁异步请求。如果请求发起成功，请求处理结果会通过TapEventID::AchievementUnlock对应的回调函数返回
  * @param self TapAchievement()返回的成就单例对象
  * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求参数
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapAchievement_AsyncUnlock(
    ITapAchievement* self,
    int64_t request_id,
    const TapAchievementUnlockRequest* request
);

/**
 * 发起分步成就步长增长异步请求。如果请求发起成功，请求处理结果会通过TapEventID::AchievementIncrement对应的回调函数返回
  * @param self TapAchievement()返回的成就单例对象
  * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 请求参数
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapAchievement_AsyncIncrement(
    ITapAchievement* self,
    int64_t request_id,
    const TapAchievementIncrementRequest* request
);

/**
 * 发起打开成就展示页同步请求。
  * @param self TapAchievement()返回的成就单例对象
  * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapAchievement_ShowAchievements(
    ITapAchievement* self
);
