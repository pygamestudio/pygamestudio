import locale
import os
import subprocess
import sys
from pathlib import Path


def _is_chinese(name: str) -> bool:
    key = str(name).strip().lower().replace('-', '_')
    return key.startswith('zh') or 'chinese' in key


def _language_candidates():
    """The names the OS reports for its own language, most reliable first.

    Several sources are asked on purpose: the stdlib locale knows the Windows
    system language even when a terminal forces ``LANG=en_US``, while Qt's UI
    languages are the only source that works for an app started from the macOS
    Finder, where no locale environment variables exist.
    """
    names = []

    getter = getattr(locale, 'getdefaultlocale', None)
    if getter is not None:
        try:
            name = getter()[0]
        except Exception:
            name = None
        if name:
            names.append(name)

    try:
        from PySide6.QtCore import QLocale
        system_locale = QLocale.system()
        names.extend(system_locale.uiLanguages() or [])
        names.append(system_locale.name())
    except Exception:
        pass

    # Windows reports 'Chinese (Simplified)_China', Linux/macOS 'zh_CN.UTF-8'.
    name = locale.getlocale()[0] or ''
    if 'chinese' in name.lower():
        names.append('zh_CN')

    for variable in ('LANG', 'LC_ALL', 'LANGUAGE'):
        value = os.environ.get(variable) or ''
        if value:
            names.append(value.split(':')[0].split('.')[0])

    return [name for name in (str(name).strip() for name in names) if name]


def get_system_language_name() -> str:
    """A name of the language the OS is set to, e.g. ``zh_CN`` or ``en_US``."""
    candidates = _language_candidates()
    return candidates[0] if candidates else ''


def get_system_lang():
    """The editor language the OS asks for: Chinese -> ``zh_CN``, else ``en``."""
    for name in _language_candidates():
        if _is_chinese(name):
            return 'zh_CN'
    return 'en'


def send_to_trash(path):
    """Move a file or folder to the system trash / recycle bin.

    Returns True on success, False on failure. Never deletes permanently.
    """
    path = Path(path)
    try:
        if sys.platform == 'win32':
            return _send_to_trash_windows(path)
        elif sys.platform == 'darwin':
            return _send_to_trash_macos(path)
        else:
            return _send_to_trash_linux(path)
    except Exception:
        return False


def _send_to_trash_windows(path):
    """Windows: use the shell API (SHFileOperationW) with FOF_ALLOWUNDO so the
    item lands in the Recycle Bin and can be restored by the user."""
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ('hwnd', wintypes.HWND),
            ('wFunc', wintypes.UINT),
            ('pFrom', wintypes.LPCWSTR),
            ('pTo', wintypes.LPCWSTR),
            ('fFlags', ctypes.c_uint16),
            ('fAnyOperationsAborted', wintypes.BOOL),
            ('hNameMappings', wintypes.LPVOID),
            ('lpszProgressTitle', wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    # FOF_ALLOWUNDO is what sends the item to the Recycle Bin (undoable);
    # NOCONFIRMATION + SILENT keep the operation quiet (no system dialog).
    FOF_ALLOWUNDO = 0x40
    FOF_NOCONFIRMATION = 0x10
    FOF_SILENT = 0x4

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = str(path) + '\0\0'   # double-NUL terminated list of paths
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return result == 0


def _send_to_trash_macos(path):
    """macOS: ask the Finder to delete the file, which sends it to the Trash."""
    script = 'tell application "Finder" to delete POSIX file "{}"'.format(path)
    result = subprocess.run(['osascript', '-e', script], capture_output=True)
    return result.returncode == 0


def _send_to_trash_linux(path):
    """Linux: use the freedesktop trash via gio, falling back to trash-put
    (trash-cli) when gio is not available."""
    # Prefer GLib's gio, fall back to trash-cli's trash-put.
    for cmd in (['gio', 'trash'], ['trash-put']):
        try:
            result = subprocess.run(cmd + [str(path)], capture_output=True)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False
