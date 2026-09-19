"""The in-editor AI agent panel.

It sits on the right of the inspector: a chat with the built-in assistant that
works directly on the open project. Unlike an external MCP client, this panel
calls the tool layer as plain Python functions (`mcp.call_tool`) - no port, no
token, no JSON-RPC - while still going through the same registry, the same
validation and the same undo stack.

Layout::

    +-------------------------------------------------+
    | [settings] [clear]                      [detach] |
    | transcript (user / assistant / tool cards)        |
    | confirm bar (Allow / Deny, only when needed)      |
    | status line                                       |
    | +-----------------------------------------------+ |
    | | composer                              [Send]  | |
    | +-----------------------------------------------+ |
    +-------------------------------------------------+
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import *

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.config import get_editor_config
from pygamestudio.gui.agent.session import AgentSession
from pygamestudio.gui.agent.settings import AgentSettingsDialog
from pygamestudio.gui.agent.view import (AgentComposer, AgentComposerFrame, AgentConfirmBar,
                                         AgentContinueBar, AgentTranscript)
from pygamestudio.gui.base.window import DetachablePanel


class AgentWindow(DetachablePanel, QWidget):
    """Chat panel that drives the editor through the MCP tool layer."""

    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._session = AgentSession(self)

        self._settings_button = QPushButton()
        self._clear_button = QPushButton()
        self._transcript = AgentTranscript()
        self._confirm_bar = AgentConfirmBar()
        self._continue_bar = AgentContinueBar()
        self._composer = AgentComposer()
        self._composer_frame = AgentComposerFrame(self._composer)
        self._send_button = QPushButton()
        self._status_label = QLabel()

        self._setup()
        self._set_signal()
        self._apply_theme()
        self.retranslate()

    # ---------------------------------------------------------------- set up
    def _setup(self):
        # The panel shares the inspector column (a narrow tab), so it must fit
        # in a small width - the standalone window can be much wider.
        self.setMinimumWidth(180)

        # Icon-only buttons (settings.png / clear.png), same toolbar look as
        # the other panels - the QSS (QPushButton#agentIconBtn) does the rest.
        for button, icon, key, default in (
                (self._settings_button, ':/images/settings.png', 'agent.settings', 'Settings'),
                (self._clear_button, ':/images/clear.png', 'agent.clear', 'Clear')):
            button.setObjectName('agentIconBtn')
            button.setIcon(QIcon(icon))
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(26, 26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(T.tr(key, default))

        self._send_button.setText(T.tr('agent.send', 'Send'))
        self._send_button.setObjectName('agentSendBtn')
        self._send_button.setFixedHeight(24)
        self._send_button.setMinimumWidth(56)
        self._send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet('QLabel { color: #8a8a8a; }')

        top_row = QHBoxLayout()
        top_row.setContentsMargins(2, 2, 2, 0)
        top_row.setSpacing(4)
        top_row.addWidget(self._settings_button)
        top_row.addWidget(self._clear_button)
        top_row.addStretch(1)
        top_row.addWidget(self.detach_button())

        # The Send/Stop button floats INSIDE the input box, in its bottom right
        # corner: same grid cell as the input, aligned there. The bottom/right
        # margin of the frame (see AgentComposerFrame) keeps that corner free.
        send_holder = QWidget()
        send_holder.setObjectName('agentSendHolder')
        holder_layout = QVBoxLayout(send_holder)
        holder_layout.setContentsMargins(0, 0, 6, 6)
        holder_layout.addWidget(self._send_button)

        composer_grid = QGridLayout()
        composer_grid.setContentsMargins(0, 0, 0, 0)
        composer_grid.setSpacing(0)
        composer_grid.addWidget(self._composer_frame, 0, 0)
        composer_grid.addWidget(send_holder, 0, 0,
                                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(top_row)
        layout.addWidget(self._transcript, 1)
        layout.addWidget(self._confirm_bar)
        layout.addWidget(self._continue_bar)
        layout.addWidget(self._status_label)
        layout.addLayout(composer_grid)

    def _set_signal(self):
        self._settings_button.clicked.connect(self.show_settings)
        self._clear_button.clicked.connect(self._on_clear_clicked)
        self._send_button.clicked.connect(self._on_send_clicked)
        self._composer.submitted.connect(self._on_submitted)
        self._confirm_bar.decided.connect(self._on_confirmed)
        self._continue_bar.continued.connect(self._on_continue_clicked)
        self._continue_bar.cancelled.connect(self._on_continue_cancelled)

        self._session.message_added.connect(self._on_message_added)
        self._session.tool_started.connect(self._transcript.add_tool_call)
        self._session.tool_finished.connect(self._on_tool_finished)
        self._session.status_changed.connect(self._on_status_changed)
        self._session.confirmation_needed.connect(self._on_confirmation_needed)
        self._session.continue_needed.connect(self._on_continue_needed)
        self._session.finished.connect(self._on_finished)

    def _apply_theme(self):
        is_dark = (get_editor_config().get('theme') or 'dark') == 'dark'
        self._transcript.apply_theme(is_dark)
        self._composer_frame.apply_theme(is_dark)
        self._status_label.setStyleSheet(
            'QLabel { color: %s; }' % ('#8a8a8a' if is_dark else '#5f5f5f'))

    # ------------------------------------------------------------- interface
    def session(self) -> AgentSession:
        """The chat session (the tests and other panels use it)."""
        return self._session

    def transcript(self) -> AgentTranscript:
        return self._transcript

    def ask(self, text):
        """Send a message as if the user typed it (used by menus/scripts)."""
        self._session.send(text)

    def clear_conversation(self):
        self._session.reset()
        self._transcript.clear()
        self._confirm_bar.clear()
        self._continue_bar.clear()
        self._on_status_changed('', False)

    def _on_clear_clicked(self):
        """The Clear button asks first - the conversation is thrown away."""
        answer = QMessageBox.question(
            self,
            T.tr('message_box.quesiton_title', 'Confirm'),
            T.tr('message_box.question_clear_agent_content',
                 'Clear the current conversation?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.clear_conversation()

    def show_settings(self):
        dialog = AgentSettingsDialog(self._session.settings(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._session.set_settings(dialog.result_settings())
            self._session.reset()
            self._continue_bar.clear()
            self._update_input_state()
            self._transcript.add_note(T.tr('agent.settings_saved',
                                           'Settings saved. The conversation was reset.'))

    def apply_theme(self, is_dark: bool):
        """Follow the editor theme (hooked up like the other panels)."""
        self._transcript.apply_theme(is_dark)
        self._composer_frame.apply_theme(is_dark)

    def retranslate(self):
        self._settings_button.setToolTip(T.tr('agent.settings', 'Settings'))
        self._clear_button.setToolTip(T.tr('agent.clear', 'Clear'))
        self._confirm_bar.retranslate()
        self._continue_bar.retranslate()
        self._composer.retranslate()
        self._update_send_button(T.tr('agent.stop', 'Stop')
                                 if self._session.is_busy() else T.tr('agent.send', 'Send'))
        self.update_window_titles()

    def get_ready_for_project(self):
        """A new project starts with a fresh conversation."""
        self.clear_conversation()

    def clean_up(self):
        self.redock()
        self._session.cancel()
        self.clear_conversation()

    # ------------------------------------------------------------------ slots
    def _on_submitted(self, text):
        if self._session.is_busy():
            return
        self._session.send(self._composer.take_text() if text else '')

    def _on_send_clicked(self):
        if self._session.is_busy():
            self._session.cancel()
            return
        self._session.send(self._composer.take_text())

    def _on_message_added(self, role, text):
        if role == 'user':
            self._transcript.add_user(text)
        elif role == 'assistant':
            self._transcript.add_assistant(text)
        else:
            self._transcript.add_note(text)

    def _on_tool_finished(self, name, ok, text):
        self._transcript.add_tool_result(name, ok, text)

    def _on_status_changed(self, text, busy):
        if busy and not text:
            text = T.tr('agent.working', 'Working...')
        self._status_label.setText(text or '')
        self._update_send_button(T.tr('agent.stop', 'Stop') if busy else T.tr('agent.send', 'Send'))
        self._update_input_state()

    def _update_input_state(self):
        """Lock the input while a turn runs or waits for the Continue button.

        Typing is pointless while the agent works, and after the step limit
        the Continue button (not a new message) is what moves things on.
        """
        busy = self._session.is_busy()
        waiting = self._session.is_awaiting_continue()
        self._composer.setReadOnly(busy or waiting)
        self._composer.setEnabled(not waiting)
        self._send_button.setEnabled(not waiting)

    def _on_continue_needed(self, steps):
        self._continue_bar.offer(steps)
        self._update_input_state()

    def _on_continue_clicked(self):
        self._continue_bar.clear()
        self._session.continue_run()
        self._update_input_state()

    def _on_continue_cancelled(self):
        """Give up on a turn paused at the step limit.

        The conversation is kept, only the pending resumption is dropped: the
        input box is handed back and the user decides what happens next.
        """
        self._continue_bar.clear()
        self._session.dismiss_continue()
        self._transcript.add_note(T.tr('agent.continue_dismissed',
                                       'Stopped at the step limit.'))
        self._update_input_state()

    def _on_confirmation_needed(self, name, arguments):
        self._confirm_bar.ask(name, arguments)

    def _on_confirmed(self, allowed):
        self._confirm_bar.clear()
        self._session.approve(allowed)

    def _on_finished(self, error_text):
        if error_text:
            self._transcript.add_error(error_text)
        self._confirm_bar.clear()
    def _update_send_button(self, text):
        self._send_button.setText(text)

    # ---------------------------------------------------------------- detach
    def _tab_title(self):
        return T.tr('agent.title', 'AI Agent')

    def _dock_index(self):
        """Re-dock as the second tab, right after the Inspector."""
        return 1

    def standalone_window_size(self):
        return (420, 700)
