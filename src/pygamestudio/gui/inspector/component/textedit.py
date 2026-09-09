from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class TextEdit(QTextEdit):
    def __init__(self, inspector_container, text='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._text = text
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setText(self._text)
        self.setMaximumHeight(150)

    def _set_signal(self):
        self.textChanged.connect(self._inspector_container.set_object_text)

    def contextMenuEvent(self, e):
        pass


class SingleLineTextEdit(QLineEdit):
    """Single-line text field bound to a line-edit (input box) string
    parameter such as placeholder."""

    def __init__(self, inspector_container, text='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr or 'placeholder'
        self.setText(text)

        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        self._inspector_container.set_object_text_input_parameter(
            self._attr, self.text())


class TextInputTextEdit(QTextEdit):
    """Multi-line-capable text field for the text-input OBJECT's content.

    Mirrors the runtime max_length: the user can never type more characters
    than the object's current max_length (0 = unlimited), so what they edit
    in the inspector matches what the running game allows."""

    def __init__(self, inspector_container, text='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setText(text)
        self.setMaximumHeight(150)
        self.textChanged.connect(self._on_text_changed)

    def _max_length(self):
        try:
            obj = self._inspector_container._game_manager.get_object(
                self._inspector_container._object_uuid_in_inspection)
            return int(getattr(obj, 'max_length', 0) or 0)
        except Exception:
            return 0

    def _on_text_changed(self):
        limit = self._max_length()
        if limit > 0:
            text = self.toPlainText()
            if len(text) > limit:
                self.blockSignals(True)
                cursor = self.textCursor()
                self.setPlainText(text[:limit])
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)
                self.blockSignals(False)
        self._inspector_container.set_object_text()

    def contextMenuEvent(self, e):
        pass