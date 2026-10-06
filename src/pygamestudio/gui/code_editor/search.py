"""VS Code style find bar for the code editor.

A small floating frame that overlays the top-right corner of the code area
(Ctrl+F): a search field with a magnifier icon, the match counter, a
"match case" toggle and previous / next / close buttons.

The widget only collects input - finding, highlighting and scrolling happen in
``CodeEditor``, which owns the document (it rebuilds the search highlights as
extra selections together with the current-line highlight).
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton)

from pygamestudio.common.i18n.translator import Translator as T

_ICON_SIZE = QSize(12, 12)
_BUTTON_SIZE = 22


class _SearchInput(QLineEdit):
    """One-line find field.

    Enter = next match, Shift+Enter = previous, Escape = close, F3 /
    Shift+F3 = next / previous and Ctrl+F selects what is already there -
    all like VS Code.
    """

    next_requested = Signal()
    previous_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._search_icon = QLabel(self)
        self._search_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._search_icon.setFixedSize(14, 14)
        pixmap = QPixmap(':/images/search.png').scaled(
            self._search_icon.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._search_icon.setPixmap(pixmap)

        h_layout = QHBoxLayout(self)
        h_layout.addWidget(self._search_icon)
        h_layout.addStretch(1)
        h_layout.setContentsMargins(5, 0, 0, 0)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.previous_requested.emit()
            else:
                self.next_requested.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        if event.key() == Qt.Key.Key_F3:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.previous_requested.emit()
            else:
                self.next_requested.emit()
            return
        if (event.key() == Qt.Key.Key_F
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            # Ctrl+F inside the field: select the query (VS Code behaviour).
            self.selectAll()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        pass


class CodeSearchBar(QFrame):
    """The floating find bar shown at the top-right of the code area."""

    text_changed = Signal(str)
    case_toggled = Signal(bool)
    next_requested = Signal()
    previous_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._case_sensitive = False
        self._showing_no_results = False

        self._input = _SearchInput(self)
        self._input.setMinimumWidth(150)
        self._count_label = QLabel(self)
        self._count_label.setMinimumWidth(52)
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._case_btn = self._icon_button(':/images/case_sensitive.png')
        self._prev_btn = self._icon_button(':/images/up_arrow.png')
        self._next_btn = self._icon_button(':/images/down_arrow.png')
        self._close_btn = self._icon_button(':/images/close.png')

        self._set_up()
        self._set_signal()
        self._set_layout()

    # ------------------------------------------------------------------ setup
    def _set_up(self):
        self.setObjectName('codeSearchBar')
        self._input.setObjectName('codeSearchLineEdit')
        self._count_label.setObjectName('codeSearchCountLabel')
        for button in (self._case_btn, self._prev_btn, self._next_btn, self._close_btn):
            button.setObjectName('codeSearchBtn')
            button.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._case_btn.setProperty('selected', False)
        self.retranslate()
        # An empty counter would leave a gap that reads like the case button
        # belongs to the field's far right: seed it with the "no results"
        # text from the very first moment.
        self.set_match_info(0, 0)
        T.add_observer(self)

    def _make_button(self):
        button = QPushButton(self)
        button.setFlat(True)
        return button

    def _icon_button(self, icon_path):
        button = self._make_button()
        button.setIcon(QIcon(icon_path))
        button.setIconSize(_ICON_SIZE)
        return button

    def _set_signal(self):
        self._input.textChanged.connect(self._on_text_changed)
        self._input.next_requested.connect(self.next_requested)
        self._input.previous_requested.connect(self.previous_requested)
        self._input.close_requested.connect(self.close_requested)
        self._case_btn.clicked.connect(self._on_case_clicked)
        self._prev_btn.clicked.connect(self.previous_requested)
        self._next_btn.clicked.connect(self.next_requested)
        self._close_btn.clicked.connect(self.close_requested)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(2)
        h_layout.addWidget(self._input)
        h_layout.addWidget(self._count_label)
        h_layout.addWidget(self._case_btn)
        h_layout.addWidget(self._prev_btn)
        h_layout.addWidget(self._next_btn)
        h_layout.addWidget(self._close_btn)

    # ------------------------------------------------------------- callbacks
    def _on_text_changed(self, text):
        self.text_changed.emit(text)

    def _on_case_clicked(self):
        self._case_sensitive = not self._case_sensitive
        self._case_btn.setProperty('selected', self._case_sensitive)
        # Repolish so the QSS [selected="true"] rule takes effect.
        self._case_btn.style().unpolish(self._case_btn)
        self._case_btn.style().polish(self._case_btn)
        self.case_toggled.emit(self._case_sensitive)

    # ------------------------------------------------------------------ API
    def search_text(self):
        return self._input.text()

    def set_search_text(self, text):
        """Fill the field - emits text_changed like typing does."""
        self._input.setText(text)

    def is_case_sensitive(self):
        return self._case_sensitive

    def input_widget(self):
        return self._input

    def focus_input(self):
        """Give the field the keyboard focus and preselect the query."""
        self._input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._input.selectAll()

    def set_match_info(self, current, total):
        """Show 'current/total' (1-based); with nothing to show the label
        keeps the "no results" text (red while a query is actually typed, so
        the initial state does not read as an error)."""
        if total <= 0:
            self._showing_no_results = True
            self._count_label.setText(T.tr('code.search_no_results', 'No results'))
            self._count_label.setStyleSheet(
                'color: rgb(241, 76, 76);' if self._input.text() else '')
            return
        self._showing_no_results = False
        self._count_label.setStyleSheet('')
        self._count_label.setText('{}/{}'.format(max(1, current), total))

    def retranslate(self):
        self._input.setPlaceholderText(T.tr('code.search_placeholder', 'Find'))
        self._case_btn.setToolTip(T.tr('code.search_case', 'Match Case'))
        self._prev_btn.setToolTip(T.tr('code.search_previous',
                                       'Previous Match (Shift+Enter)'))
        self._next_btn.setToolTip(T.tr('code.search_next', 'Next Match (Enter)'))
        self._close_btn.setToolTip(T.tr('code.search_close', 'Close (Esc)'))
        if self._showing_no_results:
            self._count_label.setText(T.tr('code.search_no_results', 'No results'))
