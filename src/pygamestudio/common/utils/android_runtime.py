"""The frozen Android runtime pack, and the tools a machine needs to use it.

The editor never downloads a toolchain and never cross-compiles anything: the
Python interpreter, pygame-ce, pymunk, SDL2 and the Java bootstrap ship as ONE
archive in ``common/res/android`` (produced by ``tools/android_spike/
freeze_runtime.py`` from a p4a dist). This module answers three questions:

1. is that archive there, and is it the archive ``VERSION.json`` describes?
2. where is it unpacked (once, into the user cache - 45 MB, LZMA)?
3. can this machine package it, i.e. is there a JDK and an Android SDK with the
   platform and build-tools the pack's Gradle project asks for?

Nothing here imports Qt, so the pack can be checked from a script or a test.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from platformdirs import user_cache_dir

from pygamestudio.common.utils.path import RES_PATH

#: Folder of the engine that ships the artefact (the zip + ``VERSION.json``).
PACK_DIR = RES_PATH / 'android'
#: Metadata file written next to the archive by the freezer.
VERSION_FILE_NAME = 'VERSION.json'
#: Android platform the pack's Gradle project is compiled against.
COMPILE_SDK = 34
#: Lowest Android version the pack supports (``android.minapi`` of the dist).
MIN_SDK = 24
#: Android Gradle Plugin 8.x refuses to run on anything older.
MIN_JAVA_VERSION = 17
#: Marker inside the unpacked folder: the archive sha256 it was made from.
MARKER_NAME = '.archive.sha256'
#: Read size for hashing / verifying.
_CHUNK = 1 << 20


class AndroidRuntimeError(RuntimeError):
    """Something the user can fix: a missing pack, a damaged one, no toolchain."""

    #: Translation key of the reason, the message carries the detail.
    reason = 'android.runtime_error'

    def __init__(self, message=''):
        super().__init__(message)
        self.detail = message


class RuntimePackMissing(AndroidRuntimeError):
    """No ``pygs-android-runtime-*.zip`` in the engine's ``res/android``."""

    reason = 'android.pack_missing'


class RuntimePackDamaged(AndroidRuntimeError):
    """The archive does not match the checksum ``VERSION.json`` records."""

    reason = 'android.pack_damaged'


def cache_root() -> Path:
    """Where the unpacked pack and Gradle's caches live (per user, per machine)."""
    return Path(user_cache_dir()) / 'PygameStudio' / 'android'


def hash_file(path) -> str:
    """SHA-256 of a file (1 MB chunks, so a 22 MB archive costs no memory)."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def find_pack() -> dict:
    """Locate and read the shipped artefact.

    :return: ``{'dir', 'version_file', 'metadata', 'archive'}``
    :raises RuntimePackMissing: the zip or its metadata is not there
    :raises RuntimePackDamaged: the metadata cannot be read
    """
    version_file = PACK_DIR / VERSION_FILE_NAME
    if not version_file.is_file():
        raise RuntimePackMissing(str(version_file))

    try:
        metadata = json.loads(version_file.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RuntimePackDamaged(f'{version_file.name}: {error}') from error

    archive_name = str((metadata.get('archive') or {}).get('name') or '')
    if not archive_name:
        version = metadata.get('version') or ''
        abi = metadata.get('abi') or ''
        archive_name = f'pygs-android-runtime-{version}-{abi}.zip'

    archive = PACK_DIR / archive_name
    if not archive.is_file():
        raise RuntimePackMissing(str(archive))

    return {'dir': PACK_DIR, 'version_file': version_file,
            'metadata': metadata, 'archive': archive}


def unpacked_dir(metadata=None) -> Path:
    """Folder the pack unpacks into (whether or not it exists yet)."""
    metadata = metadata or find_pack()['metadata']
    version = metadata.get('version') or 'unknown'
    abi = metadata.get('abi') or 'unknown'
    return cache_root() / f'runtime-{version}-{abi}'


def is_unpacked(metadata=None) -> bool:
    """True when the cache holds the very archive that ships with the editor."""
    pack = find_pack()
    metadata = metadata or pack['metadata']
    target = unpacked_dir(metadata)
    marker = target / MARKER_NAME
    if not marker.is_file():
        return False
    expected = (metadata.get('archive') or {}).get('sha256') or ''
    return marker.read_text(encoding='utf-8').strip() == expected


def _safe_members(archive):
    """Zip members that stay inside the target folder (zip-slip guard)."""
    for member in archive.infolist():
        name = member.filename.replace('\\', '/')
        if name.startswith('/') or '..' in Path(name).parts:
            raise RuntimePackDamaged(f'unsafe path in the archive: {member.filename}')
        yield member


def ensure_unpacked(on_progress=None) -> Path:
    """Unpack the shipped archive into the cache (once) and return that folder.

    The archive is verified against the sha256 recorded in ``VERSION.json``
    before anything is written, and the unpacked folder carries a marker with
    that checksum: a new pack version, or a cache damaged by a crash, unpacks
    again; an unchanged pack costs one hash of the marker.

    :param on_progress: optional ``callable(percent)`` for the build window
    """
    report = on_progress or (lambda percent: None)
    pack = find_pack()
    metadata = pack['metadata']
    target = unpacked_dir(metadata)

    if is_unpacked(metadata):
        report(100)
        return target

    expected = (metadata.get('archive') or {}).get('sha256') or ''
    report(5)
    actual = hash_file(pack['archive'])
    if expected and actual != expected:
        raise RuntimePackDamaged(f'{pack["archive"].name}: sha256 {actual} != {expected}')
    report(15)

    partial = target.with_name(target.name + '.partial')
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(pack['archive']) as archive:
            archive.extractall(partial, members=_safe_members(archive))
    except (OSError, zipfile.BadZipFile) as error:
        shutil.rmtree(partial, ignore_errors=True)
        raise RuntimePackDamaged(f'{pack["archive"].name}: {error}') from error
    report(85)

    (partial / MARKER_NAME).write_text(expected or actual, encoding='utf-8')
    previous = target.with_name(target.name + '.old')
    shutil.rmtree(previous, ignore_errors=True)
    if target.exists():
        target.rename(previous)
    partial.rename(target)
    shutil.rmtree(previous, ignore_errors=True)
    report(100)
    return target


def describe(metadata=None) -> str:
    """One line for the settings page: version, abi, python, package versions."""
    metadata = metadata or find_pack()['metadata']
    packages = metadata.get('packages') or {}
    package_text = ', '.join(f'{name} {version}' for name, version in sorted(packages.items()))
    return (f"{metadata.get('name', 'pygs-android-runtime')} "
            f"{metadata.get('version', '?')}  abi {metadata.get('abi', '?')}  "
            f"python {metadata.get('python', '?')}"
            + (f'  ({package_text})' if package_text else ''))


# ---------------------------------------------------------------- toolchain

def _candidates_jdk():
    system = platform.system()
    found = []
    for key in ('JAVA_HOME', 'JDK_HOME'):
        value = os.environ.get(key)
        if value:
            found.append(Path(value))
    if system == 'Windows':
        roots = [
            Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Java',
            Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Eclipse Adoptium',
            Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Microsoft',
            Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Android' / 'Android Studio' / 'jbr',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Eclipse Adoptium',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'JetBrains' / 'Toolbox' / 'apps',
        ]
        for root in roots:
            if not root.is_dir():
                continue
            if (root / 'bin').is_dir():
                found.append(root)
            found.extend(sorted(path for path in root.glob('*') if (path / 'bin').is_dir()))
    else:
        roots = [Path('/usr/lib/jvm'), Path('/Library/Java/JavaVirtualMachines'),
                 Path('/opt/homebrew/opt'), Path('/usr/local/opt')]
        for root in roots:
            if root.is_dir():
                found.extend(sorted((path / 'Contents' / 'Home' if (path / 'Contents' / 'Home').is_dir()
                                     else path) for path in root.glob('*')))
    return [path for path in found if java_executable(path) is not None]


def java_executable(jdk) -> Path:
    """``.../bin/java(.exe)`` of a JDK folder, or None when it is not one."""
    jdk = Path(jdk)
    name = 'java.exe' if platform.system() == 'Windows' else 'java'
    for candidate in (jdk / 'bin' / name, jdk / 'Contents' / 'Home' / 'bin' / name):
        if candidate.is_file():
            return candidate
    return None


def java_version(jdk) -> int:
    """Major version of a JDK (``1.8`` reports 8), 0 when it cannot be read."""
    executable = java_executable(jdk)
    if executable is None:
        return 0
    try:
        completed = subprocess.run([str(executable), '-version'],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace',
                                   timeout=20,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError):
        return 0
    match = re.search(r'version "([0-9][^"]*)"', completed.stdout or '')
    if not match:
        match = re.search(r'openjdk ([0-9]+)', completed.stdout or '')
        if not match:
            return 0
    parts = match.group(1).split('.') if match.lastindex and '.' in match.group(1) else [match.group(1)]
    try:
        major = int(parts[0])
    except ValueError:
        return 0
    if major == 1 and len(parts) > 1:                    # 1.8.0_402 -> 8
        try:
            major = int(parts[1])
        except ValueError:
            return 0
    return major


def guess_jdk() -> str:
    """The JDK the editor should try first (highest version wins)."""
    candidates = _candidates_jdk()
    if not candidates:
        return ''
    candidates.sort(key=java_version, reverse=True)
    return candidates[0].as_posix()


def _candidates_sdk():
    found = []
    for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        value = os.environ.get(key)
        if value:
            found.append(Path(value))
    system = platform.system()
    if system == 'Windows':
        local = os.environ.get('LOCALAPPDATA')
        if local:
            found.append(Path(local) / 'Android' / 'Sdk')
        # Android Studio and the command line tools accept any folder, so a
        # user with a second drive has the SDK somewhere the default paths do
        # not know about; a handful of stat calls per drive finds those.
        for letter in 'CDEFGHIJK':
            drive = Path(f'{letter}:/')
            if not drive.is_dir():
                continue
            found.extend((drive / 'Android' / 'Sdk', drive / 'Android' / 'sdk',
                          drive / 'SDK', drive / 'Android'))
    elif system == 'Darwin':
        found.append(Path.home() / 'Library' / 'Android' / 'sdk')
    else:
        found.append(Path.home() / 'Android' / 'Sdk')
    return [path for path in found if _looks_like_sdk(path)]


def _looks_like_sdk(path) -> bool:
    """An SDK folder is one that (at least) has a platforms/ build-tools/ ..."""
    path = Path(path)
    return path.is_dir() and any((path / name).is_dir()
                                 for name in ('platforms', 'build-tools', 'cmdline-tools'))


def guess_sdk() -> str:
    """The Android SDK the editor should try first (the one with the platform)."""
    candidates = _candidates_sdk()
    if not candidates:
        return ''
    candidates.sort(key=lambda path: (len(_installed_platforms(path)),
                                     bool(_installed_build_tools(path))),
                    reverse=True)
    return candidates[0].as_posix()


def _installed_platforms(sdk) -> list:
    folder = Path(sdk) / 'platforms'
    if not folder.is_dir():
        return []
    levels = []
    for path in folder.glob('android-*'):
        try:
            levels.append(int(path.name.split('-', 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(levels)


def _version_key(text):
    parts = []
    for piece in re.split(r'[._-]', text):
        parts.append(int(piece) if piece.isdigit() else 0)
    return parts


def _installed_build_tools(sdk) -> list:
    folder = Path(sdk) / 'build-tools'
    if not folder.is_dir():
        return []
    return sorted((path.name for path in folder.iterdir() if path.is_dir()),
                  key=_version_key)


def check_toolchain(jdk='', sdk='') -> dict:
    """Look for everything an APK needs; never raises, reports what is missing.

    :return: ``{'ok': bool, 'problems': [reason key, ...], 'jdk', 'java',
               'sdk', 'build_tools', 'platforms', 'compile_sdk'}``
    """
    result = {'ok': False, 'problems': [], 'notes': [], 'jdk': str(jdk or ''),
              'java': 0, 'sdk': str(sdk or ''), 'build_tools': '',
              'platforms': [], 'compile_sdk': COMPILE_SDK}

    resolved_jdk = Path(jdk) if jdk else (Path(guess_jdk()) if guess_jdk() else None)
    if resolved_jdk is None or java_executable(resolved_jdk) is None:
        result['problems'].append('android.jdk_missing')
    else:
        result['jdk'] = resolved_jdk.as_posix()
        dominant = java_version(resolved_jdk)
        result['java'] = dominant
        if dominant < MIN_JAVA_VERSION:
            result['problems'].append('android.jdk_old')

    resolved_sdk = Path(sdk) if sdk else (Path(guess_sdk()) if guess_sdk() else None)
    if resolved_sdk is None or not _looks_like_sdk(resolved_sdk):
        result['problems'].append('android.sdk_missing')
    else:
        result['sdk'] = resolved_sdk.as_posix()
        platforms = _installed_platforms(resolved_sdk)
        result['platforms'] = platforms
        if COMPILE_SDK not in platforms:
            result['problems'].append('android.platform_missing')
        build_tools = _installed_build_tools(resolved_sdk)
        if not build_tools:
            # Not blocking: every Android Gradle Plugin installs the build-tools
            # it wants into the SDK itself (it only needs network + licenses).
            result['notes'].append('android.build_tools_missing')
        else:
            matching = [version for version in build_tools
                        if version.startswith(f'{COMPILE_SDK}.')]
            result['build_tools'] = (matching or build_tools)[-1]

    result['ok'] = not result['problems']
    return result
