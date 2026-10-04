"""The empty node: an invisible container object."""

import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase


class ObjectNode(ObjectBase):
    """An empty node - a container with no content of its own.

    The running game draws nothing for a node: it exists purely to group
    children, so a rig (a character sprite plus its keyframes, a HUD cluster,
    ...) can be moved, scaled and rotated as one by moving the node.

    Like every other object, children are composited into the node's own
    surface, so a node's (width, height) is the window its children show
    through - size the node to cover the children it holds. Because it holds
    no content, the node is also the right parent for a keyframe timeline:
    the node itself stays invisible while its children animate.

    In the editor a faint box + border marks the node (so it can be seen,
    selected and clicked); at runtime the surface is fully transparent.
    """

    #: Editor-only decoration (the game never shows the node at all).
    EDITOR_FILL = (144, 147, 153, 36)
    EDITOR_LINE = (144, 147, 153, 200)

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/node.png'

        common_properties = {
            'name': 'Node',
            'type': OBJECT_NODE,
            'uuid': str(uuid.uuid4()),
            'x': 0,
            'y': 0,
            'pos': (0, 0),
            'width': 100,
            'height': 100,
            'size': (100, 100),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (144, 147, 153, 255),
            'visible': True,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    def _update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)

        if not self._is_for_api:
            # Editor only: a faint fill + border keeps the empty node visible
            # and clickable in the scene view. The running game skips this,
            # so the surface stays fully transparent.
            pygame.draw.rect(self.surface, self.EDITOR_FILL, self.surface.get_rect())
            pygame.draw.rect(self.surface, self.EDITOR_LINE, self.surface.get_rect(), width=1)

        scaled_size = (self.surface.width * self.scale_x, self.surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        super()._update_surface()

    def _check_click_collision(self, click_pos):
        """The whole box of a node is a hit target in the editor.

        A node has no content pixels - its surface only carries the faint
        editorial fill - and the base hit test treats every pixel below 50 %
        alpha as transparent, so only the 1 px border would ever be hit.
        Counting every painted pixel (threshold 0) makes the entire box
        clickable, exactly where the node is drawn.

        The running game keeps the base, pixel-perfect behaviour: the node
        surface is fully transparent there, so it is never hit by a click.
        """
        if self._is_for_api:
            return super()._check_click_collision(click_pos)

        if not self._get_world_rect().collidepoint(click_pos):
            return False

        mask = pygame.mask.from_surface(self.surface, 0)
        local_x = click_pos[0] - self._get_world_pos()[0]
        local_y = click_pos[1] - self._get_world_pos()[1]
        return bool(mask.get_at((local_x, local_y)))
