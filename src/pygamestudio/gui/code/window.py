from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from pygamestudio.gui.code.editor import CodeEditor
from pygamestudio.gui.scene.widget import RunProjectButton
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.i18n.translator import Translator as T


class CodeEditorWindow(QWidget):
    """The code editor panel.

    Lives as a tab in the editor's center top tab widget (right after the
    scene editor). It can be detached into its own top-level window and later
    re-docked back to the tab, so editing larger scripts is comfortable.
    """

    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None

        self._editor = CodeEditor()
        self._run_project_btn = RunProjectButton()
        self._detach_btn = QPushButton()
        self._zoom_in_btn = QPushButton()
        self._zoom_out_btn = QPushButton()

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self._detach_btn.setObjectName('codeEditorDetachBtn')
        self._detach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_detach_button_text()

        self._zoom_in_btn.setObjectName('codeEditorZoomInBtn')
        self._zoom_out_btn.setObjectName('codeEditorZoomOutBtn')
        self._zoom_in_btn.setIcon(QIcon(':/images/zoom_in.png'))
        self._zoom_out_btn.setIcon(QIcon(':/images/zoom_out.png'))
        self._zoom_in_btn.setIconSize(QSize(16, 16))
        self._zoom_out_btn.setIconSize(QSize(16, 16))
        self._zoom_in_btn.setFixedSize(26, 26)
        self._zoom_out_btn.setFixedSize(26, 26)
        self._zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_in_btn.setToolTip(T.tr('code.zoom_in', 'Zoom In'))
        self._zoom_out_btn.setToolTip(T.tr('code.zoom_out', 'Zoom Out'))
        self._update_zoom_buttons(self._editor.font_size())

    def _set_signal(self):
        self._run_project_btn.clicked.connect(self._run_project)
        self._detach_btn.clicked.connect(self.toggle_detached)
        self._editor.run_requested.connect(self._run_project)
        self._editor.modified_changed.connect(lambda modified: self._update_titles())
        self._zoom_in_btn.clicked.connect(self._editor.zoom_in)
        self._zoom_out_btn.clicked.connect(self._editor.zoom_out)
        self._editor.font_size_changed.connect(self._update_zoom_buttons)

    def _set_layout(self):
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self._zoom_out_btn)
        toolbar_layout.addWidget(self._zoom_in_btn)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._run_project_btn)
        toolbar_layout.addWidget(self._detach_btn)

        window_layout = QVBoxLayout(self)
        window_layout.addLayout(toolbar_layout)
        window_layout.addWidget(self._editor)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(4)

    def _set_object_name(self):
        self.setObjectName('codeEditorWindow')

    # ------------------------------------------------------------------ file
    def open_file(self, file_path):
        """Open a text file in the editor and bring the panel into view."""
        self._editor.open_file(file_path)
        self._update_titles()
        self._raise_window()

    def open_file_at_line(self, file_path, line):
        """Open a file and jump to a 1-based line (Ctrl+click on console
        error logs)."""
        self._editor.open_file(file_path)
        self._editor.jump_to_line(line)
        self._update_titles()
        self._raise_window()

    def _raise_window(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.show()
                self._standalone_window.raise_()
                self._standalone_window.activateWindow()
        elif self._tab_widget is not None:
            self._tab_widget.setCurrentWidget(self)

    def save(self):
        self._editor.save()

    # ------------------------------------------------------------------ run
    def _run_project(self):
        if self._editor.is_modified():
            self._editor.save()
        self._game_manager.run_project()

    # ------------------------------------------------------------------ detach / attach
    def set_tab_widget(self, tab_widget):
        """The center-top QTabWidget this panel is docked into."""
        self._tab_widget = tab_widget

    def toggle_detached(self):
        if self._is_detached:
            self.attach()
        else:
            self.detach()

    def detach(self):
        """Undock the editor into a standalone frameless window.

        The standalone window uses the custom WindowTitleBase title bar
        (drag to move, minimize/maximize/close buttons) plus edge-resizing,
        exactly like every other editor window, instead of the native OS
        window chrome.
        """
        if self._is_detached or self._tab_widget is None:
            return
        self._tab_widget.removeTab(self._tab_widget.indexOf(self))
        self.setParent(None)
        self._standalone_window = _CodeEditorStandaloneWindow(self, self._window_title())
        # removeTab() hides the page, so re-show it now that it lives in the
        # standalone window, otherwise the editor would stay invisible.
        self.show()
        self._standalone_window.show()
        self._is_detached = True
        self._update_detach_button_text()

    def attach(self):
        """Re-dock the standalone window back into the tab widget."""
        if not self._is_detached or self._tab_widget is None:
            return
        standalone = self._standalone_window
        self._standalone_window = None
        if standalone is not None:
            standalone._editor_window = None
            standalone.hide()
            standalone.deleteLater()
        self._tab_widget.insertTab(1, self, self._tab_title())
        self._tab_widget.setCurrentIndex(1)
        self.show()
        self._is_detached = False
        self._update_detach_button_text()

    def closeEvent(self, event):
        # Closing the detached window returns it to the tab widget.
        if self._is_detached:
            self.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def is_detached(self):
        return self._is_detached

    # ------------------------------------------------------------------ titles / i18n
    def _update_detach_button_text(self):
        if self._is_detached:
            self._detach_btn.setText(T.tr('code.attach', 'Attach to Tabs'))
        else:
            self._detach_btn.setText(T.tr('code.detach', 'Detach'))

    def _update_zoom_buttons(self, size):
        """Disable a zoom button when the font size reached its limit."""
        self._zoom_out_btn.setEnabled(size > self._editor.MIN_FONT_SIZE)
        self._zoom_in_btn.setEnabled(size < self._editor.MAX_FONT_SIZE)

    def _file_title(self):
        if self._editor.current_file_path():
            name = Path(self._editor.current_file_path()).name
        else:
            name = T.tr('code.untitled', 'Untitled')
        return f'*{name}' if self._editor.is_modified() else name

    def _tab_title(self):
        if self._editor.current_file_path():
            return self._file_title()
        return T.tr('code.editor', 'Code Editor')

    def _window_title(self):
        return f'{self._tab_title()} - Pygame Studio'

    def _update_titles(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.window_title.set_title_name(self._window_title())
        elif self._tab_widget is not None:
            index = self._tab_widget.indexOf(self)
            if index >= 0:
                self._tab_widget.setTabText(index, self._tab_title())

    def apply_theme(self, is_dark):
        self._editor.apply_theme(is_dark)

    def retranslate(self):
        self._update_detach_button_text()
        self._update_titles()

    def get_ready_for_project(self):
        pass

    def clean_up(self):
        self._editor.close_file()


class _CodeEditorStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the code editor while it is
    detached from the center tab widget.

    Provides the custom WindowTitleBase title bar (drag to move, minimize /
    maximize / close buttons) and the usual edge-resize behavior, matching
    the rest of the editor's windows instead of the native OS window chrome.
    """

    def __init__(self, editor_window, title):
        super().__init__()
        self._editor_window = editor_window
        self.resize(1000, 700)
        self.set_window_body(editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        # Closing the standalone window re-docks the editor into the tabs.
        if self._editor_window is not None:
            self._editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)
