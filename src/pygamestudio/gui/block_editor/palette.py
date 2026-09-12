"""
The block palette: each entry is drawn as a small block shape (Scratch style),
grouped by category, draggable onto the canvas.
"""

from PySide6.QtCore import QMimeData, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QDrag, QFont, QFontMetrics, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QListWidget, QListWidgetItem,
                               QStyle, QStyledItemDelegate, QTabWidget, QVBoxLayout, QWidget)

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.block_editor.canvas import BLOCK_MIME
from pygamestudio.gui.block_editor.registry import (CATEGORIES, category_text, definitions_by_category,
                                                    get_category, get_definition, label_text,
                                                    object_groups, object_text)

BLOCK_TYPE_ROLE = Qt.ItemDataRole.UserRole
IS_CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 1
COLOR_ROLE = Qt.ItemDataRole.UserRole + 2
IS_OBJECT_ROLE = Qt.ItemDataRole.UserRole + 3
GROUPED_ROLE = Qt.ItemDataRole.UserRole + 4

BLOCK_HEIGHT = 26.0
BLOCK_ROW_HEIGHT = 32
CATEGORY_ROW_HEIGHT = 28
OBJECT_ROW_HEIGHT = 26
BLOCK_RADIUS = 6.0


def paint_block_shape(painter, rect, color, label, font, arrow=False):
    """Draw one block: a rounded body with its label (same look as the canvas)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    outline = color.darker(140)

    path = QPainterPath()
    path.addRoundedRect(rect, BLOCK_RADIUS, BLOCK_RADIUS)
    painter.setPen(QPen(outline, 1.2))
    painter.setBrush(color)
    painter.drawPath(path)

    painter.setPen(QColor('#ffffff'))
    painter.setFont(font)
    metrics = QFontMetrics(font)
    text_rect = QRectF(rect.left() + 10, rect.top(), rect.width() - (28 if arrow else 16), rect.height())
    elided = metrics.elidedText(label, Qt.TextElideMode.ElideRight, max(int(text_rect.width()), 10))
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
    if arrow:
        x = rect.left() + 10 + metrics.horizontalAdvance(elided) + 6
        y = rect.center().y()
        painter.drawLine(x - 3, y - 2, x + 1, y + 2)
        painter.drawLine(x + 1, y + 2, x + 5, y - 2)
    painter.restore()


class BlockPalette(QWidget):
    """Left-hand toolbox: one tab per category (events / actions / control).

    The event and action tabs list their blocks under the object type they
    belong to (collapsed until the user opens one).
    """

    add_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs = QTabWidget()
        self._expanded = set()
        self._lists = []
        self._set_up()

    def _set_up(self):
        self._tabs.setObjectName('blockPaletteTabs')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tabs)
        for category in CATEGORIES:
            block_list = _BlockList(category['key'], self._expanded)
            block_list.add_requested.connect(self.add_requested)
            block_list.group_toggled.connect(self._rebuild)
            self._tabs.addTab(block_list, '')
            self._lists.append(block_list)
        self.retranslate()

    def retranslate(self):
        for index, category in enumerate(CATEGORIES):
            self._tabs.setTabText(index, category_text(category))
        self._rebuild()

    def apply_theme(self, is_dark):
        for block_list in self._lists:
            block_list.apply_theme(is_dark)

    def _rebuild(self):
        """Refresh every tab (an object group is shared between two of them)."""
        for block_list in self._lists:
            block_list.populate()


class _BlockList(QListWidget):
    """One category of blocks; events and actions are grouped by object.

    The object groups start collapsed; the “expanded” set is shared by every
    list, so opening 矩形 in the events tab opens it in the actions tab too.
    """

    add_requested = Signal(str)
    group_toggled = Signal()

    GROUPED_CATEGORIES = ('event', 'action')

    def __init__(self, category_key, expanded=None, parent=None):
        super().__init__(parent)
        self.setObjectName('blockPaletteList')
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(BlockPaletteDelegate(self))
        self.setSpacing(1)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.itemClicked.connect(self._on_item_clicked)
        self._category_key = category_key
        self._expanded = expanded if expanded is not None else set()
        self.populate()

    def apply_theme(self, is_dark):
        self.itemDelegate().set_dark(is_dark)
        self.viewport().update()

    def populate(self):
        """Rebuild this tab: object groups (collapsed) or a flat block list."""
        scroll = self.verticalScrollBar().value()
        self.clear()
        category = get_category(self._category_key)
        if self._category_key in self.GROUPED_CATEGORIES:
            for obj, members in object_groups(self._category_key):
                expanded = obj['key'] in self._expanded
                group = QListWidgetItem()
                group.setData(IS_CATEGORY_ROLE, False)
                group.setData(IS_OBJECT_ROLE, obj['key'])
                group.setData(GROUPED_ROLE, expanded)
                group.setData(COLOR_ROLE, category['color'])
                group.setText(object_text(obj))
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                group.setSizeHint(QSize(10, OBJECT_ROW_HEIGHT))
                self.addItem(group)
                if expanded:
                    for definition in members:
                        self._add_block_item(definition, category, grouped=True)
        else:
            for definition in definitions_by_category(self._category_key):
                self._add_block_item(definition, category, grouped=False)
        self.verticalScrollBar().setValue(scroll)

    def _add_block_item(self, definition, category, grouped):
        item = QListWidgetItem()
        item.setData(BLOCK_TYPE_ROLE, definition['type'])
        item.setData(IS_CATEGORY_ROLE, False)
        item.setData(IS_OBJECT_ROLE, '')
        item.setData(GROUPED_ROLE, grouped)
        item.setData(COLOR_ROLE, category['color'])
        item.setText(label_text(definition, None))
        item.setSizeHint(QSize(10, BLOCK_ROW_HEIGHT))
        self.addItem(item)

    def _on_item_clicked(self, item):
        """Clicking an object row opens / closes it in every tab."""
        object_key = item.data(IS_OBJECT_ROLE) if item is not None else None
        if not object_key:
            return
        if object_key in self._expanded:
            self._expanded.discard(object_key)
        else:
            self._expanded.add(object_key)
        self.group_toggled.emit()

    def _on_item_double_clicked(self, item):
        block_type = item.data(BLOCK_TYPE_ROLE) if item is not None else None
        if block_type:
            self.add_requested.emit(block_type)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        block_type = item.data(BLOCK_TYPE_ROLE) if item is not None else None
        if not block_type:
            return
        mime_data = QMimeData()
        mime_data.setData(BLOCK_MIME, block_type.encode('utf-8'))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.setPixmap(self.drag_pixmap(block_type))
        drag.exec(Qt.DropAction.CopyAction)

    def drag_pixmap(self, block_type):
        """A full-size preview of a block, used as the drag cursor."""
        definition = get_definition(block_type)
        label = label_text(definition, None)
        font = QFont(self.font())
        font.setBold(definition['shape'] == 'hat')
        width = QFontMetrics(font).horizontalAdvance(label) + 44
        pixmap = QPixmap(width, int(BLOCK_HEIGHT) + 2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        color = QColor(get_category(definition['category'])['color'])
        paint_block_shape(painter, QRectF(0, 1, width - 1, BLOCK_HEIGHT), color, label, font,
                          arrow=bool(definition.get('label_from_field')))
        painter.end()
        return pixmap


class BlockPaletteDelegate(QStyledItemDelegate):
    """Paints category headers, object rows and blocks as shapes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = True

    def set_dark(self, is_dark):
        self._is_dark = is_dark

    def sizeHint(self, option, index):
        return QSize(10, CATEGORY_ROW_HEIGHT if index.data(IS_CATEGORY_ROLE) else BLOCK_ROW_HEIGHT)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(index.data(COLOR_ROLE) or '#4c97ff')
        rect = QRectF(option.rect)
        object_key = index.data(IS_OBJECT_ROLE)
        if index.data(IS_CATEGORY_ROLE):
            self._paint_category(painter, rect, color, index.data(Qt.ItemDataRole.DisplayRole))
        elif object_key:
            self._paint_object(painter, rect, option, index)
        else:
            self._paint_block(painter, rect, color, index, option)
        painter.restore()

    @staticmethod
    def _paint_category(painter, rect, color, text):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(rect.left() + 2, rect.center().y() - 6, 12, 12), 3, 3)
        font = QFont(painter.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color.lighter(135))
        painter.drawText(QRectF(rect.left() + 20, rect.top(), rect.width() - 24, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, str(text))

    def _paint_object(self, painter, rect, option, index):
        """An object group row: an expand arrow plus the object's name."""
        # NOTE: only the QStyle enum flags may be used here - combining the
        # state with a raw int (or converting it) crashes PySide6 6.10.
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 26) if self._is_dark else QColor(0, 0, 0, 20))
            painter.drawRoundedRect(rect.adjusted(2, 1, -2, -1), 6, 6)
        text_color = QColor('#d0d0d0') if self._is_dark else QColor('#3b3b3b')
        centre = rect.center().y()
        x = rect.left() + 16
        painter.setPen(Qt.PenStyle.NoPen)
        arrow = QColor(text_color)
        arrow.setAlpha(170)
        painter.setBrush(arrow)
        path = QPainterPath()
        if index.data(GROUPED_ROLE):
            path.moveTo(x, centre - 2)
            path.lineTo(x + 8, centre - 2)
            path.lineTo(x + 4, centre + 3)
        else:
            path.moveTo(x + 1, centre - 4)
            path.lineTo(x + 6, centre)
            path.lineTo(x + 1, centre + 4)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(text_color)
        font = QFont(painter.font())
        painter.setFont(font)
        painter.drawText(QRectF(rect.left() + 30, rect.top(), rect.width() - 34, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         str(index.data(Qt.ItemDataRole.DisplayRole) or ''))

    @staticmethod
    def _paint_block(painter, rect, color, index, option):
        # NOTE: only the QStyle enum flags may be used here - combining the
        # state with a raw int (or converting it) crashes PySide6 6.10.
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        label = str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        font = QFont(painter.font())
        width = QFontMetrics(font).horizontalAdvance(label) + 38
        width = min(width, max(rect.width() - 24, 60))
        left = rect.left() + (12 if index.data(GROUPED_ROLE) else 4)
        shape = QRectF(left, rect.top() + 3, width, BLOCK_HEIGHT)
        if hovered or selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 46 if selected else 26))
            painter.drawRoundedRect(shape.adjusted(-3, -3, 3, 3), 8, 8)
        paint_block_shape(painter, shape, color, label, font)


def _palette_icon(color):
    """A small colour square (kept for other panels that need an icon)."""
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(1, 1, 12, 12, 4, 4)
    painter.end()
    return QIcon(pixmap)
