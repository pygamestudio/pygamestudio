import math
import random
import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.utils.path import get_project_path


class ObjectParticle(ObjectBase):
    """A particle emitter object.

    Continuously emits small particles that fly outward with a random angle,
    fall under gravity and fade out over their lifetime. The object's node
    icon is particle.png; the live particles are drawn on top of it, so the
    emitter is visible in the editor and fully animated at runtime (it can
    also be driven from a behavior script).
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/particle.png'

        common_properties = {
            'name': 'Particle',
            'type': OBJECT_PARTICLE,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 64,
            'height': 64,
            'size': (64, 64),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            # Particle emitter parameters.
            'emission_rate': 30,       # particles emitted per second
            'max_particles': 100,      # live particles at most
            'particle_lifetime': 1.0,  # seconds each particle stays alive
            'particle_speed': 120,     # initial speed in pixels per second
            'particle_size': 4,        # particle radius in pixels
            'gravity': 200,            # pixels per second^2 (positive = down)
            'spread_angle': 360,       # emission cone in degrees (360 = all)
            # Particle sprite path (project-relative); empty = built-in icon.
            'particle_image': '',
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._particles = []
        self._last_update_time = pygame.time.get_ticks()
        self._is_initialized = True

        self._start()

    # ---------------------------------------------------------------- API
    def get_emission_rate(self):
        """Particles emitted per second."""
        return self.emission_rate

    def set_emission_rate(self, emission_rate):
        self.emission_rate = emission_rate

    def get_max_particles(self):
        """Maximum number of simultaneously live particles."""
        return self.max_particles

    def set_max_particles(self, max_particles):
        self.max_particles = max_particles

    def get_particle_lifetime(self):
        """Lifetime of each particle in seconds."""
        return self.particle_lifetime

    def set_particle_lifetime(self, particle_lifetime):
        self.particle_lifetime = particle_lifetime

    def get_particle_speed(self):
        """Initial speed of emitted particles (pixels per second)."""
        return self.particle_speed

    def set_particle_speed(self, particle_speed):
        self.particle_speed = particle_speed

    def get_particle_size(self):
        """Radius of each particle in pixels."""
        return self.particle_size

    def set_particle_size(self, particle_size):
        self.particle_size = particle_size

    def get_particle_image(self):
        """Path of the particle sprite (project-relative). Empty means the
        built-in particle.png icon is used as the sprite."""
        return self.particle_image

    def set_particle_image(self, particle_image):
        self.particle_image = particle_image

    def get_gravity(self):
        """Gravity applied to particles (pixels per second^2, + = down)."""
        return self.gravity

    def set_gravity(self, gravity):
        self.gravity = gravity

    def get_spread_angle(self):
        """Emission cone angle in degrees (360 = all directions)."""
        return self.spread_angle

    def set_spread_angle(self, spread_angle):
        self.spread_angle = spread_angle

    def get_particle_count(self):
        """Number of live particles right now."""
        return len(self._particles)

    def emit_particles(self, count=1):
        """Emit an immediate burst of ``count`` particles."""
        for _ in range(count):
            self._emit_one()

    def clear_particles(self):
        """Remove all live particles."""
        self._particles = []

    def _to_dict(self):
        """Serialize the emitter config, excluding the transient runtime
        state (live particles, cached sprite surface, timers) so the scene
        file stays small and reloadable."""
        data = super()._to_dict()
        for key in ('_particles', '_sprite_cache', '_sprite_cache_path', '_last_update_time'):
            data.pop(key, None)
        return data

    # ---------------------------------------------------------------- internals
    def __setattr__(self, name, value):
        """Keep particle_image stored as a project-relative path (like the
        image object does with image_path)."""
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'particle_image':
            if value == '':
                super().__setattr__('particle_image', '')
            else:
                project_path = Path(get_project_path())
                new_path = Path(value).absolute()
                try:
                    super().__setattr__('particle_image', new_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('particle_image', new_path.as_posix())
        else:
            super().__setattr__(name, value)

    def _emit_one(self):
        if len(self._particles) >= self.max_particles:
            return
        angle_rad = math.radians(random.uniform(0, self.spread_angle))
        speed = self.particle_speed * random.uniform(0.5, 1.0)
        self._particles.append({
            'x': self.width / 2.0,
            'y': self.height / 2.0,
            'vx': math.cos(angle_rad) * speed,
            'vy': math.sin(angle_rad) * speed,
            'life': self.particle_lifetime * random.uniform(0.6, 1.0),
            'max_life': self.particle_lifetime,
            'size': max(1.0, self.particle_size * random.uniform(0.7, 1.3)),
        })

    def _advance_particles(self):
        now = pygame.time.get_ticks()
        dt = min((now - self._last_update_time) / 1000.0, 0.05)
        self._last_update_time = now

        # Emit continuously according to the rate (fractional part accumulates
        # through the random roll).
        count = self.emission_rate * dt
        for _ in range(int(count)):
            self._emit_one()
        if random.random() < count - int(count):
            self._emit_one()

        # Update positions, velocities and lifetimes.
        alive = []
        for particle in self._particles:
            particle['x'] += particle['vx'] * dt
            particle['y'] += particle['vy'] * dt
            particle['vy'] += self.gravity * dt
            particle['life'] -= dt
            if particle['life'] <= 0:
                continue
            # Particles are drawn inside the emitter's own surface (self.size),
            # so once the sprite has FULLY left that box it can no longer be
            # seen (blit clips it). Recycle it right away instead of letting it
            # occupy a max_particles slot until its lifetime runs out -
            # otherwise a high emission rate fills the cap with invisible
            # particles and the emitter appears to stop emitting until the
            # first ones die ("burst, then a gap, then it resumes").
            margin = particle['size']   # centre + radius: sprite fully outside
            if (particle['x'] < -margin or particle['x'] > self.width + margin
                    or particle['y'] < -margin or particle['y'] > self.height + margin):
                continue
            alive.append(particle)
        self._particles = alive

    def _load_particle_sprite(self):
        """Return the particle sprite surface (cached). Uses the configured
        particle_image, falling back to the built-in particle.png icon."""
        if getattr(self, '_sprite_cache_path', None) == self.particle_image:
            return self._sprite_cache

        sprite = None
        if self.particle_image:
            image_path = Path(get_project_path()) / self.particle_image
            if image_path.exists():
                try:
                    sprite = pygame.image.load(str(image_path))
                except pygame.error:
                    sprite = None
        if sprite is None:
            icon_path = RES_PATH / 'images/particle.png'
            if icon_path.exists():
                try:
                    sprite = pygame.image.load(str(icon_path))
                except pygame.error:
                    sprite = None
        if sprite is None:
            sprite = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(sprite, (255, 255, 255, 255), (4, 4), 4)
        try:
            sprite = sprite.convert_alpha()
        except pygame.error:
            pass
        self._sprite_cache = sprite
        self._sprite_cache_path = self.particle_image
        return sprite

    def _render(self):
        base = pygame.Surface(self.size, pygame.SRCALPHA)

        # Draw the live particles (sprite, tinted with the object color and
        # fading with their remaining life). Note: self.color may be a list
        # after loading from JSON, so no tuple concatenation here - pygame
        # accepts any RGB(A) sequence.
        sprite = self._load_particle_sprite()
        for particle in self._particles:
            max_life = particle['max_life'] if particle['max_life'] > 0 else 1
            alpha = max(0, min(255, int(255 * particle['life'] / max_life)))
            size = max(2, int(particle['size'] * 2))
            s = pygame.transform.smoothscale(sprite, (size, size)).copy()
            s.fill(self.color[:3], special_flags=pygame.BLEND_RGBA_MULT)
            s.set_alpha(alpha)
            base.blit(s, (int(particle['x']) - size // 2, int(particle['y']) - size // 2))

        scaled_size = (max(1, int(base.get_width() * self.scale_x)),
                       max(1, int(base.get_height() * self.scale_y)))
        scaled = pygame.transform.scale(base, scaled_size)
        rotated = pygame.transform.rotate(scaled, self.angle)
        self.surface = self._apply_alpha(rotated)

    def _update_surface(self):
        self._advance_particles()
        self._render()
        super()._update_surface()
