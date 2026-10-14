"""User: TapTap login (authorize flow), approved scopes and the OpenID."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import AuthorizeResult, Event

_dispatcher.dispatcher.register_parser(Event.AuthorizeFinished, _ffi.parse_authorize_finished)
_dispatcher.dispatcher.register_parser(Event.UserGetApprovedScopes, _ffi.parse_approved_scopes)


def login(scopes='public_profile'):
    """发起 TapTap 授权登录；最终结果通过 'authorize_finished' 事件返回。

    返回值为 AuthorizeResult（是否成功发起流程，不等于授权成功）。授权完成后
    事件负载包含 is_cancel / error / token_type / kid / mac_key /
    mac_algorithm / scope，可用 studio.sdk.taptap.pc.on('authorize_finished', cb)
    或先调用再订阅。
    Starts the authorize flow (TapTap asks the user to confirm). Returns the
    immediate AuthorizeResult; subscribe to 'authorize_finished' for the result.
    """
    result = int(_core.require_initialized().TapUser_AsyncAuthorize(_ffi.encode(scopes)))
    return AuthorizeResult(result)


def get_approved_scopes():
    """异步获取当前用户已授权的权限范围；结果经 'user.get_approved_scopes' 返回。

    Async query of the user's approved scopes; completes the returned Request
    (payload['scopes'] is the list of scope strings).
    """
    request = _dispatcher.dispatcher.new_request('user.get_approved_scopes')
    code = _core.require_initialized().TapUser_AsyncGetApprovedScopes(request.id)
    _core.check_result(code, 'TapUser_AsyncGetApprovedScopes')
    return request


def get_open_id():
    """当前用户 OpenID（未登录或不可用时为 None）。The user OpenID, or None."""
    library = _core.require_initialized()
    buffer = ctypes.create_string_buffer(256)
    if library.TapUser_GetOpenID(buffer) and buffer.value:
        return buffer.value.decode('utf-8', 'replace')
    return None
