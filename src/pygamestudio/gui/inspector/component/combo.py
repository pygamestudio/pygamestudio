from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T


class CollisionTypeComboBox(QComboBox):
    """Shape-type picker for an object's collision body.

    The combo shows translated labels (Bounding Box / Rect / Ellipse / Polygon)
    and stores the matching type code ('bbox' / 'rect' / 'ellipse' / 'polygon')
    in each item's data.
    """

    _OPTIONS = (
        ('bbox', 'inspector.collision_type_bbox', 'Bounding Box'),
        ('rect', 'inspector.collision_type_rect', 'Rect'),
        ('ellipse', 'inspector.collision_type_ellipse', 'Ellipse'),
        ('polygon', 'inspector.collision_type_polygon', 'Polygon'),
    )

    def __init__(self, inspector_container, value='rect', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._codes = [code for code, _, _ in self._OPTIONS]

        for code, key, default in self._OPTIONS:
            self.addItem(T.tr(key, default), code)

        index = self._codes.index(value) if value in self._codes else 0
        self.setCurrentIndex(index)

        self.currentIndexChanged.connect(self._on_index_changed)

    def set_collision_type(self, value):
        """Set the combo to the given type code without firing a change."""
        if value in self._codes:
            self.blockSignals(True)
            self.setCurrentIndex(self._codes.index(value))
            self.blockSignals(False)

    def _on_index_changed(self, index):
        code = self.itemData(index)
        if code:
            self._inspector_container.set_object_collision_type(code)


class PivotComboBox(QComboBox):
    """Anchor picker: the point rotation and scaling happen around.

    Rotation and scaling (a negative scale = flip, too) act around this point
    of the object's own pixel grid. 'Center' is the default - the object
    spins and mirrors in place - while 'Top Left' restores the classic
    "rotate about the object origin" behaviour. 'Custom' uses the free
    coordinates of the pivot point row.
    """

    _OPTIONS = (
        ('center', 'inspector.pivot_center', 'Center'),
        ('top_left', 'inspector.pivot_top_left', 'Top Left'),
        ('top_center', 'inspector.pivot_top_center', 'Top Center'),
        ('top_right', 'inspector.pivot_top_right', 'Top Right'),
        ('center_left', 'inspector.pivot_center_left', 'Center Left'),
        ('center_right', 'inspector.pivot_center_right', 'Center Right'),
        ('bottom_left', 'inspector.pivot_bottom_left', 'Bottom Left'),
        ('bottom_center', 'inspector.pivot_bottom_center', 'Bottom Center'),
        ('bottom_right', 'inspector.pivot_bottom_right', 'Bottom Right'),
        ('custom', 'inspector.pivot_custom', 'Custom'),
    )

    def __init__(self, inspector_container, value='center', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._codes = [code for code, _, _ in self._OPTIONS]

        for code, key, default in self._OPTIONS:
            self.addItem(T.tr(key, default), code)

        index = self._codes.index(value) if value in self._codes else 0
        self.setCurrentIndex(index)

        self.currentIndexChanged.connect(self._on_index_changed)

    def set_pivot(self, value):
        """Set the combo to the given mode without firing a change."""
        if value in self._codes:
            self.blockSignals(True)
            self.setCurrentIndex(self._codes.index(value))
            self.blockSignals(False)

    def _on_index_changed(self, index):
        code = self.itemData(index)
        if code:
            self._inspector_container.set_object_pivot(code)


class PhysicsTypeComboBox(QComboBox):
    """Body-type picker for an object's rigid body.

    The combo shows translated labels (Dynamic / Static / Kinematic) and stores
    the matching type code ('dynamic' / 'static' / 'kinematic') as item data.
    """

    _OPTIONS = (
        ('dynamic', 'inspector.physics_type_dynamic', 'Dynamic'),
        ('static', 'inspector.physics_type_static', 'Static'),
        ('kinematic', 'inspector.physics_type_kinematic', 'Kinematic'),
    )

    def __init__(self, inspector_container, value='dynamic', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._codes = [code for code, _, _ in self._OPTIONS]

        for code, key, default in self._OPTIONS:
            self.addItem(T.tr(key, default), code)

        index = self._codes.index(value) if value in self._codes else 0
        self.setCurrentIndex(index)

        self.currentIndexChanged.connect(self._on_index_changed)

    def set_physics_type(self, value):
        """Set the combo to the given type code without firing a change."""
        if value in self._codes:
            self.blockSignals(True)
            self.setCurrentIndex(self._codes.index(value))
            self.blockSignals(False)

    def _on_index_changed(self, index):
        code = self.itemData(index)
        if code:
            self._inspector_container.set_object_physics_type(code)


class PhysicsShapeComboBox(QComboBox):
    """Shape picker for an object's RIGID BODY (see the collision shape combo
    for the collision system - the two shapes are independent).

    The combo shows translated labels (Bounding Box / Rect / Ellipse / Polygon)
    and stores the matching type code in each item's data.
    """

    _OPTIONS = (
        ('bbox', 'inspector.physics_shape_bbox', 'Bounding Box'),
        ('rect', 'inspector.physics_shape_rect', 'Rect'),
        ('ellipse', 'inspector.physics_shape_ellipse', 'Ellipse'),
        ('polygon', 'inspector.physics_shape_polygon', 'Polygon'),
    )

    def __init__(self, inspector_container, value='rect', attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._codes = [code for code, _, _ in self._OPTIONS]

        for code, key, default in self._OPTIONS:
            self.addItem(T.tr(key, default), code)

        index = self._codes.index(value) if value in self._codes else 0
        self.setCurrentIndex(index)

        self.currentIndexChanged.connect(self._on_index_changed)

    def set_physics_shape_type(self, value):
        """Set the combo to the given type code without firing a change."""
        if value in self._codes:
            self.blockSignals(True)
            self.setCurrentIndex(self._codes.index(value))
            self.blockSignals(False)

    def _on_index_changed(self, index):
        code = self.itemData(index)
        if code:
            self._inspector_container.set_object_physics_shape_type(code)
