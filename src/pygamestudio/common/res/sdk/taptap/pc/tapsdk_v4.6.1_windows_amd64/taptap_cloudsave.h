#pragma once

#include "taptap_api.h"

// 注意：所有接口的字符串参数（char *）都必须是 UTF-8 编码

// 云存档函数调用结果枚举值
enum {
    TapCloudSave_Result_OK = 0,                     // 云存档请求成功发起，请等待回调通知请求执行结果
    TapCloudSave_Result_Uninitialized = 1,          // SDK 未初始化，请调用 TapSDK_Init() 并确保返回为 TapSDK_Init_Result::OK
    TapCloudSave_Result_NoTapTapClient = 2,         // 发起云存档请求失败：TapTap 客户端尚未运行
    TapCloudSave_Result_TapTapClientOutdated = 3,   // 发起云存档请求失败：TapTap 客户端版本过旧，请引导用户更新最新版 TapTap 客户端
    TapCloudSave_Result_InvalidArgument = 4,        // 发起云存档请求失败：参数错误，比如不允许 NULL 的参数传了 NULL
    TapCloudSave_Result_SdkFailed = 5,              // 发起云存档请求失败：云存档 SDK 内部错误，一般是因为没有调用 TapSDK_Init()，或者 TapSDK_Init() 返回失败
    TapCloudSave_Result_FailedToReadSaveFile = 6,   // 发起云存档请求失败：存档文件读取失败
    TapCloudSave_Result_SaveFileTooLarge = 7,       // 发起云存档请求失败：超过10M限制
    TapCloudSave_Result_FailedToReadCoverFile = 8,  // 发起云存档请求失败：封面文件读取失败
    TapCloudSave_Result_CoverFileTooLarge = 9,      // 发起云存档请求失败：超过512K限制
};
// 云存档函数调用结果，取值请参考枚举值 TapCloudSave_Result_*
typedef uint32_t TapCloudSave_Result;

//------------------------------------------------------------------------------
// 结构体定义
//------------------------------------------------------------------------------

#pragma pack(push, 8)

// 云存档信息
typedef struct {
	const char* uuid;       // 标识单个云存档的唯一 ID
	const char* file_id;    // 云存档文件 ID，用于下载云存档文件，每次更新云存档后该 ID 会变化
	const char* name;       // 云存档名称
	int32_t save_size;      // 云存档文件大小，单位：字节
	int32_t cover_size;     // 云存档封面文件大小，单位：字节。如果没有封面文件，该字段为 0
	const char* summary;    // 云存档摘要信息，如果没有摘要信息，该字段为 NULL
	const char* extra;      // 云存档额外信息，如果没有额外信息，该字段为 NULL
	int32_t playtime;       // 云存档内记录的游戏时长，单位：秒
	uint32_t created_time;  // 云存档创建时间，1970年开始的秒数
	uint32_t modified_time; // 云存档最后修改时间，1970年开始的秒数
} TapCloudSaveInfo;

// 拉取云存档列表的响应
typedef struct {
	int64_t request_id;             // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
	const TapSDK_Error* error;      // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
	int32_t save_count;             // 云存档个数
	const TapCloudSaveInfo* saves;  // 云存档信息数组，长度为 save_count。如果 save_count 为 0，则该字段为 NULL
} TapCloudSaveListResponse;

// 创建云存档请求
typedef struct {
    const char* name;            // 存档名，60字节以内，不允许空，不允许汉字
    const char* summary;         // 存档描述，500字节以内，不允许空
    const char* extra;           // 开发者自定义信息，1000字节以内，允许空
    int32_t playtime;            // 游戏时长，单位秒
    const char* data_file_path;  // 存档文件路径，创建云存档接口返回前不允许修改该文件。不允许为 NULL
    const char* cover_file_path; // 封面文件路径，创建云存档接口返回前不允许修改该文件。允许为 NULL，表示没有封面
} TapCloudSaveCreateRequest;

// 创建云存档的响应
typedef struct {
	int64_t request_id;            // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
	const TapSDK_Error* error;     // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
	const TapCloudSaveInfo* save;  // 云存档信息，如果创建失败，则该字段为 NULL
} TapCloudSaveCreateResponse;

// 更新云存档请求
typedef struct {
    const char* uuid;            // 标识单个云存档的唯一 ID，用于指定需要更新的云存档
    const char* name;            // 存档名，60字节以内，不允许空，不允许汉字
    const char* summary;         // 存档描述，500字节以内，不允许空
    const char* extra;           // 开发者自定义信息，1000字节以内，允许空
    int32_t playtime;            // 游戏时长，单位秒
    const char* data_file_path;  // 存档文件路径，创建云存档接口返回前不允许修改该文件。不允许为 NULL
    const char* cover_file_path; // 封面文件路径，创建云存档接口返回前不允许修改该文件。允许为 NULL，表示没有封面
} TapCloudSaveUpdateRequest;

// 更新云存档的响应，和创建云存档的响应相同
typedef TapCloudSaveCreateResponse TapCloudSaveUpdateResponse;

// 删除云存档的响应
typedef struct {
    int64_t request_id;         // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
	const TapSDK_Error* error;  // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
	const char* uuid;           // 被删除的云存档的唯一 ID
} TapCloudSaveDeleteResponse;

// 读取云存档数据文件/封面文件的请求
typedef struct {
	const char* uuid;    // 标识单个云存档的唯一 ID，用于指定需要拉取的云存档
	const char* file_id; // 云存档文件 ID，和 uuid 一起确定一个数据文件/封面文件。每次更新云存档后该 ID 会变化
} TapCloudSaveGetFileRequest;

// 读取云存档数据文件/封面文件的响应
typedef struct {
    int64_t request_id;         // 请求 ID。原样返回开发者调用异步接口时传入的 ID，开发者可使用该 ID 对应到原始请求
	const TapSDK_Error* error;  // 错误信息。NULL 表示请求成功；非 NULL 表示请求失败，可根据其中的错误码做相应处理
	int32_t size;               // 文件大小，单位：字节。如果 size 为 0，则 data 为 NULL
	const void* data;           // 文件内容，长度为 size 字节
} TapCloudSaveGetFileResponse;

#pragma pack(pop)

//------------------------------------------------------------------------------
// 云存档功能
//------------------------------------------------------------------------------

// 云存档接口对象，通过 TapCloudSave() 获取
typedef struct ITapCloudSave ITapCloudSave;

/**
 * 获取云存档接口单例对象
 * @return 云存档接口单例对象
 */
T_API ITapCloudSave* T_CALLTYPE TapCloudSave();

/**
 * 发起获取云存档列表的异步请求。如果请求发起成功，请求处理结果会通过TapEventID::CloudSaveList对应的回调函数返回
 * @param self TapCloudSave() 返回的云存档单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @return 请求发起结果，如果不是 TapCloudSave_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapCloudSave_Result T_CALLTYPE TapCloudSave_AsyncList(
    ITapCloudSave* self,
    int64_t request_id
);

/**
 * 发起创建云存档的异步请求。如果请求发起成功，请求处理结果会通过TapEventID::CloudSaveCreate对应的回调函数返回
 * @param self TapCloudSave() 返回的云存档单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 创建云存档请求
 * @return 请求发起结果，如果不是 TapCloudSave_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapCloudSave_Result T_CALLTYPE TapCloudSave_AsyncCreate(
    ITapCloudSave* self,
    int64_t request_id,
    const TapCloudSaveCreateRequest* request
);

/**
 * 发起更新云存档的异步请求。如果请求发起成功，请求处理结果会通过TapEventID::CloudSaveUpdate对应的回调函数返回
 * @param self TapCloudSave() 返回的云存档单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 更新云存档请求
 * @return 请求发起结果，如果不是 TapCloudSave_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapCloudSave_Result T_CALLTYPE TapCloudSave_AsyncUpdate(
    ITapCloudSave* self,
    int64_t request_id,
    const TapCloudSaveUpdateRequest* request
);

/**
 * 发起删除云存档的异步请求。如果请求发起成功，请求处理结果会通过TapEventID::CloudSaveDelete对应的回调函数返回
 * @param self TapCloudSave() 返回的云存档单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param uuid 标识单个云存档的唯一 ID，用于指定需要删除的云存档
 * @return 请求发起结果，如果不是 TapCloudSave_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapCloudSave_Result T_CALLTYPE TapCloudSave_AsyncDelete(
    ITapCloudSave* self,
    int64_t request_id,
    const char* uuid
);

/**
 * 发起读取云存档数据文件的异步请求。如果请求发起成功，请求处理结果会通过TapEventID::CloudSaveGetData对应的回调函数返回
 * @param self TapCloudSave() 返回的云存档单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 读取云存档数据文件的请求
 * @return 请求发起结果，如果不是 TapCloudSave_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapCloudSave_Result T_CALLTYPE TapCloudSave_AsyncGetData(
    ITapCloudSave* self,
    int64_t request_id,
    const TapCloudSaveGetFileRequest* request
);

/**
 * 发起读取云存档封面文件的异步请求。如果请求发起成功，请求处理结果会通过TapEventID::CloudSaveGetCover对应的回调函数返回
 * @param self TapCloudSave() 返回的云存档单例对象
 * @param request_id 开发者生成的请求 ID，请求处理完成后，调用回调函数时原样返回，开发者可使用该 ID 对应到原始请求
 * @param request 读取云存档封面文件的请求
 * @return 请求发起结果，如果不是 TapCloudSave_Result_OK，表示请求发起失败，不会触发回调函数
 */
T_API TapCloudSave_Result T_CALLTYPE TapCloudSave_AsyncGetCover(
    ITapCloudSave* self,
    int64_t request_id,
    const TapCloudSaveGetFileRequest* request
);
