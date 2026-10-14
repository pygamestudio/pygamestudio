"""Event dispatch: turns the SDK's C callbacks into Python callbacks + Requests.

The SDK delivers results Steamworks-style: an async call returns immediately
and its response arrives later through a registered callback while
``TapSDK_RunCallbacks()`` is running. This module sits between the two:

* one ``CFUNCTYPE`` trampoline per event id is registered with the SDK and
  kept alive here (the SDK would crash on a garbage-collected callback);
* the trampoline parses the payload *immediately* - the SDK only keeps the
  pointer valid during the callback - and puts a plain dict on a queue;
* ``pump()`` (called through ``studio.sdk.taptap.pc.run_callbacks()`` from the
  game loop) drains the queue on the calling thread, completes the matching
  :class:`Request` and notifies the subscribers. User callbacks therefore
  always run on the game's main thread, where pygame is safe to touch.

Online battle has its own callback pump inside the SDK; its trampoline feeds
the same queue, so one ``run_callbacks()`` call per frame covers everything.
"""

import queue
import threading
import traceback

from . import _ffi
from ._const import Event, OnlineBattleEvent

#: Main event id -> canonical name (used by pc.on/off and request completion).
MAIN_EVENT_NAMES = {
    int(Event.SystemStateChanged): 'system_state_changed',
    int(Event.AuthorizeFinished): 'authorize_finished',
    int(Event.UserGetApprovedScopes): 'user.get_approved_scopes',
    int(Event.GamePlayableStatusChanged): 'game.playable_status_changed',
    int(Event.DLCPlayableStatusChanged): 'dlc.playable_status_changed',
    int(Event.CloudSaveList): 'cloud_save.listed',
    int(Event.CloudSaveCreate): 'cloud_save.created',
    int(Event.CloudSaveUpdate): 'cloud_save.updated',
    int(Event.CloudSaveDelete): 'cloud_save.deleted',
    int(Event.CloudSaveGetData): 'cloud_save.data',
    int(Event.CloudSaveGetCover): 'cloud_save.cover',
    int(Event.AchievementUnlock): 'achievement.unlocked',
    int(Event.AchievementIncrement): 'achievement.incremented',
    int(Event.ComplianceEnsureRealName): 'compliance.real_name_result',
    int(Event.ComplianceActions): 'compliance.actions',
    int(Event.LeaderboardSubmitScores): 'leaderboard.submitted',
    int(Event.LeaderboardLoadScores): 'leaderboard.loaded',
    int(Event.LeaderboardLoadMyScores): 'leaderboard.my_scores',
    int(Event.LeaderboardLoadMyCenteredScores): 'leaderboard.my_centered_scores',
    int(Event.RelationGetFriendList): 'relation.friend_list',
    int(Event.RelationGetFollowingList): 'relation.following_list',
    int(Event.RelationGetFanList): 'relation.fan_list',
    int(Event.RelationSyncRelationshipWithOpenID): 'relation.sync_result',
    int(Event.RelationSyncRelationshipWithUnionID): 'relation.sync_result',
    int(Event.RelationUnreadMessageCountChanged): 'relation.unread_count_changed',
    int(Event.RelationNewFanCountChanged): 'relation.new_fan_count_changed',
    int(Event.RelationGameInviteReceived): 'relation.game_invite_received',
    int(Event.RelationTeamInviteReceived): 'relation.team_invite_received',
}

#: Online battle event id -> canonical name.
ONLINE_BATTLE_NAMES = {
    int(OnlineBattleEvent.ConnectResponse): 'online_battle.connected',
    int(OnlineBattleEvent.DisconnectResponse): 'online_battle.disconnected',
    int(OnlineBattleEvent.CreateRoomResponse): 'online_battle.room_created',
    int(OnlineBattleEvent.MatchRoomResponse): 'online_battle.room_matched',
    int(OnlineBattleEvent.GetRoomListResponse): 'online_battle.room_list',
    int(OnlineBattleEvent.JoinRoomResponse): 'online_battle.room_joined',
    int(OnlineBattleEvent.LeaveRoomResponse): 'online_battle.room_left',
    int(OnlineBattleEvent.UpdatePlayerCustomStatusResponse): 'online_battle.player_status_updated',
    int(OnlineBattleEvent.UpdatePlayerCustomPropertiesResponse): 'online_battle.player_properties_updated',
    int(OnlineBattleEvent.UpdateRoomPropertiesResponse): 'online_battle.room_properties_updated',
    int(OnlineBattleEvent.SendCustomMessageResponse): 'online_battle.message_sent',
    int(OnlineBattleEvent.KickRoomPlayerResponse): 'online_battle.player_kicked',
    int(OnlineBattleEvent.StartFrameSyncResponse): 'online_battle.frame_sync_started',
    int(OnlineBattleEvent.SendFrameInputResponse): 'online_battle.frame_input_sent',
    int(OnlineBattleEvent.StopFrameSyncResponse): 'online_battle.frame_sync_stopped',
    int(OnlineBattleEvent.ServiceErrorNotification): 'online_battle.service_error',
    int(OnlineBattleEvent.DisconnectNotification): 'online_battle.disconnect_notice',
    int(OnlineBattleEvent.PlayerOfflineNotification): 'online_battle.player_offline',
    int(OnlineBattleEvent.PlayerEnterRoomNotification): 'online_battle.player_entered',
    int(OnlineBattleEvent.PlayerLeaveRoomNotification): 'online_battle.player_left',
    int(OnlineBattleEvent.PlayerCustomStatusNotification): 'online_battle.player_custom_status',
    int(OnlineBattleEvent.PlayerCustomPropertiesNotification): 'online_battle.player_custom_properties',
    int(OnlineBattleEvent.RoomPropertiesNotification): 'online_battle.room_properties_changed',
    int(OnlineBattleEvent.CustomMessageNotification): 'online_battle.custom_message',
    int(OnlineBattleEvent.RoomPlayerKickedNotification): 'online_battle.kicked_notice',
    int(OnlineBattleEvent.FrameSyncStartNotification): 'online_battle.frame_sync_start_notice',
    int(OnlineBattleEvent.FrameNotification): 'online_battle.frame',
    int(OnlineBattleEvent.FrameSyncStopNotification): 'online_battle.frame_sync_stop_notice',
}


class Request:
    """One pending async SDK request.

    Completed while ``pc.run_callbacks()`` runs: ``done`` turns True, ``data``
    holds the parsed response and ``error`` stays None on success. The payment
    for not blocking: the game loop keeps running while the SDK works, so the
    callback style (``pc.wait`` / polling ``done`` in ``on_update``) is what
    keeps a game responsive.
    """

    __slots__ = ('id', 'event', 'done', 'error', 'data')

    def __init__(self, request_id, event):
        self.id = int(request_id)
        self.event = event
        self.done = False
        self.error = None
        self.data = None

    @property
    def ok(self):
        """True when the response arrived and carried no error."""
        return self.done and self.error is None

    def __repr__(self):
        return '<Request #{} {} {}>'.format(
            self.id, self.event, 'done' if self.done else 'pending')


class Dispatcher:
    """Callback trampolines, the event queue, subscribers and requests."""

    def __init__(self):
        self._lock = threading.RLock()
        self._queue = queue.Queue()
        self._requests = {}
        self._finished = []             # completed ids, oldest first (bounded)
        self._next_id = 1
        self._subscribers = {}          # name -> [callback]
        self._parsers = {}              # main event id -> parse(c_void_p) -> dict
        self._trampolines = {}          # main event id -> MainCallback (alive!)
        self._online_battle_trampoline = None
        self._extra_pumps = []          # callables for other SDK event streams

    # ------------------------------------------------------------- requests
    def new_request(self, event):
        """Register and return a fresh :class:`Request` for ``event``."""
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
        request = Request(request_id, event)
        self._requests[request_id] = request
        return request

    def request(self, request_id):
        """The Request with that id (or None)."""
        return self._requests.get(int(request_id))

    # ---------------------------------------------------------- registration
    def register_parser(self, event_id, parser):
        """Teach the dispatcher how to parse one main event's payload."""
        self._parsers[int(event_id)] = parser

    def register_pump(self, func):
        """Register an extra per-frame pump (e.g. online battle events)."""
        self._extra_pumps.append(func)

    def install(self):
        """Register one trampoline per known event with the initialized SDK."""
        library = _ffi.load()
        for event_id in sorted(self._parsers):
            if event_id in self._trampolines:
                continue
            callback = _ffi.MainCallback(self._make_main_trampoline(event_id))
            library.TapSDK_RegisterCallback(event_id, callback)
            self._trampolines[event_id] = callback

    def _make_main_trampoline(self, event_id):
        def trampoline(_value, data):
            self.handle_main_event(event_id, data)
        return trampoline

    def uninstall(self):
        """Unregister every trampoline (called before TapSDK_Shutdown)."""
        library = _ffi.load()
        for event_id, callback in list(self._trampolines.items()):
            try:
                library.TapSDK_UnregisterCallback(event_id, callback)
            except Exception:
                traceback.print_exc()
        self._trampolines.clear()

    def reset(self):
        """Clear queued events; pending requests fail instead of hanging."""
        self._trampolines.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        for request in list(self._requests.values()):
            if not request.done:
                request.done = True
                request.error = {
                    'code': -1,
                    'message': 'the SDK was shut down before the response arrived',
                }

    # ------------------------------------------------------- event handling
    def handle_main_event(self, event_id, data_pointer):
        """CFUNCTYPE target - runs inside ``TapSDK_RunCallbacks()``.

        Parses the payload immediately (the pointer dies with the callback)
        and queues it for :meth:`pump`.
        """
        parser = self._parsers.get(int(event_id))
        if parser is None or not data_pointer:
            return
        try:
            payload = parser(data_pointer)
        except Exception:
            traceback.print_exc()
            return
        name = MAIN_EVENT_NAMES.get(int(event_id), 'event_{}'.format(int(event_id)))
        self._queue.put((name, payload))

    def handle_online_battle_event(self, event_pointer):
        """CFUNCTYPE target of ``TapOnlineBattle_RunCallbacks``."""
        try:
            event = _ffi.parse_online_battle_event(event_pointer)
        except Exception:
            traceback.print_exc()
            return
        event_id = event['event_id']
        payload = event['data'] if isinstance(event['data'], dict) else {}
        payload['request_id'] = event['request_id']
        payload['error'] = event['error']
        name = ONLINE_BATTLE_NAMES.get(event_id, 'online_battle.event_{}'.format(event_id))
        self._queue.put((name, payload))

    def online_battle_trampoline(self):
        """The (single) online battle callback passed to every pump call."""
        if self._online_battle_trampoline is None:
            self._online_battle_trampoline = _ffi.OnlineBattleCallback(
                self.handle_online_battle_event)
        return self._online_battle_trampoline

    def pump(self):
        """Drain queued events: complete requests, notify subscribers.

        Returns how many events were dispatched.
        """
        count = 0
        while True:
            try:
                name, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            count += 1
            self._complete_request(payload)
            self._notify(name, payload)
        return count

    def pump_extras(self):
        """Run the extra pumps (online battle); returns how many ran."""
        ran = 0
        for func in list(self._extra_pumps):
            try:
                func()
                ran += 1
            except Exception:
                traceback.print_exc()
        return ran

    def _complete_request(self, payload):
        if not isinstance(payload, dict):
            return
        request_id = payload.get('request_id') or 0
        if not request_id:
            return
        request = self._requests.get(int(request_id))
        if request is None or request.done:
            return
        request.data = payload
        request.error = payload.get('error')
        request.done = True
        with self._lock:
            self._finished.append(int(request_id))
            while len(self._finished) > 256:
                stale = self._finished.pop(0)
                self._requests.pop(stale, None)

    # ----------------------------------------------------------- subscribers
    def _notify(self, name, payload):
        callbacks = list(self._subscribers.get(name, ()))
        callbacks += list(self._subscribers.get('*', ()))
        for callback in callbacks:
            try:
                callback(payload)
            except Exception:
                traceback.print_exc()

    def subscribe(self, event, callback):
        """Add a subscriber; returns a function that removes it again."""
        with self._lock:
            self._subscribers.setdefault(event, []).append(callback)

        def unsubscribe():
            self.unsubscribe(event, callback)

        return unsubscribe

    def unsubscribe(self, event, callback):
        with self._lock:
            entries = self._subscribers.get(event)
            if not entries:
                return
            if callback in entries:
                entries.remove(callback)
            if not entries:
                self._subscribers.pop(event, None)

    def unsubscribe_all(self, event=None):
        with self._lock:
            if event is None:
                self._subscribers.clear()
            else:
                self._subscribers.pop(event, None)

    def subscriber_count(self, event):
        with self._lock:
            return len(self._subscribers.get(event, ()))


#: The one dispatcher of this process.
dispatcher = Dispatcher()
