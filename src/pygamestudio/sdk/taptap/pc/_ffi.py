"""ctypes access to ``taptap_api.dll`` - loading, signatures and errors.

The TapTap PC SDK is a flat C API (``extern "C"`` / ``__cdecl``), so one DLL
plus ctypes covers every Python version: no compiled glue and no per-version
binaries. This module finds and loads the DLL lazily, types every function it
exposes (ctypes would otherwise truncate 64-bit handles) and re-exports the
struct layer from ``_structs``.

Search order for the DLL (first hit wins):

1. ``PYGAMESTUDIO_TAPTAP_DLL`` (exact file path, for custom setups),
2. ``<project folder>/taptap_api.dll`` (a copy placed by the developer),
3. the engine copy: ``pygamestudio/common/res/sdk/taptap/pc/tapsdk_*/``
   (searched newest-first, so updating the SDK folder needs no code change).
"""

import ctypes
import os
import sys
from pathlib import Path

from . import _structs
from ._structs import *  # noqa: F401,F403 - struct and parse layer re-export

# =============================================================================
# Errors
# =============================================================================


class TapSDKError(RuntimeError):
    """Base class of every ``studio.sdk.taptap`` error."""


class TapSDKNotAvailable(TapSDKError):
    """The SDK cannot be used here (not Windows x64, or no taptap_api.dll)."""


class TapSDKNotInitialized(TapSDKError):
    """An SDK function was called before ``studio.sdk.taptap.pc.init()``."""


class TapSDKCallError(TapSDKError):
    """The SDK refused a call (non-zero immediate result, no callback will come)."""

    def __init__(self, api, code, message=''):
        self.api = api
        self.code = int(code)
        text_ = '{} refused the call with code {}'.format(api, self.code)
        if message:
            text_ += ': ' + message
        super().__init__(text_)


class TapSDKInitError(TapSDKError):
    """``TapSDK_Init`` failed; ``result`` is an ``InitResult`` value."""

    def __init__(self, result, message=''):
        self.result = int(result)
        text_ = 'TapSDK_Init failed with result {}'.format(self.result)
        if message:
            text_ += ': ' + message
        super().__init__(text_)


# =============================================================================
# Locating and loading the DLL
# =============================================================================

#: Environment variable overriding the DLL path (exact file).
ENV_DLL_PATH = 'PYGAMESTUDIO_TAPTAP_DLL'

_WINDOWS = sys.platform == 'win32'
_64BIT = ctypes.sizeof(ctypes.c_void_p) == 8

_library = None
_library_error = None


def _candidate_paths():
    """Places the SDK DLL is looked for, in priority order."""
    candidates = []

    override = os.environ.get(ENV_DLL_PATH)
    if override:
        candidates.append(Path(override))

    try:
        from pygamestudio.common.utils.path import get_project_path
        project = get_project_path()
        if project:
            candidates.append(Path(project) / 'taptap_api.dll')
    except Exception:
        pass

    try:
        from pygamestudio.common.utils.path import RES_PATH
        root = RES_PATH / 'sdk' / 'taptap' / 'pc'
        if root.is_dir():
            for folder in sorted(root.glob('tapsdk_*'), reverse=True):
                candidates.append(folder / 'taptap_api.dll')
    except Exception:
        pass

    return candidates


def library_path():
    """The DLL that would be loaded (None when no copy is installed)."""
    for candidate in _candidate_paths():
        if candidate.is_file():
            return candidate
    return None


def is_supported():
    """Whether this machine can run the SDK at all (Windows x64)."""
    return _WINDOWS and _64BIT


def load():
    """The loaded DLL, loading it on first use.

    Raises ``TapSDKNotAvailable`` with a readable reason when the platform is
    not Windows x64 or no ``taptap_api.dll`` can be found.
    """
    global _library, _library_error
    if _library is not None:
        return _library
    if _library_error is not None:
        raise TapSDKNotAvailable(_library_error)

    if not is_supported():
        _library_error = ('the TapTap PC SDK is Windows x64 only (this is '
                          '{} on {})'.format('64-bit' if _64BIT else '32-bit', sys.platform))
        raise TapSDKNotAvailable(_library_error)

    path = library_path()
    if path is None:
        _library_error = ('taptap_api.dll was not found; expected it in the project folder '
                          'or in pygamestudio/common/res/sdk/taptap/pc/tapsdk_*/')
        raise TapSDKNotAvailable(_library_error)

    try:
        library = ctypes.WinDLL(str(path))
        _configure(library)
    except TapSDKNotAvailable as e:
        _library_error = str(e)
        raise
    except OSError as e:
        _library_error = 'taptap_api.dll could not be loaded ({}): {}'.format(path, e)
        raise TapSDKNotAvailable(_library_error)

    _library = library
    return library


# =============================================================================
# Function signatures
# =============================================================================

#: name -> (restype, argtypes). Every function the wrapper uses is typed here;
#: a missing export fails the load with a clear message instead of a random
#: crash later.
_SIGNATURES = {
    # --- core ---------------------------------------------------------------
    'TapSDK_RestartAppIfNecessary': (ctypes.c_bool, (ctypes.c_char_p,)),
    'TapSDK_Init': (ctypes.c_uint32, (ctypes.c_char_p, ctypes.c_char_p)),
    'TapSDK_Shutdown': (ctypes.c_bool, ()),
    'TapSDK_GetClientID': (ctypes.c_bool, (ctypes.c_char_p,)),
    'TapSDK_RegisterCallback': (None, (ctypes.c_uint32, MainCallback)),
    'TapSDK_UnregisterCallback': (None, (ctypes.c_uint32, MainCallback)),
    'TapSDK_RunCallbacks': (None, ()),
    'TapSDK_CreateRandomNumberGenerator': (ctypes.c_int64, (ctypes.c_int32,)),
    'TapSDK_RandomInt': (ctypes.c_int32, (ctypes.c_int64,)),
    'TapSDK_DestroyRandomNumberGenerator': (None, (ctypes.c_int64,)),

    # --- user and DLC -------------------------------------------------------
    'TapApps_IsOwned': (ctypes.c_bool, ()),
    'TapUser_AsyncAuthorize': (ctypes.c_uint32, (ctypes.c_char_p,)),
    'TapUser_AsyncGetApprovedScopes': (ctypes.c_uint32, (ctypes.c_int64,)),
    'TapUser_GetOpenID': (ctypes.c_bool, (ctypes.c_char_p,)),
    'TapDLC_ShowStore': (ctypes.c_bool, (ctypes.c_char_p,)),
    'TapDLC_IsOwned': (ctypes.c_bool, (ctypes.c_char_p,)),
    'TapDLC_QueryDetails': (ctypes.c_uint32, (ctypes.POINTER(TapDLCQueryDetailsRequest),
                                              ctypes.POINTER(TapDLCQueryDetailsResponse))),

    # --- achievements -------------------------------------------------------
    'TapAchievement': (ctypes.c_void_p, ()),
    'TapAchievement_AsyncUnlock': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64,
                                                     ctypes.POINTER(TapAchievementUnlockRequest))),
    'TapAchievement_AsyncIncrement': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64,
                                                        ctypes.POINTER(TapAchievementIncrementRequest))),
    'TapAchievement_ShowAchievements': (ctypes.c_uint32, (ctypes.c_void_p,)),

    # --- cloud save ---------------------------------------------------------
    'TapCloudSave': (ctypes.c_void_p, ()),
    'TapCloudSave_AsyncList': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
    'TapCloudSave_AsyncCreate': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64,
                                                   ctypes.POINTER(TapCloudSaveCreateRequest))),
    'TapCloudSave_AsyncUpdate': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64,
                                                   ctypes.POINTER(TapCloudSaveUpdateRequest))),
    'TapCloudSave_AsyncDelete': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64, ctypes.c_char_p)),
    'TapCloudSave_AsyncGetData': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64,
                                                    ctypes.POINTER(TapCloudSaveGetFileRequest))),
    'TapCloudSave_AsyncGetCover': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64,
                                                     ctypes.POINTER(TapCloudSaveGetFileRequest))),

    # --- compliance ---------------------------------------------------------
    'TapCompliance': (ctypes.c_void_p, ()),
    'TapCompliance_AsyncEnsureRealName': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
    'TapCompliance_EnableAntiAddiction': (ctypes.c_uint32, (ctypes.c_void_p,)),
    'TapCompliance_CheckPaymentLimit': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(TapComplianceCheckPaymentLimitRequest),
        ctypes.POINTER(TapComplianceCheckPaymentLimitResponse))),
    'TapCompliance_SubmitPayment': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(TapComplianceSubmitPaymentRequest))),

    # --- leaderboard --------------------------------------------------------
    'TapLeaderboard': (ctypes.c_void_p, ()),
    'TapLeaderboard_AsyncSubmitScores': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapLeaderboardSubmitScoresRequest))),
    'TapLeaderboard_AsyncLoadScores': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapLeaderboardLoadScoresRequest))),
    'TapLeaderboard_AsyncLoadMyScores': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapLeaderboardLoadMyScoresRequest))),
    'TapLeaderboard_AsyncLoadMyCenteredScores': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapLeaderboardLoadMyCenteredScoresRequest))),
    'TapLeaderboard_ShowLeaderboards': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(TapLeaderboardShowRequest))),

    # --- relation -----------------------------------------------------------
    'TapRelation': (ctypes.c_void_p, ()),
    'TapRelation_AsyncGetFriendList': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapRelationGetFriendListRequest))),
    'TapRelation_AsyncGetFollowingList': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapRelationGetFriendListRequest))),
    'TapRelation_AsyncGetFanList': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapRelationGetFriendListRequest))),
    'TapRelation_AsyncSyncRelationshipWithOpenID': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64,
        ctypes.POINTER(TapRelationSyncRelationshipWithOpenIDRequest))),
    'TapRelation_AsyncSyncRelationshipWithUnionID': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64,
        ctypes.POINTER(TapRelationSyncRelationshipWithUnionIDRequest))),
    'TapRelation_GetUnreadMessageCount': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))),
    'TapRelation_GetNewFanCount': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))),
    'TapRelation_ShowIM': (ctypes.c_uint32, (ctypes.c_void_p,)),
    'TapRelation_ShowUserProfile': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(TapRelationShowUserProfileRequest))),
    'TapRelation_InviteGame': (ctypes.c_uint32, (ctypes.c_void_p,)),
    'TapRelation_InviteTeam': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.POINTER(TapRelationInviteTeamRequest))),
    'TapRelation_HandleInviteScheme': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_char_p)),

    # --- online battle ------------------------------------------------------
    'TapOnlineBattle': (ctypes.c_void_p, ()),
    'TapOnlineBattle_RunCallbacks': (ctypes.c_uint32, (
        ctypes.c_void_p, OnlineBattleCallback, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32))),
    'TapOnlineBattle_AsyncConnect': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
    'TapOnlineBattle_AsyncDisconnect': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
    'TapOnlineBattle_AsyncCreateRoom': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleCreateRoomRequest))),
    'TapOnlineBattle_AsyncMatchRoom': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleMatchRoomRequest))),
    'TapOnlineBattle_AsyncGetRoomList': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleGetRoomListRequest))),
    'TapOnlineBattle_AsyncJoinRoom': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleJoinRoomRequest))),
    'TapOnlineBattle_AsyncLeaveRoom': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
    'TapOnlineBattle_AsyncUpdatePlayerCustomStatus': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.c_int32)),
    'TapOnlineBattle_AsyncUpdatePlayerCustomProperties': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.c_char_p)),
    'TapOnlineBattle_AsyncUpdateRoomProperties': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleUpdateRoomPropertiesRequest))),
    'TapOnlineBattle_AsyncSendCustomMessage': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleSendCustomMessageRequest))),
    'TapOnlineBattle_AsyncKickRoomPlayer': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.c_char_p)),
    'TapOnlineBattle_AsyncStartFrameSync': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
    'TapOnlineBattle_AsyncSendFrameInput': (ctypes.c_uint32, (
        ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(TapOnlineBattleSendFrameInputRequest))),
    'TapOnlineBattle_AsyncStopFrameSync': (ctypes.c_uint32, (ctypes.c_void_p, ctypes.c_int64)),
}


def _configure(library):
    """Apply every function signature; fail loudly on a wrong DLL."""
    missing = []
    for name, (restype, argtypes) in _SIGNATURES.items():
        try:
            function = getattr(library, name)
        except AttributeError:
            missing.append(name)
            continue
        function.restype = restype
        function.argtypes = list(argtypes)
    if missing:
        raise TapSDKNotAvailable(
            'taptap_api.dll does not export {} expected function(s) - is this the right '
            'version?: {}'.format(len(missing), ', '.join(sorted(missing))))


__all__ = [
    'TapSDKError', 'TapSDKNotAvailable', 'TapSDKNotInitialized',
    'TapSDKCallError', 'TapSDKInitError',
    'ENV_DLL_PATH', 'library_path', 'is_supported', 'load',
]
