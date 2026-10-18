"""
MIT License

Copyright (c) Ren Lushun (Louis Ren) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import sys
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from pygamestudio.gui.main import PygameStudio


if sys.platform == 'linux':
    os.environ['QT_QPA_PLATFORM'] = 'xcb'


def install_qt_message_filter():
    """Drop one known-benign Qt warning from the console.

    On Windows, DirectWrite logs a ``CreateFontFaceFromHDC()`` failure for the
    legacy bitmap font "Fixedsys" whenever Windows' own font fallback or the
    legacy IME touches it. Nothing in Pygame Studio asks for that family (the
    code editor, the console and the agent panel all use explicit families);
    Qt falls back to a scalable font and draws the text fine, so the line is
    pure noise. Every other Qt message is printed like the default handler.
    """
    def handler(mode, context, message):
        if 'CreateFontFaceFromHDC' in message:
            return
        category = getattr(context, 'category', '') or ''
        prefix = '{}: '.format(category) if category not in ('', 'default') else ''
        sys.stderr.write(prefix + message + '\n')

    qInstallMessageHandler(handler)


def set_application_icon(app):
    """Set the application (taskbar / system menu) icon to the Pygame Studio logo."""
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PygameStudio')
        except Exception:
            pass

    # The icon is registered in resources_rc (loaded when gui.main is imported),
    # so the resource path works in both the source tree and packaged builds.
    app.setWindowIcon(QIcon(':/images/logo.png'))


def main():
    install_qt_message_filter()
    app = QApplication([])
    set_application_icon(app)
    pygame_studio = PygameStudio()
    pygame_studio.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()