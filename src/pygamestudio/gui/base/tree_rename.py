"""
Inline rename editors of the tree panels (hierarchy, asset).

A tree row is exactly as tall as one line of text, while the global style sheet
gives every ``QLineEdit`` a 1px border and 3px padding. Squeezed into the row,
the editor's text area ended up SHORTER than the font, so the bottom of the text
was never drawn - a name ending in "_" showed no underscore at all.

Two small pieces fix that together: the rename box gets its own compact style
(no vertical padding) and its geometry is grown to the height it actually asks
for (centred on the row), so a bigger font keeps working too.
"""
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QLineEdit

#: Object name of an inline rename box (the style sheets target it).
RENAME_EDITOR_NAME = 'treeRenameEditor'


def prepare_rename_editor(editor):
    """Tag a freshly created inline editor so the compact style applies."""
    if isinstance(editor, QLineEdit):
        editor.setObjectName(RENAME_EDITOR_NAME)
    return editor


def fit_rename_editor(editor, rect):
    """Place the editor on ``rect``, grown to the height it needs (centred)."""
    result = QRect(rect)
    needed = editor.sizeHint().height()
    if needed > result.height():
        extra = needed - result.height()
        result.adjust(0, -(extra // 2), 0, extra - (extra // 2))
    editor.setGeometry(result)
