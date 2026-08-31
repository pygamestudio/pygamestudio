from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import QMenu

from pygamestudio.common.i18n.translator import Translator as T


class CodeEditorMenu(QMenu):
    """Custom right-click context menu for the code editor.

    Replaces the default QPlainTextEdit context menu with the same editing
    actions (undo/redo, cut/copy/paste, delete, select all) plus a Run
    Project entry that launches the current project.
    """

    run_requested = Signal()

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._create_actions()

    def _create_actions(self):
        self._undo_action = self.addAction(T.tr('menu.undo', 'Undo'), self._editor.undo)
        self._undo_action.setShortcut(QKeySequence.Undo)
        self._redo_action = self.addAction(T.tr('menu.redo', 'Redo'), self._editor.redo)
        self._redo_action.setShortcut(QKeySequence.Redo)

        self.addSeparator()

        self._cut_action = self.addAction(T.tr('menu.cut', 'Cut'), self._editor.cut)
        self._cut_action.setShortcut(QKeySequence.Cut)
        self._copy_action = self.addAction(T.tr('menu.copy', 'Copy'), self._editor.copy)
        self._copy_action.setShortcut(QKeySequence.Copy)
        self._paste_action = self.addAction(T.tr('menu.paste', 'Paste'), self._editor.paste)
        self._paste_action.setShortcut(QKeySequence.Paste)
        self._delete_action = self.addAction(T.tr('menu.delete', 'Delete'), self._delete_selection)
        self._delete_action.setShortcut(QKeySequence.Delete)

        self.addSeparator()

        self._select_all_action = self.addAction(T.tr('menu.select_all', 'Select All'), self._editor.selectAll)
        self._select_all_action.setShortcut(QKeySequence.SelectAll)

        self.addSeparator()

        self._run_action = self.addAction(T.tr('menu.run', 'Run'), self.run_requested.emit)
        self._run_action.setShortcut(QKeySequence('Ctrl+R'))

    def _delete_selection(self):
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()

    def update_actions(self):
        """Enable/disable the edit actions to match the editor state."""
        self._undo_action.setEnabled(self._editor.document().isUndoAvailable())
        self._redo_action.setEnabled(self._editor.document().isRedoAvailable())
        has_selection = self._editor.textCursor().hasSelection()
        self._cut_action.setEnabled(has_selection)
        self._copy_action.setEnabled(has_selection)
        self._delete_action.setEnabled(has_selection)
        self._paste_action.setEnabled(self._editor.canPaste())
