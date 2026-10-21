"""Python bridge of the Bilibili Toy JS SDK (``window.toy``).

The page of a Toy build loads ``toy-sdk.js``, which puts a single object on
``window``: every method returns a JS Promise (``onContainerChange`` is the one
exception and returns an unsubscribe function). Game code cannot see the
browser, so this module does the plumbing:

* :func:`call` invokes one SDK method and returns a :class:`ToyRequest`;
* the promise's ``then``/``catch`` handlers are Python callables wrapped with
  ``create_proxy`` (kept alive until the request settles, as Pyodide requires);
* arguments the SDK expects as an options object are converted with
  ``to_js``, results come back as plain Python values (``to_py``).

Nothing is imported from Pyodide at module import time: the module also loads
in the editor and in a desktop build, where :func:`available` simply answers
``False`` and every call raises :class:`ToyUnavailableError`.
"""

import asyncio
import time

#: JS name of every SDK method this module wraps (snake_case -> SDK spelling).
_BINDINGS = {
    'is_supported': 'isSupport',
    'navigate': 'navigate',
    'save_image_to_album': 'saveImageToAlbum',
    'share': 'share',
    'get_qr_code': 'getQrCode',
    'close_browser': 'closeBrowser',
    'get_user_profile': 'getUserProfile',
    'get_author_profile': 'getAuthorProfile',
    'get_author_videos': 'getAuthorVideos',
    'get_author_relation': 'getAuthorRelation',
    'get_video_user_actions': 'getVideoUserActions',
    'set_cloud_storage': 'setCloudStorage',
    'get_cloud_storage': 'getCloudStorage',
    'remove_cloud_storage': 'removeCloudStorage',
    'set_shared_storage': 'setSharedStorage',
    'get_shared_storage': 'getSharedStorage',
    'remove_shared_storage': 'removeSharedStorage',
    'submit_score': 'submitScore',
    'get_rank_list': 'getRankList',
    'get_my_rank': 'getMyRank',
    'request_camera': 'requestCamera',
    'request_microphone': 'requestMicrophone',
    'stop_media': 'stopMedia',
    'get_container_state': 'getContainerState',
    'set_container_mode': 'setContainerMode',
    'check_input_safety': 'checkInputSafety',
}

#: Depth used when a result object is converted to plain Python values.
_RESULT_DEPTH = 4
#: ``create_proxy`` keeps a proxy alive while JS may still call it.
_proxy_keepalive = []


class ToyError(RuntimeError):
    """The SDK rejected a call (``[ToySDK] ...`` messages come as they are)."""


class ToyUnavailableError(ToyError):
    """The page has no Toy SDK: the game runs in the editor, a desktop build
    or a plain web page instead of the Bilibili Toy platform."""


# =============================================================================
# Backend (the injected seam: ``window.toy`` in a browser, a fake in tests)
# =============================================================================
class _JsBackend:
    """Thin wrapper around the ``window.toy`` object."""

    def __init__(self, sdk):
        self._sdk = sdk

    def has(self, method):
        try:
            return getattr(self._sdk, method, None) is not None
        except Exception:
            return False

    def call(self, method, *args):
        return getattr(self._sdk, method)(*args)


_backend = None
_resolved = False


def set_backend(backend):
    """Engine-internal/tests: force the backend (``None`` re-resolves itself).

    ``backend`` only has to provide ``has(name)`` and ``call(name, *args)``.
    """
    global _backend, _resolved
    _backend = backend
    _resolved = backend is not None


def _resolve_backend():
    """``window.toy`` of the page, or ``None`` outside the Toy platform."""
    global _backend, _resolved
    if _resolved:
        return _backend
    _resolved = True
    _backend = None
    try:
        import js
    except Exception:
        return None
    try:
        sdk = getattr(js, 'toy', None)
    except Exception:
        sdk = None
    if sdk is not None:
        _backend = _JsBackend(sdk)
    return _backend


def available():
    """True when the page provides the Toy SDK (i.e. inside the Toy platform).

    The editor, a desktop build and a plain web build all return ``False``,
    which makes it safe to guard calls::

        if toy.available():
            toy.submit_score('level-1', score)
    """
    return _resolve_backend() is not None


# =============================================================================
# Value conversion
# =============================================================================
def _to_js(value):
    """Convert dicts/lists to JS objects/arrays; everything else passes through."""
    if not isinstance(value, (dict, list, tuple)):
        return value
    try:
        import js
        from pyodide.ffi import to_js
    except Exception:
        return value
    try:
        return to_js(value, dict_converter=js.Object.fromEntries)
    except Exception:
        try:
            return to_js(value)
        except Exception:
            return value


def _to_python(value):
    """Convert a JS result (object/array) to plain Python values.

    The proxy method is used first (``JsProxy.to_py``): newer Pyodide builds
    dropped the module-level ``to_py`` helper, which is only kept as a
    fallback. Streams and other live objects that cannot be copied stay as
    proxies - they are meant to be handed back to the SDK.
    """
    if value is None or isinstance(value, (dict, list, tuple, str, bytes,
                                           int, float, bool)):
        return value
    convert = getattr(value, 'to_py', None)
    if callable(convert):
        try:
            return convert(depth=_RESULT_DEPTH)
        except Exception:
            return value
    try:
        from pyodide.ffi import to_py
    except Exception:
        return value
    try:
        return to_py(value, depth=_RESULT_DEPTH)
    except Exception:
        return value


def _options(**kwargs):
    """Build an SDK options object, dropping the keys the caller left out."""
    return {key: value for key, value in kwargs.items() if value is not None}


# =============================================================================
# Requests
# =============================================================================
class ToyRequest:
    """One SDK call: settles when the JS Promise resolves or rejects.

    The object is also the Python equivalent of that Promise::

        toy.get_user_profile().then(show_profile)
        request = toy.get_user_profile()
        request.result()                  # once ``request.done`` is True
        value = await request.wait()      # inside an async game loop

    Callbacks are optional and run in the browser's microtask queue, i.e.
    between two frames of the game loop.
    """

    def __init__(self, method):
        self.method = method
        self.done = False
        self.ok = False
        self.value = None
        self.error = None
        self._on_ok = []
        self._on_error = []
        self._proxies = []

    # -- state ---------------------------------------------------------------
    def _settle(self, ok, payload):
        if self.done:
            return
        self.done = True
        self.ok = ok
        if ok:
            self.value = payload
        else:
            self.error = payload
        listeners = self._on_ok if ok else self._on_error
        # ``then`` callbacks run once, in registration order.
        self._on_ok = []
        self._on_error = []
        self._release_proxies()
        for callback in listeners:
            try:
                callback(payload)
            except Exception:
                import traceback
                traceback.print_exc()

    def _release_proxies(self):
        """Drop the JS callback proxies once the promise cannot call them."""
        proxies, self._proxies = self._proxies, []
        try:
            _proxy_keepalive.remove(self)
        except ValueError:
            pass
        for proxy in proxies:
            destroy = getattr(proxy, 'destroy', None)
            if callable(destroy):
                try:
                    destroy()
                except Exception:
                    pass

    def _succeed(self, value):
        self._settle(True, _to_python(value))

    def _fail(self, error):
        self._settle(False, _error_text(error))

    # -- API -----------------------------------------------------------------
    def then(self, on_ok=None, on_error=None):
        """Register callbacks; they run immediately when already settled."""
        if on_ok is not None:
            if self.done and self.ok:
                on_ok(self.value)
            elif not self.done:
                self._on_ok.append(on_ok)
        if on_error is not None:
            if self.done and not self.ok:
                on_error(self.error)
            elif not self.done:
                self._on_error.append(on_error)
        return self

    def catch(self, on_error):
        """Register a failure callback (alias of ``then(None, on_error)``)."""
        return self.then(None, on_error)

    def result(self, default=None):
        """The resolved value, or ``default`` when the call failed.

        Raises :class:`ToyError` when the call has not settled yet - use
        :meth:`then` or :meth:`wait` for that.
        """
        if not self.done:
            raise ToyError('{} has not finished yet, use then() or await '
                           'wait() instead of result()'.format(self.method))
        if not self.ok:
            return default
        return self.value

    def raise_for_error(self):
        """Raise :class:`ToyError` when the call failed, return the value."""
        if not self.done:
            raise ToyError('{} has not finished yet'.format(self.method))
        if not self.ok:
            raise ToyError(self.error or '{} failed'.format(self.method))
        return self.value

    async def wait(self, timeout=None):
        """Await the call (async game loop) and return its value.

        The promise settles between frames, so the loop keeps running while
        waiting. ``timeout`` is in seconds; on timeout the current value is
        returned with the request still pending, and a failed call raises
        :class:`ToyError`.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.done:
            await asyncio.sleep(0.01)
            if deadline is not None and time.monotonic() >= deadline:
                return self.value
        return self.raise_for_error()

    def __repr__(self):
        state = 'pending'
        if self.done:
            state = 'ok' if self.ok else 'error: {}'.format(self.error)
        return '<ToyRequest {} {}>'.format(self.method, state)


def _error_text(error):
    """Readable text of a JS rejection (``[ToySDK] ...`` stays as it is)."""
    if error is None:
        return ''
    if isinstance(error, str):
        return error
    try:
        message = getattr(error, 'message', None)
    except Exception:
        message = None
    if isinstance(message, str) and message:
        return message
    return str(error)


def _attach(request, promise):
    """Feed the JS Promise into ``request`` with Python ``then`` callbacks."""
    if promise is None:
        request._succeed(None)
        return request
    then = getattr(promise, 'then', None)
    if then is None:
        # A backend that answers directly (tests, or a future sync method).
        request._succeed(promise)
        return request

    ok_handler = request._succeed
    error_handler = request._fail
    try:
        from pyodide.ffi import create_proxy
    except Exception:
        create_proxy = None
    if create_proxy is not None:
        try:
            ok_handler = create_proxy(ok_handler)
            error_handler = create_proxy(error_handler)
            request._proxies = [ok_handler, error_handler]
            _proxy_keepalive.append(request)
        except Exception:
            pass
    then(ok_handler, error_handler)
    return request


def call(method, *args):
    """Call any Toy SDK method by its JS name and return a :class:`ToyRequest`.

    Use it for methods this module does not wrap (newer SDK versions); the
    snake_case wrappers below simply forward here.
    """
    backend = _resolve_backend()
    if backend is None:
        raise ToyUnavailableError(
            '{} needs the Bilibili Toy platform: the page has no toy SDK here '
            '(guard the call with toy.available())'.format(method))
    if not backend.has(method):
        raise ToyUnavailableError(
            '{} is not provided by the toy SDK of this page'.format(method))

    request = ToyRequest(method)
    try:
        promise = backend.call(method, *[_to_js(arg) for arg in args])
    except Exception as error:
        raise ToyError(_error_text(error) or '{} failed'.format(method)) from error
    return _attach(request, promise)


def _bound(name, *args):
    """Forward to ``call`` using the SDK spelling of ``name``."""
    return call(_BINDINGS[name], *args)


# =============================================================================
# Platform / navigation
# =============================================================================
def is_supported(ability):
    """True when this client (web page or app) supports ``ability``.

    ``ability`` is the SDK method name, e.g. ``'share'`` or ``'submitScore'``.
    """
    return _bound('is_supported', ability)


def navigate(page_type, target_id=None, extra=None):
    """Open a platform page (``page_type`` as documented by the SDK)."""
    return _bound('navigate', _options(type=page_type, id=target_id,
                                       extra=extra))


def save_image_to_album(url=None, base64_data=None, hint_msg=None):
    """Save an image to the user's album (app only; needs one of the sources)."""
    return _bound('save_image_to_album', _options(url=url,
                                                 base64Data=base64_data,
                                                 hintMsg=hint_msg))


def share(path=None):
    """Open the platform share sheet for ``path``."""
    return _bound('share', _options(path=path))


def get_qr_code(path=None, size=None):
    """The QR code of a game page as an image URL."""
    return _bound('get_qr_code', _options(path=path, size=size))


def close_browser():
    """Close the platform browser/container (app only)."""
    return _bound('close_browser')


# =============================================================================
# User, author and video
# =============================================================================
def get_user_profile():
    """Profile of the signed-in user (``nickname``, ``avatar`` ...)."""
    return _bound('get_user_profile')


def get_author_profile():
    """Profile of the uploading author (author side of the platform)."""
    return _bound('get_author_profile')


def get_author_videos(videos):
    """Details of ``videos`` (a list of BV/AV ids) of the author."""
    return _bound('get_author_videos', _options(videos=videos))


def get_author_relation():
    """The relation between the user and the author (followed, ...)."""
    return _bound('get_author_relation')


def get_video_user_actions(aids=None, videos=None):
    """What the user did with the given videos (likes, coins, ...)."""
    return _bound('get_video_user_actions', _options(aids=aids, videos=videos))


# =============================================================================
# Cloud storage
# =============================================================================
def set_cloud_storage(items):
    """Write key/value ``items`` to the user's cloud storage."""
    return _bound('set_cloud_storage', items)


def get_cloud_storage(keys=None):
    """Read ``keys`` (all of them when omitted) from the cloud storage."""
    return _bound('get_cloud_storage', *(() if keys is None else (keys,)))


def remove_cloud_storage(keys=None):
    """Delete ``keys`` (all of them when omitted) from the cloud storage."""
    return _bound('remove_cloud_storage', *(() if keys is None else (keys,)))


def set_shared_storage(storage_id, items):
    """Write into a storage shared by every player of the game."""
    return _bound('set_shared_storage', storage_id, items)


def get_shared_storage(storage_id, keys=None):
    """Read from the shared storage of the game."""
    return _bound('get_shared_storage', storage_id,
                  *(() if keys is None else (keys,)))


def remove_shared_storage(storage_id, keys=None):
    """Delete from the shared storage of the game."""
    return _bound('remove_shared_storage', storage_id,
                  *(() if keys is None else (keys,)))


# =============================================================================
# Leaderboards
# =============================================================================
def submit_score(board, score):
    """Send ``score`` to the leaderboard ``board``."""
    return _bound('submit_score', _options(board=board, score=score))


def get_rank_list(board, period=None, limit=None):
    """The leaderboard ``board`` (``period``: total/week/day as documented)."""
    return _bound('get_rank_list', _options(board=board, period=period,
                                            limit=limit))


def get_my_rank(board, period=None):
    """The user's own rank on ``board``."""
    return _bound('get_my_rank', _options(board=board, period=period))


# =============================================================================
# Media devices
# =============================================================================
def request_camera(facing_mode=None):
    """Request the camera and resolve with the media stream."""
    options = {}
    if facing_mode is not None:
        options['facingMode'] = facing_mode
    return _bound('request_camera', options) if options else _bound('request_camera')


def request_microphone():
    """Request the microphone and resolve with the media stream."""
    return _bound('request_microphone')


def stop_media(stream):
    """Release a camera/microphone stream returned by the request functions."""
    return _bound('stop_media', stream)


# =============================================================================
# Container (orientation / immersive mode)
# =============================================================================
#: Last container state delivered by ``onContainerChange`` (None until then).
_state = {'value': None}


def _on_state(state):
    _state['value'] = _to_python(state)


def on_container_change(listener):
    """Call ``listener(state)`` whenever the container changes; returns the
    function that unsubscribes."""
    backend = _resolve_backend()
    if backend is None or not backend.has('onContainerChange'):
        raise ToyUnavailableError('container events need the Bilibili Toy '
                                  'platform')

    def _forward(state):
        try:
            _on_state(state)
            listener(_state['value'])
        except Exception:
            import traceback
            traceback.print_exc()

    callback = _forward
    try:
        from pyodide.ffi import create_proxy
    except Exception:
        create_proxy = None
    if create_proxy is not None:
        try:
            callback = create_proxy(_forward)
        except Exception:
            callback = _forward

    unsubscribe = backend.call('onContainerChange', callback)
    token = object()
    _listeners[token] = (callback, unsubscribe)

    def _cancel():
        entry = _listeners.pop(token, None)
        if entry is None:
            return
        proxy, remove = entry
        try:
            remove()
        except Exception:
            pass
        destroy = getattr(proxy, 'destroy', None)
        if callable(destroy):
            try:
                destroy()
            except Exception:
                pass

    return _cancel


#: Live ``onContainerChange`` registrations: proxy + unsubscribe function.
_listeners = {}


def get_container_state():
    """Read the current container state from the platform."""
    return _bound('get_container_state')


def container_state():
    """The last state pushed to :func:`on_container_change` (None before)."""
    return _state['value']


def set_container_mode(orientation=None, immersive=None):
    """Ask the container for an orientation and/or immersive mode."""
    return _bound('set_container_mode', _options(orientation=orientation,
                                                 immersive=immersive))


# =============================================================================
# Moderation
# =============================================================================
def check_input_safety(text, scene=None):
    """Ask the platform whether user-typed ``text`` is safe to show."""
    return _bound('check_input_safety', _options(text=text, scene=scene))
