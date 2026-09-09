"""Tile map editor window (docked panel).

The editor binds to the currently selected ``TILE_MAP`` object (or the one
opened via a hierarchy double-click) and provides:

- a tileset picker + tile/grid size spinboxes (all undoable through the
  manager; the spinboxes use the same SuffixSpinBox style as the image
  editor / inspector),
- a tileset palette to pick the current tile (a status line shows how many
  whole tiles the source image yields, so the tile size can be matched to
  the tileset grid),
- an interactive map canvas with pencil / eraser / fill / pick tools,
  zooming (wheel / buttons / fit) and grid overlay. The active tool is
  highlighted like the image editor's tool bar; the zoom percentage is shown
  bottom-right in a status strip.

Every finished paint stroke is a single undoable command. The window lives as
a docked tab (like the image editor) but can be detached into its own
frameless top-level window and re-docked later.
"""

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout,
                               QInputDialog, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QScrollBar, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from pygamestudio.game.object.type import OBJECT_TILE_MAP
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import SuffixSpinBox
from pygamestudio.gui.tile_map_editor.canvas import (TileMapCanvas, TOOL_PENCIL,
                                                     TOOL_ERASE, TOOL_FILL, TOOL_PICK)
from pygamestudio.gui.tile_map_editor.palette import TilesetPalette
from pygamestudio.gui.base.window import WindowBase

IMAGE_FILTER = 'Image (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tga *.pcx)'

_TOOL_BUTTONS = (
    (TOOL_PENCIL, ':/images/pen.png', 'tile_map.tool_pencil', 'Paint'),
    (TOOL_ERASE, ':/images/eraser.png', 'tile_map.tool_erase', 'Erase'),
    (TOOL_FILL, ':/images/bucket.png', 'tile_map.tool_fill', 'Fill'),
    (TOOL_PICK, ':/images/color_picker.png', 'tile_map.tool_pick', 'Pick Tile'),
)


class TileMapEditorWindow(QWidget):
    """Docked tile map editor. Binds to one tile-map object at a time."""

    def __init__(self, game_manager=None):
        super().__init__()
        self._game_manager = game_manager
        self._object_uuid = None
        self._pending_palette_width = None
        # Detach support (mirrors the image editor).
        self._tab_widget = None
        self._is_detached = False
        self._standalone_window = None

        self._canvas_scroll = QScrollArea()
        self._canvas = TileMapCanvas(game_manager)
        self._palette_scroll = QScrollArea()
        self._palette = TilesetPalette()
        self._empty_label = QLabel()

        # Toolbar widgets.
        self._tileset_btn = QPushButton()
        self._tool_buttons = {}
        self._tile_w_spin = SuffixSpinBox()
        self._tile_h_spin = SuffixSpinBox()
        self._columns_spin = SuffixSpinBox()
        self._rows_spin = SuffixSpinBox()
        self._zoom_in_btn = QPushButton()
        self._zoom_out_btn = QPushButton()
        self._fit_btn = QPushButton()
        self._detach_btn = QPushButton()
        # Layer bar widgets (multi-layer tile maps).
        self._layer_combo = QComboBox()
        self._layer_add_btn = QToolButton()
        self._layer_remove_btn = QToolButton()
        self._layer_rename_btn = QToolButton()
        self._layer_visible_btn = QToolButton()
        self._layer_collision_btn = QToolButton()
        # Bottom status strip.
        self._status_label = QLabel()
        self._zoom_label = QLabel()

        self._set_up()

    # ------------------------------------------------------------------ setup
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self.setObjectName('tileMapEditorWindow')

    def _set_widget(self):
        self._canvas_scroll.setWidget(self._canvas)
        self._canvas_scroll.setWidgetResizable(False)
        self._canvas_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas_scroll.setMinimumWidth(150)
        self._canvas_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._palette_scroll.setWidget(self._palette)
        self._palette_scroll.setWidgetResizable(False)
        self._palette_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # The palette pane is deliberately NOT fixed-width: the splitter handle
        # must stay draggable so the user can resize the left/right panes.
        self._palette_scroll.setMinimumWidth(150)
        self._palette_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._palette.bind_scroll_area(self._palette_scroll)

        self._empty_label.setObjectName('imageEditorEmptyLabel')
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setText(T.tr('tile_map.empty_hint',
                                       'Select a Tile Map object to edit it'))

        # --- tileset picker ------------------------------------------------
        self._tileset_btn.setObjectName('imageEditorToolBtn')
        self._tileset_btn.setIcon(QIcon(':/images/browse.png'))
        self._tileset_btn.setIconSize(QSize(18, 18))
        self._tileset_btn.setFixedSize(28, 28)
        self._tileset_btn.setToolTip(T.tr('tile_map.choose_tileset', 'Choose Tileset'))
        self._tileset_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # --- tile / grid size spinboxes (image-editor SuffixSpinBox style) --
        # The suffix is drawn on the RIGHT of the value, so the grid spinboxes
        # get explicit col/row labels to tell the two apart at a glance.
        spinbox_specs = (
            (self._tile_w_spin, 'px', 'inspector.tile_width', 'Tile Width'),
            (self._tile_h_spin, 'px', 'inspector.tile_height', 'Tile Height'),
            (self._columns_spin, 'col', 'inspector.columns', 'Columns'),
            (self._rows_spin, 'row', 'inspector.rows', 'Rows'),
        )
        for spin, suffix, tooltip_key, default in spinbox_specs:
            spin.setRange(1, 99999)
            spin.setDecimals(0)
            spin.setSingleStep(1)
            spin.setValue(1)
            spin.set_suffix(suffix)
            spin.setToolTip(T.tr(tooltip_key, default))
            spin.setFixedWidth(78)

        # --- tool buttons (QToolButton + "active" highlight, like image
        # editor: NOT checkable so the icon never shifts when selected) ------
        for tool, icon, key, default in _TOOL_BUTTONS:
            btn = QToolButton(self)
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(T.tr(key, default))
            btn.setFixedSize(30, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._tool_buttons[tool] = btn
        self.set_tool(TOOL_PENCIL)

        # --- layer bar: the map is multi-layer; each layer has a name, a
        # visibility toggle and can be flagged as THE collision layer. The
        # combo width follows the longest layer name (see _fit_layer_combo).
        self._layer_combo.setMinimumWidth(48)
        self._layer_combo.setToolTip(T.tr('tile_map.layer_combo', 'Current Layer'))

        self._layer_add_btn.setObjectName('imageEditorToolBtn')
        self._layer_add_btn.setIcon(QIcon(':/images/add.png'))
        self._layer_add_btn.setToolTip(T.tr('tile_map.layer_add', 'Add Layer'))
        self._layer_remove_btn.setObjectName('imageEditorToolBtn')
        self._layer_remove_btn.setIcon(QIcon(':/images/close.png'))
        self._layer_remove_btn.setToolTip(T.tr('tile_map.layer_remove', 'Delete Layer'))
        self._layer_rename_btn.setObjectName('imageEditorToolBtn')
        self._layer_rename_btn.setIcon(QIcon(':/images/rename.png'))
        self._layer_rename_btn.setToolTip(T.tr('tile_map.layer_rename', 'Rename Layer'))
        for btn in (self._layer_add_btn, self._layer_remove_btn,
                    self._layer_rename_btn):
            btn.setIconSize(QSize(16, 16))
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Visible toggle: eye_open when the layer is shown, eye_off when it
        # is hidden (active highlight = layer is visible).
        self._layer_visible_btn = QToolButton(self)
        self._layer_visible_btn.setIcon(QIcon(':/images/eye_open.png'))
        self._layer_visible_btn.setIconSize(QSize(16, 16))
        self._layer_visible_btn.setFixedSize(26, 26)
        self._layer_visible_btn.setToolTip(T.tr('tile_map.layer_visible', 'Show / Hide Layer'))
        self._layer_visible_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._layer_visible_btn.setProperty('active', True)

        # Collision toggle: marks the current layer as THE collision layer.
        self._layer_collision_btn = QToolButton(self)
        self._layer_collision_btn.setIcon(QIcon(':/images/collide.png'))
        self._layer_collision_btn.setIconSize(QSize(16, 16))
        self._layer_collision_btn.setFixedSize(26, 26)
        self._layer_collision_btn.setToolTip(T.tr('tile_map.layer_collision', 'Collision Layer'))
        self._layer_collision_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._layer_collision_btn.setProperty('active', False)

        # --- zoom buttons --------------------------------------------------
        for btn, icon, key, default in (
            (self._zoom_out_btn, ':/images/zoom_out.png', 'tile_map.zoom_out', 'Zoom Out'),
            (self._zoom_in_btn, ':/images/zoom_in.png', 'tile_map.zoom_in', 'Zoom In'),
            (self._fit_btn, ':/images/fit_window_size.png', 'tile_map.fit', 'Fit'),
        ):
            btn.setObjectName('imageEditorToolBtn')
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(28, 28)
            btn.setToolTip(T.tr(key, default))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # --- detach button (reuses the code editor's detach look) ------------
        self._detach_btn.setObjectName('codeEditorDetachBtn')
        self._detach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_detach_button_text()

        # --- status strip --------------------------------------------------
        self._status_label.setObjectName('tileMapStatusLabel')
        self._zoom_label.setObjectName('tileMapZoomLabel')
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _set_signal(self):
        self._tileset_btn.clicked.connect(self._choose_tileset)
        self._canvas.tile_picked.connect(self._on_tile_picked)
        self._palette.tile_selected.connect(self._on_tile_selected)
        self._detach_btn.clicked.connect(self.toggle_detached)
        self._canvas.zoom_changed.connect(self._on_zoom_changed)
        self._zoom_in_btn.clicked.connect(lambda: self._zoom_by(1.25))
        self._zoom_out_btn.clicked.connect(lambda: self._zoom_by(1 / 1.25))
        self._fit_btn.clicked.connect(self._fit_to_view)

        self._layer_combo.currentIndexChanged.connect(self._on_layer_selected)
        self._layer_add_btn.clicked.connect(self._on_layer_add)
        self._layer_remove_btn.clicked.connect(self._on_layer_remove)
        self._layer_rename_btn.clicked.connect(self._on_layer_rename)
        self._layer_visible_btn.clicked.connect(self._on_layer_toggle_visible)
        self._layer_collision_btn.clicked.connect(self._on_layer_toggle_collision)

        self._tile_w_spin.valueChanged.connect(lambda v: self._set_param('tile_width', v))
        self._tile_h_spin.valueChanged.connect(lambda v: self._set_param('tile_height', v))
        self._columns_spin.valueChanged.connect(lambda v: self._set_param('columns', v))
        self._rows_spin.valueChanged.connect(lambda v: self._set_param('rows', v))

        for tool, btn in self._tool_buttons.items():
            btn.clicked.connect(lambda checked=False, t=tool: self.set_tool(t))

        gm = self._game_manager
        if gm is not None:
            gm.object_selected.connect(self._on_object_selected)
            gm.object_deleted.connect(self._on_object_deleted)
            gm.object_tile_map_parameter_changed.connect(self._on_tile_map_parameter_changed)

        T.add_observer(self)

        # Watch the mouse wheel application-wide so zooming also works over
        # the blank area around the map (see eventFilter).
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _set_layout(self):
        toolbar = QHBoxLayout()
        # One uniform gap between every toolbar control (no extra group
        # spacers), so e.g. Pick -> Zoom Out has the same spacing as any
        # other neighbouring pair of buttons.
        toolbar.setSpacing(6)
        # Left: the tileset picker + the tile/grid parameters it applies to.
        toolbar.addWidget(self._tileset_btn)
        toolbar.addWidget(self._tile_w_spin)
        toolbar.addWidget(self._tile_h_spin)
        toolbar.addWidget(self._columns_spin)
        toolbar.addWidget(self._rows_spin)
        toolbar.addStretch(1)
        # Right: the paint tools, zoom, then detach.
        for tool, btn in self._tool_buttons.items():
            toolbar.addWidget(btn)
        toolbar.addWidget(self._zoom_out_btn)
        toolbar.addWidget(self._zoom_in_btn)
        toolbar.addWidget(self._fit_btn)
        toolbar.addWidget(self._detach_btn)
        toolbar.setContentsMargins(8, 6, 8, 4)

        layer_bar = QHBoxLayout()
        layer_bar.setSpacing(6)
        # The whole layer group (combo + add/rename/delete + per-layer
        # toggles) sits on the RIGHT, so the two toolbar rows share one clean
        # right edge and never interleave with the sheet/grid parameters.
        layer_bar.addStretch(1)
        layer_bar.addWidget(self._layer_combo)
        layer_bar.addWidget(self._layer_add_btn)
        layer_bar.addWidget(self._layer_rename_btn)
        layer_bar.addWidget(self._layer_remove_btn)
        layer_bar.addWidget(self._layer_visible_btn)
        layer_bar.addWidget(self._layer_collision_btn)
        layer_bar.setContentsMargins(8, 2, 8, 4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._palette_scroll)
        self._splitter.addWidget(self._canvas_scroll)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([236, 900])

        status = QHBoxLayout()
        status.addWidget(self._status_label)
        status.addStretch(1)
        status.addSpacing(12)
        status.addWidget(self._zoom_label)
        status.setContentsMargins(8, 0, 8, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(toolbar)
        layout.addLayout(layer_bar)
        layout.addWidget(self._empty_label, 1)
        layout.addWidget(self._splitter, 1)
        layout.addLayout(status)

        self._set_edit_mode(False)

    # ------------------------------------------------------------- public
    def get_ready_for_project(self):
        self._refresh_from_object()

    def clean_up(self):
        if self._is_detached:
            self.attach()
        self.set_object(None)

    # -------------------------------------------------------------- detach
    def set_tab_widget(self, tab_widget):
        """Remember the tab widget this panel is docked into (detach support)."""
        self._tab_widget = tab_widget

    def toggle_detached(self):
        if self._is_detached:
            self.attach()
        else:
            self.detach()

    def detach(self):
        """Undock the editor into its own frameless top-level window."""
        if self._is_detached or self._tab_widget is None:
            return
        self._tab_widget.removeTab(self._tab_widget.indexOf(self))
        self.setParent(None)
        self._standalone_window = _TileMapEditorStandaloneWindow(
            self, self._window_title())
        self.show()
        self._standalone_window.show()
        self._is_detached = True
        self._update_detach_button_text()

    def attach(self):
        """Re-dock the editor back into its tab."""
        if not self._is_detached or self._tab_widget is None:
            return
        standalone = self._standalone_window
        self._standalone_window = None
        if standalone is not None:
            standalone._editor_window = None
            standalone.hide()
            standalone.deleteLater()
        if self._tab_widget.indexOf(self) < 0:
            self._tab_widget.addTab(self, self._tab_title())
        self._tab_widget.setCurrentWidget(self)
        self.show()
        self._is_detached = False
        self._update_detach_button_text()

    def closeEvent(self, event):
        if self._is_detached:
            self.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def is_detached(self):
        return self._is_detached

    def raise_editor(self):
        """Bring the editor to the front (docked: switch to its tab;
        detached: raise the standalone window)."""
        if self._is_detached:
            if self._standalone_window is not None:
                self._standalone_window.show()
                self._standalone_window.raise_()
                self._standalone_window.activateWindow()
        elif self._tab_widget is not None:
            self._tab_widget.setCurrentWidget(self)

    def _tab_title(self):
        return T.tr('tile_map.editor', 'Tile Map Editor')

    def _window_title(self):
        return ' Pygame Studio - {}'.format(self._tab_title())

    def _update_detach_button_text(self):
        if self._is_detached:
            self._detach_btn.setText(T.tr('tile_map.attach', 'Attach to Tabs'))
        else:
            self._detach_btn.setText(T.tr('tile_map.detach', 'Detach'))

    def _update_tab_text(self):
        if (not self._is_detached and self._tab_widget is not None
                and self._tab_widget.indexOf(self) >= 0):
            self._tab_widget.setTabText(self._tab_widget.indexOf(self),
                                        self._tab_title())

    def retranslate(self):
        self._tileset_btn.setToolTip(T.tr('tile_map.choose_tileset', 'Choose Tileset'))
        self._empty_label.setText(T.tr('tile_map.empty_hint', 'Select a Tile Map object to edit it'))
        for tool, btn in self._tool_buttons.items():
            key = {'pencil': 'tile_map.tool_pencil', 'erase': 'tile_map.tool_erase',
                   'fill': 'tile_map.tool_fill', 'pick': 'tile_map.tool_pick'}[tool]
            default = {'pencil': 'Paint', 'erase': 'Erase', 'fill': 'Fill',
                       'pick': 'Pick Tile'}[tool]
            btn.setToolTip(T.tr(key, default))
        self._tile_w_spin.setToolTip(T.tr('inspector.tile_width', 'Tile Width'))
        self._tile_h_spin.setToolTip(T.tr('inspector.tile_height', 'Tile Height'))
        self._columns_spin.setToolTip(T.tr('inspector.columns', 'Columns'))
        self._rows_spin.setToolTip(T.tr('inspector.rows', 'Rows'))
        self._zoom_in_btn.setToolTip(T.tr('tile_map.zoom_in', 'Zoom In'))
        self._zoom_out_btn.setToolTip(T.tr('tile_map.zoom_out', 'Zoom Out'))
        self._fit_btn.setToolTip(T.tr('tile_map.fit', 'Fit'))
        self._layer_combo.setToolTip(T.tr('tile_map.layer_combo', 'Current Layer'))
        self._layer_add_btn.setToolTip(T.tr('tile_map.layer_add', 'Add Layer'))
        self._layer_remove_btn.setToolTip(T.tr('tile_map.layer_remove', 'Delete Layer'))
        self._layer_rename_btn.setToolTip(T.tr('tile_map.layer_rename', 'Rename Layer'))
        self._layer_visible_btn.setToolTip(T.tr('tile_map.layer_visible', 'Show / Hide Layer'))
        self._layer_collision_btn.setToolTip(T.tr('tile_map.layer_collision', 'Collision Layer'))
        self._palette.setToolTip(T.tr('tile_map.palette_hint', 'Left: pick tile · Wheel: zoom · Shift+wheel: scroll'))
        self._update_detach_button_text()
        self._update_tab_text()
        self._refresh_from_object()

    def focus_canvas(self):
        self._canvas.setFocus()

    @property
    def canvas(self):
        return self._canvas

    def current_object_uuid(self):
        return self._object_uuid

    def set_object(self, object_uuid):
        """Bind the editor to a tile-map object (by uuid or object)."""
        if object_uuid is None:
            self._object_uuid = None
            self._canvas.set_object(None)
            self._reset_palette()
            self._set_edit_mode(False)
            self._clear_status()
            return
        obj = self._game_manager.get_object(object_uuid) if self._game_manager else None
        if obj is None or getattr(obj, 'type', '') != OBJECT_TILE_MAP:
            self._object_uuid = None
            self._canvas.set_object(None)
            self._reset_palette()
            self._set_edit_mode(False)
            self._clear_status()
            return
        self._object_uuid = obj.uuid
        self._canvas.set_object(obj)
        count = len(obj.get_tileset_tiles())
        self._bind_palette(obj)
        current = self._canvas.current_tile()
        if current < 0 or current >= count:
            self._canvas.set_current_tile(0)
        self._sync_spinboxes(obj)
        self._set_edit_mode(True)
        self._resize_canvas()
        self._update_zoom_label()
        self._update_status()
        self._refresh_layer_ui()
        self._palette.update()

    # --------------------------------------------------------------- edit ui
    def _set_edit_mode(self, editing):
        self._splitter.setVisible(editing)
        self._empty_label.setVisible(not editing)
        for w in (self._tileset_btn, self._tile_w_spin, self._tile_h_spin,
                  self._columns_spin, self._rows_spin):
            w.setEnabled(editing)
        for btn in self._tool_buttons.values():
            btn.setEnabled(editing)
        for w in (self._layer_combo, self._layer_add_btn, self._layer_remove_btn,
                  self._layer_rename_btn, self._layer_visible_btn,
                  self._layer_collision_btn):
            w.setEnabled(editing)
        for btn in (self._zoom_in_btn, self._zoom_out_btn, self._fit_btn):
            btn.setEnabled(editing)
        self._zoom_label.setVisible(editing)
        if editing:
            self.set_tool(TOOL_PENCIL)

    def _clear_status(self):
        self._status_label.setText('')
        self._zoom_label.setText('')
        self._palette.set_hint('')

    # ------------------------------------------------------- palette sizing
    def _natural_palette_width(self, obj):
        """Comfortable initial left-pane width that fits one full row of the
        source sheet's columns (so a 10-wide / 16px tileset starts ~382px
        wide). 0 when the tileset is unknown (236 default is used)."""
        if obj is None or not getattr(obj, 'tileset_path', ''):
            return 0
        sw, _sh = obj.get_tileset_dimensions()
        tw = int(getattr(obj, 'tile_width', 1) or 1)
        if sw and tw:
            cols = sw // tw
            if 0 < cols <= 12:
                return max(236, cols * 38 + 2)
        return 0

    def _bind_palette(self, obj):
        """Load the tileset into the palette and give the left pane a
        comfortable initial width (still user-resizable afterwards)."""
        len(obj.get_tileset_tiles())   # ensure the sheet is loaded (dims cache)
        self._palette.set_object(obj)
        self._pending_palette_width = self._natural_palette_width(obj) or 236
        self._apply_split_sizes()

    def _reset_palette(self):
        self._palette.set_object(None)
        self._pending_palette_width = None
        if self._splitter.width() > 0:
            self._splitter.setSizes([236, max(150, self._splitter.width() - 236)])

    def _apply_split_sizes(self):
        """Move the splitter handle to the desired initial width (a no-op
        while the window has no size yet - re-applied in showEvent)."""
        total = self._splitter.width()
        if total <= 0:
            return
        left = self._pending_palette_width or 236
        left = max(150, min(left, int(total * 0.55)))
        right = max(150, total - left)
        self._splitter.setSizes([left, right])

    def showEvent(self, event):
        """Once the docked tab is visible, apply the pending initial palette
        width (splitter sizes are meaningless while the widget has zero size)."""
        super().showEvent(event)
        if self._pending_palette_width:
            self._apply_split_sizes()

    # ------------------------------------------------------------- zoom/blank
    def eventFilter(self, obj, event):
        """Route mouse-wheel zoom across the WHOLE splitter content:
        - over the RIGHT (canvas) pane the map zooms (map + blank viewport),
        - over the LEFT (tileset) pane the palette preview zooms wherever the
          cursor is inside that pane (on the tiles, between them, or in the
          empty viewport below/beside the sheet).
        Scrollbars keep their native scrolling; Shift+wheel over the palette
        side keeps scrolling instead of zooming."""
        if (event.type() == QEvent.Type.Wheel
                and self._object_uuid is not None
                and self._splitter.isVisible()):
            widget = obj if isinstance(obj, QWidget) else None
            if widget is not None and self._is_inside_window(widget):
                zone = self._wheel_zone(widget)
                if zone is not None:
                    delta = event.angleDelta().y()
                    if delta:
                        if zone == 'palette' and (event.modifiers()
                                & Qt.KeyboardModifier.ShiftModifier):
                            # Shift+wheel keeps vertical scrolling.
                            return super().eventFilter(obj, event)
                        factor = 1.25 if delta > 0 else (1 / 1.25)
                        if zone == 'palette':
                            self._zoom_palette(factor)
                        else:
                            self._zoom_by(factor)
                        event.accept()
                        return True
        return super().eventFilter(obj, event)

    def _is_inside_window(self, widget):
        w = widget
        while w is not None:
            if w is self:
                return True
            w = w.parentWidget()
        return False

    def _wheel_zone(self, widget):
        """Which splitter pane a wheel event belongs to: 'canvas', 'palette'
        or None (scrollbars and unrelated widgets)."""
        w = widget
        while w is not None:
            if isinstance(w, QScrollBar):
                return None
            if w is self._palette or w is self._palette_scroll:
                return 'palette'
            if w is self._canvas_scroll or w is self._canvas:
                return 'canvas'
            w = w.parentWidget()
        return None

    def _zoom_palette(self, factor):
        """Zoom the tileset palette preview (wheel over the left pane)."""
        if self._palette.has_tiles():
            self._palette.zoom_by(factor)

    def _sync_spinboxes(self, obj):
        if obj is None:
            return
        for spin, attr in ((self._tile_w_spin, 'tile_width'),
                           (self._tile_h_spin, 'tile_height'),
                           (self._columns_spin, 'columns'),
                           (self._rows_spin, 'rows')):
            spin.blockSignals(True)
            spin.setValue(int(getattr(obj, attr)))
            spin.blockSignals(False)

    def _set_param(self, attr, value):
        if self._object_uuid and self._game_manager:
            self._game_manager.set_tile_map_parameter(self._object_uuid, attr, int(value))

    def _choose_tileset(self):
        if not self._object_uuid:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, T.tr('tile_map.choose_tileset', 'Choose Tileset'),
            '', IMAGE_FILTER)
        if path:
            self._game_manager.set_tile_map_parameter(self._object_uuid, 'tileset_path', path)

    # --------------------------------------------------------------- tools
    def set_tool(self, tool):
        """Activate a tool: update the canvas AND the visual highlight."""
        if tool not in self._tool_buttons:
            return
        self._canvas.set_tool(tool)
        for tid, btn in self._tool_buttons.items():
            active = (tid == tool)
            if btn.property('active') != active:
                btn.setProperty('active', active)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

    def _on_tile_selected(self, tile_id):
        self._canvas.set_current_tile(tile_id)
        self.set_tool(TOOL_PENCIL)

    # ---------------------------------------------------------------- layers
    def _on_layer_selected(self, index):
        """User switched the active layer in the combo: painting now targets
        that layer (editor state only - nothing to undo)."""
        obj = self._current_object()
        if obj is None:
            return
        obj.set_active_layer_index(index)
        self._layer_icon_refresh(obj)

    def _on_layer_add(self):
        obj = self._current_object()
        if obj is None or not self._game_manager:
            return
        name, ok = QInputDialog.getText(
            self, T.tr('tile_map.layer_add_title', 'Add Layer'),
            T.tr('tile_map.layer_name_prompt', 'Layer name:'),
            text=T.tr('tile_map.layer_default_name', 'Layer %1').replace(
                '%1', str(len(obj.layers) + 1)))
        if ok:
            self._game_manager.add_tile_map_layer(obj.uuid, name or None)

    def _on_layer_rename(self):
        obj = self._current_object()
        if obj is None or not self._game_manager:
            return
        index = obj.get_active_layer_index()
        name, ok = QInputDialog.getText(
            self, T.tr('tile_map.layer_rename_title', 'Rename Layer'),
            T.tr('tile_map.layer_name_prompt', 'Layer name:'),
            text=obj.get_layer_name(index))
        if ok and name and name.strip():
            self._game_manager.set_tile_map_layer_property(
                obj.uuid, index, 'name', name.strip())

    def _on_layer_remove(self):
        obj = self._current_object()
        if obj is None or not self._game_manager:
            return
        index = obj.get_active_layer_index()
        if len(obj.layers) <= 1:
            return
        name = obj.get_layer_name(index)
        answer = QMessageBox.question(
            self,
            T.tr('tile_map.layer_delete_confirm_title', 'Delete Layer'),
            T.tr('tile_map.layer_delete_confirm_text',
                 'Delete layer "{name}"?').format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._game_manager.remove_tile_map_layer(obj.uuid, index)

    def _on_layer_toggle_visible(self):
        obj = self._current_object()
        if obj is None or not self._game_manager:
            return
        index = obj.get_active_layer_index()
        self._game_manager.set_tile_map_layer_property(
            obj.uuid, index, 'visible', not obj.is_layer_visible(index))

    def _on_layer_toggle_collision(self):
        obj = self._current_object()
        if obj is None or not self._game_manager:
            return
        index = obj.get_active_layer_index()
        # If this layer already is the collision layer, pressing the button
        # turns collision OFF; otherwise it becomes THE collision layer.
        new_value = not obj.is_collision_layer(index)
        self._game_manager.set_tile_map_layer_property(
            obj.uuid, index, 'collision', new_value)

    def _current_object(self):
        if not self._object_uuid or not self._game_manager:
            return None
        obj = self._game_manager.get_object(self._object_uuid)
        if obj is None or getattr(obj, 'type', '') != OBJECT_TILE_MAP:
            return None
        return obj

    def _refresh_layer_ui(self):
        """Re-sync the layer combo + buttons with the object's layers (called
        after every layer-affecting manager change)."""
        obj = self._current_object()
        combo = self._layer_combo
        combo.blockSignals(True)
        combo.clear()
        if obj is not None:
            combo.addItems(obj.get_layer_names())
            combo.setCurrentIndex(obj.get_active_layer_index())
        combo.blockSignals(False)
        self._fit_layer_combo()
        if obj is None:
            return
        self._layer_icon_refresh(obj)

    def _fit_layer_combo(self):
        """Size the layer combo from its longest option text (+ room for the
        drop-down arrow), so short names don't leave a huge gap and long
        names stay fully readable."""
        combo = self._layer_combo
        fm = combo.fontMetrics()
        widest = 0
        for i in range(combo.count()):
            widest = max(widest, fm.horizontalAdvance(combo.itemText(i)))
        combo.setFixedWidth(max(64, min(320, widest + 34)))

    def _layer_icon_refresh(self, obj):
        index = obj.get_active_layer_index()
        visible = obj.is_layer_visible(index)
        collision = obj.is_collision_layer(index)
        self._layer_remove_btn.setEnabled(len(obj.layers) > 1)
        self._layer_collision_btn.setEnabled(True)
        self._set_button_active(self._layer_visible_btn, visible,
                                ':/images/eye_open.png' if visible
                                else ':/images/eye_off.png')
        self._set_button_active(self._layer_collision_btn, collision)
        self._layer_combo.setToolTip(T.tr(
            'tile_map.layer_combo_tip', 'Current Layer: {name}').format(
            name=obj.get_layer_name(index)))

    @staticmethod
    def _set_button_active(btn, active, icon=None):
        if icon:
            btn.setIcon(QIcon(icon))
        if btn.property('active') != active:
            btn.setProperty('active', bool(active))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _on_tile_picked(self, tile_id):
        self._canvas.set_current_tile(tile_id)
        self._palette.set_current_tile(max(0, tile_id))
        self.set_tool(TOOL_PENCIL)

    # --------------------------------------------------------------- zoom
    def _zoom_by(self, factor):
        z = self._canvas.zoom() * factor
        self._canvas.set_zoom(z)
        self._resize_canvas()
        self._update_zoom_label()

    def _on_zoom_changed(self, zoom):
        self._resize_canvas()
        self._update_zoom_label()

    def _fit_to_view(self):
        size = self._canvas.map_pixel_size()
        viewport = self._canvas_scroll.viewport().size()
        if size[0] <= 0 or viewport.width() <= 0 or viewport.height() <= 0:
            return
        z = min(viewport.width() / size[0], viewport.height() / size[1])
        self._canvas.set_zoom(z)
        self._resize_canvas()
        self._update_zoom_label()

    def _resize_canvas(self):
        size = self._canvas.map_pixel_size()
        self._canvas.setFixedSize(max(1, size[0]), max(1, size[1]))

    def _update_zoom_label(self):
        self._zoom_label.setText('{:d}%'.format(int(round(self._canvas.zoom() * 100))))

    # -------------------------------------------------------------- status
    def _update_status(self):
        """Bottom-left status line: map size + how many whole tiles the
        tileset yields (helps matching the tile size to the source grid)."""
        if not self._object_uuid or not self._game_manager:
            self._clear_status()
            return
        obj = self._game_manager.get_object(self._object_uuid)
        if obj is None or getattr(obj, 'type', '') != OBJECT_TILE_MAP:
            self._clear_status()
            return

        map_text = T.tr('tile_map.status_map', 'Map {w}×{h}').format(
            w=obj.width, h=obj.height)

        tw, th = obj.tile_width, obj.tile_height
        if obj.tileset_path:
            sw, sh = obj.get_tileset_dimensions()
            count = len(obj.get_tileset_tiles())
            if count:
                tile_text = T.tr(
                    'tile_map.status_tiles',
                    'Tileset {sw}×{sh} / tile {tw}×{th} → {n} tiles').format(
                    sw=sw, sh=sh, tw=tw, th=th, n=count)
                self._palette.set_hint('')
            else:
                tile_text = T.tr(
                    'tile_map.status_no_tiles',
                    'Tileset {sw}×{sh} fits no whole {tw}×{th} tile - set the '
                    'tile size to one cell of the source image').format(
                    sw=sw, sh=sh, tw=tw, th=th)
                self._palette.set_hint(tile_text)
        else:
            tile_text = T.tr('tile_map.status_no_tileset', 'No tileset chosen')
            self._palette.set_hint('')
        self._status_label.setText(f'{map_text}   {tile_text}')

    # -------------------------------------------------------- manager sync
    def _on_object_selected(self, object_uuid):
        if self._game_manager is None:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is not None and getattr(obj, 'type', '') == OBJECT_TILE_MAP:
            self.set_object(object_uuid)
        elif self._object_uuid is not None:
            # Selection moved to a non-tile-map object: show the empty state
            # so the panel never edits an object that is not selected.
            self.set_object(None)

    def _on_object_deleted(self, object_uuid):
        if self._object_uuid == object_uuid:
            self.set_object(None)

    def _on_tile_map_parameter_changed(self, object_uuid):
        if object_uuid != self._object_uuid:
            return
        self._refresh_from_object()

    def _refresh_from_object(self):
        if not self._object_uuid or not self._game_manager:
            return
        obj = self._game_manager.get_object(self._object_uuid)
        if obj is None or getattr(obj, 'type', '') != OBJECT_TILE_MAP:
            self.set_object(None)
            return
        self._canvas.set_object(obj)
        count = len(obj.get_tileset_tiles())
        self._palette.set_object(obj)
        current = self._canvas.current_tile()
        if current >= count:
            self._canvas.set_current_tile(max(0, count - 1))
        self._sync_spinboxes(obj)
        self._resize_canvas()
        self._update_zoom_label()
        self._palette.set_current_tile(self._canvas.current_tile())
        self._update_status()
        self._refresh_layer_ui()
        self._canvas.update()
        self._palette.update()


class _TileMapEditorStandaloneWindow(WindowBase):
    """Frameless top-level window hosting the tile map editor while it is
    detached from the center tab widget."""

    def __init__(self, editor_window, title):
        super().__init__()
        self._editor_window = editor_window
        self.resize(1100, 720)
        self.set_window_body(editor_window)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        if self._editor_window is not None:
            self._editor_window.attach()
            event.ignore()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event):
        # When detached this is its own top-level window, so scene undo/redo
        # and Ctrl+S must be handled here (they can no longer bubble up to
        # the main editor window).
        editor = self._editor_window
        gm = editor._game_manager if editor is not None else None
        if (gm is not None
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            if event.key() == Qt.Key.Key_S:
                gm.save_scene()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Z:
                gm.undo_stack.undo()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Y:
                gm.undo_stack.redo()
                event.accept()
                return
        super().keyPressEvent(event)
