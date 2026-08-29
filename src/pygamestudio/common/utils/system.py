import locale
import subprocess
import sys
from pathlib import Path


def get_system_lang():
    """Detect the OS UI language; only zh_CN is distinguished from English."""
    lang, encoding = locale.getdefaultlocale()
    if lang == 'zh_CN':
        return lang
    else:
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
