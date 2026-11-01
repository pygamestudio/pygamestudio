"""Affine transforms for scene objects (position, scale, rotation, pivot).

Every object owns ONE local transform that maps its CONTENT coordinates (the
object's own pixel grid: (0, 0) = top-left corner, bottom-right = (width,
height)) into its PARENT's content space:

    T(c) = (x, y) + pivot + R(angle) . S(scale) . (c - pivot)

The two concepts are independent:

* the ORIGIN is the object's top-left corner, wherever (x, y) puts it - it is
  what child coordinates are measured from;
* the PIVOT ("anchor") is the point the rotation and the scaling happen
  around, expressed in content coordinates. It defaults to the object's
  CENTRE, which is why a negative scale mirrors the object in place and a
  rotated parent swings its children around the parent's centre instead of
  its top-left corner. ``pivot`` = 'top_left' restores the classic
  "rotate about the origin" behaviour; 'custom' uses pivot_x / pivot_y.

The WORLD transform of a node is the composition of the transforms of all its
ancestors (outermost first) with its own - a classic scene graph, so children
follow their parent's position, scale, rotation and mirror. While nothing on
the chain is scaled or rotated the composed matrix stays a pure translation,
which is the fast path that keeps existing scenes at zero overhead.
"""

import math


class Transform:
    """A 2D affine transform stored as ``[a c e; b d f]``.

    ``x' = a*x + c*y + e`` and ``y' = b*x + d*y + f`` (the Qt/QTransform
    layout). Instances are treated as IMMUTABLE: every operation returns a
    new Transform (or the shared IDENTITY), never mutates in place - the walks
    hand the same instance to many children.
    """

    __slots__ = ('a', 'b', 'c', 'd', 'e', 'f')

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0):
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.e = e
        self.f = f

    # ------------------------------------------------------------- builders
    @classmethod
    def translation(cls, x, y):
        return cls(1.0, 0.0, 0.0, 1.0, x, y)

    @classmethod
    def from_object(cls, obj):
        """The local transform of ``obj``: content -> parent content space.

        ``pivot`` is resolved against the CURRENT width/height, so an object
        resized later rotates about its new centre without touching the
        stored pivot values. An object with no rotation and no scaling (the
        common case, and every object of a scene nobody transformed) reduces
        to a plain translation - the fast path that keeps the walks cheap.
        """
        scale_x, scale_y = float(obj.scale_x), float(obj.scale_y)
        if not obj.angle and scale_x == 1 and scale_y == 1:
            return cls(1.0, 0.0, 0.0, 1.0, float(obj.x), float(obj.y))

        pivot_x, pivot_y = resolve_pivot(obj.pivot, obj.pivot_x, obj.pivot_y,
                                         obj.width, obj.height)
        angle = math.radians(float(obj.angle) % 360.0)
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        # Linear part: R(angle) . S(scale). A positive angle turns the object
        # clockwise on screen (y grows downwards), matching pygame.rotate.
        a = cos_a * scale_x
        b = -sin_a * scale_x
        c = sin_a * scale_y
        d = cos_a * scale_y

        # Translation keeps the pivot where (x, y) + pivot is: T(pivot) must
        # equal (x, y) + pivot.
        e = float(obj.x) + pivot_x - (a * pivot_x + c * pivot_y)
        f = float(obj.y) + pivot_y - (b * pivot_x + d * pivot_y)
        return cls(a, b, c, d, e, f)

    # ---------------------------------------------------------- composition
    def compose(self, other):
        """``self . other`` - apply ``other`` first, then ``self``."""
        if other is IDENTITY:
            return self
        if self is IDENTITY:
            return other
        return Transform(
            self.a * other.a + self.c * other.b,
            self.b * other.a + self.d * other.b,
            self.a * other.c + self.c * other.d,
            self.b * other.c + self.d * other.d,
            self.a * other.e + self.c * other.f + self.e,
            self.b * other.e + self.d * other.f + self.f,
        )

    # ------------------------------------------------------------- mapping
    def map_point(self, x, y):
        return (self.a * x + self.c * y + self.e,
                self.b * x + self.d * y + self.f)

    def map_vector(self, x, y):
        """Map a DIRECTION (the translation is left out)."""
        return (self.a * x + self.c * y,
                self.b * x + self.d * y)

    def inverted(self):
        """The inverse transform, or None when it is singular (scale 0)."""
        det = self.a * self.d - self.b * self.c
        if abs(det) < 1e-12:
            return None
        inv = Transform(
            self.d / det, -self.b / det, -self.c / det, self.a / det, 0.0, 0.0)
        inv.e = -(inv.a * self.e + inv.c * self.f)
        inv.f = -(inv.b * self.e + inv.d * self.f)
        return inv

    # ------------------------------------------------------------- queries
    def is_identity(self):
        """True for the exact "draw as stored" transform (no rotation, no
        scaling, no translation) - the fast path of the walks."""
        return (self.a == 1.0 and self.b == 0.0 and self.c == 0.0
                and self.d == 1.0 and self.e == 0.0 and self.f == 0.0)

    def is_translation(self):
        """True while the transform only moves things (no rotation/scale).
        The composed transform of an untouched subtree is a translation."""
        return (self.a == 1.0 and self.b == 0.0 and self.c == 0.0
                and self.d == 1.0)

    def __repr__(self):
        return 'Transform({:.4g}, {:.4g}, {:.4g}, {:.4g}, {:.4g}, {:.4g})'.format(
            self.a, self.b, self.c, self.d, self.e, self.f)


#: The shared "no transform" instance - never mutated.
IDENTITY = Transform()


#: Pivot choices, in UI order: the nine classic anchors + free coordinates.
PIVOT_MODES = (
    'center',
    'top_left', 'top_center', 'top_right',
    'center_left', 'center_right',
    'bottom_left', 'bottom_center', 'bottom_right',
    'custom',
)


def resolve_pivot(mode, pivot_x, pivot_y, width, height):
    """The pivot point in CONTENT coordinates for one anchor mode.

    The named anchors are resolved against the object's CURRENT size, so a
    resized object keeps rotating about (for example) its new centre.
    """
    if mode == 'custom':
        return (float(pivot_x), float(pivot_y))

    width = float(width)
    height = float(height)
    x = 0.0 if mode.endswith('left') else (width if mode.endswith('right') else width / 2.0)
    y = 0.0 if mode.startswith('top') else (height if mode.startswith('bottom') else height / 2.0)
    return (x, y)
