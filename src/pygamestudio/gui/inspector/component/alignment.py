"""Alignment picker used by the text-input object inspector.

A row of three exclusive tool buttons for one axis. Icons live in
``common/res/images`` and are registered in resources.qrc:
    align_h_left.png / align_h_center.png / align_h_right.png
    align_v_top.png  / align_v_middle.png  / align_v_bottom.png
"""

from PySide6.QtCore import *
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T


class AlignmentButtonGroup(QWidget):
    """Three-button exclusive alignment picker.

    ``attr`` is either 'text_align' (left/center/right) or 'text_valign'
    (top/middle/bottom); changes go through the text-input parameter channel.
    """

    # value -> (icon resource, i18n key, default tooltip)
    _OPTIONS = {
        'text_align': (
            ('left',   ':/images/align_h_left.png',   'inspector.align_left',   'Align Left'),
            ('center', ':/images/align_h_center.png', 'inspector.align_center', 'Align Center'),
            ('right',  ':/images/align_h_right.png',  'inspector.align_right',  'Align Right'),
        ),
        'text_valign': (
            ('top',    ':/images/align_v_top.png',    'inspector.align_top',    'Align Top'),
            ('middle', ':/images/align_v_middle.png', 'inspector.align_middle', 'Align Middle'),
            ('bottom', ':/images/align_v_bottom.png', 'inspector.align_bottom', 'Align Bottom'),
        ),
    }

    def __init__(self, inspector_container, value='left', attr='text_align'):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        self._buttons = {}
        self._value = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for value_key, icon, key, default in self._OPTIONS.get(attr, ()):
            button = QToolButton(self)
            button.setIcon(QIcon(icon))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(T.tr(key, default))
            # NOT checkable on purpose: the selected state is a pure flat
            # background color (dynamic 'selected' property + QSS). Using
            # Qt's checked state would offset the icon 1px down/right (the
            # native "pressed in" content shift).
            button.setFixedSize(26, 24)
            button.setObjectName('alignmentToolBtn')
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
            self._buttons[value_key] = button
            button.clicked.connect(
                lambda checked=False, value=value_key: self._on_clicked(value))
        layout.addStretch(1)

        self.set_value(value)

    def _on_clicked(self, value):
        self.set_value(value)
        self._inspector_container.set_object_text_input_parameter(self._attr, value)

    def set_value(self, value):
        """Highlight the button matching ``value`` with the selected color
        (used when building the widget, syncing undo/redo and after a
        click). Selection never toggles Qt's checked state, so the icon does
        not move -- only the background color changes."""
        self._value = str(value)
        for value_key, button in self._buttons.items():
            selected = value_key == self._value
            if bool(button.property('selected')) == selected:
                continue
            button.setProperty('selected', selected)
            style = button.style()
            style.unpolish(button)
            style.polish(button)
            button.update()

