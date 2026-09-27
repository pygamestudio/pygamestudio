"""
The block canvas: a QGraphicsView showing the workspace as Snap/Scratch-like
blocks, with drag & drop editing, field editing, zoom/pan and snapshot undo.

Layout model
------------
Every block is a ``BlockItem`` (a ``QGraphicsObject``). Nested statement lists
are Qt child items of their owner block, so moving a block moves its whole
subtree for free. Drag & drop is implemented at the view level: dragging a
block detaches it (plus its following siblings) from the model immediately,
drops a floating copy under the cursor, and re-inserts it on release at the
nearest "gap" (every position in every statement list).
"""

import json
import re

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetrics, QKeySequence, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QGraphicsItem, QGraphicsItemGroup, QGraphicsScene,
                               QGraphicsView, QInputDialog, QMenu, QMessageBox, QRubberBand)

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.block_editor import storage
from pygamestudio.gui.block_editor.model import (VARIABLE_TYPES, block_children, clone_block,
                                                 find_block, find_variable, insert_block,
                                                 new_block, new_stack, new_variable,
                                                 new_workspace, normalize_workspace,
                                                 remove_segment, rewrite_variable_references,
                                                 variable_name_error)
from pygamestudio.gui.block_editor.registry import (FIELD_WIDTHS, OPTION_FIELD_KINDS,
                                                    PROPERTY_OPTIONS, field_spec, field_value,
                                                    get_category, get_definition, header_text,
                                                    option_text, options_for)
BLOCK_MIME = 'application/x-pygs-block'

_VARIABLE_CODE = re.compile(r'^self\.(\w+)$')


def variable_field_text(value):
    """A custom variable reads as its bare name (``self.speed`` -> ``speed``)."""
    match = _VARIABLE_CODE.match(str(value))
    return match.group(1) if match else str(value)

HEADER_HEIGHT = 34
FIELD_HEIGHT = 22
FIELD_GAP = 8
H_PADDING = 12
ARM = 16
FOOTER = 14
BODY_PAD = 4
STACK_GAP = 0
PLACEHOLDER_HEIGHT = 22
ELSE_BAR_HEIGHT = 30
LABEL_ARROW_WIDTH = 16
BLOCK_RADIUS = 7.0

SNAP_DISTANCE = 60
SNAP_PROBE_RATIO = 0.5
MIN_SCALE = 0.2
MAX_SCALE = 5.0
WHEEL_ZOOM_FACTOR = 1.05
BUTTON_ZOOM_FACTOR = 1.15
ZOOM_LIMITS = (MIN_SCALE, MAX_SCALE)
SCENE_PADDING = 1600
DRAG_THRESHOLD = 4
DEFAULT_X = 40
DEFAULT_Y = 40
HOIST_GAP = 12
SAVE_DELAY = 400
UNDO_LIMIT = 50
GRID_MINOR = 20
GRID_MAJOR = 100


def category_color(category_key):
    """The block colour of a category (falls back to the action blue)."""
    category = get_category(category_key) or get_category('action')
    return QColor(category['color'])


def new_block_size(definition):
    """An approximate size of a block that does not exist as an item yet."""
    if definition is not None and definition['shape'] in ('c', 'c_else'):
        return QSizeF(180.0, HEADER_HEIGHT * 2 + FOOTER)
    return QSizeF(140.0, HEADER_HEIGHT)


class DropIndicator(QGraphicsItem):
    """A translucent silhouette of the dragged block at the place it will land."""

    def __init__(self):
        super().__init__()
        self._rect = QRectF()
        self._accent = QColor('#7ec8ff')
        self.setZValue(1000)

    def set_target(self, rect):
        self.prepareGeometryChange()
        self._rect = QRectF(rect)

    def target_rect(self):
        return QRectF(self._rect)

    def boundingRect(self):
        return self._rect.adjusted(-4, -4, 4, 4)

    def paint(self, painter, option, widget=None):
        if self._rect.isNull() or self._rect.width() <= 0:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(self._rect, BLOCK_RADIUS, BLOCK_RADIUS)
        accent = self._accent
        # soft glow behind the ghost so the landing spot pops out
        glow = QColor(accent.red(), accent.green(), accent.blue(), 60)
        painter.setPen(QPen(glow, 7.0))
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 55))
        painter.drawPath(path)
        painter.setPen(QPen(accent, 1.8, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


# ==================================================================== block item

class BlockItem(QGraphicsItem):
    """One block (hat, statement or C-block) drawn on the canvas."""

    def __init__(self, block, parent=None):
        super().__init__(parent)
        self._block = block
        self._definition = get_definition(block.get('type'))
        self._label = ''
        self._width = 0
        self._height = HEADER_HEIGHT
        self._field_rects = {}
        self._body_slots = []
        self._bars = []          # the elif / else bars (key + top position)
        self._footer_top = HEADER_HEIGHT
        self._color = category_color(self._definition['category'] if self._definition else 'action')
        self._font = QFont(QApplication.font())
        self._shape_path = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._layout()

    # ------------------------------------------------------------ accessors
    def block(self):
        return self._block

    def definition(self):
        return self._definition

    def width(self):
        return self._width

    def height(self):
        return self._height

    def boundingRect(self):
        return QRectF(-1.0, -1.0, self._width + 2.0, self._height + 2.0)

    def shape(self):
        """Hit-testing follows the block silhouette, not its bounding box.

        A control block's bounding box covers the inside of its mouth, so a
        click next to its body rows (or a rubber band there) would count as
        touching the whole block. The outline path (cached by ``_layout``) is
        the shape instead, exactly like Scratch / Blockly hit-test.
        """
        if self._shape_path is None:
            self._shape_path = self._build_outline_path()
        return self._shape_path

    def field_at(self, position):
        """The name of the field under a local position, or None."""
        for name, rect in self._field_rects.items():
            if rect.contains(position):
                return name
        definition = self._definition
        name = definition.get('label_from_field') if definition else None
        if name and position.y() <= HEADER_HEIGHT and position.x() <= self._width - H_PADDING:
            # the block label itself is the dropdown (e.g. the event block)
            return name
        return None

    def drop_gaps(self):
        """Every insertion position of this block's statement lists.

        Returns ``[(list_reference, index, scene_point), ...]``.
        """
        gaps = []
        for slot in self._body_slots:
            items = slot['items']
            origin = slot['origin']
            y = origin.y()
            for index, item in enumerate(items):
                gaps.append((slot['list'], index, self.mapToScene(QPointF(origin.x(), y))))
                y = item.y() + item.height() + STACK_GAP
            gaps.append((slot['list'], len(items), self.mapToScene(QPointF(origin.x(), y))))
        return gaps

    # ------------------------------------------------------------ layout
    def _layout(self):
        metrics = QFontMetrics(self._font)
        definition = self._definition
        self._label = (header_text(definition) if definition
                       else str(self._block.get('type')))
        label_width = metrics.horizontalAdvance(self._label)
        if definition is not None and definition.get('label_from_field'):
            label_width += LABEL_ARROW_WIDTH
        x = H_PADDING + label_width
        self._field_rects = {}
        for spec in (definition.get('fields', []) if definition else []):
            if spec['kind'] == 'event':
                # the event field is shown as the block label plus a dropdown arrow
                continue
            field_text = self._field_text(spec)
            width = max(FIELD_WIDTHS.get(spec['kind'], 80),
                        metrics.horizontalAdvance(field_text) + 26)
            x += FIELD_GAP
            self._field_rects[spec['name']] = QRectF(
                x, (HEADER_HEIGHT - FIELD_HEIGHT) / 2.0, width, FIELD_HEIGHT)
            x += width
        header_width = max(x + H_PADDING, 96)

        width = header_width
        height = HEADER_HEIGHT
        self._body_slots = []
        self._bars = []
        self._footer_top = HEADER_HEIGHT
        if definition and definition['shape'] in ('c', 'c_else'):
            cursor = float(HEADER_HEIGHT + BODY_PAD)
            content_width = 0.0
            for key, child_blocks in block_children(self._block):
                if key != 'body':
                    # every extra slot (elif / else) starts with its own bar
                    self._bars.append({'key': key, 'top': cursor})
                    cursor += ELSE_BAR_HEIGHT
                items = [BlockItem(child, self) for child in child_blocks]
                y = cursor
                for item in items:
                    item.setPos(ARM, y)
                    y += item.height() + STACK_GAP
                    content_width = max(content_width, item.width())
                self._body_slots.append({'key': key, 'list': child_blocks,
                                         'items': items, 'origin': QPointF(ARM, cursor)})
                if items:
                    cursor = y - STACK_GAP + BODY_PAD
                else:
                    cursor = cursor + PLACEHOLDER_HEIGHT + BODY_PAD
            self._footer_top = cursor
            height = cursor + FOOTER
            width = max(header_width, ARM + content_width + H_PADDING)
        elif definition and definition['shape'] == 'hat':
            # hats carry the statements stacked below them (touching tightly)
            cursor = float(HEADER_HEIGHT)
            has_body = False
            for key, child_blocks in block_children(self._block):
                items = [BlockItem(child, self) for child in child_blocks]
                y = cursor
                for item in items:
                    item.setPos(0, y)
                    y += item.height() + STACK_GAP
                self._body_slots.append({'key': key, 'list': child_blocks,
                                         'items': items, 'origin': QPointF(0, cursor)})
                if items:
                    cursor = y - STACK_GAP
                    has_body = True
            height = cursor if has_body else HEADER_HEIGHT
            # the event block keeps its own width: a wider stack below never
            # stretches the hat (Scratch style)
            width = header_width

        self.prepareGeometryChange()
        self._width = width
        self._height = height
        # the silhouette doubles as the hit-test shape (see shape())
        self._shape_path = self._build_outline_path()

    def _field_text(self, spec):
        value = field_value(self._block, self._definition, spec['name'])
        if spec['kind'] in OPTION_FIELD_KINDS:
            for option in options_for(spec['kind']):
                if option[0] == value:
                    return option_text(option)
            return variable_field_text(value)
        if spec['kind'] == 'amount':
            return variable_field_text(value)
        return str(value)

    # ------------------------------------------------------------ painting
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = self._color
        outline = color.darker(135)
        definition = self._definition
        shape = definition['shape'] if definition else 'stack'
        width = self._width
        height = self._height

        path = self._outline_path()

        painter.setPen(QPen(outline, 1.4))
        painter.fillPath(path, color)
        painter.drawPath(path)

        # label (for blocks with "label_from_field" the label IS the dropdown)
        painter.setPen(QColor('#ffffff'))
        font = QFont(self._font)
        font.setBold(shape == 'hat')
        painter.setFont(font)
        painter.drawText(QRectF(H_PADDING, 0, width - H_PADDING, HEADER_HEIGHT),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)
        if definition is not None and definition.get('label_from_field'):
            label_width = QFontMetrics(font).horizontalAdvance(self._label)
            self._paint_arrow(painter, H_PADDING + label_width + 5, HEADER_HEIGHT / 2.0)

        # fields
        field_font = QFont(self._font)
        painter.setFont(field_font)
        for spec in (definition.get('fields', []) if definition else []):
            rect = self._field_rects.get(spec['name'])
            if rect is None:
                continue
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1.0))
            painter.setBrush(QColor(255, 255, 255, 235))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QColor('#2b2b2b'))
            text = self._field_text(spec)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._clip_text(text, rect.width() - 10))
            if spec['kind'] in ('property', 'operator', 'amount'):
                self._paint_arrow(painter, rect.right() - 10, rect.center().y())

        # elif / else separators
        for bar in self._bars:
            # The separator only spans the bar itself: the arm continues
            # straight down on the left (Scratch style) and must stay solid.
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
            painter.drawLine(QPointF(ARM + 1, bar['top'] + 1),
                             QPointF(width - 1.5, bar['top'] + 1))
            painter.setPen(QColor('#ffffff'))
            painter.drawText(QRectF(ARM + 8, bar['top'], width - ARM - 8, ELSE_BAR_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             self._bar_label(bar['key']))

        if self.isSelected():
            # the highlight follows the block outline (rounded), not a box
            painter.setPen(QPen(QColor('#ffffff'), 1.6, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _outline_path(self):
        """The block silhouette used for painting and selection."""
        if self._shape_path is None:
            self._shape_path = self._build_outline_path()
        return self._shape_path

    def _build_outline_path(self):
        """The block silhouette (control blocks keep their “mouth”).

        The mouth is built from OVERLAPPING rectangles (header, arm, footer,
        else bar). They are merged with a real union - filling overlapping
        sub-paths left a transparent hole under the odd-even rule (the “否则”
        label sat on one) and STROKING them drew outlines through the middle
        of the shape (a stray vertical line crossing the else bar and its
        text), so the path is both fill- and stroke-safe now.
        """
        definition = self._definition
        shape = definition['shape'] if definition else 'stack'
        width = self._width
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        path.addRoundedRect(QRectF(0, 0, width, HEADER_HEIGHT), 7, 7)
        if shape in ('c', 'c_else'):
            arm = QPainterPath()
            # runs from the header past the footer so the union is seamless
            arm.addRect(QRectF(0, HEADER_HEIGHT - 1, ARM, self._footer_top - HEADER_HEIGHT + 3))
            path = path.united(arm)
            footer = QPainterPath()
            footer.addRoundedRect(QRectF(0, self._footer_top, width, FOOTER), 7, 7)
            path = path.united(footer)
            if self._bars:
                for bar_info in self._bars:
                    bar = QPainterPath()
                    bar.addRect(QRectF(0, bar_info['top'], width, ELSE_BAR_HEIGHT))
                    path = path.united(bar)
            path.setFillRule(Qt.FillRule.WindingFill)
        return path

    @staticmethod
    def _paint_arrow(painter, x, y):
        """A small downward chevron (marks a dropdown)."""
        painter.drawLine(QPointF(x - 3, y - 2), QPointF(x + 1, y + 2))
        painter.drawLine(QPointF(x + 1, y + 2), QPointF(x + 5, y - 2))

    @staticmethod
    def _bar_label(key):
        """The text drawn on an elif / else bar."""
        if key == 'elif':
            return T.tr('block.ctl.elif', 'elif')
        return T.tr('block.ctl.else', 'else')

    @staticmethod
    def _rounded(rect):
        path = QPainterPath()
        path.addRoundedRect(rect, 3, 3)
        return path

    def _clip_text(self, text, available):
        metrics = QFontMetrics(self._font)
        if metrics.horizontalAdvance(text) <= available:
            return text
        while text and metrics.horizontalAdvance(text + '...') > available:
            text = text[:-1]
        return text + '...'


# ==================================================================== canvas

class BlockCanvas(QGraphicsView):
    """The block workspace view (drag & drop editing + auto-save)."""

    script_saved = Signal(str)
    modified_changed = Signal(bool)
    variables_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._workspace = new_workspace()
        self._path = None
        self._items = []
        self._drop_targets = []
        self._undo_stack = []
        self._redo_stack = []
        self._drag = None
        self._panning = False
        self._pan_origin = QPoint()
        self._press_position = QPoint()
        self._press_item = None
        self._pending_field = None
        self._selected_ids = set()
        self._clipboard = []
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._band_origin = None
        self._band_last_rect = None
        self._redo_before_drag = []
        self._scale = 1.0
        self._is_dark = None
        self._dirty = False
        self._drop_indicator = DropIndicator()
        self._scene.addItem(self._drop_indicator)
        self._drop_indicator.setVisible(False)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY)
        self._save_timer.timeout.connect(self.save_now)
        self._set_up()

    def _set_up(self):
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        # Moving a block leaves ghost trails with the default (minimal) update
        # mode: the vacated area is not invalidated reliably. Repaint the whole
        # viewport instead - the same lesson as the scene rubber band.
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self._scene.setBackgroundBrush(QColor('#2e2e2e'))
        self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.apply_theme(True)

    # ------------------------------------------------------------ files
    def open_file(self, file_path):
        """Load a block script (silently keeps an empty workspace on failure)."""
        file_path = str(file_path)
        # Re-opening the file the canvas already shows must not throw the
        # workspace (and its undo history) away: the code editor and the block
        # editor hand the SAME file back and forth, and save_workspace re-reads
        # the head/tail from disk on every save anyway.
        if self._path == file_path:
            if self._dirty:
                self.save_now()  # pending (debounced) edits, nothing to reload
            return
        if self._dirty:
            # never lose the pending edits of the previous file
            self.save_now()
        self._path = file_path
        try:
            self._workspace = storage.load_workspace(file_path)
        except (OSError, ValueError):
            self._workspace = new_workspace()
        self._undo_stack = []
        self._redo_stack = []
        self._selected_ids = set()
        self._dirty = False
        self._hoist_nested_hats()
        self._absorb_touching_stacks()
        self.rebuild()
        self.variables_changed.emit()
        self.modified_changed.emit(False)

    def file_path(self):
        return self._path

    def clear_file(self):
        """Forget the current file (project closed or switched)."""
        self._save_timer.stop()
        self._dirty = False
        self._path = None
        self._workspace = new_workspace()
        self._undo_stack = []
        self._redo_stack = []
        self._selected_ids = set()
        self.rebuild()
        self.variables_changed.emit()
        self.modified_changed.emit(False)

    def retarget_file(self, file_path):
        """Point the canvas at a moved/renamed script, keeping the workspace.

        Used when the open script was renamed or moved on disk (asset panel
        or MCP move_file): the blocks stay, only the path changes - the
        debounced auto-save then writes the new location.
        """
        if self._path is None:
            return
        self._path = str(file_path)

    def workspace(self):
        return self._workspace

    def set_workspace(self, workspace):
        """Replace the whole workspace (tests / programmatic edits)."""
        self.push_undo()
        self._workspace = workspace
        self.rebuild()
        self.variables_changed.emit()
        self.schedule_save()

    def save_now(self):
        self._save_timer.stop()
        self._dirty = False
        if self._path is not None:
            storage.save_workspace(self._path, self._workspace)
            self.script_saved.emit(self._path)
        self.modified_changed.emit(False)

    def schedule_save(self):
        self._dirty = True
        self.modified_changed.emit(True)
        if self._path is not None:
            self._save_timer.start()

    def is_modified(self):
        return self._dirty

    # ------------------------------------------------------------ variables
    # The variables belong to the workspace: they are stored in the blocks
    # marker of the script and generated as ``self.<name> = <value>`` lines
    # in __init__ (see storage.save_workspace). Every block that reads or
    # writes a property offers them next to the object's own properties.
    def variables(self):
        """The script's custom variables (id, name, value), in order."""
        return list(self._workspace.get('variables') or [])

    def check_variable_name(self, name, ignore_id=None):
        """'' when the name may be used, else the i18n key of the problem."""
        name = str(name or '').strip()
        error = variable_name_error(name)
        if error:
            return error
        if any(item.get('name') == name and str(item.get('id')) != str(ignore_id)
               for item in self.variables()):
            return 'block.var.err_duplicate'
        return ''

    def add_variable(self, name, value='0', value_type='number'):
        """Add a variable. Returns (ok, i18n key of the problem)."""
        name = str(name or '').strip()
        error = self.check_variable_name(name)
        if error:
            return False, error
        self.push_undo()
        self._workspace.setdefault('variables', [])
        self._workspace['variables'].append(new_variable(name, value, value_type))
        self.rebuild()
        self.variables_changed.emit()
        self.schedule_save()
        return True, ''

    def update_variable(self, variable_id, name, value='0', value_type=None):
        """Change the name / type / initial value of a variable.

        Renaming repoints the blocks that used it, so nothing breaks. Returns
        (ok, i18n key of the problem).
        """
        variable = find_variable(self._workspace, variable_id)
        if variable is None:
            return False, 'block.var.err_missing'
        name = str(name or '').strip()
        error = self.check_variable_name(name, ignore_id=variable_id)
        if error:
            return False, error
        self.push_undo()
        old_name = str(variable.get('name') or '')
        variable['name'] = name
        variable['value'] = str(value if value is not None else '0')
        if value_type in VARIABLE_TYPES:
            variable['type'] = value_type
        if name != old_name:
            rewrite_variable_references(self._workspace, old_name, 'self.{}'.format(name))
        self.rebuild()
        self.variables_changed.emit()
        self.schedule_save()
        return True, ''

    def remove_variable(self, variable_id):
        """Delete a variable; blocks that used it fall back to the default property."""
        variable = find_variable(self._workspace, variable_id)
        if variable is None:
            return False
        self.push_undo()
        self._workspace['variables'] = [item for item in self.variables()
                                        if str(item.get('id')) != str(variable_id)]
        rewrite_variable_references(self._workspace, str(variable.get('name') or ''),
                                    PROPERTY_OPTIONS[0][0])
        self.rebuild()
        self.variables_changed.emit()
        self.schedule_save()
        return True

    # ------------------------------------------------------------ scene
    def rebuild(self):
        """Rebuild the whole scene from the workspace model."""
        self._drag = None
        normalize_workspace(self._workspace)
        self._scene.clear()
        self._drop_indicator = DropIndicator()
        self._scene.addItem(self._drop_indicator)
        self._drop_indicator.setVisible(False)

        self._items = []
        for stack in self._workspace.get('stacks', []):
            item = BlockItem(stack)
            item.setPos(float(stack.get('x', DEFAULT_X)), float(stack.get('y', DEFAULT_Y)))
            self._scene.addItem(item)
            self._items.append(item)
        self._apply_selection()
        self._collect_drop_targets()
        self._update_scene_rect()

    def _update_scene_rect(self):
        """A generous canvas so blocks can be parked far away from the stacks."""
        rect = QRectF(-SCENE_PADDING, -SCENE_PADDING, 2 * SCENE_PADDING, 2 * SCENE_PADDING)
        for item in self._items:
            rect = rect.united(item.sceneBoundingRect())
        self._scene.setSceneRect(rect.adjusted(-SCENE_PADDING, -SCENE_PADDING,
                                               SCENE_PADDING, SCENE_PADDING))

    def _collect_drop_targets(self):
        """Every gap inside a stack where a block can be attached.

        There are no “gaps” at the top level: a block dropped in free space
        simply stays where it was dropped (as its own loose stack).
        """
        targets = []
        for item in self._items:
            self._collect_body_targets(item, targets)
        self._drop_targets = targets

    @staticmethod
    def _collect_body_targets(item, targets):
        """Recursively collect the statement-list gaps of an item and its children."""
        for target_list, index, point in item.drop_gaps():
            targets.append((target_list, index, point))
        for child in item.childItems():
            if isinstance(child, BlockItem):
                BlockCanvas._collect_body_targets(child, targets)

    def _nearest_target(self, position, is_hat, max_distance=SNAP_DISTANCE):
        """The statement-list gap nearest to a position.

        Event blocks live on the top level only, so they never attach into a
        statement list (they align with whole stacks instead).
        """
        if is_hat:
            return None
        best = None
        best_distance = max_distance
        for target_list, index, point in self._drop_targets:
            delta = position - point
            distance = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            if distance < best_distance:
                best = (target_list, index, point)
                best_distance = distance
        return best

    def _top_level_snap(self, position, size, is_hat=False):
        """Align a top-level drop tightly above/below the nearest other stack.

        The distance is measured to the place the block WOULD land (its own
        size included), so the silhouette appears exactly when the block is
        already where it will end up - a tall event stack (which carries its
        whole body) snaps just as easily as a single row. Returns
        ``(point, item, above)`` of the nearest alignment, or None.

        Event blocks must never splice onto another event block, so when the
        dragged block is a hat, other hats are not candidates at all.
        """
        best = None
        best_distance = None
        for item in self._items:
            if is_hat:
                definition = get_definition(item.block().get('type'))
                if definition is not None and definition['shape'] == 'hat':
                    continue
            stack_pos = item.pos()
            for point, above in ((QPointF(stack_pos.x(), stack_pos.y() - size.height()), True),
                                 (QPointF(stack_pos.x(), stack_pos.y() + item.height()), False)):
                delta = position - point
                distance = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
                if distance < SNAP_DISTANCE and (best_distance is None or distance < best_distance):
                    best = (point, item, above)
                    best_distance = distance
        return best

    def _nearest_target_for(self, position, size, is_hat):
        """The gap the drag will land in, or None (free placement).

        Probes both the block's top-left corner and its centre so dropping a
        block visually “onto” another one snaps.
        """
        best = None
        best_distance = None
        for point in (position, QPointF(position.x() + size.width() * SNAP_PROBE_RATIO,
                                       position.y() + size.height() * SNAP_PROBE_RATIO)):
            target = self._nearest_target(point, is_hat)
            if target is None:
                continue
            delta = point - target[2]
            distance = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            if best_distance is None or distance < best_distance:
                best = target
                best_distance = distance
        return best

    # ------------------------------------------------------------ editing api
    def add_block(self, block_type, scene_position=None):
        """Add a new block (palette double-click / drop) at a position."""
        definition = get_definition(block_type)
        if definition is None:
            return None
        if scene_position is None:
            scene_position = self.mapToScene(self.viewport().rect().center())
        self.push_undo()
        is_hat = definition['shape'] == 'hat'
        if is_hat:
            block = new_stack(block_type, scene_position.x(), scene_position.y())
        else:
            block = new_block(block_type)
        target = self._nearest_target_for(scene_position, new_block_size(definition), is_hat)
        if target is not None:
            block.pop('x', None)
            block.pop('y', None)
            insert_block(block, target[0], target[1])
        else:
            aligned = self._top_level_snap(scene_position, new_block_size(definition), is_hat)
            position = aligned[0] if aligned is not None else scene_position
            block['x'] = int(position.x())
            block['y'] = int(position.y())
            self._workspace['stacks'].append(block)
        self.rebuild()
        self.schedule_save()
        return block

    def delete_block(self, block_id):
        """Delete the block (and its subtree) from the workspace.

        Deleting an EVENT block keeps the blocks stacked below it: they land
        on the canvas as a loose stack (``delete_stack`` is the other
        behaviour - throwing everything away together).
        """
        _, _, block = find_block(self._workspace['stacks'], block_id)
        if block is None:
            return
        self.push_undo()
        self._release_body(block)
        remove_segment(self._workspace['stacks'], block_id)
        self._selected_ids.discard(block_id)
        self.rebuild()
        self.schedule_save()

    def delete_selected(self):
        """Delete every selected block as ONE undo step.

        Event blocks keep the blocks below them (they become a loose stack);
        blocks that were selected explicitly are removed with it.
        """
        ids = self._topmost_ids(self._selected_ids)
        if not ids:
            return
        extras = set(self._selected_ids) - set(ids)
        self.push_undo()
        for block_id in ids:
            _, _, block = find_block(self._workspace['stacks'], block_id)
            if block is None:
                continue
            self._release_body(block)
            remove_segment(self._workspace['stacks'], block_id)
        for block_id in extras:
            _, _, block = find_block(self._workspace['stacks'], block_id)
            if block is not None:
                remove_segment(self._workspace['stacks'], block_id)
        self._selected_ids = set()
        self.rebuild()
        self.schedule_save()

    def delete_stack(self, block_id):
        """Delete a block TOGETHER with everything stacked below / inside it."""
        _, _, block = find_block(self._workspace['stacks'], block_id)
        if block is None:
            return
        self.push_undo()
        remove_segment(self._workspace['stacks'], block_id)
        self._selected_ids = {item for item in self._selected_ids
                              if find_block(self._workspace['stacks'], item)[2] is not None}
        self.rebuild()
        self.schedule_save()

    def detach_body(self, block_id):
        """Move an event block's body blocks out to a loose stack below it."""
        _, _, block = find_block(self._workspace['stacks'], block_id)
        if block is None or not self._is_hat(block) or not block.get('body'):
            return False
        self.push_undo()
        self._release_body(block)
        self.rebuild()
        self.schedule_save()
        return True

    def copy_selected(self):
        """Copy the selected blocks (exactly as configured) to the clipboard."""
        blocks = []
        for block_id in self._topmost_ids(self._selected_ids):
            _, _, block = find_block(self._workspace['stacks'], block_id)
            if block is not None:
                blocks.append(json.loads(json.dumps(block, ensure_ascii=False)))
        if not blocks:
            return False
        self._clipboard = blocks
        return True

    def paste_blocks(self):
        """Paste the clipboard as new loose blocks (fresh ids, exact copy)."""
        if not self._clipboard:
            return []
        self.push_undo()
        center = self.mapToScene(self.viewport().rect().center())
        pasted = []
        for index, block in enumerate(self._clipboard):
            clone = clone_block(block)
            clone['x'] = int(center.x()) + 30 * index
            clone['y'] = int(center.y()) + 30 * index
            self._workspace['stacks'].append(clone)
            pasted.append(clone)
        self.rebuild()
        self._selected_ids = {block['id'] for block in pasted}
        self._apply_selection()
        self.schedule_save()
        return pasted

    @staticmethod
    def _is_hat(block):
        definition = get_definition(block.get('type'))
        return definition is not None and definition['shape'] == 'hat'

    def _release_body(self, block):
        """Re-home an event block's body as a loose stack right below it.

        The body of a control block (if / repeat / ...) is its content and is
        left alone; only event blocks give the blocks below them back.
        """
        children = block.get('body')
        if not children or not self._is_hat(block):
            return
        block['body'] = []
        x = int(block.get('x', DEFAULT_X))
        y = int(block.get('y', DEFAULT_Y)) + int(BlockItem(block).height()) + HOIST_GAP
        for child in children:
            child['x'] = x
            child['y'] = y
            y += int(BlockItem(child).height())
            self._workspace['stacks'].append(child)

    def duplicate_block(self, block_id):
        """Duplicate a block right behind its original."""
        parent_list, index, block = find_block(self._workspace['stacks'], block_id)
        if block is None:
            return None
        self.push_undo()
        clone = clone_block(block)
        if 'x' in block:
            clone['x'] = int(block['x']) + 26
            clone['y'] = int(block['y']) + 26
            self._workspace['stacks'].append(clone)
        else:
            insert_block(clone, parent_list, index + 1)
        self.rebuild()
        self.schedule_save()
        return clone

    def duplicate_selected(self):
        """Duplicate every selected block (the copies become the selection)."""
        ids = self._topmost_ids(self._selected_ids)
        if not ids:
            return []
        self.push_undo()
        clones = []
        for block_id in ids:
            parent_list, index, block = find_block(self._workspace['stacks'], block_id)
            if block is None:
                continue
            clone = clone_block(block)
            if 'x' in block:
                # a loose / top-level stack is offset so the copy is visible
                clone['x'] = int(block['x']) + 26
                clone['y'] = int(block['y']) + 26
                self._workspace['stacks'].append(clone)
            else:
                insert_block(clone, parent_list, index + 1)
            clones.append(clone)
        self.rebuild()
        self._selected_ids = {clone['id'] for clone in clones}
        self._apply_selection()
        self.schedule_save()
        return clones

    def set_field(self, block_id, field_name, value):
        """Change one field of a block (used by clicks and by tests)."""
        _, _, block = find_block(self._workspace['stacks'], block_id)
        if block is None:
            return
        self.push_undo()
        block.setdefault('fields', {})[field_name] = value
        self.rebuild()
        self.schedule_save()

    def move_block(self, block_id, target_list, index):
        """Move a block (with its subtree) to a statement list position."""
        _, _, block = find_block(self._workspace['stacks'], block_id)
        if block is None:
            return
        self.push_undo()
        remove_segment(self._workspace['stacks'], block_id)
        insert_block(block, target_list, index)
        self.rebuild()
        self.schedule_save()

    # ------------------------------------------------------------ undo
    def push_undo(self):
        self._undo_stack.append(json.dumps(self._workspace, ensure_ascii=False))
        if len(self._undo_stack) > UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._redo_stack = []

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(json.dumps(self._workspace, ensure_ascii=False))
        self._restore(self._undo_stack.pop())
        self.rebuild()
        self.variables_changed.emit()
        self.schedule_save()

    def redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(json.dumps(self._workspace, ensure_ascii=False))
        self._restore(self._redo_stack.pop())
        self.rebuild()
        self.variables_changed.emit()
        self.schedule_save()

    def _restore(self, snapshot):
        """Restore a snapshot in place so ``workspace()`` keeps its identity."""
        restored = json.loads(snapshot)
        self._workspace.clear()
        self._workspace.update(restored)

    # ------------------------------------------------------------ theme
    def apply_theme(self, is_dark):
        self._is_dark = is_dark
        self._scene.setBackgroundBrush(QColor('#2e2e2e' if is_dark else '#f0f0f0'))
        self.viewport().update()

    def drawBackground(self, painter, rect):
        """A light two-level grid so blocks can be aligned by eye."""
        super().drawBackground(painter, rect)
        dark = self._is_dark in (True, None)
        minor_color = QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 22)
        major_color = QColor(255, 255, 255, 42) if dark else QColor(0, 0, 0, 42)
        for color, step in ((minor_color, GRID_MINOR), (major_color, GRID_MAJOR)):
            painter.setPen(QPen(color, 1.0))
            x = int(rect.left()) - (int(rect.left()) % step)
            while x < rect.right():
                if step == GRID_MINOR or x % GRID_MAJOR == 0:
                    painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += step
            y = int(rect.top()) - (int(rect.top()) % step)
            while y < rect.bottom():
                if step == GRID_MINOR or y % GRID_MAJOR == 0:
                    painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += step

    # ------------------------------------------------------------ zoom
    def zoom_in(self):
        self._zoom_by(BUTTON_ZOOM_FACTOR)

    def zoom_out(self):
        self._zoom_by(1 / BUTTON_ZOOM_FACTOR)

    def zoom_scale(self):
        return self._scale

    def _zoom_by(self, factor):
        new_scale = min(max(self._scale * factor, MIN_SCALE), MAX_SCALE)
        if abs(new_scale - self._scale) < 1e-9:
            return
        factor = new_scale / self._scale
        self._scale = new_scale
        self.scale(factor, factor)

    # ------------------------------------------------------------ mouse
    def wheelEvent(self, event):
        self._zoom_by(WHEEL_ZOOM_FACTOR if event.angleDelta().y() > 0 else 1 / WHEEL_ZOOM_FACTOR)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            item = self._block_item_at(event.position().toPoint())
            if item is not None:
                # A field (or the event label) only opens its picker when the
                # button is RELEASED without moving - pressing must stay a drag
                # start, otherwise the event block could never be moved.
                local = item.mapFromScene(self.mapToScene(event.position().toPoint()))
                self._pending_field = (item, item.field_at(local))
                self._press_item = item
                self._press_position = event.position().toPoint()
                self._select(item.block()['id'])
                event.accept()
                return
            self._press_item = None
            self._pending_field = None
            # pressing the empty canvas clears the selection and starts the
            # rubber band (drag a box over several blocks to select them)
            self._select(None)
            self._start_band(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._pan_origin = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._band_origin is not None:
            self._update_band(event.position().toPoint())
            event.accept()
            return
        if self._drag is None and self._press_item is not None:
            travel = (event.position().toPoint() - self._press_position).manhattanLength()
            if travel >= DRAG_THRESHOLD:
                item = self._press_item
                press_position = self._press_position
                self._press_item = None
                self._pending_field = None
                self._begin_drag(item, press_position)
        if self._drag is not None:
            scene_position = self.mapToScene(event.position().toPoint())
            self._drag['group'].setPos(scene_position - self._drag['offset'])
            self._update_drop_indicator()
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._band_origin is not None:
                self._finish_band()
                event.accept()
                return
            if self._drag is not None:
                self._finish_drag()
                event.accept()
                return
            if self._pending_field is not None:
                item, field_name = self._pending_field
                self._pending_field = None
                self._press_item = None
                if field_name is not None:
                    self._edit_field(item, field_name)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------ selection
    def selected_ids(self):
        """The ids of the selected blocks (a copy - mutate via the methods)."""
        return set(self._selected_ids)

    def _select(self, block_id):
        """Select exactly one item (or clear the whole selection)."""
        self._set_selection([block_id] if block_id else [])

    def _set_selection(self, block_ids):
        """Select exactly the given blocks.

        A click picks the one block under the cursor; a rubber band picks
        every block it covers (rows of a stack included).
        """
        self._selected_ids = {block_id for block_id in block_ids if block_id}
        self._apply_selection()

    def _apply_selection(self):
        """Push the selection state onto every item (no rebuild).

        The dashed frame shows exactly what the user selected: clicking one
        block marks that block, a rubber band marks every block it covers.
        """
        selected = self._selected_ids

        def apply(item):
            item.setSelected(item.block()['id'] in selected)
            for child in item.childItems():
                if isinstance(child, BlockItem):
                    apply(child)

        for item in self._items:
            apply(item)

    def _topmost_ids(self, block_ids):
        """Drop the ids that live inside another selected block.

        A parent already carries its whole subtree (delete / duplicate), so
        selecting both would do the same work twice. Document order is kept.
        """
        selected = set(block_ids)
        result = []

        def walk(blocks, inside_selection):
            for block in blocks:
                is_selected = block.get('id') in selected
                if is_selected and not inside_selection:
                    result.append(block['id'])
                for _key, children in block_children(block):
                    walk(children, inside_selection or is_selected)

        walk(self._workspace.get('stacks', []), False)
        return result

    # ------------------------------------------------------------ rubber band
    def _start_band(self, view_position):
        self._band_origin = view_position
        self._band_last_rect = None
        self._rubber_band.setGeometry(QRect(view_position, QSize()))
        self._rubber_band.show()

    def _update_band(self, view_position):
        rect = QRect(self._band_origin, view_position).normalized()
        if rect == self._band_last_rect:
            return
        self._band_last_rect = rect
        self._rubber_band.setGeometry(rect)
        # The band is a child widget painted ON TOP of the viewport and the
        # selection outlines are dashed - a partial repaint leaves ghost lines
        # behind when the band jumps, so repaint the whole viewport.
        self.viewport().update()
        self._set_selection(self._band_ids(rect))

    def _finish_band(self):
        self._rubber_band.hide()
        self._band_origin = None
        self._band_last_rect = None
        self.viewport().update()

    def _band_ids(self, view_rect):
        """The ids of the blocks the band really touches (shapes, not boxes).

        A control block's shape does NOT cover the inside of its mouth, so a
        band inside an if body picks those rows while a band over the whole
        stack selects the stack itself (see _topmost_ids).
        """
        scene_rect = self.mapToScene(view_rect).boundingRect()
        found = []
        for candidate in self._scene.items(scene_rect, Qt.ItemSelectionMode.IntersectsItemShape):
            if isinstance(candidate, BlockItem):
                found.append(candidate.block()['id'])
        return found

    def _block_item_at(self, view_position):
        item = self.itemAt(view_position)
        while item is not None:
            if isinstance(item, BlockItem):
                return item
            item = item.parentItem()
        return None

    # ------------------------------------------------------------ field editing
    def _edit_field(self, item, field_name):
        definition = item.definition()
        spec = field_spec(definition, field_name)
        if spec is None:
            return
        value = self._choose_field_value(item, spec)
        if value is None:
            return
        self.push_undo()
        item.block().setdefault('fields', {})[field_name] = value
        self.rebuild()
        self.schedule_save()

    def _choose_field_value(self, item, spec):
        """Ask the user for a new field value (dropdown menu or text dialog)."""
        current = field_value(item.block(), item.definition(), spec['name'])
        variables = self.variables()
        if spec['kind'] == 'amount':
            return self._choose_amount(current)
        if spec['kind'] in OPTION_FIELD_KINDS and options_for(spec['kind'], variables):
            menu = QMenu(self)
            # Long lists (the key picker has the whole keyboard) stay usable:
            # Qt keeps the menu inside the screen and scrolls it.
            menu.setStyleSheet('QMenu { menu-scrollable: 1; }')
            for option in options_for(spec['kind'], variables):
                action = menu.addAction(option_text(option))
                action.setCheckable(True)
                action.setChecked(option[0] == current)
                action.setData(option[0])
                if option[0] == current:
                    menu.setActiveAction(action)
            chosen = menu.exec(QCursor.pos())
            return chosen.data() if chosen is not None else None
        text, accepted = QInputDialog.getText(
            self, T.tr('block.edit_field', 'Edit field'),
            T.tr('block.edit_field_value', 'Value:'), text=str(current))
        return text if accepted else None

    def _choose_amount(self, current):
        """A number, or one of the script's number variables (change-by blocks)."""
        menu = QMenu(self)
        menu.setStyleSheet('QMenu { menu-scrollable: 1; }')
        custom_action = menu.addAction(T.tr('block.amount.custom', 'Custom number...'))
        variable_actions = {}
        options = options_for('amount', self.variables())
        if options:
            menu.addSeparator()
            for option in options:
                action = menu.addAction(option_text(option))
                action.setCheckable(True)
                action.setChecked(option[0] == str(current))
                variable_actions[action] = option[0]
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return None
        if chosen in variable_actions:
            return variable_actions[chosen]
        if chosen is not custom_action:
            return None
        text = str(current)
        while True:
            text, accepted = QInputDialog.getText(
                self, T.tr('block.edit_field', 'Edit field'),
                T.tr('block.amount.prompt', 'Number:'), text=text)
            if not accepted:
                return None
            text = str(text).strip()
            try:
                float(text)
            except ValueError:
                QMessageBox.warning(self, T.tr('block.edit_field', 'Edit field'),
                                    T.tr('block.amount.invalid', 'Please enter a number.'))
                continue
            return text

    # ------------------------------------------------------------ drag
    def _begin_drag(self, item, view_position):
        definition = item.definition()
        block = item.block()
        parent_list, index, _ = find_block(self._workspace['stacks'], block['id'])
        if parent_list is None:
            return
        is_hat = bool(definition and definition['shape'] == 'hat')
        self._redo_before_drag = list(self._redo_stack)
        self.push_undo()
        self._press_position = view_position
        # The grab offset is where the cursor actually holds the block: pressing
        # the far right of a wide block must not teleport it to the left.
        press_scene = self.mapToScene(view_position)
        offset = press_scene - item.mapToScene(QPointF(0.0, 0.0))
        del parent_list[index]
        self.rebuild()

        group = QGraphicsItemGroup()
        self._scene.addItem(group)
        drag_item = BlockItem(block)
        self._scene.addItem(drag_item)
        group.addToGroup(drag_item)
        drag_item.setPos(0, 0)
        drag_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        group.setOpacity(0.85)
        group.setZValue(999)

        group.setPos(press_scene - offset)
        self._drag = {
            'group': group,
            'block': block,
            'is_hat': is_hat,
            'size': QSizeF(drag_item.width(), drag_item.height()),
            'origin_list': parent_list,
            'origin_index': index,
            'offset': offset,
            'start_pos': QPointF(group.pos()),
        }
        self._update_drop_indicator()

    def _update_drop_indicator(self):
        drag = self._drag
        target = self._nearest_target_for(drag['group'].pos(), drag['size'], drag['is_hat'])
        rect = None
        if target is not None:
            gap = target[2]
            rect = QRectF(gap.x(), gap.y(), drag['size'].width(), drag['size'].height())
        else:
            aligned = self._top_level_snap(drag['group'].pos(), drag['size'], drag['is_hat'])
            if aligned is not None:
                point = aligned[0]
                rect = QRectF(point.x(), point.y(), drag['size'].width(), drag['size'].height())
        if rect is None or rect.isNull():
            self._drop_indicator.setVisible(False)
            return
        self._drop_indicator.set_target(rect)
        self._drop_indicator.setVisible(True)

    def _finish_drag(self):
        drag = self._drag
        self._drag = None
        if drag is None:
            return
        group = drag['group']
        drop_point = QPointF(group.pos())
        self._scene.removeItem(group)
        moved = (drop_point - drag['start_pos']).manhattanLength() > DRAG_THRESHOLD
        target = self._nearest_target_for(drop_point, drag['size'], drag['is_hat'])
        self._drop_indicator.setVisible(False)
        if target is None:
            if not moved:
                # a plain click: put it back exactly where it was, without
                # polluting the undo stack / dirty flag
                self._undo_stack.pop()
                self._redo_stack = self._redo_before_drag
                insert_block(drag['block'], drag['origin_list'], drag['origin_index'])
                self.rebuild()
                return
            # dropped in free space: it stays there (aligned with a stack when
            # it was released right next to / on top of one)
            aligned = self._top_level_snap(drop_point, drag['size'], drag['is_hat'])
            if aligned is not None:
                position, stack_item, above = aligned
                stack_definition = get_definition(stack_item.block().get('type'))
                if (drag['is_hat'] and above and stack_definition is not None
                        and stack_definition['shape'] != 'hat'):
                    # the event block PICKS UP the stack it was dropped on: the
                    # blocks become its body, so they really sit under the
                    # event (same width, they move together, the generator
                    # emits them) - instead of two stacks parked side by side.
                    # NEVER another event block: event-on-event is not a thing.
                    self._absorb_stack(drag['block'], stack_item)
                drag['block']['x'] = int(position.x())
                drag['block']['y'] = int(position.y())
            else:
                drag['block']['x'] = int(drop_point.x())
                drag['block']['y'] = int(drop_point.y())
            self._workspace['stacks'].append(drag['block'])
            # dropping an event block on a loose stack picks up that stack;
            # the blocks still touching its new bottom (an otherwise separate
            # chain parked below) fold in as well, so one drag carries ALL of
            # them instead of one more row per drag.
            self._absorb_touching_stacks()
            self.rebuild()
            self.schedule_save()
            return
        insert_block(drag['block'], target[0], target[1])
        drag['block'].pop('x', None)
        drag['block'].pop('y', None)
        self.rebuild()
        self.schedule_save()

    def _absorb_stack(self, block, stack_item):
        """Move a top-level stack into a block's body (dropped on top of it)."""
        stack_block = stack_item.block()
        stacks = self._workspace['stacks']
        for index, candidate in enumerate(stacks):
            if candidate is stack_block:
                del stacks[index]
                break
        stack_block.pop('x', None)
        stack_block.pop('y', None)
        block.setdefault('body', []).append(stack_block)

    def _hoist_nested_hats(self):
        """Event blocks live on the top level: pull any nested one out again.

        Only files written before this invariant (or the previous round's
        absorb) can contain a hat inside another block. An event block is an
        independent callback, so it gets its own top-level stack back at the
        position it had on screen, with a small gap so it does not look
        spliced onto what it came from.
        """
        while True:
            entry = None
            for stack in list(self._workspace.get('stacks', [])):
                item = BlockItem(stack)
                nested_item = self._first_nested_hat_item(item)
                if nested_item is None:
                    continue
                offset = QPointF(0.0, 0.0)
                current = nested_item
                while current is not None and current is not item:
                    offset += current.pos()
                    current = current.parentItem()
                entry = (stack, nested_item.block(), offset)
                break
            if entry is None:
                return
            stack, block, offset = entry
            parent_list, index, _ = find_block(self._workspace['stacks'], block['id'])
            if parent_list is None or parent_list is self._workspace['stacks']:
                return
            del parent_list[index]
            block['x'] = int(float(stack.get('x', DEFAULT_X)) + offset.x())
            block['y'] = int(float(stack.get('y', DEFAULT_Y)) + offset.y()) + HOIST_GAP
            self._workspace['stacks'].append(block)

    @staticmethod
    def _first_nested_hat_item(item):
        """The first event block living INSIDE this item, or None."""
        for child in item.childItems():
            if not isinstance(child, BlockItem):
                continue
            definition = get_definition(child.block().get('type'))
            if definition is not None and definition['shape'] == 'hat':
                return child
            found = BlockCanvas._first_nested_hat_item(child)
            if found is not None:
                return found
        return None

    def _absorb_touching_stacks(self):
        """Fold “parked right below a hat” stacks into the event's body.

        A dropped event block parks its pickup as its own top-level stack when
        the two only TOUCH, so the blocks never became the event's body.
        Exactly touching, same-x pairs are folded together when the file is
        opened and after every drop, so a whole detached chain comes back in
        one go instead of one row per drag.
        """
        stacks = self._workspace.get('stacks', [])
        changed = True
        while changed:
            changed = False
            for hat in list(stacks):
                definition = get_definition(hat.get('type'))
                if definition is None or definition['shape'] != 'hat':
                    continue
                hat_x = float(hat.get('x', DEFAULT_X))
                bottom = float(hat.get('y', DEFAULT_Y)) + BlockItem(hat).height()
                for candidate in list(stacks):
                    if candidate is hat:
                        continue
                    candidate_definition = get_definition(candidate.get('type'))
                    if (candidate_definition is not None
                            and candidate_definition['shape'] == 'hat'):
                        # events never splice onto each other
                        continue
                    if abs(float(candidate.get('x', DEFAULT_X)) - hat_x) > 0.5:
                        continue
                    if abs(float(candidate.get('y', DEFAULT_Y)) - bottom) > 0.5:
                        continue
                    for index, other in enumerate(stacks):
                        if other is candidate:
                            del stacks[index]
                            break
                    candidate.pop('x', None)
                    candidate.pop('y', None)
                    hat.setdefault('body', []).append(candidate)
                    changed = True
                    break
                if changed:
                    break

    # ------------------------------------------------------------ drag & drop (palette)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        """Swallow the leave of a palette drag.

        ``dragEnterEvent`` accepts the palette drag itself instead of handing
        it to the scene (no item accepts drops - the drop is handled at view
        level), so the base implementation would log “drag leave received
        before drag enter”. There is nothing to clean up here: the drop
        indicator only belongs to the canvas' own block dragging, which never
        uses Qt drag & drop.
        """
        event.accept()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(BLOCK_MIME):
            super().dropEvent(event)
            return
        block_type = bytes(event.mimeData().data(BLOCK_MIME)).decode('utf-8')
        position = self.mapToScene(event.position().toPoint())
        self.add_block(block_type, position)
        event.acceptProposedAction()

    # ------------------------------------------------------------ keyboard / menu
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self._selected_ids:
            self.delete_selected()
            event.accept()
            return
        if (event.key() == Qt.Key.Key_D
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and self._selected_ids):
            self.duplicate_selected()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Copy) and self._selected_ids:
            self.copy_selected()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Paste) and self._clipboard:
            self.paste_blocks()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        item = self._block_item_at(event.pos())
        menu = QMenu(self)
        if item is not None:
            # right-clicking a block keeps an existing multi-selection (the
            # actions then apply to every selected block); right-clicking an
            # unselected block selects it first.
            if item.block()['id'] not in self._selected_ids:
                self._select(item.block()['id'])
            delete_action = menu.addAction(T.tr('block.delete', 'Delete block'))
            duplicate_action = menu.addAction(T.tr('block.duplicate', 'Duplicate block'))
            copy_action = menu.addAction(T.tr('block.copy', 'Copy block'))
            detach_action = delete_stack_action = None
            definition = get_definition(item.block().get('type'))
            if (definition is not None and definition['shape'] == 'hat'
                    and item.block().get('body')):
                # an event block owns what is stacked below it: offer to split
                # the two apart, and to throw everything away in one go
                detach_action = menu.addAction(T.tr('block.detach', 'Detach the blocks below'))
                delete_stack_action = menu.addAction(
                    T.tr('block.delete_stack', 'Delete the whole stack'))
            chosen = menu.exec(event.globalPos())
            if chosen == delete_action:
                self.delete_selected()
            elif chosen == duplicate_action:
                self.duplicate_selected()
            elif chosen == copy_action:
                self.copy_selected()
            elif detach_action is not None and chosen is detach_action:
                self.detach_body(item.block()['id'])
            elif delete_stack_action is not None and chosen is delete_stack_action:
                self.delete_stack(item.block()['id'])
            return
        menu.addAction(T.tr('block.nothing_here', 'No block here')).setEnabled(False)
        if self._clipboard:
            paste_action = menu.addAction(T.tr('block.paste', 'Paste'))
            if menu.exec(event.globalPos()) == paste_action:
                self.paste_blocks()
            return
        menu.exec(event.globalPos())
