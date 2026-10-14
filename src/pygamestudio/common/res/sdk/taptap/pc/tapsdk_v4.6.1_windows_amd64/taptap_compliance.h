#pragma once

#include "taptap_api.h"

// 注意：所有接口的字符串参数（char *）都必须是 UTF-8 编码

//------------------------------------------------------------------------------
// 结构体定义
//------------------------------------------------------------------------------
#pragma pack(push, 8)

enum {
    TapComplianceActionType_None = 0,
    TapComplianceActionType_Toast = 1,
    TapComplianceActionType_Alert = 2,
    TapComplianceActionType_Exit = 3,
};
typedef uint32_t TapComplianceActionType;

typedef struct {
    TapComplianceActionType action_type;  // UI 动作
    const char* title;                    // 标题
    const char* description;              // 描述
    uint32_t display_duration_seconds;    // 展示时长
} TapComplianceAction;

typedef struct {
    uint32_t count;
    const TapComplianceAction* actions;
} TapComplianceActionsEvent;

enum {
    TapComplianceRealNameStatus_None = 0,
    TapComplianceRealNameStatus_Success = 1,
    TapComplianceRealNameStatus_Canceled = 2,
    TapComplianceRealNameStatus_Failed = 3,
};
typedef uint32_t TapComplianceRealNameStatus;

typedef struct {
    int64_t request_id;                 // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
    const TapSDK_Error* error;          // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
    TapComplianceRealNameStatus status; // 实名状态
}  TapComplianceEnsureRealNameResponse;

// 支付检查请求
typedef struct {
    uint32_t amount;     // 支付金额,单位分(64800 -> 648元)
} TapComplianceCheckPaymentLimitRequest;
// 支付检查响应
typedef struct {
    bool allow;              // 是否可支付
    char title[256];         // 不可支付时需要展示的title
    char description[4096];  // 不可支付时需要展示的描述文字
} TapComplianceCheckPaymentLimitResponse;

// 上报支付金额请求
typedef struct {
    uint32_t amount;     // 支付金额,单位分(64800 -> 648元)
} TapComplianceSubmitPaymentRequest;

#pragma pack(pop)

//------------------------------------------------------------------------------
// 合规认证功能
//------------------------------------------------------------------------------

// 合规认证接口对象，通过 TapCompliance() 获取
typedef struct ITapCompliance ITapCompliance;

/**
 * 获取合规认证单例对象
 * @return 合规认证单例对象
 */
T_API ITapCompliance* T_CALLTYPE TapCompliance();

/**
 * 发起检查实名的异步请求,如果未实名会在 TapTap PC 弹出实名窗口。如果请求发起成功，请求处理结果会通过 TapEventID::ComplianceEnsureRealName 对应的回调函数返回
 * @param self TapCompliance() 返回的合规认证单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapSDK_Result T_CALLTYPE TapCompliance_AsyncEnsureRealName(
    ITapCompliance* self,
    int64_t request_id
);

/**
 * 启动防沉迷检查。
 * @param self TapCompliance() 返回的合规认证单例对象
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapCompliance_EnableAntiAddiction(
    ITapCompliance* self
);

/**
 * 发起检查充值限制的同步请求。
 * @param self TapCompliance() 返回的合规认证单例对象
 * @param request 检查支付限制的请求
 * @param response 检查支付限制的响应
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapCompliance_CheckPaymentLimit(
    ITapCompliance* self,
    const TapComplianceCheckPaymentLimitRequest* request,
    TapComplianceCheckPaymentLimitResponse* response
);

/**
 * 发起上报充值金额的同步请求。
 * @param self TapCompliance() 返回的合规认证单例对象
 * @param request 上报充值金额的请求
 * @return 请求发起结果，如果不是TapSDK_Result_OK，表示请求发起失败
 */
T_API TapSDK_Result T_CALLTYPE TapCompliance_SubmitPayment(
    ITapCompliance* self,
    const TapComplianceSubmitPaymentRequest* request
);
