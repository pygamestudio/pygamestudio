
import math
import os
import time
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.transform import (
    IDENTITY as TRANSFORM_IDENTITY, Transform, PIVOT_MODES, resolve_pivot)
from pygamestudio.game.core.collision import collide, collide_point, rect_shape
from pygamestudio.common.utils.system import get_system_lang
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.i18n.translator import Translator as T


#: Memo of asset file states, shared by every object: absolute path ->
#: (checked_at, state, phase fraction). See ObjectBase._asset_file_state.
_FILE_STATE_MEMO = {}


def _file_state_phase(key):
    """A stable 0..1 phase for one memo key.

    It delays the re-check of this file by up to one interval, which is what
    keeps hundreds of different files from all re-reading their disk state on
    the same frame (that lands as a periodic hitch while a game runs).
    """
    return (abs(hash(key)) % 1000) / 1000.0


def _scaled_surface(surface, scale_x, scale_y):
    """Scale a surface by EXPLICIT factors, mirroring negative ones.

    pygame cannot scale to a negative size, so a negative factor flips that
    axis first - which is exactly a mirror. Always returns a NEW surface: the
    callers keep writing into it (rounded corners, alpha, tint).
    """
    if scale_x < 0 or scale_y < 0:
        surface = pygame.transform.flip(surface, scale_x < 0, scale_y < 0)
    elif scale_x == 1 and scale_y == 1:
        return surface.copy()

    size = (max(1, int(surface.get_width() * abs(scale_x))),
            max(1, int(surface.get_height() * abs(scale_y))))
    return pygame.transform.scale(surface, size)


class ObjectBase:
    """Base class for every scene object (rect, text, image, ...).

    Used in two modes:
    - Editor mode (is_for_api=False): driven by GameManager, properties are
      serialized to the .scene file, and pygame surfaces are rendered into the
      editor's scene view.
    - Runtime mode (is_for_api=True): driven by SceneLoader, the object is
      rendered into the game window and a behavior script (script_path) can be
      attached.
    """

    # How often the disk state of a cached asset (font, image) is re-read while
    # the game runs: replacing the file is picked up within this many seconds
    # (plus the per-file phase below). Set to 0 to look on every frame (used by
    # the tests).
    ASSET_CHECK_INTERVAL = 0.25

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        self._is_for_api = is_for_api
        self._game_manager = game_manager

        # Editor-only bookkeeping (never serialized to disk).
        internal_properties = {
            'expanded': True,
            'selected': False,
            'icon': '',
        }
    
        if not self._is_for_api:
            for key, value in internal_properties.items():
                setattr(self, key, object_data.get(key, value))

        self.surface = None
        # The behavior script instance attached to this object at runtime
        # (created from script_path). None when no script is attached.
        self.script_instance = None

        # Path of the object script (a .py file inside the project, e.g.
        # './script/new.py', relative to the project path). Empty string means
        # no script is attached. It is serialized into the .scene file and used
        # by the runtime to attach a behavior script to the object.
        self.script_path = object_data.get('script_path', '')

        # ------------------------------------------------------------------
        # Child clipping. A parent does NOT clip its children by default: the
        # whole tree is drawn flat onto the screen at world coordinates, so a
        # child that leaves its parent's box stays fully visible (only the
        # game window itself clips). Set clip_children to True to get the
        # classic "one layer inside the box" rendering instead - a real
        # viewport / mask container (the editor bakes it the same way).
        # ------------------------------------------------------------------
        self.clip_children = bool(object_data.get('clip_children', False))

        # ------------------------------------------------------------------
        # Transform pivot ("anchor"): the point of the object's own pixel
        # grid that rotation and scaling happen around. It defaults to the
        # CENTRE, so a negative scale mirrors the object IN PLACE and a
        # rotated parent swings its children around its centre instead of
        # its top-left corner. 'top_left' restores the classic behaviour,
        # 'custom' uses pivot_x / pivot_y (content pixels, resolved against
        # the CURRENT size for the named anchors - see resolve_pivot).
        # ------------------------------------------------------------------
        self.pivot = object_data.get('pivot', 'center')
        self.pivot_x = float(object_data.get('pivot_x', 0.0))
        self.pivot_y = float(object_data.get('pivot_y', 0.0))

        # ------------------------------------------------------------------
        # Collision configuration (default: disabled).
        #   collision_enabled: master switch. When False the object takes NO
        #       part in any collision test (is_colliding_with_* / collides_with_*
        #       always return False) and no shape is drawn in the editor.
        #   collision_type: 'bbox' | 'rect' | 'ellipse' | 'polygon'
        #       'bbox'    = always the object's rendered world bounding box.
        #       'rect'    = a box; uses collision_width/height (full size).
        #       'ellipse' = an ellipse inscribed in the collision box
        #                   (collision_width/height is its full size).
        #       'polygon' = free vertices in collision_points.
        #   collision_offset_x/y shift the shape from the object's local
        #       centre (content pixels); available for every type but bbox.
        #   All sizes are CONCRETE: a stored 0 really means a zero-sized shape
        #       (no collision). The first time a shape type is used its
        #       still-zero fields are filled from the object's own size.
        # ------------------------------------------------------------------
        # Legacy scenes may still hold 'circle' or radius fields: migrate them
        # to the ellipse model (a circle is an ellipse with equal axes).
        _data_type = object_data.get('collision_type', 'rect')
        _legacy_radius = float(object_data.get('collision_radius', 0))
        _legacy_rx = float(object_data.get('collision_radius_x', 0))
        _legacy_ry = float(object_data.get('collision_radius_y', 0))
        _collision_width = float(object_data.get('collision_width', 0))
        _collision_height = float(object_data.get('collision_height', 0))
        if _data_type == 'circle':
            _data_type = 'ellipse'
            if _legacy_radius > 0:
                _collision_width = _legacy_radius * 2
                _collision_height = _legacy_radius * 2
        elif _data_type == 'ellipse':
            if _legacy_rx > 0:
                _collision_width = _legacy_rx * 2
            if _legacy_ry > 0:
                _collision_height = _legacy_ry * 2

        self.collision_enabled = bool(object_data.get('collision_enabled', False))
        self.collision_type = _data_type if _data_type in ('bbox', 'rect', 'ellipse', 'polygon') else 'rect'
        self.collision_offset_x = float(object_data.get('collision_offset_x', 0))
        self.collision_offset_y = float(object_data.get('collision_offset_y', 0))
        self.collision_width = _collision_width
        self.collision_height = _collision_height
        self.collision_points = list(object_data.get('collision_points', []))
        # Becomes True once the shape fields carry explicit values (never
        # serialized).
        self._collision_configured = False

        # ------------------------------------------------------------------
        # Physics (default: disabled). A physics-enabled object is driven by
        # the 2D physics world while the game runs (see core/physics.py):
        #   physics_type: 'static' (never moves), 'dynamic' (falls, is pushed,
        #       rotates) or 'kinematic' (moved by a script, pushes others).
        #   The SHAPE is the rigid-body shape below (physics_shape_*) - it is
        #       independent from the collision shape and the collision_enabled
        #       switch is not required.
        #   physics_fixed_rotation keeps the object upright (characters).
        #   physics_gravity_scale 0 = floats, 1 = normal, -1 = falls upwards.
        # ------------------------------------------------------------------
        _physics_type = object_data.get('physics_type', 'dynamic')
        self.physics_enabled = bool(object_data.get('physics_enabled', False))
        self.physics_type = _physics_type if _physics_type in ('static', 'dynamic', 'kinematic') else 'dynamic'
        self.physics_mass = float(object_data.get('physics_mass', 1.0) or 1.0)
        self.physics_friction = float(object_data.get('physics_friction', 0.6))
        self.physics_elasticity = float(object_data.get('physics_elasticity', 0.2))
        self.physics_gravity_scale = float(object_data.get('physics_gravity_scale', 1.0))
        self.physics_fixed_rotation = bool(object_data.get('physics_fixed_rotation', False))
        self.physics_linear_damping = float(object_data.get('physics_linear_damping', 0.0))
        self.physics_angular_damping = float(object_data.get('physics_angular_damping', 0.0))

        # ------------------------------------------------------------------
        # Rigid-body shape (only used while physics_enabled). Same model as
        # the collision fields above - type/offset/size/points - but a
        # separate set of values so the body can differ from the collision
        # shape. Zero-sized fields are filled from the object's own size the
        # first time a shape type is used (see _ensure_physics_shape_defaults).
        # ------------------------------------------------------------------
        _physics_shape_type = object_data.get('physics_shape_type', 'rect')
        self.physics_shape_type = _physics_shape_type if _physics_shape_type in ('bbox', 'rect', 'ellipse', 'polygon') else 'rect'
        self.physics_shape_offset_x = float(object_data.get('physics_shape_offset_x', 0))
        self.physics_shape_offset_y = float(object_data.get('physics_shape_offset_y', 0))
        self.physics_shape_width = float(object_data.get('physics_shape_width', 0))
        self.physics_shape_height = float(object_data.get('physics_shape_height', 0))
        self.physics_shape_points = list(object_data.get('physics_shape_points', []))
        # Becomes True once the body shape fields carry explicit values (never
        # serialized).
        self._physics_shape_configured = False

    def is_pressed(self, x:int, y:int) -> bool:
        """Pixel-perfect hit test: True when (x, y) (world coords) hits a
        non-transparent pixel of the object. More expensive than
        is_point_inside(); prefer it for clicks, not per-frame checks."""
        return True if self._check_click_collision((x, y)) else False

    def is_visible(self) -> bool:
        return self.visible

    def is_shown(self) -> bool:
        return self.visible

    def is_hidden(self) -> bool:
        return not self.visible

    def is_point_inside(self, x: int, y: int) -> bool:
            """Cheap rect-based hit test (unlike is_pressed, no pixel mask)."""
            return self._get_world_rect().collidepoint(x, y)
    
    def is_colliding_with_rect(self, x: int, y: int, width: int, height: int) -> bool:
        """True when the object's collision shape overlaps the given rectangle
        (world coords). Returns False when collision is not enabled."""
        shape = self._collision_shape()
        if shape is None:
            return False
        return collide(shape, rect_shape(pygame.Rect(x, y, width, height)))

    def is_colliding_with_object(self, other) -> bool:
        """True when BOTH objects have collision enabled and their collision
        shapes overlap. Returns False when either side is disabled."""
        shape = self._collision_shape()
        other_shape = other._collision_shape() if hasattr(other, '_collision_shape') else None
        if shape is None or other_shape is None:
            return False
        return collide(shape, other_shape)

    # ------------------------------------------------------------ collision API
    def is_collision_enabled(self) -> bool:
        """Whether this object takes part in shape-based collision tests."""
        return bool(self.collision_enabled)

    def set_collision_enabled(self, enabled: bool):
        """Enable/disable collision detection for this object."""
        self.collision_enabled = bool(enabled)

    def get_collision_type(self) -> str:
        """One of 'bbox', 'rect', 'ellipse' or 'polygon'."""
        return self.collision_type

    def set_collision_type(self, collision_type: str):
        """Set the collision shape type: 'bbox' (rendered bounding box),
        'rect', 'ellipse' or 'polygon'."""
        if collision_type in ('bbox', 'rect', 'ellipse', 'polygon'):
            self.collision_type = collision_type
            self._collision_configured = True

    def set_collision_offset(self, x: float, y: float):
        """Offset of the shape's centre from the object's local centre, in
        unscaled content pixels. The offset follows the object's scale/rotate."""
        self.collision_offset_x = float(x)
        self.collision_offset_y = float(y)
        self._collision_configured = True

    def get_collision_offset(self) -> tuple:
        """(offset_x, offset_y) of the shape centre vs the object centre."""
        return (self.collision_offset_x, self.collision_offset_y)

    def get_collision_size(self) -> tuple:
        """The stored (width, height) of the collision shape: full box size for
        a rect, and the full bounding-box size for an ellipse."""
        return (self.collision_width, self.collision_height)

    def get_collision_radius(self) -> float:
        """Radius of an ellipse shape (half of the smaller side of its box)."""
        return min(self.collision_width, self.collision_height) / 2.0

    def set_collision_size(self, width: int, height: int):
        """Collision box size in content pixels (used by rect and ellipse)."""
        self.collision_width = float(int(width))
        self.collision_height = float(int(height))
        self._collision_configured = True

    def set_collision_ellipse(self, radius_x: float, radius_y: float):
        """Convenience: set the two radii of an ellipse (content pixels) and
        switch to the 'ellipse' type."""
        self.collision_width = float(radius_x) * 2
        self.collision_height = float(radius_y) * 2
        self.collision_type = 'ellipse'
        self._collision_configured = True

    def set_collision_polygon(self, points):
        """Set explicit polygon vertices (local content pixels, top-left
        origin) and switch the shape type to 'polygon'."""
        self.collision_points = [(float(px), float(py)) for (px, py) in points]
        self.collision_type = 'polygon'
        self._collision_configured = True

    def get_collision_polygon(self) -> list:
        """The explicit polygon vertices, or [] when using auto (box)."""
        return list(self.collision_points)

    def reset_collision_shape(self):
        """Reset every editable field back to the object-sized default (all
        stored values are made concrete, matching the object)."""
        self.collision_offset_x = 0
        self.collision_offset_y = 0
        self.collision_width = 0
        self.collision_height = 0
        self.collision_points = []
        self._collision_configured = False
        self._ensure_collision_defaults(force=True)

    def collides_with_point(self, x: int, y: int) -> bool:
        """True when (x, y) (world coords) is inside the collision shape.
        Returns False when collision is not enabled."""
        shape = self._collision_shape()
        if shape is None:
            return False
        return collide_point(shape, x, y)

    def collides_with_rect(self, rect) -> bool:
        """True when the collision shape overlaps ``rect`` (pygame.Rect or
        (x, y, w, h) tuple, world coords). False when collision is disabled."""
        shape = self._collision_shape()
        if shape is None:
            return False
        if not isinstance(rect, pygame.Rect):
            rect = pygame.Rect(*rect)
        return collide(shape, rect_shape(rect))

    def collides_with_object(self, other) -> bool:
        """Alias for is_colliding_with_object (shape-aware)."""
        return self.is_colliding_with_object(other)

    def get_collision_center(self) -> tuple:
        """World coordinates of the centre of the collision shape (the object
        centre for auto / centred shapes)."""
        cw = self.collision_width if self.collision_width > 0 else self.width
        ch = self.collision_height if self.collision_height > 0 else self.height
        # Centre of the shape in local content coordinates.
        cx = self.width / 2.0 + self.collision_offset_x
        cy = self.height / 2.0 + self.collision_offset_y
        if self.collision_type == 'polygon' and self.collision_points:
            xs = [px for (px, py) in self.collision_points]
            ys = [py for (px, py) in self.collision_points]
            if xs and ys:
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
        return self._point_to_world(cx, cy)

    # ---------------------------------------------------- collision internals
    def _get_local_origin_world(self):
        """World coordinates of the object's local content origin (the
        (0, 0) corner of its own pixel grid, before scaling/rotation)."""
        return self._get_world_transform().map_point(0.0, 0.0)

    def _local_transform(self):
        """This object's own transform: content -> parent content space."""
        return Transform.from_object(self)

    def _get_parent_context(self):
        """(transform, ops) of the whole ancestor chain.

        ``transform`` maps the parent content space into the scene. ``ops``
        are the (scale_x, scale_y, angle) of every ancestor that really is
        scaled or rotated, INNERMOST FIRST - the exact sequence the drawing
        applies to a bitmap (each step is an axis-aligned scale or a rotation,
        so a child never shears). Both stay identity / empty for an untouched
        scene, which is the fast path of the walks.
        """
        chain = []
        parent_object = self._game_manager.get_parent_object(self.uuid)
        while parent_object is not None:
            chain.append(parent_object)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        transform = TRANSFORM_IDENTITY
        for ancestor in reversed(chain):
            transform = transform.compose(ancestor._local_transform())

        ops = []
        for ancestor in chain:
            if ancestor.angle or ancestor.scale_x != 1 or ancestor.scale_y != 1:
                ops.append((float(ancestor.scale_x), float(ancestor.scale_y),
                            float(ancestor.angle)))
        return transform, tuple(ops)

    def _get_parent_transform(self):
        """Composed transform of every ancestor, outermost first (the canvas
        included). IDENTITY while nothing above the object is moved at all."""
        return self._get_parent_context()[0]

    def _get_parent_ops(self):
        """The (scale, angle) ops of every transformed ancestor, innermost
        first (see _get_parent_context)."""
        return self._get_parent_context()[1]

    def _get_world_transform(self):
        """The whole chain: content -> scene coordinates."""
        return self._get_parent_transform().compose(self._local_transform())

    def _world_delta_to_local(self, dx, dy):
        """Convert a scene-space delta into this object's parent space.

        Dragging measures the mouse delta on SCREEN, but (x, y) live in the
        parent's space: inside a rotated, scaled or mirrored parent the delta
        has to be mapped back through the inverse transform, otherwise the
        object would drift away from the cursor.
        """
        inverse = self._get_parent_transform().inverted()
        if inverse is None:
            return (dx, dy)
        return inverse.map_vector(dx, dy)

    def _points_to_world(self, local_points):
        """Map points of the object's own pixel grid into scene coordinates.

        The very same transform the drawing uses - position, scale, mirror,
        rotation and pivot of every ancestor included - so collision and
        rigid-body shapes stay exactly on the drawn pixels.
        """
        transform = self._get_world_transform()
        return [transform.map_point(px, py) for (px, py) in local_points]

    def _point_to_world(self, x, y):
        """Map one local content point to world coordinates."""
        return self._points_to_world([(x, y)])[0]

    def _collision_geometry_world(self):
        """Return the collision shape as a world-space descriptor, or None
        when the object has no usable shape (see core/collision.py). 'bbox'
        always returns the rendered world bounding box."""
        ctype = self.collision_type if self.collision_type in ('bbox', 'rect', 'ellipse', 'polygon') else 'rect'

        if ctype == 'bbox':
            return rect_shape(self._get_world_rect())

        # First use of a fresh shape fills its still-zero fields from the
        # object's own size (see _ensure_collision_defaults).
        self._ensure_collision_defaults()

        return self._shape_geometry_world(
            ctype, self.collision_offset_x, self.collision_offset_y,
            self.collision_width, self.collision_height, self.collision_points)

    def _physics_shape_geometry_world(self):
        """Return the RIGID-BODY shape (physics_shape_*) as a world-space
        descriptor, or None. Same model as the collision shape, separate
        values; 'bbox' returns the rendered world bounding box."""
        ctype = self.physics_shape_type if self.physics_shape_type in ('bbox', 'rect', 'ellipse', 'polygon') else 'rect'

        if ctype == 'bbox':
            return rect_shape(self._get_world_rect())

        self._ensure_physics_shape_defaults()

        return self._shape_geometry_world(
            ctype, self.physics_shape_offset_x, self.physics_shape_offset_y,
            self.physics_shape_width, self.physics_shape_height,
            self.physics_shape_points)

    def _shape_geometry_world(self, ctype, offset_x, offset_y, box_width, box_height, points):
        """World descriptor of a type/offset/size/points shape definition.

        Shared by the collision shape and the rigid-body shape."""
        cw = float(box_width)
        ch = float(box_height)
        if cw <= 0 or ch <= 0:
            return None

        # Centre of the shape in local content coordinates (offset shifts the
        # shape away from the object centre for every non-bbox type).
        cx = self.width / 2.0 + offset_x
        cy = self.height / 2.0 + offset_y
        sx = abs(self.scale_x)
        sy = abs(self.scale_y)

        if ctype == 'ellipse':
            rx, ry = cw / 2.0, ch / 2.0
            if abs(rx - ry) < 1e-9:
                # Equal radii + (possibly) uniform scale -> exact circle.
                return self._circle_or_poly(rx, cx, cy, sx, sy)
            local = [(cx + rx * math.cos(2 * math.pi * i / 24),
                      cy + ry * math.sin(2 * math.pi * i / 24))
                     for i in range(24)]
            return {'kind': 'poly', 'points': self._points_to_world(local)}

        if ctype == 'rect':
            hw, hh = cw / 2.0, ch / 2.0
            local = [(cx - hw, cy - hh), (cx + hw, cy - hh),
                     (cx + hw, cy + hh), (cx - hw, cy + hh)]
            world = self._points_to_world(local)
            if not self.angle:
                xs = [p[0] for p in world]
                ys = [p[1] for p in world]
                return rect_shape(pygame.Rect(round(min(xs)), round(min(ys)),
                                              round(max(xs) - min(xs)),
                                              round(max(ys) - min(ys))))
            return {'kind': 'poly', 'points': world}

        # 'polygon': explicit vertices (absolute local pixels + offset shift)
        # or the shape's own box.
        if points:
            local = [(float(px) + offset_x,
                      float(py) + offset_y)
                     for (px, py) in points]
        else:
            hw, hh = cw / 2.0, ch / 2.0
            local = [(cx - hw, cy - hh), (cx + hw, cy - hh),
                     (cx + hw, cy + hh), (cx - hw, cy + hh)]
        world = self._points_to_world(local)
        if len(world) < 3:
            return None
        return {'kind': 'poly', 'points': world}

    def _circle_or_poly(self, radius, cx, cy, sx, sy):
        """World descriptor for a circle of ``radius`` centred at local (cx,
        cy): an exact circle when scale is uniform, otherwise a sampled
        ellipse polygon."""
        if abs(sx - sy) < 1e-6:
            wcx, wcy = self._point_to_world(cx, cy)
            return {'kind': 'circle', 'cx': wcx, 'cy': wcy, 'r': radius * sx}
        local = [(cx + radius * math.cos(2 * math.pi * i / 24),
                  cy + radius * math.sin(2 * math.pi * i / 24))
                 for i in range(24)]
        return {'kind': 'poly', 'points': self._points_to_world(local)}

    def _ensure_collision_defaults(self, force=False, for_type=None):
        """Fill still-zero size fields with object-sized defaults (concrete
        numbers, no 'auto' semantics). Called when the inspector enables a
        shape or switches its type, and defensively from the geometry code on
        first use. Afterwards a stored 0 really means a zero-sized shape."""
        ctype = for_type
        if ctype not in ('rect', 'ellipse', 'polygon'):
            ctype = self.collision_type if self.collision_type in ('rect', 'ellipse', 'polygon') else 'rect'

        if force or not self._collision_configured:
            if self.collision_width <= 0:
                self.collision_width = float(self.width)
            if self.collision_height <= 0:
                self.collision_height = float(self.height)
            self._collision_configured = True

    def _ensure_physics_shape_defaults(self, force=False, for_type=None):
        """Fill the rigid-body shape's still-zero size fields from the
        object's own size (same model as _ensure_collision_defaults). Called
        when the inspector enables physics or switches the shape, and
        defensively from the body builder on first use."""
        ctype = for_type
        if ctype not in ('rect', 'ellipse', 'polygon'):
            ctype = self.physics_shape_type if self.physics_shape_type in ('rect', 'ellipse', 'polygon') else 'rect'

        if force or not self._physics_shape_configured:
            if self.physics_shape_width <= 0:
                self.physics_shape_width = float(self.width)
            if self.physics_shape_height <= 0:
                self.physics_shape_height = float(self.height)
            self._physics_shape_configured = True

    def _collision_shape(self):
        """The world-space descriptor used by collision tests, or None when
        collision is not enabled (the object then never collides)."""
        if not self.collision_enabled:
            return None
        return self._collision_geometry_world()

    # --------------------------------------------------------------- physics API
    def _physics_world(self):
        """The running scene's physics world, or None (editor, or a scene
        without a physics world)."""
        getter = getattr(self._game_manager, 'physics_world', None)
        return getter() if callable(getter) else None

    def is_physics_enabled(self) -> bool:
        """Whether this object is driven by the physics world."""
        return bool(self.physics_enabled)

    def set_physics_enabled(self, enabled: bool):
        """Turn the rigid body of this object on or off (while the game runs
        the body appears/disappears on the next frame)."""
        self.physics_enabled = bool(enabled)

    def get_physics_type(self) -> str:
        """'static', 'dynamic' or 'kinematic'."""
        return self.physics_type

    def set_physics_type(self, physics_type: str):
        """static: never moves. dynamic: falls and is pushed. kinematic: moved
        by a script, pushes the others."""
        if physics_type in ('static', 'dynamic', 'kinematic'):
            self.physics_type = physics_type

    def get_physics_mass(self) -> float:
        return self.physics_mass

    def set_physics_mass(self, mass: float):
        """Heavier bodies need more force/impulse for the same movement."""
        self.physics_mass = max(0.0001, float(mass))

    def get_physics_friction(self) -> float:
        return self.physics_friction

    def set_physics_friction(self, friction: float):
        """0 = ice, 1 = sticky."""
        self.physics_friction = max(0.0, float(friction))

    def get_physics_elasticity(self) -> float:
        return self.physics_elasticity

    def set_physics_elasticity(self, elasticity: float):
        """Bounce of the body: 0 = lands dead, 1 = bounces back fully."""
        self.physics_elasticity = max(0.0, float(elasticity))

    def get_physics_gravity_scale(self) -> float:
        return self.physics_gravity_scale

    def set_physics_gravity_scale(self, scale: float):
        """0 = floats, 1 = normal gravity, negative = falls upwards."""
        self.physics_gravity_scale = float(scale)

    def is_physics_fixed_rotation(self) -> bool:
        return bool(self.physics_fixed_rotation)

    def set_physics_fixed_rotation(self, fixed: bool):
        """True keeps the body upright (a character never tips over)."""
        self.physics_fixed_rotation = bool(fixed)

    def get_physics_damping(self) -> tuple:
        """(linear, angular) damping: how quickly movement dies down."""
        return (self.physics_linear_damping, self.physics_angular_damping)

    def set_physics_damping(self, linear: float, angular: float = 0.0):
        self.physics_linear_damping = max(0.0, float(linear))
        self.physics_angular_damping = max(0.0, float(angular))

    def get_physics_shape_type(self) -> str:
        """One of 'bbox', 'rect', 'ellipse' or 'polygon' - the shape of the
        rigid body (independent from the collision shape)."""
        return self.physics_shape_type

    def set_physics_shape_type(self, shape_type: str):
        """Set the rigid-body shape type: 'bbox' (rendered bounding box),
        'rect', 'ellipse' or 'polygon'."""
        if shape_type in ('bbox', 'rect', 'ellipse', 'polygon'):
            self.physics_shape_type = shape_type
            self._physics_shape_configured = True

    def get_physics_shape_offset(self) -> tuple:
        """(offset_x, offset_y) of the body shape centre vs the object centre."""
        return (self.physics_shape_offset_x, self.physics_shape_offset_y)

    def set_physics_shape_offset(self, x: float, y: float):
        """Offset of the body shape's centre from the object's local centre,
        in unscaled content pixels."""
        self.physics_shape_offset_x = float(x)
        self.physics_shape_offset_y = float(y)
        self._physics_shape_configured = True

    def get_physics_shape_size(self) -> tuple:
        """The stored (width, height) of the body shape: the full box size
        for a rect, the bounding-box size for an ellipse."""
        return (self.physics_shape_width, self.physics_shape_height)

    def set_physics_shape_size(self, width: int, height: int):
        """Body shape box size in content pixels (used by rect and ellipse)."""
        self.physics_shape_width = float(int(width))
        self.physics_shape_height = float(int(height))
        self._physics_shape_configured = True

    def set_physics_shape_ellipse(self, radius_x: float, radius_y: float):
        """Convenience: set the two radii of the body ellipse (content
        pixels) and switch to the 'ellipse' type."""
        self.physics_shape_width = float(radius_x) * 2
        self.physics_shape_height = float(radius_y) * 2
        self.physics_shape_type = 'ellipse'
        self._physics_shape_configured = True

    def set_physics_shape_polygon(self, points):
        """Set explicit body vertices (local content pixels, top-left origin)
        and switch the shape type to 'polygon'."""
        self.physics_shape_points = [(float(px), float(py)) for (px, py) in points]
        self.physics_shape_type = 'polygon'
        self._physics_shape_configured = True

    def get_physics_shape_polygon(self) -> list:
        """The explicit body polygon vertices, or [] when using auto (box)."""
        return list(self.physics_shape_points)

    def reset_physics_shape(self):
        """Reset the body shape back to the object-sized default (all stored
        values are made concrete, matching the object)."""
        self.physics_shape_offset_x = 0
        self.physics_shape_offset_y = 0
        self.physics_shape_width = 0
        self.physics_shape_height = 0
        self.physics_shape_points = []
        self._physics_shape_configured = False
        self._ensure_physics_shape_defaults(force=True)

    def apply_force(self, force):
        """Push the body every frame while it is called (wind, thrusters).

        The force is ``mass * acceleration``: with the default mass of 1, a
        force of 1200 adds 1200 pixels/second of speed per second."""
        world = self._physics_world()
        if world is not None:
            world.apply_force(self, force)

    def apply_impulse(self, impulse):
        """Add an instant push (a jump, an explosion): ``mass * pixels/s``."""
        world = self._physics_world()
        if world is not None:
            world.apply_impulse(self, impulse)

    def get_velocity(self):
        """(vx, vy) in pixels per second, or None without a body."""
        world = self._physics_world()
        return world.get_velocity(self) if world is not None else None

    def set_velocity(self, velocity):
        """Set the movement speed directly (pixels per second)."""
        world = self._physics_world()
        if world is not None:
            world.set_velocity(self, velocity)

    def get_angular_velocity(self):
        """Spin in degrees per second, or None without a body."""
        world = self._physics_world()
        return world.get_angular_velocity(self) if world is not None else None

    def set_angular_velocity(self, angular_velocity):
        """Set the spin in degrees per second."""
        world = self._physics_world()
        if world is not None:
            world.set_angular_velocity(self, angular_velocity)

    def is_grounded(self) -> bool:
        """True while the body stands on something (a short memory covers
        walking off a ledge, so a jump still works just after it)."""
        world = self._physics_world()
        return world.is_grounded(self) if world is not None else False

    def get_name(self) -> str:
        return self.name
        
    def get_uuid(self) -> str:
        return self.uuid

    def get_type(self) -> str:
        return self.type

    def get_pos(self) -> tuple:
        return self.pos
    
    def get_world_pos(self) -> tuple:
        return self._get_world_pos()
    
    def get_x(self) -> int:
        return self.x
    
    def get_y(self) -> int:
        return self.y
    
    def get_width(self) -> int:
        return self.width
    
    def get_height(self) -> int:
        return self.height
    
    def get_size(self) -> tuple:
        return self.size
    
    def get_scale_x(self) -> float:
        return self.scale_x
    
    def get_scale_y(self) -> float:
        return self.scale_y
    
    def get_scale(self) -> tuple:
        return self.scale

    def get_pivot(self) -> str:
        """The anchor rotation/scaling happen around ('center', 'top_left',
        'custom', ...)."""
        return self.pivot

    def get_pivot_point(self) -> tuple:
        """The pivot resolved to content pixels (see resolve_pivot)."""
        return resolve_pivot(self.pivot, self.pivot_x, self.pivot_y,
                             self.width, self.height)

    def get_visible_state(self) -> bool:
        return self.visible
    
    def get_color(self) -> tuple:
        return self.color
    
    def set_pos(self, x:int, y:int):
        self.x = x
        self.y = y

    def set_world_pos(self, x:int, y:int):
        self._set_world_rect(x, y)

    def set_x(self, x:int) -> int:
        self.x = x

    def set_y(self, y:int) -> int:
        self.y = y

    def set_width(self, width:int):
        self.width = width
    
    def set_height(self, height:int):
        self.height = height

    def set_size(self, width:int , height:int):
        self.size = (width, height)
    
    def set_scale_x(self, scale_x:float):
        self.scale_x = scale_x
    
    def set_scale_y(self, scale_y:float):
        self.scale_y = scale_y

    def set_scale(self, scale_x:float, scale_y:float):
        self.scale = (scale_x, scale_y)

    def set_pivot(self, pivot:str):
        """Choose the anchor: 'center' (default), 'top_left', 'top_center',
        ..., or 'custom' (see set_pivot_point)."""
        self.pivot = pivot

    def set_pivot_point(self, x:float, y:float):
        """Rotate/scale around a free point of the object's own pixel grid."""
        self.pivot_x = x
        self.pivot_y = y
        self.pivot = 'custom'

    def get_angle(self) -> float:
        return self.angle
    
    def set_angle(self, angle:float):
        self.angle = angle

    def set_visible_state(self, visible:bool):
        self.visible = visible
    
    def set_color(self, color:tuple):
        self.color = color

    def get_rect(self) -> pygame.Rect:
        """Local bounding rect (x, y, width, height) of the object."""
        return self._get_rect()

    def get_world_rect(self) -> pygame.Rect:
        """Bounding rect of the object in scene (world) coordinates."""
        return self._get_world_rect()

    def get_collision_rect(self, x: int, y: int, width: int, height: int):
        """Return the overlapping pygame.Rect with the given rectangle, or
        None when they don't overlap."""
        overlap = self._get_world_rect().clip(pygame.Rect(x, y, width, height))
        if overlap.width > 0 and overlap.height > 0:
            return overlap
        return None

    def get_center(self) -> tuple:
        """Center of the object in world coordinates."""
        world_rect = self._get_world_rect()
        return (world_rect.centerx, world_rect.centery)

    def set_center(self, x: int, y: int):
        """Move the object so its center is at (x, y) (world coordinates)."""
        world_rect = self._get_world_rect()
        self._set_world_rect(x - world_rect.width // 2, y - world_rect.height // 2)

    def move(self, dx: int, dy: int):
        """Move the object by (dx, dy) pixels (world coordinates)."""
        world_x, world_y = self._get_world_pos()
        self._set_world_rect(world_x + dx, world_y + dy)

    def distance_to(self, x: int, y: int) -> float:
        """Euclidean distance from the object's center to the point (x, y)."""
        center_x, center_y = self.get_center()
        return math.hypot(x - center_x, y - center_y)

    def distance_to_object(self, other) -> float:
        """Euclidean distance between this object's center and another
        object's center."""
        center_x, center_y = self.get_center()
        other_x, other_y = other.get_center()
        return math.hypot(other_x - center_x, other_y - center_y)

    def get_direction_to(self, x: int, y: int) -> tuple:
        """Normalized (unit) direction vector from the object's center to
        (x, y). Returns (0.0, 0.0) when the target equals the center."""
        center_x, center_y = self.get_center()
        dx = x - center_x
        dy = y - center_y
        length = math.hypot(dx, dy)
        if length == 0:
            return (0.0, 0.0)
        return (dx / length, dy / length)

    def show(self):
        """Make the object visible."""
        self.visible = True

    def hide(self):
        """Hide the object."""
        self.visible = False

    def on_start(self):
        """User hook: called once when the object enters the scene at runtime."""
        ...

    def on_destroy(self):
        """User hook: called when the object leaves the scene at runtime."""
        ...
    
    def on_update(self):
        """User hook: called every frame (before drawing) at runtime."""
        ...

    def on_mouse_enter(self):
        """User hook: called when the pointer moves onto the object at runtime."""
        ...

    def on_mouse_leave(self):
        """User hook: called when the pointer leaves the object at runtime."""
        ...

    def on_pressed(self):
        """User hook: called when the left mouse button goes down on the object."""
        ...

    def on_released(self):
        """User hook: called when the button that went down on this object is released."""
        ...

    def on_clicked(self):
        """User hook: called when the object is clicked (pressed and released on it)."""
        ...

    def on_double_clicked(self):
        """User hook: called when the object is double-clicked at runtime."""
        ...

    def on_right_clicked(self):
        """User hook: called when the object is right-clicked at runtime."""
        ...

    def on_drag_start(self):
        """User hook: called when a pointer drag on the object starts at runtime."""
        ...

    def on_drag(self, pos):
        """User hook: called on every pointer move while the object is dragged.

        :param pos: the pointer position in world coordinates
        """
        ...

    def on_drag_end(self):
        """User hook: called when a pointer drag on the object ends at runtime."""
        ...

    def on_visible_changed(self, visible):
        """User hook: called when the object is shown or hidden at runtime."""
        ...

    def on_collision_enter(self, other):
        """User hook: called when the object starts overlapping another object
        with collision enabled (hidden ones included).

        :param other: the other object
        """
        ...

    def on_collision_exit(self, other):
        """User hook: called when the object stops overlapping another object.

        :param other: the other object
        """
        ...

    def _start(self):
        """Internal wrapper for on_start (driven by the script system)."""
        self.on_start()

    def _destroy(self):
        """Internal wrapper for on_destroy (driven by the script system)."""
        self.on_destroy()

    def _emit_event(self, event_name, *args):
        """Internal: forward an object event to the runtime scene loader.

        Objects are built with the editor's GameManager while editing and with
        the runtime SceneLoader in the game; only the loader knows how to
        reach the attached script, so the event is forwarded to it (and the
        call is simply a no-op in the editor).
        """
        emit = getattr(self._game_manager, '_emit_object_event', None)
        if callable(emit):
            emit(self, event_name, *args)

    def _blit(self, parent_surface, rect, surface=None):
        """Blit ``surface`` (the object's own by default) at ``rect`` (editor
        mode adds the blue selection outline around exactly that rect)."""
        parent_surface.blit(self.surface if surface is None else surface, rect)
        if not self._is_for_api and self.selected:
            pygame.draw.rect(parent_surface, (0, 122, 204), rect, width=2)

    def _draw(self, parent_surface, position=None):
        """Blit this object onto a surface.

        ``position`` is where the object's top-left corner goes on that
        surface; the default draws it at its own local position (inside its
        parent's surface). The transformed walks use _draw_in_transform.

        In editor mode a blue selection outline is drawn around the object.
        """
        rect = self._get_rect()
        if position is not None:
            rect = pygame.Rect(int(position[0]), int(position[1]),
                               rect.width, rect.height)
        self._blit(parent_surface, rect)

    def _parent_render(self, surface, parent_ops):
        """``surface`` with the ancestors' scale / rotation applied.

        Applying the ancestors' ops (innermost first: scale by theirs, rotate
        by theirs) to the object's own surface reproduces the composed linear
        map of the whole chain exactly - a child inside a scaled, rotated or
        mirrored parent is drawn scaled, rotated and mirrored itself. The
        result is cached, so an unchanged scene pays for it once.
        """
        if not parent_ops:
            return surface

        cache = self.__dict__.get('_parent_render_cache')
        if (cache is not None and cache[0][0] is surface
                and cache[0][1] == parent_ops):
            return cache[1]

        result = surface
        for (scale_x, scale_y, angle) in parent_ops:
            result = _scaled_surface(result, scale_x, scale_y)
            if angle % 360:
                result = pygame.transform.rotate(result, angle)
        self._parent_render_cache = ((surface, parent_ops), result)
        return result

    def _bitmap_origin_in(self, parent_transform, parent_ops, surface):
        """FLOAT top-left of the object's bitmap under ``parent_transform``.

        Without a transformed ancestor and with no rotation / scaling of its
        own, the classic "blit the surface at the object's (x, y)" placement
        applies - the fast path of every untouched scene. Otherwise the
        bitmap (the own surface with the ancestors' ops applied) is placed so
        its CENTRE, the image of the content centre, sits where the transform
        maps it - which is what makes the pivot hold for the whole chain.
        """
        if (not parent_ops and not self.angle
                and self.scale_x == 1 and self.scale_y == 1):
            return parent_transform.map_point(self.x, self.y)

        world = parent_transform.compose(self._local_transform())
        centre_x, centre_y = world.map_point(self.width / 2.0,
                                             self.height / 2.0)
        return (centre_x - surface.get_width() / 2.0,
                centre_y - surface.get_height() / 2.0)

    def _drawn_bitmap_in(self, parent_transform, parent_ops):
        """(surface, rect) of what this object draws, in the coordinates
        ``parent_transform`` maps the parent content space into."""
        surface = self._parent_render(self.surface, parent_ops)
        x, y = self._bitmap_origin_in(parent_transform, parent_ops, surface)
        return surface, pygame.Rect(int(round(x)), int(round(y)),
                                    surface.get_width(), surface.get_height())

    def _drawn_bitmap(self):
        """(surface, rect) of what this object draws, in SCENE
        coordinates."""
        parent_transform, parent_ops = self._get_parent_context()
        return self._drawn_bitmap_in(parent_transform, parent_ops)

    def _draw_in_transform(self, target_surface, transform, parent_ops=()):
        """Draw this object where ``transform`` puts it (the transformed
        runtime walk and the editor bake use this instead of _draw)."""
        surface, rect = self._drawn_bitmap_in(transform, parent_ops)
        self._blit(target_surface, rect, surface)

    def _get_surface(self):
        return self.surface

    def _update_surface(self):
        self.on_update()

    def _get_world_pos(self):
        return self._get_world_rect().topleft

    def _get_rect(self):
        # Get the rect of the object. Note that the rect returned by Surface.get_rect() always starts at (0, 0).
        return pygame.Rect(self.x, self.y, self.surface.width, self.surface.height)

    def _get_world_rect(self):
        """Bounding rect of the object's own drawing in scene coordinates
        (the axis-aligned box around its drawn bitmap, so a rotated, scaled or
        mirrored object - inside a transformed parent too - reports where it
        really is)."""
        return self._drawn_bitmap()[1]
    
    def _set_world_rect(self, world_x, world_y):
        """Move the object so its world bounding rect lands at (world_x,
        world_y) - the inverse of _get_world_rect.

        The delta is measured against the EXACT (unrounded) bitmap position
        and converted through the parent's transform, so repeated syncs (the
        physics step writes every body back on every frame) are idempotent
        and dragging inside a rotated or mirrored parent still follows the
        mouse exactly.
        """
        parent_transform, parent_ops = self._get_parent_context()
        surface = self._parent_render(self.surface, parent_ops)
        current_x, current_y = self._bitmap_origin_in(parent_transform,
                                                      parent_ops, surface)
        delta_x = world_x - current_x
        delta_y = world_y - current_y
        if not delta_x and not delta_y:
            return

        local_delta_x, local_delta_y = self._world_delta_to_local(delta_x, delta_y)
        self.pos = (self.x + local_delta_x, self.y + local_delta_y)

    def _get_data(self):
        """Return the object's full attribute dict (used to clone objects)."""
        return self.__dict__.copy()

    def _check_click_collision(self, click_pos):
        """Pixel-perfect hit test: first a cheap world-rect test, then a
        per-pixel alpha mask so transparent pixels don't count as a hit.

        The mask is sampled in the DRAWN surface's own pixels (the rect the
        surface is blitted at), which stays exact for rotated, scaled and
        mirrored objects.
        """
        rect = self._get_world_rect()
        if not rect.collidepoint(click_pos):
            return False

        surface, rect = self._drawn_bitmap()
        mask = pygame.mask.from_surface(surface)
        local_x = click_pos[0] - rect.x
        local_y = click_pos[1] - rect.y
        return mask.get_at((local_x, local_y))
    
    def _check_rect_collision(self, rect):
        return self._get_world_rect().colliderect(rect)
    
    def _to_dict(self):
        """Serialize the object for the .scene JSON file.

        Runtime-only / non-persistent fields (surface, script instance, the
        manager reference, editor selection/expansion state, render caches,
        ...) are excluded so the file stays small, reloadable, and comparable
        against the saved snapshot regardless of transient UI state.
        """
        exclude_fields = [
            '_is_initialized', '_is_for_api', '_game_manager', 'surface', 'icon',
            'script_instance', 'selected', 'expanded', '_collision_configured',
            '_physics_shape_configured',
            '_font_cache', '_font_cache_key', '_image_cache', '_image_cache_key',
            '_render_cache', '_render_state', '_file_state_cache',
            '_parent_render_cache',
        ]
        data = {
            key: value for key, value in self.__dict__.items() 
            if key not in exclude_fields
        }
        # Derived tuples are normalized: the component fields are what the
        # inspector and scripts write, so a stale tuple copy must never win
        # when the object is loaded again or compared against the disk state.
        data['scale'] = (self.scale_x, self.scale_y)
        data['pos'] = (self.x, self.y)
        if data.get('pivot') not in PIVOT_MODES:
            data['pivot'] = 'center'
        return data

    @staticmethod
    def _file_state(file_path):
        """(modification time, size) of an asset file, or None when it is
        missing.

        Objects that cache what they loaded (fonts, images) include this in
        their cache key so replacing a file on disk - a common thing to do
        while a game runs, e.g. after exporting an image - is picked up
        without restarting.
        """
        try:
            stat = os.stat(file_path)
        except OSError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def _asset_file_state(self, asset_path):
        """Like _file_state for a path relative to the project, memoized per
        FILE (not per object) so asking for it on every frame stays cheap.

        The memo is shared by every object: a background made of several
        hundred IMAGE objects that all use the same texture stats the file
        once per interval instead of once per object (that burst alone used to
        cost several milliseconds on one frame - four times per second - and
        grew with the object count).

        Each file also gets a deterministic phase (0..interval) so that many
        DIFFERENT files do not all re-stat on the same frame; a replaced file
        shows up within ``ASSET_CHECK_INTERVAL`` (0.25 s) to 2x that.
        """
        key = (get_project_path(), asset_path)
        now = time.monotonic()
        entry = _FILE_STATE_MEMO.get(key)
        if entry is not None and now - entry[0] < self.ASSET_CHECK_INTERVAL * (1.0 + entry[2]):
            return entry[1]

        state = self._file_state(Path(key[0]) / asset_path)
        _FILE_STATE_MEMO[key] = (now, state, _file_state_phase(key))
        return state

    def _apply_alpha(self, surface):
        if len(self.color) < 4:
            alpha = 255
        else:
            alpha = self.color[-1]
        
        if alpha > 255:
            alpha = 255
        elif alpha < 0:
            alpha = 0
            
        surface.set_alpha(alpha)
        return surface

    def _apply_scale(self, surface):
        """Scale the object's content by scale_x / scale_y.

        A NEGATIVE factor mirrors that axis (see _scaled_surface): -1 means
        "flip", and because the drawing places the bitmap around the pivot, a
        mirrored object stays exactly where it was (with the default centre
        pivot).
        """
        return _scaled_surface(surface, float(self.scale_x), float(self.scale_y))
    
    def __setattr__(self, name, value):
        """Intercept attribute writes to keep derived fields in sync.

        - pos/size/scale also update their x/y/width/height components.
        - script_path is stored relative to the project path.
        - At runtime, name/uuid/type are read-only (identity fields).
        """
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return
        
        if self._is_for_api:
            if name == 'name' or name == 'uuid' or name == 'type':
                print(f'{name} is a read-only property and cannot be modified.')
                return

        if name == 'visible':
            changed = bool(self.visible) != bool(value)
            super().__setattr__('visible', value)
            if changed:
                self._emit_event('on_visible_changed', bool(value))
            return
        
        if name == 'pos':
            super().__setattr__('x', value[0])
            super().__setattr__('y', value[1])
            super().__setattr__('pos', value)

        elif name == 'size':
            super().__setattr__('width', value[0])
            super().__setattr__('height', value[1])
            super().__setattr__('size', value)

        elif name == 'scale':
            super().__setattr__('scale_x', value[0])
            super().__setattr__('scale_y', value[1])
            super().__setattr__('scale', value)

        elif name in ('scale_x', 'scale_y'):
            # Writing ONE component keeps the scale tuple in sync: the tuple
            # is what the scene saves (and what __init__ applies last), so a
            # stale copy would silently win on the next load - and an undo
            # would restore the old factor instead.
            super().__setattr__(name, value)
            super().__setattr__('scale', (self.scale_x, self.scale_y))

        elif name == 'pivot':
            mode = str(value).strip().lower()
            super().__setattr__('pivot', mode if mode in PIVOT_MODES else 'center')

        elif name in ('pivot_x', 'pivot_y'):
            super().__setattr__(name, float(value))

        elif name == 'script_path':
            # Store the script path relative to the project (e.g. './script/x.py').
            if value == '':
                super().__setattr__('script_path', '')
            else:
                project_path = Path(get_project_path())
                new_script_path = Path(value).absolute()
                try:
                    super().__setattr__('script_path', new_script_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('script_path', new_script_path.as_posix())

        else:
            super().__setattr__(name, value)

