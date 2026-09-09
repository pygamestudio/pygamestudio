import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path

# Image formats pygame can load; these are picked as the tileset image.
_TILESET_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp',
                       '.tga', '.pcx', '.qoi', '.xpm', '.lbm'}


class ObjectTileMap(ObjectBase):
    """A multi-layer tile-map object: a grid of small images (tiles) cut from
    one tileset image, spread over one or more named layers.

    Data model
    ----------
    ``layers`` is the persisted content: a list of dicts, one per layer::

        {'name': str, 'visible': bool, 'collision': bool,
         'tiles': [int, ...]}          # flat list, length columns*rows; -1 = empty

    - Layers render BOTTOM-UP (index 0 first); hidden layers are skipped.
    - The layer flagged ``collision`` is the collision layer: any cell of that
      layer that holds a tile (-1 = empty) is solid (per-tile collision).
    - The editor paints into the ACTIVE layer (``get_active_layer_index()``);
      that index is transient editor state and is never serialized.

    The pixel box (width/height/size) is always DERIVED from the shared grid:
    columns*tile_width x rows*tile_height. Old scenes that stored a single
    ``tiles`` list are migrated into one "Layer 1" automatically.
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/tile_map.png'

        common_properties = {
            'name': 'Tile Map',
            'type': OBJECT_TILE_MAP,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            # Tile map parameters. The pixel box (width/height/size) is always
            # DERIVED from the grid: columns*tile_width x rows*tile_height.
            'tileset_path': '',      # project-relative tileset image
            'tile_width': 32,        # one tile, in pixels
            'tile_height': 32,
            'columns': 8,            # map grid size, in tiles
            'rows': 6,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # ---- layers -----------------------------------------------------
        layers = object_data.get('layers')
        if not isinstance(layers, list) or not layers:
            # Migrate the old single-grid form into one layer.
            legacy_tiles = object_data.get('tiles', [])
            layers = [{'name': 'Layer 1', 'visible': True, 'collision': False,
                       'tiles': list(legacy_tiles)}]
        self.layers = layers
        # Which layer the editor paints into (transient, never serialized).
        self._active_layer = int(object_data.get('_active_layer', 0) or 0)

        self._normalize_grid_geometry()

        # Transient render caches (excluded from serialization).
        self._content_surface = None
        self._content_baked_version = -1
        self._content_version = 0
        self._tileset_cache = {}   # (path, tile_width, tile_height) -> [Surface]
        self._tileset_dims_cache = {}   # same key -> (sheet_width, sheet_height)

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)

        self._is_initialized = True

        self._start()

    # ---------------------------------------------------------------- API
    # -- layers ----------------------------------------------------------
    def get_layer_count(self) -> int:
        return len(self.layers)

    def get_layer_names(self) -> list:
        return [str(L.get('name', 'Layer')) for L in self.layers]

    def get_layer_name(self, index: int) -> str:
        if 0 <= index < len(self.layers):
            return str(self.layers[index].get('name', 'Layer'))
        return ''

    def get_layer_tiles(self, index: int) -> list:
        """The flat tiles list of one layer (index into ``layers``)."""
        if 0 <= index < len(self.layers):
            return self.layers[index]['tiles']
        return []

    def is_layer_visible(self, index: int) -> bool:
        return bool(0 <= index < len(self.layers) and self.layers[index].get('visible', True))

    def is_collision_layer(self, index: int) -> bool:
        return bool(0 <= index < len(self.layers) and self.layers[index].get('collision', False))

    def get_collision_layer_index(self):
        """Index of the layer flagged as the collision layer, or None."""
        for i, layer in enumerate(self.layers):
            if layer.get('collision', False):
                return i
        return None

    def get_active_layer_index(self) -> int:
        return max(0, min(self._active_layer, len(self.layers) - 1))

    def set_active_layer_index(self, index: int):
        """Switch which layer the editor paints into (editor state only)."""
        if 0 <= index < len(self.layers):
            self._active_layer = int(index)

    def get_active_layer_tiles(self) -> list:
        return self.get_layer_tiles(self.get_active_layer_index())

    # -- tile access (defaults to the ACTIVE layer) ----------------------
    def get_tile(self, column: int, row: int, layer=None) -> int:
        """Tile id at a grid cell of a layer (default: the active one).
        -1 when out of range or the cell is empty."""
        if layer is None:
            layer = self.get_active_layer_index()
        if not (0 <= int(column) < self.columns and 0 <= int(row) < self.rows):
            return -1
        if not (0 <= layer < len(self.layers)):
            return -1
        tiles = self.layers[layer]['tiles']
        index = int(row) * self.columns + int(column)
        return tiles[index] if 0 <= index < len(tiles) else -1

    def set_tile(self, column: int, row: int, tile_id: int, layer=None):
        """Set a tile id at a grid cell of a layer (default: active one)."""
        if layer is None:
            layer = self.get_active_layer_index()
        if not (0 <= int(column) < self.columns and 0 <= int(row) < self.rows):
            return
        if not (0 <= layer < len(self.layers)):
            return
        tiles = self.layers[layer]['tiles']
        index = int(row) * self.columns + int(column)
        if 0 <= index < len(tiles) and tiles[index] != int(tile_id):
            tiles[index] = int(tile_id)
            self._bump_content_version()

    def fill_tiles(self, tile_id: int, layer=None):
        """Fill every cell of a layer with the same tile id (-1 clears)."""
        if layer is None:
            layer = self.get_active_layer_index()
        if not (0 <= layer < len(self.layers)):
            return
        tiles = self.layers[layer]['tiles']
        if tiles and all(t == int(tile_id) for t in tiles):
            return
        for i in range(len(tiles)):
            tiles[i] = int(tile_id)
        self._bump_content_version()

    def clear_tiles(self, layer=None):
        """Empty every cell of a layer (equivalent to fill_tiles(-1))."""
        self.fill_tiles(-1, layer)

    # -- tileset ---------------------------------------------------------
    def get_tileset_path(self) -> str:
        """Project-relative path of the tileset image ('', none)."""
        return self.tileset_path

    def set_tileset_path(self, tileset_path: str):
        self.tileset_path = tileset_path

    def get_tile_size(self) -> tuple:
        """(tile_width, tile_height) in pixels."""
        return (self.tile_width, self.tile_height)

    def set_tile_size(self, tile_width: int, tile_height: int):
        self.tile_width = tile_width
        self.tile_height = tile_height

    def get_map_size(self) -> tuple:
        """(columns, rows) - the map grid size, in tiles."""
        return (self.columns, self.rows)

    def set_map_size(self, columns: int, rows: int):
        """Resize the map grid (in tiles) for EVERY layer."""
        self.columns = columns
        self.rows = rows

    def get_map_pixel_size(self) -> tuple:
        """(width, height) of the whole map, in pixels."""
        return (self.width, self.height)

    def get_tileset_tile_count(self) -> int:
        """How many tiles the configured tileset provides (0 when none)."""
        return len(self._tileset_tiles())

    def get_tileset_tiles(self):
        """The sliced tile surfaces of the configured tileset (row-major, in
        tile-id order). Empty list when there is no usable tileset."""
        return list(self._tileset_tiles())

    def get_tileset_dimensions(self) -> tuple:
        """(sheet_width, sheet_height) in pixels of the configured tileset
        image; (0, 0) when none is set or it failed to load."""
        if not self.tileset_path:
            return (0, 0)
        self._tileset_tiles()   # ensure the sheet is loaded/cached
        key = (self.tileset_path, self.tile_width, self.tile_height)
        return self._tileset_dims_cache.get(key, (0, 0))

    @staticmethod
    def _fit_tiles(tiles, columns, rows):
        """Return a copy of ``tiles`` resized to a columns*rows grid (padded
        with -1 or trimmed). Used when the map grid dimensions change."""
        tiles = [int(t) for t in (tiles or [])]
        expected = max(1, int(columns)) * max(1, int(rows))
        if len(tiles) < expected:
            tiles += [-1] * (expected - len(tiles))
        else:
            tiles = tiles[:expected]
        return tiles

    # ------------------------------------------------- per-tile collision
    def is_cell_solid(self, column: int, row: int) -> bool:
        """True when the COLLISION layer holds a tile at this cell (a cell
        that has a tile there is solid; -1/empty is not)."""
        layer = self.get_collision_layer_index()
        if layer is None:
            return False
        return self.get_tile(column, row, layer) != -1

    def get_collision_rects(self) -> list:
        """Collision rects in LOCAL (content) pixels - one merged rect per
        contiguous run of solid cells in each row (platformer style)."""
        layer = self.get_collision_layer_index()
        if layer is None:
            return []
        tw, th = self.tile_width, self.tile_height
        tiles = self.get_layer_tiles(layer)
        rects = []
        for row in range(self.rows):
            col = 0
            while col < self.columns:
                index = row * self.columns + col
                if 0 <= index < len(tiles) and tiles[index] != -1:
                    start = col
                    while col < self.columns:
                        idx = row * self.columns + col
                        if not (0 <= idx < len(tiles) and tiles[idx] != -1):
                            break
                        col += 1
                    rects.append(pygame.Rect(start * tw, row * th,
                                             (col - start) * tw, th))
                else:
                    col += 1
        return rects

    def get_collision_rects_world(self) -> list:
        """Collision rects in WORLD pixels: local rects shifted by the parent
        chain and scaled by (scale_x, scale_y). Rotation is not supported
        (returns [] when the map is rotated)."""
        if (int(self.angle or 0) % 360) != 0:
            return []
        origin_x, origin_y = self._get_local_origin_world()
        sx = abs(self.scale_x) or 1.0
        sy = abs(self.scale_y) or 1.0
        world_rects = []
        for rect in self.get_collision_rects():
            world_rects.append(pygame.Rect(
                int(round(origin_x + rect.x * sx)),
                int(round(origin_y + rect.y * sy)),
                max(1, int(round(rect.w * sx))),
                max(1, int(round(rect.h * sy)))))
        return world_rects

    def is_solid_at(self, world_x: float, world_y: float) -> bool:
        """True when the world point lands on a solid cell of the collision
        layer. Rotation is not supported (returns False for a rotated map)."""
        if (int(self.angle or 0) % 360) != 0:
            return False
        origin_x, origin_y = self._get_local_origin_world()
        sx = abs(self.scale_x) or 1.0
        sy = abs(self.scale_y) or 1.0
        local_x = (world_x - origin_x) / sx
        local_y = (world_y - origin_y) / sy
        if local_x < 0 or local_y < 0:
            return False
        column = int(local_x // self.tile_width)
        row = int(local_y // self.tile_height)
        if column >= self.columns or row >= self.rows:
            return False
        return self.is_cell_solid(column, row)

    def collides_with_world_rect(self, rect) -> bool:
        """True when any solid cell rect overlaps the given world rect."""
        for solid_rect in self.get_collision_rects_world():
            if solid_rect.colliderect(rect):
                return True
        return False

    # ------------------------------------------------------------- geometry
    def _normalize_grid_geometry(self):
        """Clamp the stored grid fields to sane integers, derive the pixel box
        and fit every layer's tiles to the grid (init/load time, before the
        __setattr__ guards are active)."""
        self.columns = max(1, int(self.columns or 1))
        self.rows = max(1, int(self.rows or 1))
        self.tile_width = max(1, int(self.tile_width or 1))
        self.tile_height = max(1, int(self.tile_height or 1))
        self.width = self.columns * self.tile_width
        self.height = self.rows * self.tile_height
        self.size = (self.width, self.height)

        normalized = []
        for layer in (self.layers or []):
            if not isinstance(layer, dict):
                layer = {}
            normalized.append({
                'name': str(layer.get('name', 'Layer')),
                'visible': bool(layer.get('visible', True)),
                'collision': bool(layer.get('collision', False)),
                'tiles': self._fit_tiles(layer.get('tiles', []),
                                         self.columns, self.rows),
            })
        if not normalized:
            normalized.append({'name': 'Layer 1', 'visible': True,
                               'collision': False,
                               'tiles': [-1] * (self.columns * self.rows)})
        self.layers = normalized
        self._active_layer = max(0, min(int(self._active_layer or 0),
                                        len(self.layers) - 1))

    def _resync_geometry(self):
        """Re-derive the pixel box and refit every layer after a grid or tile
        size change."""
        columns = max(1, int(self.columns))
        rows = max(1, int(self.rows))
        tile_width = max(1, int(self.tile_width))
        tile_height = max(1, int(self.tile_height))
        super().__setattr__('columns', columns)
        super().__setattr__('rows', rows)
        super().__setattr__('tile_width', tile_width)
        super().__setattr__('tile_height', tile_height)
        super().__setattr__('width', columns * tile_width)
        super().__setattr__('height', rows * tile_height)
        super().__setattr__('size', (columns * tile_width, rows * tile_height))
        for layer in self.layers:
            layer['tiles'] = self._fit_tiles(layer.get('tiles', []),
                                             columns, rows)

    def _bump_content_version(self):
        super().__setattr__('_content_version',
                            getattr(self, '_content_version', 0) + 1)

    def __setattr__(self, name, value):
        """Normalize path/grid fields; any content change bumps the render
        cache version."""
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'tileset_path':
            raw = str(value).strip() if value is not None else ''
            if not raw:
                super().__setattr__('tileset_path', '')
            else:
                project_root = (Path(get_project_path()).absolute()
                                if (get_project_path() or '').strip()
                                else Path.cwd())
                # A relative path is ALWAYS project-relative (undo/redo may
                # feed back the stored relative value, e.g. './tileset.png');
                # resolving it against the CWD would corrupt it.
                path = Path(raw)
                if not path.is_absolute():
                    path = project_root / path
                path = path.absolute()
                try:
                    super().__setattr__('tileset_path',
                                        path.relative_to(project_root).as_posix())
                except ValueError:
                    super().__setattr__('tileset_path', path.as_posix())
            self._bump_content_version()
            return

        if name in ('columns', 'rows', 'tile_width', 'tile_height'):
            int_value = max(1, int(value))
            if getattr(self, name, -1) == int_value:
                return
            super().__setattr__(name, int_value)
            self._resync_geometry()
            self._bump_content_version()
            return

        super().__setattr__(name, value)

    # --------------------------------------------------------------- render
    def _tileset_tiles(self):
        """The tile surfaces cut from the configured tileset (cached per
        path + tile size). Returns [] when there is no usable tileset."""
        key = (self.tileset_path, self.tile_width, self.tile_height)
        if key in self._tileset_cache:
            return self._tileset_cache[key]

        tiles = []
        if self.tileset_path:
            path = Path(get_project_path()) / self.tileset_path
            if path.is_file() and path.suffix.lower() in _TILESET_EXTENSIONS:
                try:
                    sheet = pygame.image.load(str(path))
                except Exception:
                    sheet = None
                if sheet is not None:
                    # convert_alpha() needs a display mode; fall back to the
                    # raw loaded surface when none is set (headless / tests).
                    try:
                        sheet = sheet.convert_alpha()
                    except pygame.error:
                        pass
                    self._tileset_dims_cache[key] = (sheet.get_width(),
                                                     sheet.get_height())
                    tw, th = self.tile_width, self.tile_height
                    columns = sheet.get_width() // tw
                    rows = sheet.get_height() // th
                    for row in range(max(0, rows)):
                        for col in range(max(0, columns)):
                            tiles.append(sheet.subsurface(
                                pygame.Rect(col * tw, row * th, tw, th)))
                else:
                    self._tileset_dims_cache[key] = (0, 0)
            else:
                self._tileset_dims_cache[key] = (0, 0)
        else:
            self._tileset_dims_cache[key] = (0, 0)

        self._tileset_cache[key] = tiles
        return tiles

    def _bake_content_surface(self):
        """Composite every VISIBLE layer (bottom-up) onto a fresh map surface.
        Tiles of upper layers draw over lower ones."""
        tiles_by_id = self._tileset_tiles()
        tw, th = self.tile_width, self.tile_height
        width = max(1, self.columns * tw)
        height = max(1, self.rows * th)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        if not tiles_by_id:
            return surface
        for layer in self.layers:
            if not layer.get('visible', True):
                continue
            tiles = layer.get('tiles', [])
            for row in range(self.rows):
                base = row * self.columns
                for col in range(self.columns):
                    tile_id = tiles[base + col] if base + col < len(tiles) else -1
                    if 0 <= tile_id < len(tiles_by_id):
                        surface.blit(tiles_by_id[tile_id], (col * tw, row * th))
        return surface

    def _update_surface(self):
        # Re-bake the map content only when the map actually changed (the
        # expensive part). The cheap scale/rotate/tint step below still runs
        # every call so the object always hands out a FRESH surface (children
        # drawn by the editor onto it never linger across repaints).
        if (self._content_surface is None
                or self._content_baked_version != self._content_version):
            self._content_surface = self._bake_content_surface()
            self._content_baked_version = self._content_version

        content = self._content_surface
        if (self.scale_x, self.scale_y) == (1, 1) and not (self.angle % 360):
            base = content.copy()
        else:
            scaled_size = (max(1, int(content.get_width() * self.scale_x)),
                           max(1, int(content.get_height() * self.scale_y)))
            scaled = pygame.transform.scale(content, scaled_size)
            base = pygame.transform.rotate(scaled, self.angle)

        self.surface = self._apply_alpha(base)
        self.surface.fill(self.color[0:3], special_flags=pygame.BLEND_RGBA_MULT)

        super()._update_surface()

    def _to_dict(self):
        """Serialize the map config + layers, excluding the transient render
        caches and the active-layer index."""
        data = super()._to_dict()
        for key in ('_content_surface', '_content_baked_version',
                    '_content_version', '_tileset_cache',
                    '_tileset_dims_cache', '_active_layer'):
            data.pop(key, None)
        return data
