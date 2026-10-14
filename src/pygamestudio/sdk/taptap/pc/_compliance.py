"""Compliance (China release): real-name check, anti-addiction, payment limits."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import Event

_handle = None


def _object():
    """The cached TapCompliance singleton (obtained once, cleared on shutdown)."""
    global _handle
    if _handle is None:
        _handle = _core.require_initialized().TapCompliance()
        if not _handle:
            raise _ffi.TapSDKError('TapCompliance() returned NULL - is the SDK initialized?')
    return _handle


def _reset():
    global _handle
    _handle = None


_core.register_reset(_reset)
_dispatcher.dispatcher.register_parser(Event.ComplianceEnsureRealName, _ffi.parse_real_name_result)
_dispatcher.dispatcher.register_parser(Event.ComplianceActions, _ffi.parse_compliance_actions)


def ensure_real_name():
    """发起实名检查（未实名时 TapTap 会弹出认证窗口）；结果经 'compliance.real_name_result' 返回。

    The Request completes as 'compliance.real_name_result'; data['status'] is
    a RealNameStatus (Success / Canceled / Failed).
    """
    request = _dispatcher.dispatcher.new_request('compliance.real_name_result')
    code = _core.require_initialized().TapCompliance_AsyncEnsureRealName(_object(), request.id)
    _core.check_result(code, 'TapCompliance_AsyncEnsureRealName')
    return request


def enable_anti_addiction():
    """启动防沉迷检查；之后通过 'compliance.actions' 事件收到提示/退出等动作。

    Start the anti-addiction check; popups arrive as 'compliance.actions'
    events (data['actions'] - one dict per action: action_type/title/
    description/display_duration_seconds).
    """
    code = _core.require_initialized().TapCompliance_EnableAntiAddiction(_object())
    _core.check_result(code, 'TapCompliance_EnableAntiAddiction')


def check_payment_limit(amount):
    """检查充值限制（同步）；amount 单位为分（64800 = 648 元）。

    返回 {'allow': bool, 'title': str, 'description': str}（不允许时 title/
    description 是给玩家看的提示）。
    Synchronous payment-limit check; amounts are in cents (64800 = 648 CNY).
    """
    request = _ffi.TapComplianceCheckPaymentLimitRequest()
    request.amount = int(amount)
    response = _ffi.TapComplianceCheckPaymentLimitResponse()
    code = _core.require_initialized().TapCompliance_CheckPaymentLimit(
        _object(), ctypes.byref(request), ctypes.byref(response))
    _core.check_result(code, 'TapCompliance_CheckPaymentLimit')
    return {
        'allow': bool(response.allow),
        'title': response.title.decode('utf-8', 'replace'),
        'description': response.description.decode('utf-8', 'replace'),
    }


def submit_payment(amount):
    """上报充值金额（同步）；amount 单位为分。Report a payment (cents)."""
    request = _ffi.TapComplianceSubmitPaymentRequest()
    request.amount = int(amount)
    code = _core.require_initialized().TapCompliance_SubmitPayment(_object(),
                                                                   ctypes.byref(request))
    _core.check_result(code, 'TapCompliance_SubmitPayment')
