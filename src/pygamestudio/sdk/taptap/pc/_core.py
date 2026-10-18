"""Core of ``studio.sdk.taptap.pc``: lifecycle, the per-frame pump, shared state.

The lifecycle mirrors the SDK exactly::

    pc.restart_app_if_necessary(client_id)   # before Game().run(); True -> sys.exit()
    pc.init(client_id, pub_key)              # keys from the TapTap developer center
    ...                                      # game loop: pc.run_callbacks() every frame
    pc.shutdown()                            # optional, when the game quits

The client id and the game public key are the game's own settings: pass them
to ``init()`` / ``restart_app_if_necessary()``, or keep them in an optional
``taptap`` section of ``project.pygs`` that the developer adds himself (the
editor never writes it) and let the defaults read it::

    {"taptap": {"client_id": "...", "public_key": "..."}}

Explicit arguments always win over that section.
"""

import ctypes
import traceback

from . import _dispatcher, _ffi
from ._const import Event, InitResult


class _State:
    __slots__ = ('initialized', 'client_id', 'pub_key', 'init_result')

    def __init__(self):
        self.initialized = False
        self.client_id = None
        self.pub_key = None
        self.init_result = None


_state = _State()

#: Handle-clearing hooks of the feature modules (cached C singleton handles).
_resetters = []


def register_reset(func):
    """Engine-internal: register a hook that drops a cached SDK handle."""
    _resetters.append(func)


def _run_resets():
    for func in list(_resetters):
        try:
            func()
        except Exception:
            traceback.print_exc()


def check_result(code, api):
    """Engine-internal: raise TapSDKCallError on a non-zero immediate result."""
    if int(code) != 0:
        raise _ffi.TapSDKCallError(api, int(code))


# Core event parsers (every feature module registers its own).
_dispatcher.dispatcher.register_parser(Event.SystemStateChanged, _ffi.parse_system_state)
_dispatcher.dispatcher.register_parser(Event.GamePlayableStatusChanged, _ffi.parse_game_playable)


# =============================================================================
# Availability and state
# =============================================================================


def available():
    """本机是否可以使用 TapTap PC SDK（Windows x64 且已安装 taptap_api.dll）。True when this machine can use the SDK."""
    return _ffi.is_supported() and _ffi.library_path() is not None


def library_path():
    """将被加载的 taptap_api.dll 路径（未安装时为 None）。Path of the DLL that would load (None when missing)."""
    path = _ffi.library_path()
    return str(path) if path is not None else None


def is_initialized():
    """SDK 是否已成功初始化。True after init() succeeded (until shutdown())."""
    return _state.initialized


def require_initialized():
    """Engine-internal: the loaded DLL, or raise when init() was not called."""
    if not _state.initialized:
        raise _ffi.TapSDKNotInitialized(
            'the TapTap PC SDK is not initialized yet - call studio.sdk.taptap.pc.init() first')
    return _ffi.load()


def _project_taptap_config():
    """The optional ``taptap`` section of project.pygs ({} when unavailable).

    The editor never writes this section - the game decides whether to keep its
    keys in project.pygs or in its own code. When it exists, ``init()`` and
    ``restart_app_if_necessary()`` use it for values the caller left out;
    explicit arguments always win.
    """
    config = {}
    try:
        from pygamestudio.api.config.project import get_project_config
        config = get_project_config() or {}
    except Exception:
        try:
            import json
            from pathlib import Path

            from pygamestudio.common.utils import assets
            candidate = Path.cwd() / 'project.pygs'
            if candidate.is_file():
                config = json.loads(assets.read_text(candidate)) or {}
        except Exception:
            config = {}
    section = config.get('taptap') if isinstance(config, dict) else None
    return section if isinstance(section, dict) else {}


# =============================================================================
# Lifecycle
# =============================================================================


def restart_app_if_necessary(client_id=None):
    """检查游戏是否需要通过 TapTap 重启；在 main.py 最顶部、创建窗口前调用。

    返回 True 表示 TapTap 正在重新启动游戏，当前进程应立即退出（sys.exit()）。
    client_id 可以传参；缺省时读取 project.pygs 中若存在的 taptap.client_id
    （该字段由开发者自行添加，编辑器不会写入）。
    True when the game must restart through TapTap - quit the current process.
    """
    client_id = client_id or _project_taptap_config().get('client_id')
    if not client_id:
        raise _ffi.TapSDKError(
            'restart_app_if_necessary needs the client id: pass client_id=... (from the '
            'TapTap developer center), or add a "taptap" section with "client_id" to '
            'project.pygs yourself and read it in your game')
    library = _ffi.load()
    return bool(library.TapSDK_RestartAppIfNecessary(_ffi.encode(client_id)))


def init(client_id=None, pub_key=None):
    """初始化 TapSDK；成功返回 InitResult.OK，失败抛出 TapSDKInitError。

    client_id / pub_key 可以直接传参（推荐，key 属于游戏自己的代码）；缺省时
    读取 project.pygs 中若存在的 taptap.client_id / taptap.public_key —— 该
    字段由开发者自行添加，编辑器不会写入。传参优先于配置。
    Initialize the SDK. Returns InitResult.OK, raises TapSDKInitError otherwise.
    """
    if _state.initialized:
        return InitResult.OK
    library = _ffi.load()               # raises TapSDKNotAvailable with a reason
    config = _project_taptap_config()
    client_id = client_id or config.get('client_id')
    pub_key = pub_key or config.get('public_key') or config.get('pub_key')
    if not pub_key:
        raise _ffi.TapSDKError(
            'the TapSDK needs the game public key: pass pub_key=... (from the TapTap '
            'developer center), or add a "taptap" section with "public_key" to '
            'project.pygs yourself and read it in your game')

    error_buffer = ctypes.create_string_buffer(1024)
    result = int(library.TapSDK_Init(error_buffer, _ffi.encode(pub_key)))
    message = error_buffer.value.decode('utf-8', 'replace') if error_buffer.value else ''
    _state.init_result = result
    if result != int(InitResult.OK):
        hints = {
            int(InitResult.NoPlatform): 'the TapTap client is not installed or not running',
            int(InitResult.NotLaunchedByPlatform): 'the game must be started through the TapTap client',
            int(InitResult.PlatformVersionMismatch): 'update the TapTap client and the game',
        }
        detail = '; '.join(part for part in (message, hints.get(result, '')) if part)
        raise _ffi.TapSDKInitError(result, detail)

    _state.initialized = True
    _state.client_id = client_id
    _state.pub_key = pub_key
    _dispatcher.dispatcher.install()
    return InitResult.OK


def shutdown():
    """关闭 SDK、注销全部回调（未初始化时安全地什么都不做）。Shut the SDK down (safe when not initialized)."""
    if not _state.initialized:
        return
    try:
        _dispatcher.dispatcher.uninstall()
    except Exception:
        pass                            # never block a shutdown on unregistering
    try:
        _ffi.load().TapSDK_Shutdown()
    finally:
        _state.initialized = False
        _state.init_result = None
        _run_resets()
        _dispatcher.dispatcher.reset()


def get_client_id():
    """当前客户端 ID（不可用时为 None）。The client id in use, or None."""
    library = require_initialized()
    buffer = ctypes.create_string_buffer(256)
    if library.TapSDK_GetClientID(buffer) and buffer.value:
        return buffer.value.decode('utf-8', 'replace')
    return _state.client_id


# =============================================================================
# The per-frame pump and the event table
# =============================================================================


def run_callbacks():
    """处理 SDK 回调并派发事件；请在游戏主循环中每帧调用。

    返回本帧送达 Python 回调的事件数。
    Process SDK callbacks and deliver events; call it every frame. Returns the
    number of events delivered to Python callbacks. Safe before init() (0).
    """
    if not _state.initialized:
        return 0
    _ffi.load().TapSDK_RunCallbacks()
    _dispatcher.dispatcher.pump_extras()
    return _dispatcher.dispatcher.pump()


def wait(request, timeout=10.0, interval=0.01):
    """运行回调泵直到请求完成（或超时）；期间游戏不渲染。

    Use it on loading screens; in a running game prefer polling
    ``request.done`` in ``on_update()`` so the window keeps drawing.
    Returns the request (finished or not).
    """
    import time
    deadline = time.monotonic() + max(0.0, float(timeout))
    while not request.done and time.monotonic() < deadline:
        run_callbacks()
        if request.done:
            break
        time.sleep(interval)
    return request


def on(event, callback):
    """订阅事件（事件名见文档；'*' 订阅全部）；返回取消订阅的函数。

    Subscribe to an event name ('*' = every event); returns an unsubscribe
    function. Callbacks run inside run_callbacks(), on the game thread.
    """
    return _dispatcher.dispatcher.subscribe(str(event), callback)


def off(event, callback):
    """取消一个事件订阅。Remove one subscription."""
    _dispatcher.dispatcher.unsubscribe(str(event), callback)


def off_all(event=None):
    """取消全部订阅（或某事件的订阅）。Remove every subscription (or one event's)."""
    _dispatcher.dispatcher.unsubscribe_all(event)


# =============================================================================
# Misc core helpers
# =============================================================================


def is_app_owned():
    """当前用户是否拥有游戏本体。Whether the user owns the game on TapTap."""
    return bool(require_initialized().TapApps_IsOwned())


def create_random_number_generator(seed):
    """创建确定性随机数生成器（与平台共享序列），返回生成器 ID。

    A deterministic RNG shared with the platform (same seed = same sequence).
    Returns the generator id; raises on failure.
    """
    generator = int(require_initialized().TapSDK_CreateRandomNumberGenerator(int(seed)))
    if not generator:
        raise _ffi.TapSDKError('the random number generator could not be created')
    return generator


def random_int(generator):
    """生成 [0, 2^31) 的随机整数。A random int in [0, 2^31)."""
    value = int(require_initialized().TapSDK_RandomInt(int(generator)))
    if value < 0:
        raise _ffi.TapSDKError('the random number generator id is invalid')
    return value


def destroy_random_number_generator(generator):
    """销毁随机数生成器。Destroy an RNG (invalid ids are ignored)."""
    require_initialized().TapSDK_DestroyRandomNumberGenerator(int(generator))
