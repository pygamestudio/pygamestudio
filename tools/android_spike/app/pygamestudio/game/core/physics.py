"""2D rigid-body physics for scene objects (Chipmunk, through pymunk).

The world lives in the same pixel space as the rest of the engine (x to the
right, y downwards). Chipmunk uses y upwards, so every coordinate crossing the
boundary is flipped; because the flip is applied to the local shape offsets as
well, the object's rotation angle keeps its sign (positive = clockwise on
screen, exactly like ``pygame.transform.rotate``).

A body is attached at the centre of the object's content - the point the
renderer rotates around - and the collision shape (see ``core/collision.py``)
is attached relative to it. Syncing a body back into its object is therefore
exact: the object's (x, y) is the top-left of the rotated bounding box the
renderer blits.

An object takes part when ``physics_enabled`` is True. The shape comes from the
object's COLLISION shape (``collision_type`` / offset / size / points); the
``collision_enabled`` switch itself is not required - physics and collision
events are two different things that share the same shape. Contacts between a
physics body and anything else are reported and fed into the same
``on_collision_enter`` / ``on_collision_exit`` events the geometry-based system
uses.
"""

import math

import pymunk

#: Default gravity in pixels per second squared (y points down, like every
#: other coordinate in the engine).
GRAVITY_DEFAULT = (0.0, 980.0)
#: Physics runs on a fixed timestep so the behaviour does not depend on the
#: frame rate. A frame longer than ``MAX_FRAME_TIME`` is clamped (a stopped
#: debugger must not make the world explode).
FIXED_DT = 1.0 / 60.0
MAX_FRAME_TIME = 0.25
#: How long "I was standing on something" stays true after leaving the ground
#: (coyote time: a jump is still possible just after walking off a ledge).
GROUNDED_MEMORY = 0.12
#: Normal component (physics space, so up is +y) that counts as a floor.
GROUND_NORMAL = 0.5

#: Body type names used by the editor/API.
BODY_TYPES = ('static', 'dynamic', 'kinematic')
_BODY_TYPES = {
    'static': pymunk.Body.STATIC,
    'dynamic': pymunk.Body.DYNAMIC,
    'kinematic': pymunk.Body.KINEMATIC,
}


def to_physics(point):
    """Screen pixels (y down) -> physics units (y up)."""
    return (float(point[0]), -float(point[1]))


def to_screen(point):
    """Physics units (y up) -> screen pixels (y down)."""
    return (float(point[0]), -float(point[1]))


def convex_hull(points):
    """The convex hull of ``points`` as a counter-clockwise polygon.

    Chipmunk only accepts convex polygons, so a hand-drawn collision polygon
    is reduced to its hull (a warning-worthy step that the physics section of
    the documentation spells out).
    """
    unique = sorted(set((round(float(x), 4), round(float(y), 4))
                        for (x, y) in points))
    if len(unique) < 3:
        return unique

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def polygon_centroid(points):
    """Area centroid of a simple polygon (falls back to the vertex mean)."""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < 1e-9:
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)
    return (cx / (3.0 * area), cy / (3.0 * area))


class _BodyRecord:
    """One object's physics body plus what was built from it."""

    def __init__(self, obj, body, shapes, geometry, signature, moment):
        self.object = obj
        self.body = body
        self.shapes = shapes
        self.geometry = geometry
        self.signature = signature
        self.moment = moment
        # Last transform written back into the object: a script that writes
        # obj.x/obj.y on a kinematic body teleports it (see _sync).
        self.last_pos = (float(obj.x), float(obj.y))
        self.last_angle = float(obj.angle)


class PhysicsWorld:
    """Physics space holding one body per physics-enabled object."""

    def __init__(self):
        self._space = pymunk.Space()
        self._bodies = {}            # object uuid -> _BodyRecord
        self._by_shape = {}          # id(shape) -> object
        # Screen-space forces, accumulated per frame and applied on every
        # substep (chipmunk clears body.force after each step).
        self._forces = {}
        # Physics contacts of the current frame: {(uuid, uuid): (obj, obj)}.
        self._pairs = {}
        # Pairs a body currently stands on, and the coyote-time deadline.
        self._floor_pairs = {}
        self._grounded_until = {}
        self._accumulator = 0.0
        self._time = 0.0

        self.enabled = True
        self.time_scale = 1.0
        self.gravity = GRAVITY_DEFAULT
        self._apply_gravity()
        self._space.on_collision(None, None,
                                 begin=self._on_contact_begin,
                                 separate=self._on_contact_separate)

    # ------------------------------------------------------------------ world
    def _apply_gravity(self):
        """Chipmunk gravity: y up, so the screen-space gravity is negated."""
        self._space.gravity = (float(self.gravity[0]), -float(self.gravity[1]))

    def set_gravity(self, gravity):
        self.gravity = (float(gravity[0]), float(gravity[1]))
        self._apply_gravity()

    def paused(self) -> bool:
        """True while the world does not step (disabled or time scale 0)."""
        return not self.enabled or float(self.time_scale) <= 0.0

    # ---------------------------------------------------------------- objects
    def has_object(self, obj) -> bool:
        return obj.uuid in self._bodies

    def object_count(self) -> int:
        return len(self._bodies)

    def add_object(self, obj) -> bool:
        """Give ``obj`` a body. No-op when it already has one (see
        refresh_object)."""
        if obj.uuid in self._bodies:
            return True
        geometry = self._shape_geometry(obj)
        if geometry is None:
            return False

        body_type = _BODY_TYPES.get(getattr(obj, 'physics_type', 'dynamic'),
                                    pymunk.Body.DYNAMIC)
        body = pymunk.Body(body_type=body_type)
        body.position = to_physics(self._content_center_world(obj))
        body.angle = math.radians(float(obj.angle))
        shapes, moment = self._build_shapes(obj, body, geometry)
        if not shapes:
            return False

        # Mass, moment and the center of gravity have to be in place BEFORE
        # the body enters the space: chipmunk caches what it needs when the
        # body is added, and a center of gravity set afterwards leaves the
        # body frozen mid-air.
        self._configure_body(obj, body, moment)
        self._space.add(body, *shapes)

        record = _BodyRecord(obj, body, shapes, geometry, self._signature(obj), moment)
        self._bodies[obj.uuid] = record
        for shape in shapes:
            self._by_shape[id(shape)] = obj

        return True

    def remove_object(self, obj):
        record = self._bodies.pop(obj.uuid, None)
        if record is None:
            return
        for shape in record.shapes:
            self._by_shape.pop(id(shape), None)
        # Drop the contacts of this body: its events end here, not next frame
        # (the object may be gone by then).
        for key in [key for key in self._pairs if obj.uuid in key]:
            self._pairs.pop(key, None)
        for key in [key for key in self._floor_pairs if obj.uuid in key]:
            self._floor_pairs.pop(key, None)
        self._grounded_until.pop(obj.uuid, None)
        self._forces.pop(obj.uuid, None)
        try:
            self._space.remove(record.body, *record.shapes)
        except (AssertionError, KeyError):
            pass

    def refresh_object(self, obj) -> bool:
        """Keep the body in sync with the object's settings and shape.

        Cheap when nothing changed (one tuple comparison); re-creates the body
        when the collision shape changed, applies the numeric settings live
        otherwise.
        """
        record = self._bodies.get(obj.uuid)
        if record is None:
            return self.add_object(obj)
        signature = self._signature(obj)
        if signature != record.signature:
            position = record.body.position
            velocity = record.body.velocity
            angle = record.body.angle
            angular_velocity = record.body.angular_velocity
            self.remove_object(obj)
            if not self.add_object(obj):
                return False
            record = self._bodies[obj.uuid]
            record.body.position = position
            record.body.velocity = velocity
            record.body.angle = angle
            record.body.angular_velocity = angular_velocity
        self._apply_settings(obj, record)
        return True

    # ------------------------------------------------------------------ frame
    def step(self, delta_time):
        """Advance the simulation and write the results back into the objects."""
        frame_time = min(max(0.0, float(delta_time)), MAX_FRAME_TIME)
        if self.paused():
            frame_time = 0.0
        else:
            frame_time *= float(self.time_scale)

        self._accumulator = min(self._accumulator + frame_time, MAX_FRAME_TIME)
        substeps = 0
        while self._accumulator >= FIXED_DT and substeps < 8:
            self._apply_forces()
            self._space.step(FIXED_DT)
            self._accumulator -= FIXED_DT
            self._time += FIXED_DT
            substeps += 1
        self._forces.clear()

        for record in list(self._bodies.values()):
            self._sync(record)

    def _apply_forces(self):
        """Push the frame's forces (and gravity scaling) into the bodies.

        Chipmunk clears ``body.force`` after every step, so the frame's forces
        are applied on each substep - which is exactly "this force for the
        whole frame's duration".
        """
        gravity_y = float(self.gravity[1])
        for record in self._bodies.values():
            body = record.body
            if body.body_type != pymunk.Body.DYNAMIC:
                continue
            force = self._forces.get(record.object.uuid, (0.0, 0.0))
            gravity_scale = float(getattr(record.object, 'physics_gravity_scale', 1.0))
            # chipmunk force = mass * acceleration, and its own gravity is not
            # scalable per body: the missing part is applied as a force.
            extra_y = gravity_y * body.mass * (gravity_scale - 1.0)
            body.force = to_physics((force[0], force[1] + extra_y))
            if force != (0.0, 0.0):
                # A resting body falls asleep; a script that pushes it has to
                # wake it up or the force would be ignored.
                body.activate()

    def _sync(self, record):
        """Write one body's transform back into its object."""
        obj = record.object
        body = record.body

        if body.body_type == pymunk.Body.KINEMATIC:
            # A script that writes obj.x/obj.y on a kinematic body teleports
            # it (moving platforms push properly when driven with
            # set_velocity, this path is for doors and elevators).
            if (abs(float(obj.x) - record.last_pos[0]) > 0.01
                    or abs(float(obj.y) - record.last_pos[1]) > 0.01
                    or abs(float(obj.angle) - record.last_angle) > 0.01):
                body.position = to_physics(self._content_center_world(obj))
                body.angle = math.radians(float(obj.angle))
                body.activate()

        center_x, center_y = to_screen(body.position)
        angle = math.degrees(body.angle)
        width = abs(float(obj.width) * float(obj.scale_x))
        height = abs(float(obj.height) * float(obj.scale_y))
        rad = math.radians(angle)
        rotated_w = abs(width * math.cos(rad)) + abs(height * math.sin(rad))
        rotated_h = abs(width * math.sin(rad)) + abs(height * math.cos(rad))

        obj.angle = angle
        obj._set_world_rect(center_x - rotated_w / 2.0, center_y - rotated_h / 2.0)
        record.last_pos = (obj.x, obj.y)
        record.last_angle = obj.angle

    def pairs(self):
        """Physics contacts of the current frame: {(uuid, uuid): (obj, obj)}."""
        return dict(self._pairs)

    def is_grounded(self, obj) -> bool:
        """True when the object stands on (or just left) another body."""
        uuid = obj.uuid
        for uuids in self._floor_pairs.values():
            if uuid in uuids:
                return True
        return self._grounded_until.get(uuid, -1.0) >= self._time

    # ---------------------------------------------------------------- actions
    def apply_force(self, obj, force):
        """Accumulate a force (pixels/s^2 scaled by mass) for this frame."""
        uuid = obj.uuid
        if uuid not in self._bodies:
            return
        current = self._forces.get(uuid, (0.0, 0.0))
        self._forces[uuid] = (current[0] + float(force[0]), current[1] + float(force[1]))

    def apply_impulse(self, obj, impulse):
        """Add an instant velocity change (mass * pixels/second)."""
        record = self._bodies.get(obj.uuid)
        if record is None:
            return
        mass = max(1e-6, record.body.mass)
        record.body.velocity += to_physics((float(impulse[0]) / mass,
                                            float(impulse[1]) / mass))
        record.body.activate()

    def get_velocity(self, obj):
        record = self._bodies.get(obj.uuid)
        if record is None:
            return None
        return to_screen(record.body.velocity)

    def set_velocity(self, obj, velocity):
        record = self._bodies.get(obj.uuid)
        if record is None:
            return
        record.body.velocity = to_physics(velocity)
        record.body.activate()

    def get_angular_velocity(self, obj):
        record = self._bodies.get(obj.uuid)
        if record is None:
            return None
        return math.degrees(record.body.angular_velocity)

    def set_angular_velocity(self, obj, angular_velocity):
        record = self._bodies.get(obj.uuid)
        if record is None:
            return
        record.body.angular_velocity = math.radians(float(angular_velocity))
        record.body.activate()

    def raycast(self, start, end):
        """The first object a ray from ``start`` to ``end`` (world pixels)
        hits, or None."""
        hit = self._space.segment_query_first(to_physics(start), to_physics(end),
                                              0, pymunk.ShapeFilter())
        if hit is None:
            return None
        return self._by_shape.get(id(hit.shape))

    # --------------------------------------------------------------- geometry
    def _signature(self, obj):
        """Everything the body is built from: a change re-creates it."""
        return (
            getattr(obj, 'physics_type', 'dynamic'),
            getattr(obj, 'physics_shape_type', 'rect'),
            round(float(obj.physics_shape_offset_x), 4),
            round(float(obj.physics_shape_offset_y), 4),
            round(float(obj.physics_shape_width), 4),
            round(float(obj.physics_shape_height), 4),
            tuple((round(float(x), 4), round(float(y), 4))
                  for (x, y) in (obj.physics_shape_points or [])),
            round(float(obj.width), 4), round(float(obj.height), 4),
            round(float(obj.scale_x), 4), round(float(obj.scale_y), 4),
        )

    def _content_center_world(self, obj):
        """World position of the centre of the object's scaled content."""
        center_x, center_y = obj._point_to_world(obj.width / 2.0, obj.height / 2.0)
        return (center_x, center_y)

    def _shape_geometry(self, obj):
        """The rigid-body shape relative to the body origin (physics units).

        Reads the object's own physics_shape_* fields (independent from the
        collision shape). Returns {'kind': 'box'|'circle'|'poly', ...} or None
        when the object has no usable shape.
        """
        shape_type = getattr(obj, 'physics_shape_type', 'rect')
        scale_x = abs(float(obj.scale_x))
        scale_y = abs(float(obj.scale_y))
        width = float(obj.width)
        height = float(obj.height)

        if shape_type == 'bbox':
            # In the geometry tests 'bbox' follows the ROTATED world bounding
            # box; a body cannot do that (it rotates), so physics treats it as
            # the object's own box, exactly like a default 'rect'.
            return {'kind': 'box', 'hw': width * scale_x / 2.0,
                    'hh': height * scale_y / 2.0, 'offset': (0.0, 0.0)}

        obj._ensure_physics_shape_defaults()
        box_width = float(obj.physics_shape_width)
        box_height = float(obj.physics_shape_height)
        if box_width <= 0 or box_height <= 0:
            return None
        # Shape centre in scaled screen pixels, relative to the content centre.
        offset_x = float(obj.physics_shape_offset_x) * scale_x
        offset_y = float(obj.physics_shape_offset_y) * scale_y

        if shape_type == 'ellipse':
            radius_x = box_width * scale_x / 2.0
            radius_y = box_height * scale_y / 2.0
            if abs(radius_x - radius_y) < 1e-6:
                return {'kind': 'circle', 'radius': radius_x,
                        'offset': (offset_x, -offset_y)}
            points = [(offset_x + radius_x * math.cos(2 * math.pi * i / 24),
                       offset_y + radius_y * math.sin(2 * math.pi * i / 24))
                      for i in range(24)]
            return {'kind': 'poly', 'points': [(x, -y) for (x, y) in points]}

        if shape_type == 'rect':
            return {'kind': 'box', 'hw': box_width * scale_x / 2.0,
                    'hh': box_height * scale_y / 2.0,
                    'offset': (offset_x, -offset_y)}

        # 'polygon': explicit vertices in content pixels (the offset shifts
        # them too), relative to the content centre and scaled; chipmunk needs
        # a convex hull.
        if obj.physics_shape_points:
            local = [((float(px) + float(obj.physics_shape_offset_x)) * scale_x - width * scale_x / 2.0,
                      (float(py) + float(obj.physics_shape_offset_y)) * scale_y - height * scale_y / 2.0)
                     for (px, py) in obj.physics_shape_points]
        else:
            local = [(-box_width * scale_x / 2.0, -box_height * scale_y / 2.0),
                     (box_width * scale_x / 2.0, -box_height * scale_y / 2.0),
                     (box_width * scale_x / 2.0, box_height * scale_y / 2.0),
                     (-box_width * scale_x / 2.0, box_height * scale_y / 2.0)]
        points = convex_hull([(x, -y) for (x, y) in local])
        if len(points) < 3:
            return None
        return {'kind': 'poly', 'points': points}

    def _build_shapes(self, obj, body, geometry):
        """Create the pymunk shape(s) for a geometry dict + the body moment."""
        mass = max(0.0001, float(getattr(obj, 'physics_mass', 1.0)))
        friction = max(0.0, float(getattr(obj, 'physics_friction', 0.6)))
        elasticity = max(0.0, float(getattr(obj, 'physics_elasticity', 0.2)))
        kind = geometry['kind']

        if kind == 'box':
            size = (max(1e-3, geometry['hw'] * 2.0), max(1e-3, geometry['hh'] * 2.0))
            shape = pymunk.Poly.create_box(body, size)
            moment = pymunk.moment_for_box(mass, size)
            center_of_gravity = to_physics(geometry['offset'])
        elif kind == 'circle':
            radius = max(1e-3, geometry['radius'])
            shape = pymunk.Circle(body, radius, to_physics(geometry['offset']))
            moment = pymunk.moment_for_circle(mass, 0.0, radius)
            center_of_gravity = to_physics(geometry['offset'])
        else:
            points = geometry['points']
            shape = pymunk.Poly(body, points)
            center_of_gravity = polygon_centroid(points)
            recentered = [(x - center_of_gravity[0], y - center_of_gravity[1])
                          for (x, y) in points]
            moment = pymunk.moment_for_poly(mass, recentered)

        shape.friction = friction
        shape.elasticity = elasticity
        body.center_of_gravity = center_of_gravity
        return [shape], moment

    def _configure_body(self, obj, body, moment):
        """Mass, moment and damping from the object's settings.

        Also used while the game runs, so a script can change the mass or the
        damping live; the center of gravity is only set when the body is built
        (see add_object).
        """
        if body.body_type == pymunk.Body.DYNAMIC:
            body.mass = max(0.0001, float(getattr(obj, 'physics_mass', 1.0)))
            if bool(getattr(obj, 'physics_fixed_rotation', False)):
                body.moment = float('inf')
            else:
                body.moment = moment
        body.linear_damping = max(0.0, float(getattr(obj, 'physics_linear_damping', 0.0)))
        body.angular_damping = max(0.0, float(getattr(obj, 'physics_angular_damping', 0.0)))

    def _apply_settings(self, obj, record):
        """Push the live settings (type, mass, damping, ...) into the body."""
        body = record.body
        body_type = _BODY_TYPES.get(getattr(obj, 'physics_type', 'dynamic'),
                                    pymunk.Body.DYNAMIC)
        if body.body_type != body_type:
            # chipmunk resets mass/moment when a body changes its type.
            body.body_type = body_type
        self._configure_body(obj, body, record.moment)

    # ---------------------------------------------------------------- contacts
    def _on_contact_begin(self, arbiter, space, data):
        """Register a new physics contact (and who stands on whom)."""
        shape_a, shape_b = arbiter.shapes
        obj_a = self._by_shape.get(id(shape_a))
        obj_b = self._by_shape.get(id(shape_b))
        if obj_a is None or obj_b is None:
            return True

        key = tuple(sorted((obj_a.uuid, obj_b.uuid)))
        self._pairs[key] = (obj_a, obj_b)

        normal_y = float(arbiter.normal.y)          # from shape A to shape B
        if normal_y > GROUND_NORMAL:
            standing_on_top = obj_b                # B is pushed up by A
        elif normal_y < -GROUND_NORMAL:
            standing_on_top = obj_a                # A is pushed up by B
        else:
            standing_on_top = None
        if standing_on_top is not None and getattr(standing_on_top, 'physics_type', '') == 'dynamic':
            self._floor_pairs.setdefault(key, set()).add(standing_on_top.uuid)
            self._grounded_until[standing_on_top.uuid] = self._time + GROUNDED_MEMORY
        return True

    def _on_contact_separate(self, arbiter, space, data):
        shape_a, shape_b = arbiter.shapes
        obj_a = self._by_shape.get(id(shape_a))
        obj_b = self._by_shape.get(id(shape_b))
        if obj_a is None or obj_b is None:
            return
        key = tuple(sorted((obj_a.uuid, obj_b.uuid)))
        self._pairs.pop(key, None)
        self._floor_pairs.pop(key, None)
