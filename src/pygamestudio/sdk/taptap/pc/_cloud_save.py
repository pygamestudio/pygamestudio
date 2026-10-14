"""Cloud save: list / create / update / delete saves, download data and covers."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import Event

_handle = None


def _object():
    """The cached TapCloudSave singleton (obtained once, cleared on shutdown)."""
    global _handle
    if _handle is None:
        _handle = _core.require_initialized().TapCloudSave()
        if not _handle:
            raise _ffi.TapSDKError('TapCloudSave() returned NULL - is the SDK initialized?')
    return _handle


def _reset():
    global _handle
    _handle = None


_core.register_reset(_reset)
_dispatcher.dispatcher.register_parser(Event.CloudSaveList, _ffi.parse_cloud_save_list)
_dispatcher.dispatcher.register_parser(Event.CloudSaveCreate, _ffi.parse_cloud_save_created)
_dispatcher.dispatcher.register_parser(Event.CloudSaveUpdate, _ffi.parse_cloud_save_created)
_dispatcher.dispatcher.register_parser(Event.CloudSaveDelete, _ffi.parse_cloud_save_deleted)
_dispatcher.dispatcher.register_parser(Event.CloudSaveGetData, _ffi.parse_cloud_save_file)
_dispatcher.dispatcher.register_parser(Event.CloudSaveGetCover, _ffi.parse_cloud_save_file)


def list_saves():
    """拉取云存档列表（异步）。结果经 'cloud_save.listed' 返回。

    Async list; the Request completes as 'cloud_save.listed' with
    data['saves'] - a list of save infos (uuid, file_id, name, sizes, ...).
    """
    request = _dispatcher.dispatcher.new_request('cloud_save.listed')
    code = _core.require_initialized().TapCloudSave_AsyncList(_object(), request.id)
    _core.check_result(code, 'TapCloudSave_AsyncList')
    return request


def create(name, data_file, summary, extra='', playtime=0, cover_file=None):
    """创建云存档（异步）。结果经 'cloud_save.created' 返回。

    name 60 字节以内、不允许空、不允许汉字；summary 500 字节以内、不允许空；
    data_file / cover_file 是本地文件路径（存档 ≤10MB，封面 ≤512KB）。
    Create a save; files are read from disk (see the limits above).
    """
    request = _dispatcher.dispatcher.new_request('cloud_save.created')
    data = _ffi.TapCloudSaveCreateRequest()
    encoded = {
        'name': _ffi.encode(name),
        'summary': _ffi.encode(summary),
        'extra': _ffi.encode(extra),
        'data': _ffi.encode(str(data_file)),
        'cover': _ffi.encode(str(cover_file)) if cover_file else None,
    }
    data.name = encoded['name']
    data.summary = encoded['summary']
    data.extra = encoded['extra']
    data.playtime = int(playtime)
    data.data_file_path = encoded['data']
    data.cover_file_path = encoded['cover']
    code = _core.require_initialized().TapCloudSave_AsyncCreate(_object(), request.id,
                                                                 ctypes.byref(data))
    _core.check_result(code, 'TapCloudSave_AsyncCreate')
    return request


def update(uuid, name, data_file, summary, extra='', playtime=0, cover_file=None):
    """更新云存档（异步）。结果经 'cloud_save.updated' 返回；参数同 create()。

    Update a save (same rules and limits as create()); completes as
    'cloud_save.updated' with the refreshed save info in data['save'].
    """
    request = _dispatcher.dispatcher.new_request('cloud_save.updated')
    data = _ffi.TapCloudSaveUpdateRequest()
    encoded = {
        'uuid': _ffi.encode(uuid),
        'name': _ffi.encode(name),
        'summary': _ffi.encode(summary),
        'extra': _ffi.encode(extra),
        'data': _ffi.encode(str(data_file)),
        'cover': _ffi.encode(str(cover_file)) if cover_file else None,
    }
    data.uuid = encoded['uuid']
    data.name = encoded['name']
    data.summary = encoded['summary']
    data.extra = encoded['extra']
    data.playtime = int(playtime)
    data.data_file_path = encoded['data']
    data.cover_file_path = encoded['cover']
    code = _core.require_initialized().TapCloudSave_AsyncUpdate(_object(), request.id,
                                                                 ctypes.byref(data))
    _core.check_result(code, 'TapCloudSave_AsyncUpdate')
    return request


def delete(uuid):
    """删除云存档（异步）。结果经 'cloud_save.deleted' 返回。

    Delete a save; completes as 'cloud_save.deleted' (data['uuid']).
    """
    request = _dispatcher.dispatcher.new_request('cloud_save.deleted')
    encoded = _ffi.encode(uuid)
    code = _core.require_initialized().TapCloudSave_AsyncDelete(_object(), request.id, encoded)
    _core.check_result(code, 'TapCloudSave_AsyncDelete')
    return request


def get_data(uuid, file_id):
    """下载云存档数据文件（异步）。结果经 'cloud_save.data' 返回。

    The file arrives in memory: the Request completes as 'cloud_save.data'
    with data['data'] (bytes) and data['size']. Write it to disk yourself.
    """
    return _get_file('cloud_save.data', 'TapCloudSave_AsyncGetData', uuid, file_id)


def get_cover(uuid, file_id):
    """下载云存档封面文件（异步）。结果经 'cloud_save.cover' 返回（data['data'] 为 bytes）。

    Download the cover; completes as 'cloud_save.cover' with the same payload
    shape as get_data().
    """
    return _get_file('cloud_save.cover', 'TapCloudSave_AsyncGetCover', uuid, file_id)


def _get_file(event, api_name, uuid, file_id):
    request = _dispatcher.dispatcher.new_request(event)
    data = _ffi.TapCloudSaveGetFileRequest()
    encoded = {'uuid': _ffi.encode(uuid), 'file': _ffi.encode(file_id)}
    data.uuid = encoded['uuid']
    data.file_id = encoded['file']
    function = getattr(_core.require_initialized(), api_name)
    code = function(_object(), request.id, ctypes.byref(data))
    _core.check_result(code, api_name)
    return request
