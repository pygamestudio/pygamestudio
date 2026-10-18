"""studio.sdk.taptap.pc - the TapTap PC SDK, callable from Python.

Windows x64 only (the SDK ships as a Windows DLL); games published on TapTap
use it for login, DLC, achievements, cloud saves, leaderboards, compliance
(China release) and online battle. Nothing needs a compiler: the DLL is driven
with ctypes, so one file works on every Python version.

Typical game integration::

    import pygamestudio as studio

    # keys from the TapTap developer center; keep them in the game's own code
    CLIENT_ID = '...'
    PUB_KEY = '...'

    pc = studio.sdk.taptap.pc
    pc.restart_app_if_necessary(CLIENT_ID)   # before Game().run()
    # -> True: TapTap relaunches the game, exit the process
    pc.init(CLIENT_ID, PUB_KEY)

    # in the game loop (on_update):
    pc.run_callbacks()

    # results are events + Request objects:
    pc.on('authorize_finished', my_handler)
    request = pc.achievement.unlock('first_win')
    # request.done / request.ok / request.data once run_callbacks() delivered it

Where the SDK is not available (web build, non-Windows, DLL missing)
``available()`` is False and every call raises ``TapSDKNotAvailable`` with a
readable reason instead of failing randomly.

``client_id`` / ``public_key`` are optional arguments. A game that prefers to
keep them in its project settings may add the section itself (the editor never
writes it) and let the defaults read it::

    {"taptap": {"client_id": "...", "public_key": "..."}}
"""

from . import _achievement as achievement
from . import _cloud_save as cloud_save
from . import _compliance as compliance
from . import _core
from . import _dlc as dlc
from . import _leaderboard as leaderboard
from . import _online_battle as online_battle
from . import _relation as relation
from . import _user as user
from ._const import (
    AuthorizeResult,
    CloudSaveResult,
    ComplianceActionType,
    ErrorCode,
    Event,
    InitResult,
    LeaderboardCollection,
    OnlineBattleEvent,
    RealNameStatus,
    RelationAction,
    Result,
    SystemState,
)
from ._core import (
    available,
    create_random_number_generator,
    destroy_random_number_generator,
    get_client_id,
    init,
    is_app_owned,
    is_initialized,
    library_path,
    off,
    off_all,
    on,
    random_int,
    restart_app_if_necessary,
    run_callbacks,
    shutdown,
    wait,
)
from ._dispatcher import Request
from ._ffi import (
    TapSDKCallError,
    TapSDKError,
    TapSDKInitError,
    TapSDKNotAvailable,
    TapSDKNotInitialized,
)

__all__ = [
    # lifecycle / pump
    'available', 'library_path', 'is_initialized', 'init', 'shutdown',
    'restart_app_if_necessary', 'get_client_id', 'run_callbacks', 'wait',
    'on', 'off', 'off_all',
    # helpers
    'is_app_owned', 'create_random_number_generator', 'random_int',
    'destroy_random_number_generator',
    # feature namespaces
    'user', 'dlc', 'achievement', 'cloud_save', 'leaderboard',
    'compliance', 'relation', 'online_battle',
    # types
    'Request',
    'TapSDKError', 'TapSDKNotAvailable', 'TapSDKNotInitialized',
    'TapSDKCallError', 'TapSDKInitError',
    'InitResult', 'AuthorizeResult', 'Result', 'ErrorCode', 'Event',
    'SystemState', 'CloudSaveResult', 'ComplianceActionType', 'RealNameStatus',
    'LeaderboardCollection', 'RelationAction', 'OnlineBattleEvent',
]
