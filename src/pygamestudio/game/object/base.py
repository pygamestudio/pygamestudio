
import math
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.core.collision import collide, collide_point, rect_shape
from pygamestudio.common.utils.system import get_system_lang
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.i18n.translator import Translator as T


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
        """World coordinates of the object's local content origin (its top-left
        before scaling/rotation): own (x, y) shifted up the parent chain."""
        ox, oy = self.x, self.y
        parent_object = self._game_manager.get_parent_object(self.uuid)
        while parent_object:
            ox += parent_object.x
            oy += parent_object.y
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)
        return ox, oy

    def _points_to_world(self, local_points):
        """Map local content points to world coordinates replicating EXACTLY
        how the object is rendered: scale about the content origin, then a
        pygame-style rotation about the scaled content centre whose result is
        blitted so its bounding-box top-left lands on the object's (x, y)."""
        sx, sy = self.scale_x, self.scale_y
        ox, oy = self._get_local_origin_world()
        angle = float(self.angle) % 360.0
        if not angle:
            return [(ox + px * sx, oy + py * sy) for (px, py) in local_points]

        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # Scaled content size/centre.
        sw = self.width * sx
        sh = self.height * sy
        cx, cy = sw / 2.0, sh / 2.0
        # Bounding box of the rotated (scaled) content - identical to the size
        # pygame.transform.rotate returns.
        rw = abs(sw * cos_a) + abs(sh * sin_a)
        rh = abs(sw * sin_a) + abs(sh * cos_a)
        # pygame.rotate keeps the input centre at the centre of the rotated
        # surface, whose top-left is blitted at (x, y) (+parents).
        wcx = ox + rw / 2.0
        wcy = oy + rh / 2.0

        world = []
        for (px, py) in local_points:
            dx = px * sx - cx
            dy = py * sy - cy
            # pygame.transform.rotate uses a POSITIVE angle for a clockwise
            # rotation on screen (y grows downwards), hence the -/+ signs.
            world.append((wcx + dx * cos_a + dy * sin_a,
                          wcy - dx * sin_a + dy * cos_a))
        return world

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

        cw = float(self.collision_width)
        ch = float(self.collision_height)
        if cw <= 0 or ch <= 0:
            return None

        # Centre of the shape in local content coordinates (offset shifts the
        # shape away from the object centre for every non-bbox type).
        cx = self.width / 2.0 + self.collision_offset_x
        cy = self.height / 2.0 + self.collision_offset_y
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
        # or the collision box.
        if self.collision_points:
            local = [(float(px) + self.collision_offset_x,
                      float(py) + self.collision_offset_y)
                     for (px, py) in self.collision_points]
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

    def _collision_shape(self):
        """The world-space descriptor used by collision tests, or None when
        collision is not enabled (the object then never collides)."""
        if not self.collision_enabled:
            return None
        return self._collision_geometry_world()

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

    def _start(self):
        """Internal wrapper for on_start (driven by the script system)."""
        self.on_start()

    def _destroy(self):
        """Internal wrapper for on_destroy (driven by the script system)."""
        self.on_destroy()

    def _draw(self, parent_surface):
        """Blit this object onto its parent surface at its local position.

        In editor mode a blue selection outline is drawn around the object.
        """
        parent_surface.blit(self.surface, self._get_rect())
        if not self._is_for_api and self.selected:
            pygame.draw.rect(parent_surface, (0, 122, 204), self._get_rect(), width=2)

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
        """Rect in scene coordinates: local rect shifted up the parent chain
        until the canvas root, so nested objects report absolute positions."""
        world_rect = self._get_rect()
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object._get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        return world_rect
    
    def _set_world_rect(self, world_x, world_y):
        """Inverse of _get_world_rect: convert a scene (world) position back
        into the object's local position by subtracting parent offsets."""
        px, py = 0, 0
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object._get_rect()
            px += parent_rect.x
            py += parent_rect.y
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        self.x = world_x - px
        self.y = world_y - py

    def _get_data(self):
        """Return the object's full attribute dict (used to clone objects)."""
        return self.__dict__.copy()

    def _check_click_collision(self, click_pos):
        """Pixel-perfect hit test: first a cheap world-rect test, then a
        per-pixel alpha mask so transparent pixels don't count as a hit."""
        if not self._get_world_rect().collidepoint(click_pos):
            return False

        rotated_mask = pygame.mask.from_surface(self.surface)
        local_x = click_pos[0] - self._get_world_pos()[0]
        local_y = click_pos[1] - self._get_world_pos()[1]
        return rotated_mask.get_at((local_x, local_y))
    
    def _check_rect_collision(self, rect):
        return self._get_world_rect().colliderect(rect)
    
    def _to_dict(self):
        """Serialize the object for the .scene JSON file.

        Runtime-only / non-persistent fields (surface, script instance, the
        manager reference, editor selection/expansion state, ...) are excluded
        so the file stays small, reloadable, and comparable against the saved
        snapshot regardless of transient UI state.
        """
        exclude_fields = ['_is_initialized', '_is_for_api', '_game_manager', 'surface', 'icon', 'script_instance', 'selected', 'expanded', '_collision_configured']
        return {
            key: value for key, value in self.__dict__.items() 
            if key not in exclude_fields
        }
    
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

