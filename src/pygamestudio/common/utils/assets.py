"""Access to project files, transparently handling protected (encrypted) builds.

A protected build encrypts the project's data files - images, audio, fonts,
scene files, ``project.pygs`` - **and its python modules** inside the staging
copy that PyInstaller packages. Game code keeps using ordinary paths: every
helper here returns the decrypted bytes for a protected file and the plain
bytes for anything else, so the editor and unprotected (source) runs behave
exactly as before.

Container format (written by ``pygamestudio.gui.build.assets``)::

    PGSXA1 | salt (16 bytes) | sha256(plaintext)[:16] | payload

The payload is XORed with a SHAKE-256 keystream derived from ``key + salt``,
and the digest lets the reader detect a damaged file or a wrong key. The
keystream is generated in C by hashlib and the XOR is done on big integers, so
even a multi-megabyte soundtrack is decrypted in a few milliseconds.

The build key itself is not shipped as a separate "key" file: it is hidden
inside ``resources.cache``, a small binary blob that looks like a resource
index (see ``encode_key_blob``). That is obfuscation, not security - the key
ships with the game and can be recovered - so it is only ever a speed bump on
top of the obfuscated code.
"""
import hashlib
import io
import os
from pathlib import Path

from pygamestudio.common.utils.path import get_project_path

#: Set of suffixes the build encrypts; build and runtime share this list.
ASSET_EXTENSIONS = frozenset((
    # images
    '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tga', '.ico',
    # audio
    '.mp3', '.ogg', '.wav', '.flac', '.m4a', '.aac',
    # fonts
    '.ttf', '.otf',
    # project data (scene files and the project configuration)
    '.scene', '.pygs',
))

#: Python modules the build encrypts as well (except the entry ``main.py``,
#: which the packaging tools have to read).
CODE_EXTENSIONS = frozenset(('.py',))

#: Name of the file the build writes into the packaged project root. It looks
#: like (and is) a small binary cache; the build key is hidden inside it.
KEY_FILE_NAME = 'resources.cache'

_MAGIC = b'PGSXA1'
_SALT_SIZE = 16
_DIGEST_SIZE = 16
_HEADER_SIZE = len(_MAGIC) + _SALT_SIZE + _DIGEST_SIZE

_KEY_MAGIC = b'PGCACHE1'
_KEY_SALT_SIZE = 16
_KEY_CHECK_SIZE = 8
_KEY_BLOCK_SIZE = 256
_KEY_SIZE = 32
_KEY_MASK_LABEL = b'pygs-cache'


class AssetError(RuntimeError):
    """Raised when a protected asset cannot be read."""


#: Cached build key; None means "no key file" and _key_loaded tracks that.
_key_loaded = False
_key = None


def reset_cache():
    """Forget the cached key (used by tests and when the project changes)."""
    global _key_loaded, _key
    _key_loaded = False
    _key = None


def get_key():
    """The key of the current build, or None for an unprotected project.

    The key travels inside ``resources.cache`` in the packaged build; a project
    run from source (editor, ``python main.py``) has no such file and needs no
    key at all.
    """
    global _key_loaded, _key
    if not _key_loaded:
        _key = None
        project_path = (get_project_path() or '').strip()
        if project_path:
            key_file = Path(project_path) / KEY_FILE_NAME
            try:
                if key_file.is_file():
                    _key = decode_key_blob(key_file.read_bytes())
            except OSError:
                _key = None
        _key_loaded = True
    return _key


def _key_positions(salt: bytes):
    """Slots of the key bytes inside the cache block (stride is odd, so unique)."""
    stride = 3 + 2 * (salt[0] % 3)
    start = salt[1]
    return [(start + index * stride) % _KEY_BLOCK_SIZE for index in range(_KEY_SIZE)]


def encode_key_blob(key: bytes) -> bytes:
    """Hide a build key inside a small, cache looking binary blob."""
    salt = os.urandom(_KEY_SALT_SIZE)
    mask = hashlib.sha256(salt + _KEY_MASK_LABEL).digest()
    block = bytearray(os.urandom(_KEY_BLOCK_SIZE))
    for index, position in enumerate(_key_positions(salt)):
        block[position] = key[index] ^ mask[index % len(mask)]
    check = hashlib.sha256(key).digest()[:_KEY_CHECK_SIZE]
    return _KEY_MAGIC + salt + check + bytes(block)


def decode_key_blob(data: bytes):
    """Recover the build key from the blob, or None when it is not one."""
    header = len(_KEY_MAGIC) + _KEY_SALT_SIZE + _KEY_CHECK_SIZE
    if len(data) < header + _KEY_BLOCK_SIZE or data[:len(_KEY_MAGIC)] != _KEY_MAGIC:
        return None
    salt = data[len(_KEY_MAGIC):len(_KEY_MAGIC) + _KEY_SALT_SIZE]
    check = data[len(_KEY_MAGIC) + _KEY_SALT_SIZE:header]
    block = data[header:header + _KEY_BLOCK_SIZE]
    mask = hashlib.sha256(salt + _KEY_MASK_LABEL).digest()
    key = bytes(block[position] ^ mask[index % len(mask)]
                for index, position in enumerate(_key_positions(salt)))
    if hashlib.sha256(key).digest()[:_KEY_CHECK_SIZE] != check:
        return None
    return key


def resolve(path) -> Path:
    """Absolute path of a project asset (relative paths use the project root)."""
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return Path(get_project_path() or Path.cwd()) / resolved


def is_encrypted_bytes(data: bytes) -> bool:
    """True when the bytes carry the protected asset header."""
    return data[:len(_MAGIC)] == _MAGIC


def is_encrypted(path) -> bool:
    """True when the file at the given path is protected."""
    try:
        with open(resolve(path), 'rb') as file:
            return is_encrypted_bytes(file.read(len(_MAGIC)))
    except OSError:
        return False


def _xor(data: bytes, keystream: bytes) -> bytes:
    """XOR two byte strings of the same length (big integer trick, fast)."""
    if not data:
        return b''
    return (int.from_bytes(data, 'big') ^ int.from_bytes(keystream, 'big')).to_bytes(len(data), 'big')


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Wrap plain data into the protected container (used by the build)."""
    salt = os.urandom(_SALT_SIZE)
    digest = hashlib.sha256(data).digest()[:_DIGEST_SIZE]
    keystream = hashlib.shake_256(key + salt).digest(len(data))
    return _MAGIC + salt + digest + _xor(data, keystream)


def decrypt_bytes(data: bytes, key=None) -> bytes:
    """Unwrap a protected container.

    :raises AssetError: when the data is not a valid container, the key does
                        not match it or the payload is damaged.
    """
    if not is_encrypted_bytes(data):
        raise AssetError('the file is not a protected asset')
    if key is None:
        key = get_key()
    if not key:
        raise AssetError('this build contains protected assets but no {} was '
                         'found next to the game'.format(KEY_FILE_NAME))
    if len(data) < _HEADER_SIZE:
        raise AssetError('the protected asset is truncated')
    salt = data[len(_MAGIC):len(_MAGIC) + _SALT_SIZE]
    digest = data[len(_MAGIC) + _SALT_SIZE:_HEADER_SIZE]
    payload = data[_HEADER_SIZE:]
    keystream = hashlib.shake_256(key + salt).digest(len(payload))
    plain = _xor(payload, keystream)
    if hashlib.sha256(plain).digest()[:_DIGEST_SIZE] != digest:
        raise AssetError('the protected asset is damaged or belongs to a different build key')
    return plain


def exists(path) -> bool:
    """True when the asset file exists on disk."""
    return resolve(path).is_file()


def read_bytes(path) -> bytes:
    """Plain bytes of an asset (decrypted when the file is protected)."""
    data = resolve(path).read_bytes()
    if is_encrypted_bytes(data):
        return decrypt_bytes(data)
    return data


def read_text(path, encoding='utf-8') -> str:
    """Text content of an asset (decrypted when the file is protected)."""
    return read_bytes(path).decode(encoding)


def open_stream(path) -> io.BytesIO:
    """In-memory stream of an asset, for loaders that accept a file object."""
    return io.BytesIO(read_bytes(path))
