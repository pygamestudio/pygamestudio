"""studio.sdk.toy - the Bilibili Toy bridge.

A game packaged with the Web build for the Bilibili Toy platform gets the
platform's JS SDK on its page (``window.toy``). This module is the Python side
of it: every SDK method has a snake_case wrapper here, and each call returns a
:class:`ToyRequest` that settles when the JS Promise resolves.

Typical use inside a game object::

    from pygamestudio.sdk import toy

    if toy.available():
        toy.get_user_profile().then(lambda user: print(user['nickname']))

Outside Toy (the editor, a desktop build) nothing breaks: every call raises
:class:`ToyUnavailableError`, so guard them with ``toy.available()`` or let the
exceptions alone - they only appear where the SDK is missing.
"""

from ._core import (ToyError, ToyRequest, ToyUnavailableError, available,
                    call, check_input_safety, close_browser,
                    container_state, get_author_profile, get_author_relation,
                    get_author_videos, get_cloud_storage, get_container_state,
                    get_my_rank, get_qr_code, get_rank_list,
                    get_shared_storage, get_user_profile,
                    get_video_user_actions, is_supported, navigate,
                    on_container_change, remove_cloud_storage,
                    remove_shared_storage, request_camera, request_microphone,
                    save_image_to_album, set_backend, set_cloud_storage,
                    set_container_mode, set_shared_storage, share,
                    stop_media, submit_score)

__all__ = [
    'ToyError', 'ToyRequest', 'ToyUnavailableError',
    'available', 'call', 'set_backend',
    'is_supported', 'navigate', 'save_image_to_album', 'share',
    'get_qr_code', 'close_browser',
    'get_user_profile', 'get_author_profile', 'get_author_videos',
    'get_author_relation', 'get_video_user_actions',
    'set_cloud_storage', 'get_cloud_storage', 'remove_cloud_storage',
    'set_shared_storage', 'get_shared_storage', 'remove_shared_storage',
    'submit_score', 'get_rank_list', 'get_my_rank',
    'request_camera', 'request_microphone', 'stop_media',
    'on_container_change', 'get_container_state', 'container_state',
    'set_container_mode', 'check_input_safety',
]
