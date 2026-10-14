#pragma once

#include "taptap_api.h"

// 注意：所有接口的字符串参数（char *）都必须是 UTF-8 编码

//------------------------------------------------------------------------------
// 结构体定义
//------------------------------------------------------------------------------
#pragma pack(push, 8)

enum {
  TapLeaderboardCollection_Public  = 0, // 总榜
  TapLeaderboardCollection_Friends = 1, // 好友榜
};
typedef uint32_t TapLeaderboardCollection;

typedef struct {
  const char* period_token; // 周期 token
  const char* display;      // 展示文本，如 "4月20日 - 4月26日"，永久榜为空
} TapLeaderboardPeriod;

typedef struct {
  const char* open_id;  // open_id
  const char* union_id; // union_id
  const char* name;     // 昵称
  const char* avatar;   // 头像 URL
} TapLeaderboardUserInfo;

typedef struct {
  uint32_t               rank;                 // 排名
  int64_t                score;                // 分数
  TapLeaderboardUserInfo user;                 // 用户信息
  uint64_t               score_submitted_time; // 分数提交时间
} TapLeaderboardScore;

// 榜单实例
typedef struct {
  const char*                  id;                      // 排行榜ID
  const char*                  name;                    // 排行榜名称，如"巅峰赛战力榜"
  const TapLeaderboardPeriod*  period;                  // 当前周期，NULL 表示永久榜
  uint32_t                     available_period_count; // 可用周期数量
  const TapLeaderboardPeriod*  available_periods;       // 排行榜可用周期
} TapLeaderboardInfo;

typedef struct {
  const char* leaderboard_id; // 排行榜 ID
  int64_t     score;          // 分数
} TapLeaderboardScoreItem;

typedef struct {
  uint32_t item_count;                    // 分数数量，最多 5 个
  const    TapLeaderboardScoreItem* items; // 分数列表
} TapLeaderboardSubmitScoresRequest;

typedef struct {
  bool    new_best;  // 是否是新成绩
  int64_t raw_score; // 原始分数
} TapLeaderboardSubmitScoreResultData;

typedef struct {
  const char* leaderboard_id; // 榜单id
  const char* period_token;   // 榜单周期
  const TapLeaderboardSubmitScoreResultData* score_result; // 分数提交结果
  const char* open_id;    // open_id
  const char* union_id;   // union_id
} TapLeaderboardSubmitScoreResult;

typedef struct {
  int64_t                                request_id;
  const TapSDK_Error*                    error;
  uint32_t                               result_count;
  const TapLeaderboardSubmitScoreResult* results;
} TapLeaderboardSubmitScoresResponse;

typedef struct {
  const char*              leaderboard_id;     // 排行榜 ID
  TapLeaderboardCollection collection;         // 总榜 / 好友榜
  const char*              continuation_token; // 分页游标，首次传 NULL
  const char*              period_token;       // 历史周期标识，NULL 表示当前周期
} TapLeaderboardLoadScoresRequest;

typedef struct {
  int64_t                       request_id;
  const TapSDK_Error*           error;
  const TapLeaderboardInfo* leaderboard;
  uint32_t                      score_count;
  const TapLeaderboardScore*    scores;
  const char*                   continuation_token;
  bool                          is_truncated;       // 是否还有下一页
} TapLeaderboardLoadScoresResponse;

typedef struct {
  const char*              leaderboard_id; // 排行榜 ID
  TapLeaderboardCollection collection;     // 总榜 / 好友榜
  const char*              period_token;   // 历史周期标识，NULL 表示当前周期
} TapLeaderboardLoadMyScoresRequest;

typedef struct {
  int64_t                    request_id; // 请求 ID
  const TapSDK_Error*        error;      // NULL 表示成功
  const TapLeaderboardInfo* leaderboard;
  const TapLeaderboardScore* score;      // 当前用户排名，NULL 表示未上榜
} TapLeaderboardLoadMyScoresResponse;

typedef struct {
  const char*              leaderboard_id; // 排行榜 ID
  TapLeaderboardCollection collection;     // 总榜 / 好友榜
  uint32_t                 max_results;      // 返回总数（含当前用户），0 表示服务端默认值
} TapLeaderboardLoadMyCenteredScoresRequest;

typedef struct {
  int64_t                       request_id;   // 请求 ID
  const TapSDK_Error*           error;        // NULL 表示成功
  const TapLeaderboardInfo* leaderboard;
  uint32_t                      score_count; // 分数数量
  const TapLeaderboardScore*    scores;       // 分数列表（当前用户居中）
} TapLeaderboardLoadMyCenteredScoresResponse;

typedef struct {
  const char*              leaderboard_id; // 排行榜 ID
  TapLeaderboardCollection collection;     // 打开时默认展示的集合类型
} TapLeaderboardShowRequest;

#pragma pack(pop)

//------------------------------------------------------------------------------
// 排行榜功能
//------------------------------------------------------------------------------

typedef struct ITapLeaderboard ITapLeaderboard;

/**
 * 获取排行榜单例对象
 * @return 排行榜单例对象
 */
T_API ITapLeaderboard* T_CALLTYPE TapLeaderboard();

/**
  * 发起批量上报分数异步请求。结果通过 TapEventID::LeaderboardSubmitScores 回调返回 TapLeaderboardSubmitScoresResponse
  *
  * @param self       TapLeaderboard() 返回的单例对象
  * @param request_id 开发者生成的请求 ID，回调时原样返回
  * @param request    上报请求，最多 5 条
  * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
  */
T_API TapSDK_Result T_CALLTYPE TapLeaderboard_AsyncSubmitScores(
    ITapLeaderboard*                         self,
    int64_t                                  request_id,
    const TapLeaderboardSubmitScoresRequest* request
);

/**
  * 发起获取排行榜数据的异步请求。结果通过 TapEventID::LeaderboardLoadScores 回调返回 TapLeaderboardLoadScoresResponse
  *
  * @param self       TapLeaderboard() 返回的单例对象
  * @param request_id 请求 ID
  * @param request    查询参数
  * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
  */
T_API TapSDK_Result T_CALLTYPE TapLeaderboard_AsyncLoadScores(
    ITapLeaderboard*                       self,
    int64_t                                request_id,
    const TapLeaderboardLoadScoresRequest* request
);

/**
  * 发起获取当前用户分数的异步请求。结果通过 TapEventID::LeaderboardLoadMyScores 回调返回 TapLeaderboardLoadMyScoresResponse
  *
  * @param self       TapLeaderboard() 返回的单例对象
  * @param request_id 请求 ID
  * @param request    查询参数
  * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
  */
T_API TapSDK_Result T_CALLTYPE TapLeaderboard_AsyncLoadMyScores(
    ITapLeaderboard*                          self,
    int64_t                                   request_id,
    const TapLeaderboardLoadMyScoresRequest*  request
);

/**
  * 发起获取用户相近分数的异步请求。结果通过 TapEventID::LeaderboardLoadMyCenteredScores 回调返回 TapLeaderboardLoadMyCenteredScoresResponse
  *
  * @param self       TapLeaderboard() 返回的单例对象
  * @param request_id 请求 ID
  * @param request    查询参数
  * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
  */
T_API TapSDK_Result T_CALLTYPE TapLeaderboard_AsyncLoadMyCenteredScores(
    ITapLeaderboard*                                 self,
    int64_t                                          request_id,
    const TapLeaderboardLoadMyCenteredScoresRequest* request
);

/**
  * 发起打开排行榜页面的同步请求
  *
  * @param self       TapLeaderboard() 返回的单例对象
  * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
  */
T_API TapSDK_Result T_CALLTYPE TapLeaderboard_ShowLeaderboards(
    ITapLeaderboard*                 self,
    const TapLeaderboardShowRequest* request
);
