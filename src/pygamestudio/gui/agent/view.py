"""Widgets of the AI agent panel: the transcript view, the composer and the
confirmation bar.

The transcript is HTML inside a read-only ``QTextBrowser`` (same approach as the
console panel): plain, fast, no extra dependency, and it copes with streaming
amounts of text. Tool calls are shown as compact cards so the user can see what
the agent did, and every result can be traced back to the tool that produced it.
"""

import html
import json

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QTextCharFormat, QTextCursor,
                           QTextDocument, QTextDocumentFragment)
from PySide6.QtWidgets import *

from pygamestudio.common.i18n.translator import Translator as T

#: Colors of the chat messages/cards. The surface itself (background, border)
#: is themed by the editor QSS (``QTextBrowser#agentTranscript`` -> #282828 in
#: the dark theme), exactly like the console log browser.
COLORS = {
    'dark': {
        'text': '#d4d4d4', 'muted': '#8a8a8a',
        'user': '#4daafc', 'assistant': '#d4d4d4', 'tool': '#c58af9',
        'ok': '#3fa34d', 'error': '#e05252', 'card': '#232323', 'border': '#3c3c3c',
    },
    'light': {
        'text': '#1f1f1f', 'muted': '#6a6a6a',
        'user': '#0a66c2', 'assistant': '#1f1f1f', 'tool': '#7a3fbf',
        'ok': '#2f7d32', 'error': '#c62828', 'card': '#f3f3f3', 'border': '#d0d0d0',
    },
}


class AgentTranscript(QTextBrowser):
    """Read-only chat transcript (user / assistant / tool cards).

    The chat surface comes from the theme QSS, so the panel follows the editor
    theme even when it is detached; only the HTML colors of the messages are
    switched here.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme = 'dark'
        #: Every message ever written (kind, payload...). The color of a block
        #: lives in its inline HTML, so a theme switch re-renders this log.
        self._entries = []
        self.setObjectName('agentTranscript')
        self.setOpenExternalLinks(False)
        self.setReadOnly(True)

    # ----------------------------------------------------------------- theme
    def apply_theme(self, is_dark: bool):
        """Follow the editor theme, re-rendering everything already written.

        The message colors are baked into the HTML of each block, so simply
        remembering the new palette would leave old tool cards dark on a light
        surface: the log is rendered again with the new colors instead.
        """
        theme = 'dark' if is_dark else 'light'
        if theme == self._theme:
            return
        self._theme = theme
        self._rebuild()

    def clear(self):
        """Empty the transcript, log included."""
        self._entries.clear()
        super().clear()

    def _rebuild(self):
        """Render the logged entries again with the current colors."""
        scrollbar = self.verticalScrollBar()
        scroll_value = scrollbar.value()
        entries = list(self._entries)
        self._entries = []
        super().clear()
        for entry in entries:
            self._entries.append(entry)
            self._render(entry)
        scrollbar.setValue(min(scroll_value, scrollbar.maximum()))

    def _colors(self):
        return COLORS[self._theme]

    # -------------------------------------------------------------- content
    def _scroll_to_end(self):
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_html(self, block: str, blank_lines: int = 0):
        """Append one rich-text block, always starting on a fresh line.

        A markdown answer ends inside its own block, so inserting the next
        ``<p>`` right away would glue it to the answer - a block break first
        keeps every message on its own line (and lets the margins apply).
        ``blank_lines`` adds empty lines above the block, which is how a new
        user prompt is kept apart from the answer before it.
        """
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if cursor.block().text():
            cursor.insertBlock()
        if blank_lines and not self.document().isEmpty():
            for _ in range(blank_lines):
                cursor.insertBlock()
        cursor.insertHtml(block)
        self.setTextCursor(cursor)
        self._scroll_to_end()

    def add_user(self, text):
        self._add(('user', text))

    def add_assistant(self, text):
        """The answer of the assistant, rendered as markdown.

        Qt's markdown importer turns the answer into rich text (headings, bold,
        lists, tables, ``code`` and code blocks), so the panel does not show the
        raw ``**``/``` markup. The colour is taken from the insertion point, so
        the answer follows the editor theme, and the text stays selectable.
        """
        self._add(('assistant', text))

    def add_note(self, text):
        self._add(('note', text))

    def add_error(self, text):
        self._add(('error', text))

    def add_tool_call(self, name, arguments):
        self._add(('tool_call', name, arguments))

    def add_tool_result(self, name, ok, text):
        self._add(('tool_result', name, ok, text))

    # ------------------------------------------------------------ rendering
    def _add(self, entry):
        """Log one entry and draw it with the current colors."""
        self._entries.append(entry)
        self._render(entry)

    def _render(self, entry):
        """Draw one logged entry (used for new messages and for re-renders)."""
        kind = entry[0]
        if kind == 'user':
            self._render_user(entry[1])
        elif kind == 'assistant':
            self._render_assistant(entry[1])
        elif kind == 'note':
            self._render_note(entry[1])
        elif kind == 'error':
            self._render_error(entry[1])
        elif kind == 'tool_call':
            self._render_tool_call(entry[1], entry[2])
        elif kind == 'tool_result':
            self._render_tool_result(entry[1], entry[2], entry[3])

    def _render_user(self, text):
        c = self._colors()
        body = html.escape(text).replace('\n', '<br>')
        # Two empty lines separate a new prompt from the answer above it.
        self._append_html(
            f'<p style="margin:0 0 4px 0;color:{c["user"]};"><b>&gt; {body}</b></p>',
            blank_lines=2)

    def _render_assistant(self, text):
        text = (text or '').strip()
        if not text:
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(self._colors()['assistant']))
        cursor.setCharFormat(char_format)
        document = QTextDocument()
        document.setMarkdown(text)
        cursor.insertFragment(QTextDocumentFragment(document))
        self._scroll_to_end()

    def _render_note(self, text):
        c = self._colors()
        self._append_html(
            f'<p style="margin:2px 0;color:{c["muted"]};"><i>{html.escape(text)}</i></p>')

    def _render_error(self, text):
        c = self._colors()
        body = html.escape(text).replace('\n', '<br>')
        self._append_html(f'<p style="margin:6px 0;color:{c["error"]};"><b>{body}</b></p>')

    def _render_tool_call(self, name, arguments):
        c = self._colors()
        args = html.escape(_short_json(arguments, 300))
        self._append_html(
            f'<div style="margin:4px 0;padding:4px 6px;background:{c["card"]};'
            f'border-left:3px solid {c["tool"]};border-radius:3px;">'
            f'<span style="color:{c["tool"]};"><b>{html.escape(name)}</b></span>'
            f'<div style="color:{c["muted"]};font-family:Consolas,monospace;'
            f'font-size:11px;">{args}</div></div>')

    def _render_tool_result(self, name, ok, text):
        c = self._colors()
        color = c['ok'] if ok else c['error']
        status = 'ok' if ok else 'error'
        preview = html.escape(_short_text(text, 600))
        self._append_html(
            f'<div style="margin:0 0 6px 0;padding:4px 6px;background:{c["card"]};'
            f'border-left:3px solid {c["border"]};border-radius:3px;">'
            f'<span style="color:{color};">{html.escape(name)} - {status}</span>'
            f'<div style="color:{c["muted"]};font-family:Consolas,monospace;'
            f'font-size:11px;">{preview}</div></div>')


class AgentComposer(QPlainTextEdit):
    """Input box: Enter sends, Shift+Enter adds a newline.

    The editor itself stays transparent - the rounded surface and its blue
    focus ring are painted by the surrounding :class:`AgentComposerFrame`
    (a stylesheet border is not drawn on a QPlainTextEdit by the native
    Windows style, so it only showed up in fragments).
    """

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('agentComposer')
        self.setFrameShape(QFrame.Shape.NoFrame)   # the frame paints the border
        self.setPlaceholderText(T.tr('agent.placeholder',
                                     'Ask the agent to build, change or explain something...'))
        self.setTabChangesFocus(True)
        # Two lines; the visible input box is taller because the frame adds the
        # padding, including the room for the Send button floating inside it.
        self.setFixedHeight(44)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                return super().keyPressEvent(event)
            self.submitted.emit(self.toPlainText())
            return
        return super().keyPressEvent(event)

    def take_text(self) -> str:
        text = self.toPlainText()
        self.clear()
        return text

    def retranslate(self):
        self.setPlaceholderText(T.tr('agent.placeholder',
                                     'Ask the agent to build, change or explain something...'))


class AgentComposerFrame(QWidget):
    """The rounded input surface around an :class:`AgentComposer`.

    Qt does not paint stylesheet borders on a QPlainTextEdit when the native
    Windows style is active (only fragments of the focus ring showed up), so
    the background and the border - grey normally, blue while the input is
    focused or hovered - are painted here instead. That is also why the editor
    inside keeps a transparent background and the padding is a layout margin:
    the bottom strip is the room reserved for the Send button.
    """

    #: Per theme: input background, idle border, active (focus/hover) border.
    COLORS = {
        'dark': {'bg': '#282828', 'idle': '#3c3c3c', 'active': '#007acc'},
        'light': {'bg': '#f2f2f2', 'idle': '#c0c0c0', 'active': '#007acc'},
    }
    #: Corner radius of the painted box.
    RADIUS = 5.0

    def __init__(self, composer, parent=None):
        super().__init__(parent)
        self.setObjectName('agentComposerFrame')
        self._composer = composer
        self._theme = 'dark'
        self._hovered = False
        composer.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 30)
        layout.addWidget(composer)

    # ------------------------------------------------------------- interface
    def composer(self) -> AgentComposer:
        return self._composer

    def apply_theme(self, is_dark: bool):
        """Follow the editor theme (dark/light surface colours)."""
        self._theme = 'dark' if is_dark else 'light'
        self.update()

    # ---------------------------------------------------------------- events
    def eventFilter(self, watched, event):
        """Repaint the ring when the editor gains focus or is hovered."""
        if watched is self._composer:
            kind = event.type()
            if kind == QEvent.Type.Enter:
                self._hovered = True
                self.update()
            elif kind == QEvent.Type.Leave:
                self._hovered = False
                self.update()
            elif kind in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
                self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        colors = self.COLORS[self._theme]
        active = self._composer.hasFocus() or self._hovered
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outline = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors['bg']))
        painter.drawRoundedRect(outline, self.RADIUS, self.RADIUS)
        pen = QPen(QColor(colors['active'] if active else colors['idle']))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(outline, self.RADIUS, self.RADIUS)
        painter.end()


class AgentConfirmBar(QWidget):
    """A thin bar that asks the user to allow or deny one tool call."""

    decided = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel()
        self._allow_button = QPushButton()
        self._deny_button = QPushButton()

        self._label.setWordWrap(True)
        self._allow_button.setText(T.tr('agent.allow', 'Allow'))
        self._deny_button.setText(T.tr('agent.deny', 'Deny'))
        self._allow_button.clicked.connect(lambda: self.decided.emit(True))
        self._deny_button.clicked.connect(lambda: self.decided.emit(False))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._allow_button)
        layout.addWidget(self._deny_button)
        self.hide()

    def ask(self, tool_name, arguments):
        self._label.setText(T.tr('agent.confirm_tool', 'Run {}?').format(tool_name))
        self._label.setToolTip(_short_json(arguments, 600))
        self.show()

    def clear(self):
        self.hide()

    def retranslate(self):
        self._allow_button.setText(T.tr('agent.allow', 'Allow'))
        self._deny_button.setText(T.tr('agent.deny', 'Deny'))


class AgentContinueBar(QWidget):
    """Shown when a turn stopped at the step limit: continue it or drop it.

    While the bar is visible the input box is locked, so the user does not
    have to guess what to type to continue - pressing Continue picks the work
    up exactly where it stopped (like the Continue button of Copilot), while
    Cancel ends the turn and hands the input box back.
    """

    continued = Signal()
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel()
        self._continue_button = QPushButton()
        self._cancel_button = QPushButton()
        self._steps = None

        self._label.setWordWrap(True)
        self._continue_button.setObjectName('agentContinueBtn')
        self._continue_button.setText(T.tr('agent.continue', 'Continue'))
        self._continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_button.clicked.connect(lambda: self.continued.emit())
        self._cancel_button.setText(T.tr('agent.cancel', 'Cancel'))
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_button.clicked.connect(lambda: self.cancelled.emit())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._cancel_button)
        layout.addWidget(self._continue_button)
        self._equalize_buttons()
        self.hide()

    def offer(self, steps):
        self._steps = steps
        self._label.setText(self._message())
        self._equalize_buttons()
        self.show()

    def clear(self):
        self.hide()

    def retranslate(self):
        self._continue_button.setText(T.tr('agent.continue', 'Continue'))
        self._cancel_button.setText(T.tr('agent.cancel', 'Cancel'))
        self._equalize_buttons()
        if self._steps is not None:
            self._label.setText(self._message())

    def _equalize_buttons(self):
        """Both buttons form one pair, so they get the same size.

        The primary Continue button is styled (padding, colours) while Cancel
        keeps the plain button look, which alone would make them different
        widths and heights - the wider/taller of the two wins.
        """
        width = max(self._continue_button.sizeHint().width(),
                    self._cancel_button.sizeHint().width())
        height = max(self._continue_button.sizeHint().height(),
                     self._cancel_button.sizeHint().height())
        for button in (self._continue_button, self._cancel_button):
            button.setFixedSize(width, height)

    def _message(self) -> str:
        return T.tr('agent.step_limit',
                    'Step limit reached ({} steps). Continue when you are ready.').format(self._steps)


def _short_json(value, limit):
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    return _short_text(text, limit)


def _short_text(text, limit):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + ' ...'
