"""File protection for game builds.

The build packages a staging copy of the project (see ``obfuscation.py``). This
module protects the files of that copy - images, audio, fonts, scene files,
``project.pygs`` and the project's python modules (already stripped and
obfuscated by the time they get here) - so the packaged game ships neither a
plain resource nor readable code in the clear. The project itself is never
touched: only the staging copy is rewritten.

The per-build key is hidden inside ``resources.cache``, a small binary blob in
the staging root that looks like a resource index; the runtime
(``pygamestudio.common.utils.assets``) reads it from there and decrypts every
protected file on the fly, so game code keeps using ordinary paths. A wrong or
missing key fails loudly instead of feeding garbage to pygame.
"""
import os
from pathlib import Path

from pygamestudio.common.utils import assets as asset_format

#: Never part of a build (defensive copy of the staging rules).
IGNORED_DIR_NAMES = {'__pycache__', 'node_modules', 'venv', 'env', 'dist', 'build', '_protected'}


class AssetBuildError(RuntimeError):
    """Raised when the project assets cannot be protected."""


def generate_key() -> bytes:
    """A fresh random key for one build."""
    return os.urandom(32)


def write_key_file(project_dir, key: bytes) -> Path:
    """Hide the build key inside the cache blob that ships with the game."""
    key_file = Path(project_dir) / asset_format.KEY_FILE_NAME
    key_file.write_bytes(asset_format.encode_key_blob(key))
    return key_file


def _is_ignored(relative: Path) -> bool:
    for part in relative.parts:
        if part.startswith('.') or part in IGNORED_DIR_NAMES:
            return True
    return False


def encrypt_assets(project_dir, key: bytes) -> dict:
    """Encrypt every protected file of the staging copy in place.

    That is the project's resources (images, audio, fonts, scene files,
    ``project.pygs``) and its python modules. ``main.py`` stays readable because
    PyInstaller has to analyse the entry script; user data with other suffixes
    (``.txt``, ``.json``, ...) is left alone on purpose, so game code that opens
    it directly keeps working.

    :return: a summary with the number of files, modules and plain bytes.
    """
    project_dir = Path(project_dir)
    files = 0
    modules = 0
    byte_count = 0
    for path in sorted(project_dir.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(project_dir)
        if _is_ignored(relative):
            continue
        if path.name == asset_format.KEY_FILE_NAME:
            continue

        suffix = path.suffix.lower()
        is_module = suffix in asset_format.CODE_EXTENSIONS
        if is_module:
            if path.name == 'main.py':
                continue
        elif suffix not in asset_format.ASSET_EXTENSIONS:
            continue

        data = path.read_bytes()
        if asset_format.is_encrypted_bytes(data):
            continue
        encrypted = asset_format.encrypt_bytes(data, key)
        # The build is aborted when a file cannot be restored exactly, so a
        # broken container can never reach the packaged game.
        if asset_format.decrypt_bytes(encrypted, key) != data:
            raise AssetBuildError(f'{relative} could not be encrypted reliably')
        path.write_bytes(encrypted)
        files += 1
        modules += 1 if is_module else 0
        byte_count += len(data)

    return {'files': files, 'modules': modules, 'bytes': byte_count}


def prepare(project_dir) -> dict:
    """Protect the assets of the staging copy and hand out its build key."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise AssetBuildError(f'the staging project {project_dir} does not exist')
    key = generate_key()
    try:
        summary = encrypt_assets(project_dir, key)
    except AssetBuildError:
        raise
    except OSError as error:
        raise AssetBuildError(f'failed to encrypt the project assets: {error}') from error
    key_file = write_key_file(project_dir, key)
    return {'key_file': str(key_file), 'summary': summary}
