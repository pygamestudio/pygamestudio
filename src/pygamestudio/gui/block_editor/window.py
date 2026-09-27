"""
The block editor panel: palette + canvas, docked as a center tab (between the
code editor and the image editor) or detached into its own window.
"""

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.path import followed_path
from pygamestudio.gui.base.window import DetachButton, WindowBase, editor_run_handler
from pygamestudio.gui.block_editor.canvas import BlockCanvas
from pygamestudio.gui.block_editor.model import variable_type
from pygamestudio.gui.block_editor.palette import BlockPalette
from pygamestudio.gui.scene.widget import RunProjectButton

TAB_INDEX = 2  # right between the code editor and the image editor


class BlockEditorWindow(QWidget):
    """The visual (block) script editor panel."""

    script_saved = Signal(str)
    # emitted with the shown file path so the code editor opens the SAME file
    switch_to_code_requested = Signal(str)

    def __init__(self, game_manager=None):
        super().__init__()
        self._game_manager = game_manager
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None

        self._file_label = QLabel()
        self._undo_btn = QPushButton()
        self._redo_btn = QPushButton()
        self._zoom_in_btn = QPushButton()
        self._zoom_out_btn = QPushButton()
        self._code_btn = QPushButton()
        self._detach_btn = DetachButton()
        self._run_btn = RunProjectButton()
        self._palette = BlockPalette()
        self._canvas = BlockCanvas()
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self._file_label.setObjectName('blockEditorFileLabel')
        self._update_detach_button()
        for button, icon_name in ((self._undo_btn, 'undo'), (self._redo_btn, 'redo'),
                                  (self._zoom_in_btn, 'zoom_in'), (self._zoom_out_btn, 'zoom_out')):
            button.setObjectName('blockEditorToolBtn')
            button.setIcon(QIcon(':/images/{}.png'.format(icon_name)))
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(26, 26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._code_btn.setObjectName('editorSwitchBtn')
        self._code_btn.setIcon(QIcon(':/images/code.png'))
        self._code_btn.setIconSize(QSize(16, 16))
        self._code_btn.setFixedSize(26, 26)
        self._code_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _set_signal(self):
        self._palette.add_requested.connect(self._canvas.add_block)
        self._palette.variable_new_requested.connect(self._on_variable_new)
        self._palette.variable_edit_requested.connect(self._on_variable_edit)
        self._palette.variable_delete_requested.connect(self._on_variable_delete)
        self._canvas.variables_changed.connect(self._sync_variables)
        self._canvas.script_saved.connect(self._on_script_saved)
        self._canvas.modified_changed.connect(lambda _modified: self._update_titles())
        self._undo_btn.clicked.connect(self._canvas.undo)
        self._redo_btn.clicked.connect(self._canvas.redo)
        self._zoom_in_btn.clicked.connect(self._canvas.zoom_in)
        self._zoom_out_btn.clicked.connect(self._canvas.zoom_out)
        self._detach_btn.clicked.connect(self.toggle_detached)
        self._run_btn.clicked.connect(self._run_project)
        self._code_btn.clicked.connect(self._request_switch_to_code)
        self._sync_variables()
        self.retranslate()

    def _set_layout(self):
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self._file_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._undo_btn)
        toolbar_layout.addWidget(self._redo_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self._zoom_out_btn)
        toolbar_layout.addWidget(self._zoom_in_btn)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self._code_btn)
        toolbar_layout.addWidget(self._run_btn)
        toolbar_layout.addWidget(self._detach_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._palette)
        splitter.addWidget(self._canvas)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 760])

        window_layout = QVBoxLayout(self)
        window_layout.addLayout(toolbar_layout)
        window_layout.addWidget(splitter)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(4)

    def _set_object_name(self):
        self.setObjectName('blockEditorWindow')

    # ------------------------------------------------------------------ api
    def canvas(self):
        return self._canvas

    def open_file(self, file_path):
        """Load a block script and bring the panel into view."""
        self._canvas.open_file(file_path)
        self._update_titles()
        self._raise_window()

    def save(self):
        self._canvas.save_now()

    def _run_project(self):
        """Save the blocks and run the project (the script runs when an object
        of the scene uses it)."""
        self._canvas.save_now()
        if self._game_manager is not None:
            self._game_manager.run_project()

    def _request_switch_to_code(self):
        """Hand the file over to the code editor (saving pending edits first,
        so the code editor reads what the canvas currently shows)."""
        if self._canvas.is_modified():
            self._canvas.save_now()
        file_path = self._canvas.file_path()
        self.switch_to_code_requested.emit(str(file_path) if file_path else '')

    def _raise_window(self):
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.show()
                self._standalone_window.raise_()
                self._standalone_window.activateWindow()
        elif self._tab_widget is not None:
            self._tab_widget.setCurrentWidget(self)

    def raise_editor(self):
        """Bring this editor into view (its tab, or its detached window)."""
        self._raise_window()

    def focus_editor(self):
        """Give the keyboard focus to the block canvas."""
        self._canvas.setFocus()

    def _on_script_saved(self, path):
        self._update_titles()
        self.script_saved.emit(path)

    def handle_deleted_files(self, paths):
        """Clear the canvas when its script was deleted on disk.

        ``paths`` are the files/folders deleted in the asset panel (or via
        the MCP delete_file tool); a file below a deleted folder counts as
        deleted too. Clearing also forgets the path, so the debounced
        auto-save can no longer write the deleted script back to disk.
        """
        file_path = self._canvas.file_path()
        if file_path is None:
            return
        current = os.path.normcase(str(file_path))
        for path in paths:
            root = os.path.normcase(str(Path(path)))
            if current == root or current.startswith(root + os.sep):
                self._canvas.clear_file()
                self._update_titles()
                return

    def handle_moved_files(self, old_path, new_path):
        """Follow a script that was renamed / moved on disk.

        ``old_path`` -> ``new_path`` comes from the asset panel (rename,
        cut/paste, drag & drop) or the MCP move_file tool. When the canvas
        shows the moved script - or a script below a moved folder - it keeps
        its workspace and switches to the new path (the debounced auto-save
        then lands in the right place).
        """
        file_path = self._canvas.file_path()
        if file_path is None:
            return
        followed = followed_path(file_path, old_path, new_path)
        if followed is None:
            return
        self._canvas.retarget_file(followed)
        self._update_titles()

    # ------------------------------------------------------------------ variables
    def _sync_variables(self):
        """Mirror the variables of the opened script into the palette tab."""
        self._palette.set_variables(self._canvas.variables())

    def _on_variable_new(self):
        entry = self._ask_variable()
        if entry is not None:
            self._show_variable_error(self._canvas.add_variable(*entry)[1])

    def _on_variable_edit(self, variable_id):
        variable = next((item for item in self._canvas.variables()
                         if str(item.get('id')) == str(variable_id)), None)
        if variable is None:
            return
        entry = self._ask_variable(variable)
        if entry is not None:
            self._show_variable_error(self._canvas.update_variable(variable_id, *entry)[1])

    def _on_variable_delete(self, variable_id):
        variable = next((item for item in self._canvas.variables()
                         if str(item.get('id')) == str(variable_id)), None)
        if variable is None:
            return
        answer = QMessageBox.question(
            self, T.tr('block.var.title', 'Variable'),
            T.tr('block.var.delete_confirm', 'Delete the variable "{name}"?')
            .format(name=variable.get('name', '')))
        if answer == QMessageBox.StandardButton.Yes:
            self._canvas.remove_variable(variable_id)

    def _ask_variable(self, variable=None):
        """Ask for name (validated right away), type and initial value.

        Returns (name, value, type) or None when the user cancels. The name is
        checked as soon as the first dialog is accepted, so a bad name is
        reported before the type / value are ever asked for.
        """
        title = T.tr('block.var.title', 'Variable')
        current_name = str(variable.get('name', '')) if variable else ''
        current_value = str(variable.get('value', '0')) if variable else '0'
        current_type = variable_type(variable) if variable else 'number'
        while True:
            name, accepted = QInputDialog.getText(
                self, title, T.tr('block.var.name_prompt', 'Variable name:'),
                text=current_name)
            if not accepted:
                return None
            name = str(name).strip()
            error = self._canvas.check_variable_name(name, (variable or {}).get('id'))
            if not error:
                break
            QMessageBox.warning(self, title, T.tr(error, error))
            current_name = name
        type_choices = [(T.tr('block.var.type_number', 'Number'), 'number'),
                        (T.tr('block.var.type_text', 'Text'), 'text'),
                        (T.tr('block.var.type_bool', 'Boolean (True / False)'), 'bool')]
        labels = [text for text, _key in type_choices]
        keys = {text: key for text, key in type_choices}
        label, accepted = QInputDialog.getItem(
            self, title, T.tr('block.var.type_prompt', 'Variable type:'), labels,
            [key for _text, key in type_choices].index(current_type), False)
        if not accepted or str(label) not in keys:
            return None
        value_type = keys[str(label)]
        value = self._ask_variable_value(title, value_type, current_value)
        if value is None:
            return None
        return name, value, value_type

    def _ask_variable_value(self, title, value_type, current_value):
        """The initial value: booleans are picked, numbers are validated."""
        prompt = T.tr('block.var.value_prompt', 'Initial value:')
        if value_type == 'bool':
            options = ['True', 'False']
            index = 1 if str(current_value) in ('False', '0', '') else 0
            chosen, accepted = QInputDialog.getItem(self, title, prompt, options, index, False)
            return str(chosen) if accepted else None
        current = str(current_value)
        while True:
            text, accepted = QInputDialog.getText(self, title, prompt, text=current)
            if not accepted:
                return None
            text = str(text).strip()
            if value_type != 'number':
                return text
            try:
                float(text)
            except ValueError:
                QMessageBox.warning(self, title, T.tr(
                    'block.var.err_number', 'The initial value must be a number.'))
                current = text
                continue
            return text

    def _show_variable_error(self, error):
        if error:
            QMessageBox.warning(self, T.tr('block.var.title', 'Variable'), T.tr(error, error))

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
        """Undock the editor into a standalone frameless window."""
        if self._is_detached or self._tab_widget is None:
            return
        # Read the run entry point while the editor is still docked: the
        # floating window forwards Ctrl+R to it (WindowBase.keyPressEvent).
        run_handler = editor_run_handler(self)
        self._tab_widget.removeTab(self._tab_widget.indexOf(self))
        self.setParent(None)
        self._standalone_window = _BlockEditorStandaloneWindow(self, self._window_title())
        self._standalone_window.set_editor_run_handler(run_handler)
        self.show()
        self._standalone_window.show()
        self._is_detached = True
        self._update_detach_button()

    def attach(self):
        """Re-dock the standalone window back into the tab widget."""
        if not self._is_detached or self._tab_widget is None:
            return
        standalone = self._standalone_window
        self._standalone_window = None
        if standalone is not None:
            standalone._block_editor_window = None
            standalone.hide()
            standalone.deleteLater()
        self._tab_widget.insertTab(TAB_INDEX, self, self._tab_title())
        self._tab_widget.setCurrentIndex(TAB_INDEX)
        self.show()
        self._is_detached = False
        self._update_detach_button()

    def closeEvent(self, event):
        # Closing the detached window returns it to the tab widget.
        if self._is_detached:
            self.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def is_detached(self):
        return self._is_detached

    def is_floating_active(self):
        """True while this editor floats in its own window and that window
        is the active one (the user is working in the floating editor)."""
        return (self._is_detached
                and self._standalone_window is not None
                and self._standalone_window.isActiveWindow())

    def is_active(self):
        """True while this editor is the one the user is working in: the
        current tab, or its floating window being the active one."""
        if self._is_detached:
            return self.is_floating_active()
        return (self._tab_widget is not None
                and self._tab_widget.currentWidget() is self)

    # ------------------------------------------------------------------ titles / i18n
    def _file_title(self):
        """The file name shown inside the window (with the modified marker)."""
        path = self._canvas.file_path()
        if path:
            name = Path(path).name
            return '*{}'.format(name) if self._canvas.is_modified() else name
        return T.tr('block.editor', 'Block Editor')

    def _tab_title(self):
        # the tab keeps its editor name - the window shows the file itself
        return T.tr('block.editor', 'Block Editor')

    def _window_title(self):
        return ' Pygame Studio - {}'.format(self._file_title())

    def _update_titles(self):
        self._file_label.setText(self._file_title())
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.window_title.set_title_name(self._window_title())
        elif self._tab_widget is not None:
            index = self._tab_widget.indexOf(self)
            if index >= 0:
                self._tab_widget.setTabText(index, self._tab_title())

    def _update_detach_button(self):
        """Show the attach icon while the editor floats in its own window."""
        self._detach_btn.set_detached(self._is_detached)

    def apply_theme(self, is_dark):
        self._canvas.apply_theme(is_dark)
        self._palette.apply_theme(is_dark)

    def retranslate(self):
        self._undo_btn.setToolTip(T.tr('block.undo', 'Undo'))
        self._redo_btn.setToolTip(T.tr('block.redo', 'Redo'))
        self._zoom_in_btn.setToolTip(T.tr('block.zoom_in', 'Zoom In'))
        self._zoom_out_btn.setToolTip(T.tr('block.zoom_out', 'Zoom Out'))
        self._code_btn.setToolTip(T.tr('menu.open_in_code_editor', 'Open in Code Editor'))
        self._update_detach_button()
        self._palette.retranslate()
        # Blocks are labelled when their item is built, so a language switch
        # has to rebuild the scene - otherwise the canvas keeps the old text.
        self._canvas.rebuild()
        self._update_titles()

    def get_ready_for_project(self):
        # A project switch must not leave another project's script loaded.
        self._canvas.clear_file()
        self._update_titles()

    def clean_up(self):
        self._canvas.save_now()
        self._canvas.clear_file()
        self._update_titles()


class _BlockEditorStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the block editor while detached."""

    def __init__(self, block_editor_window, title):
        super().__init__()
        self._block_editor_window = block_editor_window
        self.resize(1100, 720)
        self.set_window_body(block_editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        # Closing the standalone window re-docks the editor into the tabs.
        if self._block_editor_window is not None:
            self._block_editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)
