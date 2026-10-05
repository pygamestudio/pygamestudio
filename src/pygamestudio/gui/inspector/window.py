from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.base.window import DetachablePanel
from pygamestudio.gui.inspector.widget import *
from pygamestudio.gui.inspector.container import Container


class _AnimationEditingHint(QFrame):
    """Banner: the animation editor owns the object the inspector shows.

    While a Keyframe object is edited in the animation editor, the values
    the scene shows are the KEYFRAMES', not the object's own - so the
    property rows are disabled and this hint says why. The close button
    leaves the editing (the editor body switches to the console tab, which
    is exactly what switching the dock to another tab does by hand).
    """

    closed = Signal()

    def __init__(self):
        super().__init__()
        self._label = QLabel()
        self._close_btn = QPushButton()
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.retranslate()
        self.hide()

    def _set_widget(self):
        self.setObjectName('animationEditingHint')
        self._label.setObjectName('animationEditingHintLabel')
        # Long sentences must wrap instead of widening the whole panel.
        self._label.setWordWrap(True)
        self._close_btn.setObjectName('animationEditingHintCloseBtn')
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = QPixmap(':/images/close.png')
        scaled_pixmap = pixmap.scaled(self._close_btn.size(),
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self._close_btn.setIcon(QIcon(scaled_pixmap))

    def _set_signal(self):
        self._close_btn.clicked.connect(self.closed.emit)

    def _set_layout(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(6, 4, 4, 2)
        h_layout.setSpacing(4)
        h_layout.addWidget(self._label, 1)
        h_layout.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignTop)

    def retranslate(self):
        self._label.setText(T.tr('inspector.animation_editing',
                                 'This object is being edited in the Animation Editor'))
        self._close_btn.setToolTip(T.tr('inspector.animation_editing_close',
                                        'Close and switch to the Console'))


class InspectorWindow(DetachablePanel, QWidget):
    #: The hint's close button was clicked: the editor body leaves the
    #: animation editing (switch to the console tab, which releases the
    #: object - the animation editor claims it only while its tab is shown).
    animation_hint_closed = Signal()

    def __init__(self, parent=None, game_manager=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._animation_editing_uuid = None
        self._select_previous_object_button = SelectPreviousObjectButton()
        self._select_next_object_button = SelectNextObjectButton()
        self._editing_hint = _AnimationEditingHint()
        self._container = Container(self, game_manager)
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setMinimumWidth(220)
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName('inspectorScrollArea')
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setMinimumWidth(220)
        # A long property list must scroll instead of being clipped.
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setWidget(self._container)
    
    def _set_signal(self):
        self._select_previous_object_button.clicked.connect(self._container.select_previous_object)
        self._select_next_object_button.clicked.connect(self._container.select_next_object)
        self._container.selection_history_changed.connect(self._update_select_buttons)
        self._container.selection_index_changed.connect(self._update_select_buttons)
        self._editing_hint.closed.connect(self.animation_hint_closed.emit)
        # The hint text follows the editor language like every other panel.
        T.add_observer(self)

    def _set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self._select_previous_object_button)
        h_layout.addWidget(self._select_next_object_button)
        h_layout.addStretch(1)
        h_layout.addWidget(self._detach_btn)
        h_layout.setContentsMargins(0, 4, 0, 0)
        v_layout.addLayout(h_layout)
        # The lock notice stays fixed above the (scrolling) property rows.
        v_layout.addWidget(self._editing_hint)
        v_layout.addWidget(self._scroll_area, 1)
        v_layout.setSpacing(5)
        v_layout.setContentsMargins(0, 0, 0, 0)

    def _set_object_name(self):
        self.setObjectName('inspector')

    # ------------------------------------------------------------------ detach
    def _tab_title(self):
        return T.tr('inspector.inspector', 'Inspector')

    def standalone_window_size(self):
        return (360, 720)

    def _update_select_buttons(self, selection_history_length, current_index):
        if not selection_history_length:
            self._select_previous_object_button.set_disabled()
            self._select_next_object_button.set_disabled()
            return
        
        if current_index <= 0:
            self._select_previous_object_button.set_disabled()
        else:
            self._select_previous_object_button.set_enabled()

        if current_index >= selection_history_length - 1:
            self._select_next_object_button.set_disabled()
        else:
            self._select_next_object_button.set_enabled()

    def get_ready_for_project(self):
        self._container.get_ready_for_project()

    # --------------------------------------------------- animation editing lock
    def set_animation_editing_object(self, object_uuid):
        """Follow the animation editor: it is editing ``object_uuid`` now.

        The properties of that object are locked while it is edited there;
        '' releases everything (the editor is not the surface in view).
        """
        self._animation_editing_uuid = object_uuid or None
        self.update_animation_editing_lock()

    def update_animation_editing_lock(self):
        """Apply the hint and the lock for the object being inspected right now.

        Called whenever the inspected object OR the animation editor's
        target changes: both must be the same object for the lock to apply.
        """
        locked = (self._animation_editing_uuid is not None
                  and self._animation_editing_uuid
                  == self._container.inspected_object_uuid())
        self._editing_hint.setVisible(locked)
        self._container.set_properties_locked(locked)

    def retranslate(self):
        self._editing_hint.retranslate()

    def clean_up(self):
        self.redock()
        self._container.clean_up()
        self.update_animation_editing_lock()