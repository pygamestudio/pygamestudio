"""DLC: ownership, the store page and product details."""

import ctypes

from . import _core, _dispatcher, _ffi
from ._const import Event

_dispatcher.dispatcher.register_parser(Event.DLCPlayableStatusChanged, _ffi.parse_dlc_playable)


def is_owned(dlc_id):
    """当前用户是否拥有指定 DLC。Whether the user owns the DLC."""
    return bool(_core.require_initialized().TapDLC_IsOwned(_ffi.encode(dlc_id)))


def show_store(dlc_id):
    """打开指定 DLC 的 TapTap 商店页；返回是否成功打开。

    Open the DLC's store page in the TapTap client (True on success).
    """
    return bool(_core.require_initialized().TapDLC_ShowStore(_ffi.encode(dlc_id)))


def query_details(dlc_ids):
    """查询 DLC 商品明细（同步接口，一次最多 20 个 ID），返回字典列表。

    ids/name/type (1 = DLC, 2 = complete edition)/owned/prices are in cents
    (原创价、折后价), discount_start_time / discount_end_time are unix seconds
    (0 when there is no discount right now).
    """
    ids = [str(item) for item in dlc_ids]
    if not ids:
        raise ValueError('dlc_ids must not be empty')
    if len(ids) > 20:
        raise ValueError('the SDK accepts at most 20 DLC ids per query')

    request = _ffi.TapDLCQueryDetailsRequest()
    request.id_count = len(ids)
    for index, dlc_id in enumerate(ids):
        request.ids[index].value = dlc_id.encode('utf-8')
    response = _ffi.TapDLCQueryDetailsResponse()

    code = _core.require_initialized().TapDLC_QueryDetails(ctypes.byref(request),
                                                           ctypes.byref(response))
    _core.check_result(code, 'TapDLC_QueryDetails')

    details = []
    for index in range(response.detail_count):
        entry = response.details[index]
        details.append({
            'id': entry.id.decode('utf-8', 'replace'),
            'name': entry.name.decode('utf-8', 'replace'),
            'type': int(entry.type),
            'owned': bool(entry.owned),
            'original_price': int(entry.original_price),
            'discounted_price': int(entry.discounted_price),
            'discount_start_time': int(entry.discount_start_time),
            'discount_end_time': int(entry.discount_end_time),
        })
    return details
