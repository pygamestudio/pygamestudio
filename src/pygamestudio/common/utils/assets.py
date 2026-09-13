"""Access to project assets, transparently handling protected (encrypted) builds.

A protected build encrypts the project's data files - images, audio, fonts,
scene files and ``project.pygs`` - inside the staging copy that PyInstaller
packages, and writes the per-build key next to them (``assets.key``). Game code
keeps using ordinary paths: every helper here returns the decrypted bytes for a
protected file and the plain bytes for anything else, so the editor and
unprotected (source) runs behave exactly as before.

Container format (written by ``pygamestudio.gui.build.assets``)::

    PGSXA1 | salt (16 bytes) | sha256(plaintext)[:16] | payload

The payload is XORed with a SHAKE-256 keystream derived from ``key + salt``,
and the digest lets the reader detect a damaged file or a wrong key. The
keystream is generated in C by hashlib and the XOR is done on big integers, so
even a multi-megabyte soundtrack is decrypted in a few milliseconds.
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

#: Name of the key file the build writes into the packaged project root.
KEY_FILE_NAME = 'assets.key'

_MAGIC = b'PGSXA1'
_SALT_SIZE = 16
_DIGEST_SIZE = 16
_HEADER_SIZE = len(_MAGIC) + _SALT_SIZE + _DIGEST_SIZE


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

    The key lives next to the game in the packaged build; a project run from
    source (editor, ``python main.py``) has no key file and needs none.
    """
    global _key_loaded, _key
    if not _key_loaded:
        _key = None
        project_path = (get_project_path() or '').strip()
        if project_path:
            key_file = Path(project_path) / KEY_FILE_NAME
            try:
                if key_file.is_file():
                    _key = bytes.fromhex(key_file.read_text(encoding='ascii').strip())
            except (OSError, ValueError):
                _key = None
        _key_loaded = True
    return _key


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
