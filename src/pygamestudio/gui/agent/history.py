"""Conversation history of the AI agent panel.

A small dialog listing the stored conversations of the open project (newest
first): the title comes from the first user message, the tooltip shows when it
was last used and how many messages it holds. A conversation can be opened
(click / double click / Open), deleted or a fresh chat started - the dialog
only reports what the user picked, the panel does the storing.
"""
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton,
                               QVBoxLayout)

from pygamestudio.common.i18n.translator import Translator as T


def _when(timestamp) -> str:
    """'just now' / '5 min ago' / '3 h ago' / '2026-10-06 14:03'."""
    try:
        seconds = float(timestamp or 0)
    except (TypeError, ValueError):
        return ''
    delta = time.time() - seconds
    if delta < 90:
        return T.tr('agent.when_now', 'just now')
    if delta < 3600:
        return T.tr('agent.when_minutes', '{} min ago').format(int(delta // 60))
    if delta < 24 * 3600:
        return T.tr('agent.when_hours', '{} h ago').format(int(delta // 3600))
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(seconds))


class AgentHistoryDialog(QDialog):
    """Pick a stored conversation, delete one or start a new chat."""

    #: A conversation was deleted (the panel removes it from the store).
    deleted = Signal(str)

    def __init__(self, records, current_id='', parent=None):
        super().__init__(parent)
        self._records = [record for record in (records or []) if isinstance(record, dict)]
        self._current_id = current_id
        self._chosen_id = ''
        self._wants_new_chat = False

        self.setWindowTitle(T.tr('agent.history', 'History'))
        self.setModal(True)
        self.setMinimumSize(430, 340)

        self._list = QListWidget()
        self._list.setObjectName('agentHistoryList')
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(lambda _item: self._open_selected())

        self._open_button = QPushButton(T.tr('agent.session_open', 'Open'))
        self._new_button = QPushButton(T.tr('agent.new_chat', 'New chat'))
        self._delete_button = QPushButton(T.tr('agent.session_delete', 'Delete'))
        self._close_button = QPushButton(T.tr('agent.close', 'Close'))
        self._open_button.clicked.connect(self._open_selected)
        self._new_button.clicked.connect(self._start_new_chat)
        self._delete_button.clicked.connect(self._delete_selected)
        self._close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self._new_button)
        buttons.addStretch(1)
        buttons.addWidget(self._delete_button)
        buttons.addWidget(self._open_button)
        buttons.addWidget(self._close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list, 1)
        layout.addLayout(buttons)

        self._fill()
        self._update_buttons()

    # ------------------------------------------------------------------ list
    def _fill(self):
        """Draw the records (the current conversation is marked bold)."""
        self._list.clear()
        current_font = QFont()
        current_font.setBold(True)
        for record in self._records:
            title = str(record.get('title') or '').strip() \
                or T.tr('agent.session_untitled', 'Untitled conversation')
            item = QListWidgetItem(title)
            messages = record.get('messages') or []
            item.setData(Qt.ItemDataRole.UserRole, str(record.get('id') or ''))
            item.setToolTip(T.tr('agent.session_meta', '{} · {} messages').format(
                _when(record.get('updated_at')), len(messages)))
            if str(record.get('id') or '') == self._current_id:
                item.setFont(current_font)
                item.setToolTip(item.toolTip() + ' · ' + T.tr('agent.session_current',
                                                              'current'))
            self._list.addItem(item)
        if not self._records:
            placeholder = QListWidgetItem(T.tr('agent.session_empty',
                                               'No saved conversations yet.'))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)
        self._list.setCurrentRow(0 if self._records else -1)
        self._update_buttons()

    def _selected_id(self) -> str:
        item = self._list.currentItem()
        if item is None:
            return ''
        return str(item.data(Qt.ItemDataRole.UserRole) or '')

    def _update_buttons(self):
        has_selection = bool(self._selected_id())
        self._open_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)

    def _on_item_clicked(self, item):
        self._update_buttons()

    # --------------------------------------------------------------- actions
    def _open_selected(self):
        session_id = self._selected_id()
        if not session_id:
            return
        self._chosen_id = session_id
        self.accept()

    def _start_new_chat(self):
        self._wants_new_chat = True
        self.accept()

    def _delete_selected(self):
        session_id = self._selected_id()
        if not session_id:
            return
        answer = QMessageBox.question(
            self,
            T.tr('message_box.quesiton_title', 'Confirm'),
            T.tr('agent.session_delete_confirm',
                 'Delete this conversation? This cannot be undone.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._records = [record for record in self._records
                         if str(record.get('id') or '') != session_id]
        self.deleted.emit(session_id)
        self._fill()

    # ---------------------------------------------------------------- result
    def chosen_session_id(self) -> str:
        """The conversation the user opened ('' when none was picked)."""
        return self._chosen_id

    def wants_new_chat(self) -> bool:
        """True when the user asked for a fresh conversation."""
        return self._wants_new_chat
