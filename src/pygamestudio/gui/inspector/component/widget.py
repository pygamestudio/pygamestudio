from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.inspector.component.spinbox import SuffixSpinBox


class PolygonPointsWidget(QWidget):
    """Widget for a polygon's vertex list.

    A vertex-count spin box on top, followed by one X/Y spin box pair per
    vertex, each labelled with its index (0, 1, 2, ...). Raising/lowering the
    count appends/removes trailing pairs, and any coordinate edit immediately
    pushes the new vertex list so the polygon is redrawn in real time.

    The widget has its own objectName so the theme QSS (dark.qss / light.qss)
    paints its background to match the inspector container.
    """

    def __init__(self, inspector_container, points='', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._points = list(points) if isinstance(points, (list, tuple)) else []
        self._pairs = []
        self._set_up()

    def _set_up(self):
        self.setObjectName('polygonPointsWidget')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._count_spinbox = SuffixSpinBox()
        self._count_spinbox.setRange(0, 64)
        self._count_spinbox.setSingleStep(1)
        self._count_spinbox.setDecimals(0)
        self._count_spinbox.setValue(len(self._points))
        self._count_spinbox.valueChanged.connect(self._on_count_changed)
        self._layout.addWidget(self._count_spinbox)

        self._pairs_widget = QWidget()
        self._pairs_widget.setObjectName('polygonPointsWidgetPairs')
        self._pairs_layout = QVBoxLayout(self._pairs_widget)
        self._pairs_layout.setContentsMargins(0, 0, 0, 0)
        self._pairs_layout.setSpacing(2)
        self._layout.addWidget(self._pairs_widget)

        self._rebuild_pairs()

    def _create_pair_row(self, index):
        """Build one row: [index label] [X spin box] [Y spin box]."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        index_label = QLabel(f'[{index}]')
        index_label.setFixedWidth(20)
        index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        x_spinbox = SuffixSpinBox()
        x_spinbox.setRange(-999999, 999999)
        x_spinbox.setSingleStep(1)
        x_spinbox.setDecimals(0)
        x_spinbox.set_suffix('X')

        y_spinbox = SuffixSpinBox()
        y_spinbox.setRange(-999999, 999999)
        y_spinbox.setSingleStep(1)
        y_spinbox.setDecimals(0)
        y_spinbox.set_suffix('Y')

        if index < len(self._points):
            x, y = self._points[index]
            x_spinbox.setValue(x)
            y_spinbox.setValue(y)

        # Connect after the initial value is set so no spurious update fires.
        x_spinbox.valueChanged.connect(self._on_pair_changed)
        y_spinbox.valueChanged.connect(self._on_pair_changed)

        row.addWidget(index_label)
        row.addWidget(x_spinbox)
        row.addWidget(y_spinbox)

        self._pairs.append((x_spinbox, y_spinbox))
        return row

    def _rebuild_pairs(self):
        """Recreate every x/y row to match the current vertex count."""
        while self._pairs_layout.count():
            item = self._pairs_layout.takeAt(0)
            sub_layout = item.layout()
            if sub_layout:
                self._clear_layout(sub_layout)
                sub_layout.deleteLater()

        self._pairs = []
        for i in range(len(self._points)):
            self._pairs_layout.addLayout(self._create_pair_row(i))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                PolygonPointsWidget._clear_layout(item.layout())

    def set_points(self, points):
        """Sync the widget with a (possibly external) vertex list, e.g. after
        undo/redo. When the values already match, only the spin box values are
        refreshed in place so the row being edited keeps focus."""
        points = list(points)
        if points == self._points and len(self._pairs) == len(points):
            for i, (x_spinbox, y_spinbox) in enumerate(self._pairs):
                x, y = points[i]
                if int(x_spinbox.value()) != x:
                    x_spinbox.blockSignals(True)
                    x_spinbox.setValue(x)
                    x_spinbox.blockSignals(False)
                if int(y_spinbox.value()) != y:
                    y_spinbox.blockSignals(True)
                    y_spinbox.setValue(y)
                    y_spinbox.blockSignals(False)
            return

        self._points = points
        self._count_spinbox.blockSignals(True)
        self._count_spinbox.setValue(len(points))
        self._count_spinbox.blockSignals(False)
        self._rebuild_pairs()

    def _on_count_changed(self, value):
        # SuffixSpinBox is a QDoubleSpinBox, so the signal carries a float.
        value = int(value)
        current = len(self._points)
        if value == current:
            return

        if value > current:
            self._points.extend([(0, 0)] * (value - current))
        else:
            self._points = self._points[:value]

        self._rebuild_pairs()
        self._inspector_container.set_object_points(list(self._points))

    def _on_pair_changed(self, *args):
        points = self._collect_points()
        if points != self._points:
            self._points = points
            self._inspector_container.set_object_points(points)

    def _collect_points(self):
        """Read every X/Y spin box back into a list of (x, y) tuples."""
        return [(int(x_spinbox.value()), int(y_spinbox.value()))
                for x_spinbox, y_spinbox in self._pairs]


class CollisionPointsWidget(PolygonPointsWidget):
    """Reuses PolygonPointsWidget to edit an object's collision polygon
    vertices; every edit is pushed as a collision parameter change."""

    def _on_count_changed(self, value):
        # SuffixSpinBox is a QDoubleSpinBox, so the signal carries a float.
        value = int(value)
        current = len(self._points)
        if value == current:
            return

        if value > current:
            self._points.extend([(0, 0)] * (value - current))
        else:
            self._points = self._points[:value]

        self._rebuild_pairs()
        self._notify_collision_changed()

    def _on_pair_changed(self, *args):
        points = self._collect_points()
        if points != self._points:
            self._points = points
            self._notify_collision_changed()

    def _notify_collision_changed(self):
        self._inspector_container.set_object_collision_parameter(
            'collision_points', list(self._points))